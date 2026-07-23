import pytest

from pr_gate.domain.types import CommitSha, PolicyVersion, PullRequestRef


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


def test_commit_sha_and_policy_version_are_validated() -> None:
    assert str(CommitSha("A" * 40)) == "a" * 40
    assert str(PolicyVersion("1.0.0")) == "1.0.0"


@pytest.mark.parametrize("value", ["not-a-sha", "a" * 39])
def test_reject_invalid_commit_sha(value: str) -> None:
    with pytest.raises(ValueError):
        CommitSha(value)
