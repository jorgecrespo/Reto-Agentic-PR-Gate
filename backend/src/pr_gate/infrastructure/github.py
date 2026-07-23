from __future__ import annotations

from dataclasses import dataclass
from os import environ

import httpx

from pr_gate.domain.types import PullRequestRef


class GitHubError(RuntimeError):
    """Safe, actionable GitHub integration failure."""


@dataclass(frozen=True)
class PullRequestSnapshot:
    ref: PullRequestRef
    title: str
    body: str
    draft: bool
    base_sha: str
    head_sha: str
    files: tuple[dict[str, object], ...]
    clone_url: str


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token or environ.get("GITHUB_TOKEN")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def fetch_snapshot(self, ref: PullRequestRef) -> PullRequestSnapshot:
        async with httpx.AsyncClient(
            base_url="https://api.github.com", headers=self._headers(), timeout=20
        ) as client:
            response = await client.get(f"/repos/{ref.owner}/{ref.repository}/pulls/{ref.number}")
            if response.status_code in {401, 403, 404}:
                raise GitHubError("El PR no es accesible con las credenciales actuales.")
            response.raise_for_status()
            payload = response.json()
            files: list[dict[str, object]] = []
            page = 1
            while True:
                page_response = await client.get(
                    f"/repos/{ref.owner}/{ref.repository}/pulls/{ref.number}/files",
                    params={"per_page": 100, "page": page},
                )
                page_response.raise_for_status()
                current = page_response.json()
                files.extend(current)
                if len(current) < 100:
                    break
                page += 1
                if page > 20:
                    raise GitHubError("El PR excede el límite de archivos del MVP.")
        if any("patch" not in item for item in files):
            raise GitHubError("GitHub no entregó un diff íntegro para todos los archivos.")
        return PullRequestSnapshot(
            ref=ref,
            title=str(payload["title"]),
            body=str(payload.get("body") or ""),
            draft=bool(payload["draft"]),
            base_sha=str(payload["base"]["sha"]),
            head_sha=str(payload["head"]["sha"]),
            files=tuple(files),
            clone_url=str(payload["base"]["repo"]["clone_url"]),
        )

    async def fetch_current_head_sha(self, ref: PullRequestRef) -> str:
        async with httpx.AsyncClient(
            base_url="https://api.github.com", headers=self._headers(), timeout=20
        ) as client:
            response = await client.get(f"/repos/{ref.owner}/{ref.repository}/pulls/{ref.number}")
            if response.status_code in {401, 403, 404}:
                raise GitHubError("No fue posible verificar el SHA actual del PR.")
            response.raise_for_status()
            return str(response.json()["head"]["sha"])
