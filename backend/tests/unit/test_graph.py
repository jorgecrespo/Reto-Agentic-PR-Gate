import pytest

from pr_gate.graph.builder import route_after_validation, validate_request


@pytest.mark.asyncio
async def test_invalid_request_routes_to_gate() -> None:
    state = await validate_request({"pull_request_url": "invalid"})
    assert state["context_complete"] is False
    assert route_after_validation(state) == "apply_quality_gate"


@pytest.mark.asyncio
async def test_valid_request_continues_to_github() -> None:
    state = await validate_request({"pull_request_url": "https://github.com/a/b/pull/1"})
    assert route_after_validation(state) == "fetch_pull_request"
