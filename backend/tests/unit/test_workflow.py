from pr_gate.application.workflow import build_context
from pr_gate.domain.types import PullRequestRef
from pr_gate.infrastructure.github import PullRequestSnapshot


def test_context_redacts_secrets_and_excludes_sensitive_files() -> None:
    snapshot = PullRequestSnapshot(
        ref=PullRequestRef.parse("https://github.com/acme/shop/pull/1"),
        title="Change",
        body="",
        draft=False,
        base_sha="base",
        head_sha="head",
        clone_url="",
        files=(
            {"filename": "app/service.py", "patch": "+ api_key = 'abcdefghijklmnop'"},
            {"filename": ".env", "patch": "+ OPENAI_API_KEY=should-not-appear"},
        ),
    )
    context, secrets_detected = build_context(snapshot)
    assert secrets_detected
    assert "abcdefghijklmnop" not in context
    assert "should-not-appear" not in context
    assert "[REDACTED_SECRET]" in context
