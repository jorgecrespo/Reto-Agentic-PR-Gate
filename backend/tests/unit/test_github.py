from __future__ import annotations

import httpx
import pytest

from pr_gate.domain.types import PullRequestRef
from pr_gate.infrastructure.github import GitHubClient, GitHubError


def response(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/pulls/1"):
        return httpx.Response(
            200,
            json={
                "title": "T",
                "body": None,
                "draft": False,
                "base": {"sha": "a" * 40, "repo": {"clone_url": "https://github.com/a/r.git"}},
                "head": {"sha": "b" * 40},
            },
        )
    if path.endswith("/files"):
        return httpx.Response(200, json=[{"filename": "app/a.py", "patch": "+x"}])
    if path.endswith("/commits"):
        return httpx.Response(200, json=[{"sha": "c" * 40}])
    if path.endswith("/check-runs"):
        return httpx.Response(200, json={"check_runs": [{"name": "tests"}]})
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_fetches_complete_snapshot_with_commits_and_checks() -> None:
    client = GitHubClient(transport=httpx.MockTransport(response))
    snapshot = await client.fetch_snapshot(
        PullRequestRef.parse("https://github.com/acme/shop/pull/1")
    )
    assert snapshot.head_sha == "b" * 40
    assert snapshot.commits[0]["sha"] == "c" * 40
    assert snapshot.checks[0]["name"] == "tests"


@pytest.mark.asyncio
async def test_rate_limit_is_mapped_without_exposing_token() -> None:
    client = GitHubClient(
        token="never-show-this",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
        ),
    )
    with pytest.raises(GitHubError, match="límite") as error:
        await client.fetch_snapshot(PullRequestRef.parse("https://github.com/acme/shop/pull/1"))
    assert "never-show-this" not in str(error.value)


@pytest.mark.asyncio
async def test_missing_patch_is_inconclusive_error() -> None:
    def missing_patch(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/files"):
            return httpx.Response(200, json=[{"filename": "app/a.py"}])
        return response(request)

    client = GitHubClient(transport=httpx.MockTransport(missing_patch))
    with pytest.raises(GitHubError, match="diff no está íntegro"):
        await client.fetch_snapshot(PullRequestRef.parse("https://github.com/acme/shop/pull/1"))
