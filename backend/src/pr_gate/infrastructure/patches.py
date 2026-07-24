from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from pr_gate.infrastructure.security import scan_and_redact


class PatchValidationError(ValueError):
    pass


_DIFF_PATH = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)
_HEADER_PATH = re.compile(r"^(?:--- a/|\+\+\+ b/)(.+)$", re.MULTILINE)
_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)
_PROTECTED = {".github", ".git", "docker-compose.yml", "Dockerfile", "pyproject.toml"}


@dataclass(frozen=True)
class ValidatedPatch:
    paths: tuple[str, ...]
    sha256: str


def _validate_path(path: str, allowed_prefixes: tuple[str, ...]) -> None:
    normalized = PurePosixPath(path).as_posix()
    if not path or path != normalized or path.startswith("/") or ".." in PurePosixPath(path).parts:
        raise PatchValidationError("El parche contiene una ruta insegura.")
    if any(
        normalized == protected or normalized.startswith(f"{protected}/")
        for protected in _PROTECTED
    ):
        raise PatchValidationError("El parche modifica un archivo protegido del runner.")
    if not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
        raise PatchValidationError("El parche modifica una ruta fuera del perfil permitido.")


def validate_patch(
    patch: str, allowed_prefixes: tuple[str, ...], max_bytes: int = 100_000
) -> ValidatedPatch:
    if not patch.startswith("diff --git "):
        raise PatchValidationError("El parche debe ser un unified diff.")
    if len(patch.encode()) > max_bytes:
        raise PatchValidationError("El parche excede el tamaño permitido.")
    if "GIT binary patch" in patch or "\x00" in patch:
        raise PatchValidationError("El parche no puede contener archivos binarios.")
    pairs = tuple(_DIFF_PATH.findall(patch))
    if not pairs or any(left != right for left, right in pairs):
        raise PatchValidationError("El parche debe modificar paths consistentes.")
    header_paths = tuple(_HEADER_PATH.findall(patch))
    paths = tuple(right for _, right in pairs)
    if set(header_paths) != set(paths):
        raise PatchValidationError("Los headers del parche no coinciden con sus archivos.")
    for path in paths:
        _validate_path(path, allowed_prefixes)
    if scan_and_redact(patch).detected:
        raise PatchValidationError("El parche contiene un secreto potencial.")
    _validate_hunk_counts(patch)
    return ValidatedPatch(paths, sha256(patch.encode()).hexdigest())


def _validate_hunk_counts(patch: str) -> None:
    header: re.Match[str] | None = None
    old_lines = new_lines = 0

    def check_hunk() -> None:
        if header is None:
            return
        expected_old = int(header.group("old_count") or "1")
        expected_new = int(header.group("new_count") or "1")
        if (old_lines, new_lines) != (expected_old, expected_new):
            raise PatchValidationError("Los conteos de un hunk no coinciden con su contenido.")

    for line in patch.splitlines():
        next_header = _HUNK_HEADER.match(line)
        if next_header:
            check_hunk()
            header = next_header
            old_lines = new_lines = 0
            continue
        if header is None or line.startswith("\\ No newline"):
            continue
        if line.startswith((" ", "-")):
            old_lines += 1
        if line.startswith((" ", "+")):
            new_lines += 1
    check_hunk()


def normalize_hunk_counts(patch: str) -> str:
    """Correct hunk metadata without changing paths or patch content."""
    if not patch.strip():
        return ""
    lines = patch.splitlines()
    normalized = list(lines)
    in_hunk = False
    for index, line in enumerate(lines):
        if _HUNK_HEADER.match(line):
            in_hunk = True
            continue
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if in_hunk and line and not line.startswith((" ", "+", "-", "\\")):
            normalized[index] = f" {line}"
    lines = normalized
    header_index: int | None = None
    header: re.Match[str] | None = None
    old_lines = new_lines = 0

    def write_header() -> None:
        if header is None or header_index is None:
            return
        normalized[header_index] = (
            f"@@ -{header.group('old_start')},{old_lines} "
            f"+{header.group('new_start')},{new_lines} @@"
        )

    for index, line in enumerate(lines):
        next_header = _HUNK_HEADER.match(line)
        if next_header:
            write_header()
            header_index = index
            header = next_header
            old_lines = new_lines = 0
            continue
        if header is None or line.startswith("\\ No newline"):
            continue
        if line.startswith((" ", "-")):
            old_lines += 1
        if line.startswith((" ", "+")):
            new_lines += 1
    write_header()
    return "\n".join(normalized) + "\n"


def rebase_hunk_positions(patch: str, workspace: Path) -> str:
    """Adjust hunk offsets only when their original lines have one unambiguous location."""
    if not patch.strip():
        return ""
    lines = patch.splitlines()
    rebased = list(lines)
    current_path: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("+++ b/"):
            current_path = line.removeprefix("+++ b/")
            index += 1
            continue
        header = _HUNK_HEADER.match(line)
        if header is None or current_path is None:
            index += 1
            continue
        end = index + 1
        while (
            end < len(lines)
            and not _HUNK_HEADER.match(lines[end])
            and not lines[end].startswith("diff --git ")
        ):
            end += 1
        old_lines = [
            hunk_line[1:]
            for hunk_line in lines[index + 1 : end]
            if hunk_line.startswith((" ", "-"))
        ]
        new_lines = [
            hunk_line[1:]
            for hunk_line in lines[index + 1 : end]
            if hunk_line.startswith((" ", "+"))
        ]
        source = (workspace / current_path).resolve()
        if old_lines and source.is_relative_to(workspace.resolve()) and source.is_file():
            file_lines = source.read_text(errors="replace").splitlines()
            matches = [
                offset
                for offset in range(len(file_lines) - len(old_lines) + 1)
                if file_lines[offset : offset + len(old_lines)] == old_lines
            ]
            if len(matches) == 1:
                start = matches[0] + 1
                rebased[index] = f"@@ -{start},{len(old_lines)} +{start},{len(new_lines)} @@"
        index = end
    return "\n".join(rebased) + "\n"


def validate_patch_shape(patch: str, allowed_prefixes: tuple[str, ...]) -> tuple[str, ...]:
    """Compatibility wrapper for existing graph and domain tests."""
    return validate_patch(patch, allowed_prefixes).paths
