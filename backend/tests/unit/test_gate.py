from pr_gate.domain.gate import evaluate_quality_gate
from pr_gate.domain.types import DecisionStatus, GateFacts


def facts(**changes: object) -> GateFacts:
    values: dict[str, object] = {
        "head_sha_current": True,
        "context_complete": True,
        "tests_executed": True,
        "tests_passed": True,
        "critical_findings": 0,
        "secrets_detected": False,
        "required_criteria_evaluated": True,
        "required_criteria_passed": True,
        "patch_applied": True,
        "regression_reproduced": True,
        "regression_fixed": True,
        "suite_passed": True,
        "business_logic_changed": False,
        "tests_changed": False,
        "pr_is_draft": False,
        "no_newer_pr": True,
    }
    values.update(changes)
    return GateFacts(**values)  # type: ignore[arg-type]


def test_ready_when_all_required_controls_pass() -> None:
    assert evaluate_quality_gate(facts()).status is DecisionStatus.READY


def test_missing_test_execution_is_inconclusive() -> None:
    assert evaluate_quality_gate(facts(tests_executed=None)).status is DecisionStatus.INCONCLUSIVE


def test_tests_not_executed_is_inconclusive_not_blocked() -> None:
    assert (
        evaluate_quality_gate(facts(tests_executed=None, tests_passed=None)).status
        is DecisionStatus.INCONCLUSIVE
    )


def test_critical_finding_blocks() -> None:
    assert evaluate_quality_gate(facts(critical_findings=1)).status is DecisionStatus.BLOCKED


def test_draft_is_conditional() -> None:
    assert evaluate_quality_gate(facts(pr_is_draft=True)).status is DecisionStatus.CONDITIONAL
