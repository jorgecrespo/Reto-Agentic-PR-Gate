from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from pr_gate.infrastructure.github import PullRequestSnapshot


class WorkspaceError(RuntimeError):
    """A safe workspace operation could not be completed."""


@dataclass(frozen=True)
class Workspaces:
    root: Path
    baseline: Path
    candidate: Path


class WorkspaceManager:
    async def prepare(self, snapshot: PullRequestSnapshot) -> Workspaces:
        root = Path(tempfile.mkdtemp(prefix="pr-gate-"))
        archive_path = root / "source.zip"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    f"https://api.github.com/repos/{snapshot.ref.owner}/{snapshot.ref.repository}/zipball/{snapshot.head_sha}",
                    headers={
                        "Accept": "application/vnd.github+json",
                        **(
                            {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
                            if os.environ.get("GITHUB_TOKEN")
                            else {}
                        ),
                    },
                )
                response.raise_for_status()
                archive_path.write_bytes(response.content)
            extracted = self._extract_archive(archive_path, root / "extract")
            baseline, candidate = root / "baseline", root / "candidate"
            shutil.copytree(extracted, baseline)
            shutil.copytree(extracted, candidate)
            return Workspaces(root=root, baseline=baseline, candidate=candidate)
        except (httpx.HTTPError, OSError, zipfile.BadZipFile) as error:
            shutil.rmtree(root, ignore_errors=True)
            raise WorkspaceError("No fue posible preparar el snapshot del PR.") from error

    @staticmethod
    def _extract_archive(archive_path: Path, target: Path) -> Path:
        target.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                destination = (target / member.filename).resolve()
                if not destination.is_relative_to(target.resolve()):
                    raise WorkspaceError("El archive contiene una ruta insegura.")
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
        patch_file.write_text(patch)
        try:
            check = await asyncio.create_subprocess_exec(
                "git", "apply", "--check", str(patch_file), cwd=workspace
            )
            if await check.wait() != 0:
                return False
            apply = await asyncio.create_subprocess_exec(
                "git", "apply", str(patch_file), cwd=workspace
            )
            return await apply.wait() == 0
        finally:
            patch_file.unlink(missing_ok=True)

    @staticmethod
    def cleanup(workspaces: Workspaces | None) -> None:
        if workspaces is not None:
            shutil.rmtree(workspaces.root, ignore_errors=True)
