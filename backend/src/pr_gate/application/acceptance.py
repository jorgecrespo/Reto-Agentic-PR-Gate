from __future__ import annotations

from dataclasses import dataclass

from pr_gate.domain.types import AcceptanceStatus


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    text: str
    required: bool


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
    evidence_ids: tuple[str, ...],
) -> tuple[AcceptanceEvaluation, ...]:
    """Tests establish only that explicitly supplied criteria were evaluated by validation."""
    status = (
        AcceptanceStatus.PASSED
        if suite_passed is True
        else AcceptanceStatus.FAILED
        if suite_passed is False
        else AcceptanceStatus.NOT_EVALUATED
    )
    return tuple(
        AcceptanceEvaluation(
            criterion.id,
            status,
            evidence_ids if status is not AcceptanceStatus.NOT_EVALUATED else (),
            "validation",
        )
        for criterion in criteria
    )
