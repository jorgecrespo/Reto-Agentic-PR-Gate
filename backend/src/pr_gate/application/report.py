from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisReport:
    """Sanitized workflow output for persistence and API responses."""

    data: dict[str, Any]

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> AnalysisReport:
        snapshot = _mapping(state.get("pr_snapshot"))
        decision = _mapping(state.get("gate_decision"))
        analysis_output = (
            _mapping(state.get("analysis_output")) if state.get("analysis_output") else None
        )
        return cls(
            {
                "analysis_id": state.get("analysis_id"),
                "head_sha": snapshot.get("head_sha") if snapshot else None,
                "pull_request": {
                    "url": snapshot.get("url") if snapshot else None,
                    "title": snapshot.get("title") if snapshot else None,
                    "base_sha": snapshot.get("base_sha") if snapshot else None,
                    "head_sha": snapshot.get("head_sha") if snapshot else None,
                    "draft": snapshot.get("draft") if snapshot else None,
                    "modified_files": [
                        str(item.get("filename"))
                        for item in snapshot.get("files", [])
                        if isinstance(item, Mapping) and isinstance(item.get("filename"), str)
                    ]
                    if snapshot
                    else [],
                },
                "decision": decision,
                "findings": analysis_output,
                "fix": state.get("candidate_fix"),
                "validations": {
                    "original": state.get("original_validation"),
                    "baseline": state.get("baseline_validation"),
                    "candidate": state.get("candidate_validation"),
                },
                "acceptance_criteria": state.get("acceptance_results", []),
                "secret_evidence": state.get("secret_evidence", []),
                "llm_usage": state.get("llm_usage", {}),
                "execution": state.get("execution_summary", {}),
                "errors": state.get("errors", []),
                "finalized": bool(state.get("finalized")),
                "cleanup_succeeded": state.get("cleanup_succeeded"),
            }
        )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
