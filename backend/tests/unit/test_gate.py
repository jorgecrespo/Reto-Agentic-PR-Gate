import pytest

from pr_gate.domain.gate import evaluate_quality_gate
from pr_gate.domain.types import DecisionStatus, GateFacts


def facts(**changes: object) -> GateFacts:
    values: dict[str, object] = {
        "head_sha_current": True,
        "context_complete": True,
        "analysis_completed": True,
        "tests_executed": True,
        "tests_passed": True,
        "lint_executed": True,
        "lint_passed": True,
        "critical_findings": 0,
        "secrets_detected": False,
        "required_criteria_evaluated": True,
        "required_criteria_passed": True,
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


@pytest.mark.parametrize(
    ("change", "expected_status"),
    [
        ({"head_sha_current": False}, DecisionStatus.INCONCLUSIVE),
        ({"context_complete": False}, DecisionStatus.INCONCLUSIVE),
        ({"analysis_completed": False}, DecisionStatus.INCONCLUSIVE),
        ({"tests_executed": False}, DecisionStatus.INCONCLUSIVE),
        ({"tests_passed": False}, DecisionStatus.BLOCKED),
        ({"lint_executed": False}, DecisionStatus.INCONCLUSIVE),
        ({"lint_passed": False}, DecisionStatus.BLOCKED),
        ({"critical_findings": 1}, DecisionStatus.BLOCKED),
        ({"secrets_detected": True}, DecisionStatus.BLOCKED),
        ({"required_criteria_evaluated": False}, DecisionStatus.INCONCLUSIVE),
        ({"required_criteria_passed": False}, DecisionStatus.BLOCKED),
        (
            {"business_logic_changed": True, "tests_changed": False},
            DecisionStatus.CONDITIONAL,
        ),
        ({"pr_is_draft": True}, DecisionStatus.CONDITIONAL),
        ({"no_newer_pr": False}, DecisionStatus.INCONCLUSIVE),
    ],
)
def test_each_gate_rule_has_the_policy_outcome(
    change: dict[str, object], expected_status: DecisionStatus
) -> None:
    assert evaluate_quality_gate(facts(**change)).status is expected_status


def test_critical_finding_blocks() -> None:
    assert evaluate_quality_gate(facts(critical_findings=1)).status is DecisionStatus.BLOCKED


def test_draft_is_conditional() -> None:
    assert evaluate_quality_gate(facts(pr_is_draft=True)).status is DecisionStatus.CONDITIONAL


def test_secret_blocks() -> None:
    assert evaluate_quality_gate(facts(secrets_detected=True)).status is DecisionStatus.BLOCKED


def test_secret_blocks_when_later_controls_are_unknown() -> None:
    decision = evaluate_quality_gate(
        facts(
            secrets_detected=True,
            tests_executed=None,
            tests_passed=None,
        )
    )
    assert decision.status is DecisionStatus.BLOCKED
    assert decision.summary == "Se detectó un secreto potencial en el cambio."


def test_required_criterion_not_evaluated_is_inconclusive() -> None:
    assert (
        evaluate_quality_gate(facts(required_criteria_evaluated=None)).status
        is DecisionStatus.INCONCLUSIVE
    )


def test_blocking_failure_takes_precedence_over_missing_acceptance_evidence() -> None:
    decision = evaluate_quality_gate(facts(tests_passed=False, required_criteria_evaluated=False))
    assert decision.status is DecisionStatus.BLOCKED


def test_rule_evidence_and_required_action_are_preserved() -> None:
    decision = evaluate_quality_gate(
        facts(
            critical_findings=1,
            evidence_by_rule=(("GATE-005", ("finding-123",)),),
        )
    )
    rule = next(rule for rule in decision.rules if rule.rule_id == "GATE-005")
    assert rule.evidence_ids == ("finding-123",)
    assert "GATE-005" in decision.required_actions[0]
