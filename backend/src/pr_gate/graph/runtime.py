from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pr_gate.domain.types import PullRequestRef
from pr_gate.graph.builder import AnalysisState, GraphDependencies, RunEvent, patch_hash
from pr_gate.infrastructure.config import ModelProfile
from pr_gate.infrastructure.database import AnalysisStore
from pr_gate.infrastructure.github import GitHubClient, PullRequestSnapshot
from pr_gate.infrastructure.llm import OpenAILLMGateway
from pr_gate.infrastructure.runner import DockerRunner
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
        self._profile = profile
        timeout_seconds = profile.get("timeout_seconds")
        if not isinstance(timeout_seconds, int):
            raise RuntimeError("El perfil de validación contiene un timeout inválido.")
        self._runner = DockerRunner(timeout_seconds=timeout_seconds)

    async def run(self, workspace: str, phase: str) -> dict[str, Any]:
        command = self._command_for(phase)
        result = await self._runner.run(Path(workspace), phase, command)
        return {
            "command_name": result.command_name,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "infrastructure_error": result.infrastructure_error,
        }

    def _command_for(self, phase: str) -> tuple[str, ...]:
        if phase in {"baseline-regression", "candidate-regression"}:
            configured = self._profile.get("regression_test_command", self._profile["test_command"])
        elif phase == "candidate-suite":
            configured = self._profile["test_command"]
        else:
            configured = self._profile["lint_command"]
        if not isinstance(configured, list) or not all(
            isinstance(value, str) for value in configured
        ):
            raise RuntimeError("El perfil de validación contiene un comando inválido.")
        return tuple(configured)


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
        self._store.save_gate_decision(
            analysis_id,
            str(decision["status"]),
            str(decision["policy_version"]),
            str(decision["summary"]),
            [{"rule_id": rule["id"], "message": rule["message"]} for rule in decision["rules"]],
        )
        self._store.finish(
            analysis_id,
            str(decision["status"]),
            {
                "analysis_id": analysis_id,
                "head_sha": snapshot.get("head_sha") if snapshot else None,
                "decision": decision,
                "findings": state.get("analysis_output"),
                "fix": fix,
                "validations": {
                    "baseline": state.get("baseline_validation"),
                    "candidate": state.get("candidate_validation"),
                },
                "acceptance_criteria": state.get("acceptance_results", []),
                "errors": state.get("errors", []),
            },
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
