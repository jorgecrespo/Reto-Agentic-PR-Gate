from __future__ import annotations

import asyncio
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from pr_gate.infrastructure.github import GitHubClient, GitHubError, PullRequestSnapshot
from pr_gate.infrastructure.patches import rebase_hunk_positions


class WorkspaceError(RuntimeError):
    """A safe workspace operation could not be completed."""


@dataclass(frozen=True)
class Workspaces:
    root: Path
    baseline: Path
    candidate: Path


class WorkspaceManager:
    def __init__(
        self, github: GitHubClient | None = None, max_archive_bytes: int = 100_000_000
    ) -> None:
        self._github = github or GitHubClient()
        self._max_archive_bytes = max_archive_bytes

    async def prepare(self, snapshot: PullRequestSnapshot) -> Workspaces:
        root = Path(tempfile.mkdtemp(prefix="pr-gate-"))
        archive_path = root / "source.zip"
        try:
            await self._github.download_archive(snapshot, archive_path, self._max_archive_bytes)
            extracted = self._extract_archive(archive_path, root / "extract")
            baseline, candidate = root / "baseline", root / "candidate"
            shutil.copytree(extracted, baseline)
            shutil.copytree(extracted, candidate)
            return Workspaces(root=root, baseline=baseline, candidate=candidate)
        except (GitHubError, OSError, zipfile.BadZipFile) as error:
            shutil.rmtree(root, ignore_errors=True)
            raise WorkspaceError("No fue posible preparar el snapshot del PR.") from error

    @staticmethod
    def _extract_archive(archive_path: Path, target: Path) -> Path:
        target.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            if sum(member.file_size for member in archive.infolist()) > 250_000_000:
                raise WorkspaceError("El archive excede el límite descomprimido.")
            for member in archive.infolist():
                destination = (target / member.filename).resolve()
                if not destination.is_relative_to(target.resolve()):
                    raise WorkspaceError("El archive contiene una ruta insegura.")
                if member.is_dir():
                    continue
                archive.extract(member, target)
        directories = [path for path in target.iterdir() if path.is_dir()]
        if len(directories) != 1:
            raise WorkspaceError("El archive de GitHub tiene una estructura inesperada.")
        return directories[0]

    @staticmethod
    async def apply_patch(workspace: Path, patch: str) -> bool:
        if not patch.strip():
            return False
        patch_file = workspace / ".pr-gate.patch"
        patch_file.write_text(rebase_hunk_positions(patch, workspace))
        try:
            check = await asyncio.create_subprocess_exec(
                "git",
                "apply",
                "--check",
                "--recount",
                "--unidiff-zero",
                str(patch_file),
                cwd=workspace,
            )
            if await check.wait() != 0:
                return False
            apply = await asyncio.create_subprocess_exec(
                "git", "apply", "--recount", "--unidiff-zero", str(patch_file), cwd=workspace
            )
            return await apply.wait() == 0
        except FileNotFoundError as error:
            raise WorkspaceError(
                "La herramienta de aplicación de parches no está disponible."
            ) from error
        finally:
            patch_file.unlink(missing_ok=True)

    @staticmethod
    def cleanup(workspaces: Workspaces | None) -> None:
        if workspaces is not None:
            shutil.rmtree(workspaces.root, ignore_errors=True)
