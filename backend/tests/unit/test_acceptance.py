from pr_gate.application.acceptance import AcceptanceCriterion, evaluate_acceptance_criteria
from pr_gate.domain.types import AcceptanceStatus


def test_acceptance_is_not_evaluated_without_validation_evidence() -> None:
    result = evaluate_acceptance_criteria(
        (AcceptanceCriterion("AC-1", "works", True, ("test_works",)),), None, (), ()
    )
    assert result[0].status is AcceptanceStatus.NOT_EVALUATED


def test_acceptance_records_evidence_when_validation_passes() -> None:
    result = evaluate_acceptance_criteria(
        (AcceptanceCriterion("AC-1", "works", True, ("test_works",)),),
        True,
        ("test_works",),
        (),
    )
    assert result[0].status is AcceptanceStatus.PASSED
    assert result[0].evidence_ids == ("test:test_works",)


def test_acceptance_is_not_evaluated_when_suite_passes_without_evidence() -> None:
    result = evaluate_acceptance_criteria(
        (AcceptanceCriterion("AC-1", "works", True),), True, (), ()
    )
    assert result[0].status is AcceptanceStatus.NOT_EVALUATED


def test_acceptance_fails_when_configured_test_failed() -> None:
    result = evaluate_acceptance_criteria(
        (AcceptanceCriterion("AC-1", "works", True, ("test_works",)),),
        False,
        ("test_works",),
        ("test_works",),
    )
    assert result[0].status is AcceptanceStatus.FAILED
