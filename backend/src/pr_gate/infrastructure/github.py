from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any

import httpx

from pr_gate.domain.types import PullRequestRef


class GitHubError(RuntimeError):
    def __init__(self, message: str, code: str = "GITHUB_UNAVAILABLE") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SnapshotLimits:
    max_files: int = 500
    max_pages: int = 10
    max_diff_bytes: int = 1_000_000


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
    commits: tuple[dict[str, object], ...] = ()
    checks: tuple[dict[str, object], ...] = ()
    diff_integrity: bool = True


class GitHubClient:
    """Read-only GitHub REST client with bounded retries and no secret-bearing errors."""

    def __init__(
        self,
        token: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 20,
        max_retries: int = 2,
        limits: SnapshotLimits | None = None,
    ) -> None:
        self._token = token if token is not None else environ.get("GITHUB_TOKEN")
        self._transport = transport
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._limits = limits or SnapshotLimits()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "agentic-pr-gate/0.1",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(self, client: httpx.AsyncClient, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = await client.get(path, **kwargs)
            except httpx.TimeoutException as error:
                if attempt == self._max_retries:
                    raise GitHubError(
                        "GitHub excedió el tiempo de espera.", "GITHUB_TIMEOUT"
                    ) from error
            except httpx.HTTPError as error:
                if attempt == self._max_retries:
                    raise GitHubError("No fue posible conectar con GitHub.") from error
            else:
                if response.status_code in {401, 404}:
                    raise GitHubError(
                        "El PR no es accesible con las credenciales actuales.", "GITHUB_ACCESS"
                    )
                if response.status_code == 403:
                    if response.headers.get("x-ratelimit-remaining") == "0":
                        raise GitHubError(
                            "GitHub agotó el límite de solicitudes.", "GITHUB_RATE_LIMIT"
                        )
                    raise GitHubError("GitHub rechazó el acceso al PR.", "GITHUB_ACCESS")
                if (
                    response.status_code in {429, 500, 502, 503, 504}
                    and attempt < self._max_retries
                ):
                    await asyncio.sleep(min(0.25 * (2**attempt), 1.0))
                    continue
                if response.is_error:
                    raise GitHubError(f"GitHub respondió con HTTP {response.status_code}.")
                return response
        raise GitHubError("No fue posible recuperar datos de GitHub.")

    async def _paginated(
        self, client: httpx.AsyncClient, path: str, *, limit: int | None = None
    ) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for page in range(1, self._limits.max_pages + 1):
            response = await self._request(client, path, params={"per_page": 100, "page": page})
            payload = response.json()
            if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
                raise GitHubError("GitHub devolvió una respuesta con formato inesperado.")
            items.extend(payload)
            if limit is not None and len(items) > limit:
                raise GitHubError("El PR excede los límites de análisis del MVP.", "SNAPSHOT_LIMIT")
            if len(payload) < 100:
                return items
        raise GitHubError("El PR excede el límite de paginación del MVP.", "SNAPSHOT_LIMIT")

    async def fetch_snapshot(self, ref: PullRequestRef) -> PullRequestSnapshot:
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=self._headers(),
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            pr = (
                await self._request(
                    client, f"/repos/{ref.owner}/{ref.repository}/pulls/{ref.number}"
                )
            ).json()
            if not isinstance(pr, dict):
                raise GitHubError("GitHub devolvió metadata de PR inválida.")
            files = await self._paginated(
                client,
                f"/repos/{ref.owner}/{ref.repository}/pulls/{ref.number}/files",
                limit=self._limits.max_files,
            )
            commits = await self._paginated(
                client, f"/repos/{ref.owner}/{ref.repository}/pulls/{ref.number}/commits"
            )
            head = pr.get("head")
            base = pr.get("base")
            if (
                not isinstance(head, dict)
                or not isinstance(base, dict)
                or not isinstance(head.get("sha"), str)
                or not isinstance(base.get("sha"), str)
            ):
                raise GitHubError("GitHub no devolvió los SHA requeridos.")
            checks_payload = (
                await self._request(
                    client, f"/repos/{ref.owner}/{ref.repository}/commits/{head['sha']}/check-runs"
                )
            ).json()
            checks = (
                checks_payload.get("check_runs", []) if isinstance(checks_payload, dict) else []
            )
            if not isinstance(checks, list) or not all(isinstance(item, dict) for item in checks):
                raise GitHubError("GitHub devolvió checks inválidos.")
        diff_size = sum(len(str(item.get("patch", ""))) for item in files)
        integral = (
            all(isinstance(item.get("patch"), str) for item in files)
            and diff_size <= self._limits.max_diff_bytes
        )
        if not integral:
            raise GitHubError(
                "El diff no está íntegro o excede el presupuesto de análisis.", "DIFF_INCOMPLETE"
            )
        repository = base.get("repo") if isinstance(base, dict) else None
        clone_url = repository.get("clone_url") if isinstance(repository, dict) else None
        if not isinstance(clone_url, str):
            raise GitHubError("GitHub no devolvió la URL de lectura del repositorio.")
        return PullRequestSnapshot(
            ref,
            str(pr.get("title") or ""),
            str(pr.get("body") or ""),
            bool(pr.get("draft", False)),
            str(base["sha"]),
            str(head["sha"]),
            tuple(files),
            clone_url,
            tuple(commits),
            tuple(checks),
            integral,
        )

    async def fetch_current_head_sha(self, ref: PullRequestRef) -> str:
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=self._headers(),
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            payload = (
                await self._request(
                    client, f"/repos/{ref.owner}/{ref.repository}/pulls/{ref.number}"
                )
            ).json()
        try:
            return str(payload["head"]["sha"])
        except (KeyError, TypeError) as error:
            raise GitHubError("GitHub no devolvió el SHA actual del PR.") from error

    async def download_archive(
        self, snapshot: PullRequestSnapshot, target: Path, max_bytes: int = 100_000_000
    ) -> str:
        """Download a SHA-pinned archive only; extraction is handled by WorkspaceManager."""
        target.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(
            headers=self._headers(),
            timeout=self._timeout,
            transport=self._transport,
            follow_redirects=True,
        ) as client:
            response = await self._request(
                client,
                f"https://api.github.com/repos/{snapshot.ref.owner}/{snapshot.ref.repository}/zipball/{snapshot.head_sha}",
            )
        content = response.content
        if len(content) > max_bytes:
            raise GitHubError("El archive excede el límite permitido.", "ARCHIVE_LIMIT")
        target.write_bytes(content)
        return hashlib.sha256(content).hexdigest()
