from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath

from pr_gate.infrastructure.security import scan_and_redact


class PatchValidationError(ValueError):
    pass


_DIFF_PATH = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)
_HEADER_PATH = re.compile(r"^(?:--- a/|\+\+\+ b/)(.+)$", re.MULTILINE)
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
    return ValidatedPatch(paths, sha256(patch.encode()).hexdigest())


def validate_patch_shape(patch: str, allowed_prefixes: tuple[str, ...]) -> tuple[str, ...]:
    """Compatibility wrapper for existing graph and domain tests."""
    return validate_patch(patch, allowed_prefixes).paths
