from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pr_gate.domain.types import PullRequestRef
from pr_gate.graph.builder import AnalysisState, GraphDependencies, RunEvent, patch_hash
from pr_gate.infrastructure.config import ModelProfile
from pr_gate.infrastructure.database import AnalysisStore
from pr_gate.infrastructure.github import GitHubClient, PullRequestSnapshot
from pr_gate.infrastructure.llm import OpenAILLMGateway
from pr_gate.infrastructure.remote_runner import RemoteRunner
from pr_gate.infrastructure.workspaces import WorkspaceManager, Workspaces


class RuntimeWorkspaces:
    def __init__(self) -> None:
        self._manager = WorkspaceManager()
        self._workspaces: Workspaces | None = None

    async def prepare(self, snapshot: PullRequestSnapshot) -> tuple[str, str]:
        self._workspaces = await self._manager.prepare(snapshot)
        return str(self._workspaces.baseline), str(self._workspaces.candidate)

    async def apply_patch(self, workspace: str, patch: str) -> bool:
        return await self._manager.apply_patch(Path(workspace), patch)

    async def cleanup(
        self, baseline_workspace: str | None, candidate_workspace: str | None
    ) -> None:
        self._manager.cleanup(self._workspaces)
        self._workspaces = None


class RuntimeRunner:
    def __init__(self, profile: Mapping[str, object]) -> None:
        profile_id = profile.get("id")
        if not isinstance(profile_id, str):
            raise RuntimeError("El perfil de validación no tiene un ID válido.")
        executor_url = os.environ.get("EXECUTOR_URL", "http://executor:8090")
        self._runner = RemoteRunner(executor_url, profile_id)

    async def run(self, workspace: str, phase: str) -> dict[str, Any]:
        return await self._runner.run(workspace, phase)


class RuntimeRepository:
    def __init__(self, store: AnalysisStore) -> None:
        self._store = store

    async def persist(self, state: AnalysisState) -> None:
        analysis_id = state["analysis_id"]
        snapshot = state.get("pr_snapshot")
        if snapshot:
            parsed = PullRequestRef.parse(str(snapshot["url"]))
            self._store.save_snapshot(
                analysis_id,
                parsed.owner,
                parsed.repository,
                parsed.number,
                parsed.url,
                str(snapshot["base_sha"]),
                str(snapshot["head_sha"]),
                bool(snapshot["draft"]),
                {"files": snapshot["files"]},
                title=str(snapshot["title"]),
            )
        finding_ids: list[str] = []
        for finding in state.get("analysis_output", {}).get("findings", []):
            finding_ids.append(self._store.save_finding(analysis_id, finding))
        fix = state.get("candidate_fix")
        if fix and finding_ids:
            self._store.save_candidate_fix(
                finding_ids[0],
                str(fix["patch"]),
                str(fix["regression_test_patch"]),
                patch_hash(str(fix["patch"])),
                "APPLICABLE" if state.get("patch_valid") else "INVALID",
            )
        for evaluation in state.get("acceptance_results", []):
            self._store.save_acceptance_evaluation(
                analysis_id,
                str(evaluation["id"]),
                str(evaluation["text"]),
                bool(evaluation["required"]),
                str(evaluation["status"]),
                [{"id": item} for item in evaluation["evidence"]],
            )
        decision = state["gate_decision"]
        usage = state.get("llm_usage") or {}
        secret_detected = bool(state.get("secret_scan", {}).get("detected"))
        errors = state.get("errors", [])
        first_error = errors[0]["message"] if errors else None
        llm_executed = "analysis_output" in state
        candidate_executed = "candidate_validation" in state
        omission_reason = (
            "Omitido porque se detectó un secreto potencial en el cambio."
            if secret_detected
            else first_error or "No hubo evidencia suficiente para ejecutar este control."
        )
        not_executed_controls = [
            {
                "id": rule["id"],
                "label": rule["message"],
                "reason": omission_reason,
            }
            for rule in decision["not_evaluated_rules"]
        ]
        self._store.save_gate_decision(
            analysis_id,
            str(decision["status"]),
            str(decision["policy_version"]),
            str(decision["summary"]),
            [{"rule_id": rule["id"], "message": rule["message"]} for rule in decision["rules"]],
        )
        raw_input_tokens = usage.get("input_tokens")
        raw_output_tokens = usage.get("output_tokens")
        raw_cost = usage.get("estimated_cost")
        input_tokens = raw_input_tokens if isinstance(raw_input_tokens, int) else None
        output_tokens = raw_output_tokens if isinstance(raw_output_tokens, int) else None
        estimated_cost = float(raw_cost) if isinstance(raw_cost, int | float) else None
        self._store.finish(
            analysis_id,
            str(decision["status"]),
            {
                "analysis_id": analysis_id,
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
                        if isinstance(item, dict) and isinstance(item.get("filename"), str)
                    ]
                    if snapshot
                    else [],
                },
                "decision": decision,
                "findings": state.get("analysis_output"),
                "fix": fix,
                "validations": {
                    "original": state.get("original_validation"),
                    "baseline": state.get("baseline_validation"),
                    "candidate": state.get("candidate_validation"),
                },
                "acceptance_criteria": state.get("acceptance_results", []),
                "secret_evidence": state.get("secret_evidence", []),
                "execution": {
                    "llm": {
                        "status": "EXECUTED" if llm_executed else "NOT_EXECUTED",
                        "reason": None if llm_executed else omission_reason,
                    },
                    "candidate_validation": {
                        "status": "EXECUTED" if candidate_executed else "NOT_EXECUTED",
                        "reason": None if candidate_executed else omission_reason,
                    },
                    "not_executed_controls": not_executed_controls,
                },
                "errors": errors,
            },
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
        )


class StoreEventPublisher:
    def __init__(self, store: AnalysisStore) -> None:
        self._store = store
        self._sequences: dict[str, int] = {}

    async def publish(self, analysis_id: str, event: RunEvent) -> None:
        sequence = self._sequences.get(analysis_id, 0) + 1
        self._sequences[analysis_id] = sequence
        self._store.add_event(analysis_id, sequence, event["node"], event["message"])


def build_runtime_dependencies(
    store: AnalysisStore, profile: Mapping[str, object], model_profile: ModelProfile | None = None
) -> GraphDependencies:
    allowed_paths = profile.get("allowed_paths", [])
    if not isinstance(allowed_paths, list) or not all(
        isinstance(path, str) for path in allowed_paths
    ):
        raise RuntimeError("El perfil de validación contiene paths permitidos inválidos.")
    return GraphDependencies(
        pull_requests=GitHubClient(),
        llm=OpenAILLMGateway(model_profile),
        workspaces=RuntimeWorkspaces(),
        runner=RuntimeRunner(profile),
        repository=RuntimeRepository(store),
        events=StoreEventPublisher(store),
        allowed_patch_prefixes=tuple(path.removesuffix("**") for path in allowed_paths),
    )
