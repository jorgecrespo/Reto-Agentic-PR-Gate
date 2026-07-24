from __future__ import annotations

from dataclasses import dataclass

from pr_gate.domain.types import AcceptanceStatus


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    text: str
    required: bool
    validation_tests: tuple[str, ...] = ()


@dataclass(frozen=True)
class AcceptanceEvaluation:
    criterion_id: str
    status: AcceptanceStatus
    evidence_ids: tuple[str, ...]
    source: str
    confidence: float | None = None


def evaluate_acceptance_criteria(
    criteria: tuple[AcceptanceCriterion, ...],
    suite_passed: bool | None,
    executed_tests: tuple[str, ...],
    failed_tests: tuple[str, ...],
) -> tuple[AcceptanceEvaluation, ...]:
    """Criteria pass only when their configured tests ran and did not fail."""
    executed = set(executed_tests)
    failed = set(failed_tests)
    results: list[AcceptanceEvaluation] = []
    for criterion in criteria:
        expected = set(criterion.validation_tests)
        if not expected or not expected.issubset(executed) or suite_passed is None:
            results.append(
                AcceptanceEvaluation(
                    criterion.id,
                    AcceptanceStatus.NOT_EVALUATED,
                    (),
                    "validation",
                )
            )
            continue
        status = (
            AcceptanceStatus.FAILED
            if expected & failed or suite_passed is False
            else AcceptanceStatus.PASSED
        )
        results.append(
            AcceptanceEvaluation(
                criterion.id,
                status,
                tuple(f"test:{test}" for test in sorted(expected)),
                "validation",
            )
        )
    return tuple(results)
