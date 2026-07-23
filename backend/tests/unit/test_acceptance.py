from pr_gate.application.acceptance import AcceptanceCriterion, evaluate_acceptance_criteria
from pr_gate.domain.types import AcceptanceStatus


def test_acceptance_is_not_evaluated_without_validation_evidence() -> None:
    result = evaluate_acceptance_criteria((AcceptanceCriterion("AC-1", "works", True),), None, ())
    assert result[0].status is AcceptanceStatus.NOT_EVALUATED


def test_acceptance_records_evidence_when_validation_passes() -> None:
    result = evaluate_acceptance_criteria(
        (AcceptanceCriterion("AC-1", "works", True),), True, ("suite-1",)
    )
    assert result[0].status is AcceptanceStatus.PASSED
    assert result[0].evidence_ids == ("suite-1",)
