import pytest

from pr_gate.domain.types import PullRequestRef


def test_parse_github_pull_request_url() -> None:
    ref = PullRequestRef.parse("https://github.com/acme/shop/pull/42?foo=bar")
    assert (ref.owner, ref.repository, ref.number) == ("acme", "shop", 42)
    assert ref.url == "https://github.com/acme/shop/pull/42"


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b/pull/1",
        "https://gitlab.com/a/b/pull/1",
        "https://github.com/a/b/issues/1",
    ],
)
def test_reject_invalid_pull_request_url(url: str) -> None:
    with pytest.raises(ValueError):
        PullRequestRef.parse(url)
