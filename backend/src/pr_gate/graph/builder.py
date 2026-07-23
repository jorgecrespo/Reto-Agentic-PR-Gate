from __future__ import annotations

import hashlib
import operator
from dataclasses import dataclass
from typing import Annotated, Any, Protocol, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from pr_gate.application.acceptance import (
    AcceptanceCriterion,
)
from pr_gate.application.acceptance import (
    evaluate_acceptance_criteria as evaluate_acceptance,
)
from pr_gate.application.models import AnalysisOutput, FixOutput
from pr_gate.domain.gate import evaluate_quality_gate
from pr_gate.domain.types import GateFacts, PullRequestRef
from pr_gate.infrastructure.context import build_context_bundle
from pr_gate.infrastructure.github import PullRequestSnapshot
from pr_gate.infrastructure.patches import PatchValidationError, validate_patch_shape


class WorkflowError(TypedDict):
    code: str
    message: str


class RunEvent(TypedDict):
    node: str
    message: str


class AnalysisState(TypedDict, total=False):
    """JSON-serializable workflow data; adapters are captured by node closures, never state."""

    analysis_id: str
    request: dict[str, Any]
    pr_snapshot: dict[str, Any]
    baseline_workspace: str
    candidate_workspace: str
    context_bundle: str
    context_complete: bool
    context_excluded: list[str]
    secret_scan: dict[str, bool]
    analysis_output: dict[str, Any]
    candidate_fix: dict[str, Any]
    patch_valid: bool
    baseline_validation: dict[str, Any]
    candidate_validation: dict[str, Any]
    acceptance_results: list[dict[str, Any]]
    gate_decision: dict[str, Any]
    finalized: bool
    events: Annotated[list[RunEvent], operator.add]
    errors: Annotated[list[WorkflowError], operator.add]


class PullRequestProvider(Protocol):
    async def fetch_snapshot(self, ref: PullRequestRef) -> PullRequestSnapshot: ...

    async def fetch_current_head_sha(self, ref: PullRequestRef) -> str: ...


class LLMGateway(Protocol):
    async def analyze(self, context: str) -> AnalysisOutput: ...

    async def propose_fix(self, context: str) -> FixOutput: ...


class WorkspaceProvider(Protocol):
    async def prepare(self, snapshot: PullRequestSnapshot) -> tuple[str, str]: ...

    async def apply_patch(self, workspace: str, patch: str) -> bool: ...

    async def cleanup(
        self, baseline_workspace: str | None, candidate_workspace: str | None
    ) -> None: ...


class SandboxRunner(Protocol):
    async def run(self, workspace: str, phase: str) -> dict[str, Any]: ...


class AnalysisRepository(Protocol):
    async def persist(self, state: AnalysisState) -> None: ...


class EventPublisher(Protocol):
    async def publish(self, analysis_id: str, event: RunEvent) -> None: ...


@dataclass(frozen=True)
class GraphDependencies:
    pull_requests: PullRequestProvider
    llm: LLMGateway
    workspaces: WorkspaceProvider
    runner: SandboxRunner
    repository: AnalysisRepository
    events: EventPublisher
    allowed_patch_prefixes: tuple[str, ...]


def _event(node: str, message: str) -> dict[str, list[RunEvent]]:
    return {"events": [{"node": node, "message": message}]}


def _error(code: str, message: str) -> dict[str, list[WorkflowError]]:
    return {"errors": [{"code": code, "message": message}]}


def _snapshot_to_data(snapshot: PullRequestSnapshot) -> dict[str, Any]:
    return {
        "url": snapshot.ref.url,
        "title": snapshot.title,
        "body": snapshot.body,
        "draft": snapshot.draft,
        "base_sha": snapshot.base_sha,
        "head_sha": snapshot.head_sha,
        "files": [dict(item) for item in snapshot.files],
        "clone_url": snapshot.clone_url,
        "commits": [dict(item) for item in snapshot.commits],
        "checks": [dict(item) for item in snapshot.checks],
        "diff_integrity": snapshot.diff_integrity,
    }


def _snapshot_from_state(state: AnalysisState) -> PullRequestSnapshot:
    data = state["pr_snapshot"]
    return PullRequestSnapshot(
        ref=PullRequestRef.parse(str(data["url"])),
        title=str(data["title"]),
        body=str(data["body"]),
        draft=bool(data["draft"]),
        base_sha=str(data["base_sha"]),
        head_sha=str(data["head_sha"]),
        files=tuple(dict(item) for item in data["files"]),
        clone_url=str(data["clone_url"]),
        commits=tuple(dict(item) for item in data.get("commits", [])),
        checks=tuple(dict(item) for item in data.get("checks", [])),
        diff_integrity=bool(data.get("diff_integrity", True)),
    )


def _has_error(state: AnalysisState, code: str) -> bool:
    return any(error["code"] == code for error in state.get("errors", []))


def build_graph(dependencies: GraphDependencies) -> Any:
    async def validate_request(state: AnalysisState) -> dict[str, Any]:
        request = state.get("request", {})
        analysis_id = state.get("analysis_id", str(uuid4()))
        try:
            PullRequestRef.parse(str(request.get("pull_request_url", "")))
        except ValueError as error:
            return {
                "analysis_id": analysis_id,
                **_event("validate_request", "Solicitud inválida."),
                **_error("INVALID_REQUEST", str(error)),
            }
        return {
            "analysis_id": analysis_id,
            **_event("validate_request", "Solicitud validada."),
        }

    async def fetch_pull_request(state: AnalysisState) -> dict[str, Any]:
        try:
            ref = PullRequestRef.parse(str(state["request"]["pull_request_url"]))
            snapshot = await dependencies.pull_requests.fetch_snapshot(ref)
        except (RuntimeError, ValueError) as error:
            return {
                **_event("fetch_pull_request", "No fue posible recuperar el PR."),
                **_error("GITHUB_UNAVAILABLE", str(error)),
            }
        return {
            "pr_snapshot": _snapshot_to_data(snapshot),
            **_event("fetch_pull_request", "Snapshot del PR recuperado."),
        }

    async def prepare_workspaces(state: AnalysisState) -> dict[str, Any]:
        try:
            baseline, candidate = await dependencies.workspaces.prepare(_snapshot_from_state(state))
        except RuntimeError as error:
            return {
                **_event("prepare_workspaces", "No fue posible preparar workspaces."),
                **_error("WORKSPACE_UNAVAILABLE", str(error)),
            }
        return {
            "baseline_workspace": baseline,
            "candidate_workspace": candidate,
            **_event("prepare_workspaces", "Workspaces efímeros preparados."),
        }

    async def build_context_node(state: AnalysisState) -> dict[str, Any]:
        bundle = build_context_bundle(_snapshot_from_state(state))
        return {
            "context_bundle": bundle.prompt,
            "secret_scan": {"detected": bundle.secrets_detected},
            "context_complete": bundle.complete,
            "context_excluded": list(bundle.excluded),
            **_event("build_context", "Contexto acotado construido."),
        }

    async def scan_context(state: AnalysisState) -> dict[str, Any]:
        secret_found = bool(state.get("secret_scan", {}).get("detected"))
        return {
            "secret_scan": {"detected": secret_found},
            **_event("scan_context", "Contexto saneado."),
        }

    async def analyze_change(state: AnalysisState) -> dict[str, Any]:
        try:
            output = await dependencies.llm.analyze(state["context_bundle"])
        except RuntimeError as error:
            return {
                **_event("analyze_change", "El análisis estructurado no estuvo disponible."),
                **_error("LLM_UNAVAILABLE", str(error)),
            }
        return {
            "analysis_output": output.model_dump(),
            **_event("analyze_change", "Cambio analizado."),
        }

    async def generate_candidate_fix(state: AnalysisState) -> dict[str, Any]:
        try:
            fix = await dependencies.llm.propose_fix(state["context_bundle"])
        except RuntimeError as error:
            return {
                **_event("generate_candidate_fix", "No fue posible proponer corrección."),
                **_error("LLM_UNAVAILABLE", str(error)),
            }
        return {
            "candidate_fix": fix.model_dump(),
            **_event("generate_candidate_fix", "Corrección propuesta."),
        }

    async def validate_patch_shape_node(state: AnalysisState) -> dict[str, Any]:
        fix = state["candidate_fix"]
        try:
            validate_patch_shape(str(fix["patch"]), dependencies.allowed_patch_prefixes)
            validate_patch_shape(
                str(fix["regression_test_patch"]), dependencies.allowed_patch_prefixes
            )
        except PatchValidationError as error:
            return {
                "patch_valid": False,
                **_event("validate_patch_shape", "El parche no es aplicable dentro del perfil."),
                **_error("INVALID_PATCH", str(error)),
            }
        return {"patch_valid": True, **_event("validate_patch_shape", "Forma de parche válida.")}

    async def run_baseline_regression(state: AnalysisState) -> dict[str, Any]:
        fix = state["candidate_fix"]
        applied = await dependencies.workspaces.apply_patch(
            state["baseline_workspace"], str(fix["regression_test_patch"])
        )
        if not applied:
            return {
                "baseline_validation": {"executed": False, "reproduced": None},
                **_error(
                    "PATCH_NOT_APPLIED", "El test de regresión no pudo aplicarse al baseline."
                ),
            }
        result = await dependencies.runner.run(state["baseline_workspace"], "baseline-regression")
        infrastructure = bool(result.get("infrastructure_error") or result.get("timed_out"))
        classification = result.get("classification")
        reproduced = (
            classification == "ASSERTION_FAILURE"
            if isinstance(classification, str)
            else result.get("exit_code") != 0
        )
        return {
            "baseline_validation": {
                "executed": not infrastructure,
                "reproduced": None if infrastructure else reproduced,
                "result": result,
            },
            **_event("run_baseline_regression", "Regresión ejecutada sobre baseline."),
        }

    async def run_candidate_validation(state: AnalysisState) -> dict[str, Any]:
        fix = state["candidate_fix"]
        source_applied = await dependencies.workspaces.apply_patch(
            state["candidate_workspace"], str(fix["patch"])
        )
        test_applied = await dependencies.workspaces.apply_patch(
            state["candidate_workspace"], str(fix["regression_test_patch"])
        )
        if not (source_applied and test_applied):
            return {
                "candidate_validation": {"patch_applied": False, "tests_executed": False},
                **_error("PATCH_NOT_APPLIED", "El parche no pudo aplicarse al candidate."),
            }
        regression = await dependencies.runner.run(
            state["candidate_workspace"], "candidate-regression"
        )
        suite = await dependencies.runner.run(state["candidate_workspace"], "candidate-suite")
        lint = await dependencies.runner.run(state["candidate_workspace"], "candidate-lint")
        results = (regression, suite, lint)
        infrastructure = any(
            bool(result.get("infrastructure_error") or result.get("timed_out"))
            for result in results
        )
        return {
            "candidate_validation": {
                "patch_applied": True,
                "tests_executed": not infrastructure,
                "regression_fixed": None if infrastructure else regression.get("exit_code") == 0,
                "suite_passed": None
                if infrastructure
                else suite.get("exit_code") == 0 and lint.get("exit_code") == 0,
                "results": list(results),
            },
            **_event("run_candidate_validation", "Candidate validado con comandos administrados."),
        }

    async def evaluate_acceptance_criteria(state: AnalysisState) -> dict[str, Any]:
        criteria = state["request"].get("acceptance_criteria", [])
        suite_passed = state.get("candidate_validation", {}).get("suite_passed")
        evaluations = evaluate_acceptance(
            tuple(
                AcceptanceCriterion(
                    str(item["id"]), str(item["text"]), bool(item.get("required", True))
                )
                for item in criteria
            ),
            suite_passed,
            ("validation:candidate-suite",),
        )
        results = [
            {
                "id": item.criterion_id,
                "text": next(str(c["text"]) for c in criteria if c["id"] == item.criterion_id),
                "required": next(
                    bool(c.get("required", True)) for c in criteria if c["id"] == item.criterion_id
                ),
                "status": str(item.status),
                "evidence": list(item.evidence_ids),
                "source": item.source,
            }
            for item in evaluations
        ]
        return {
            "acceptance_results": results,
            **_event("evaluate_acceptance_criteria", "Criterios evaluados."),
        }

    async def apply_quality_gate(state: AnalysisState) -> dict[str, Any]:
        validation = state.get("candidate_validation", {})
        baseline = state.get("baseline_validation", {})
        criteria = state.get("acceptance_results", [])
        required = [item for item in criteria if item["required"]]
        analysis = state.get("analysis_output", {})
        critical = sum(
            finding.get("severity") == "critical" for finding in analysis.get("findings", [])
        )
        snapshot = state.get("pr_snapshot", {})
        sha_current: bool | None = None
        if snapshot:
            try:
                ref = PullRequestRef.parse(str(snapshot["url"]))
                sha_current = (
                    await dependencies.pull_requests.fetch_current_head_sha(ref)
                    == snapshot["head_sha"]
                )
            except RuntimeError:
                sha_current = None
        decision = evaluate_quality_gate(
            GateFacts(
                head_sha_current=sha_current,
                context_complete=bool(state.get("context_complete")) if snapshot else None,
                tests_executed=validation.get("tests_executed"),
                tests_passed=validation.get("suite_passed"),
                critical_findings=critical,
                secrets_detected=state.get("secret_scan", {}).get("detected"),
                required_criteria_evaluated=all(
                    item["status"] != "NOT_EVALUATED" for item in required
                ),
                required_criteria_passed=all(item["status"] == "PASSED" for item in required),
                patch_applied=validation.get("patch_applied"),
                regression_reproduced=baseline.get("reproduced"),
                regression_fixed=validation.get("regression_fixed"),
                suite_passed=validation.get("suite_passed"),
                business_logic_changed=bool(analysis.get("findings")),
                tests_changed=bool(state.get("candidate_fix")),
                pr_is_draft=bool(state.get("pr_snapshot", {}).get("draft", False)),
                no_newer_pr=sha_current,
                evidence_by_rule=(
                    ("GATE-001", ("github:head-sha",)),
                    ("GATE-015", ("github:head-sha",)),
                    ("GATE-003", ("validation:candidate-suite",)),
                    (
                        "GATE-007",
                        tuple(
                            evidence for item in criteria for evidence in item.get("evidence", [])
                        ),
                    ),
                ),
            )
        )
        return {
            "gate_decision": {
                "status": str(decision.status),
                "summary": decision.summary,
                "policy_version": decision.policy_version,
                "rules": [
                    {
                        "id": rule.rule_id,
                        "outcome": str(rule.outcome),
                        "message": rule.message,
                        "evidence_ids": list(rule.evidence_ids),
                    }
                    for rule in decision.rules
                ],
            },
            **_event("apply_quality_gate", "Política determinística aplicada."),
        }

    async def persist_report(state: AnalysisState) -> dict[str, Any]:
        await dependencies.repository.persist(state)
        for event in state.get("events", []):
            await dependencies.events.publish(state["analysis_id"], event)
        return _event("persist_report", "Informe persistido.")

    async def finalize(state: AnalysisState) -> dict[str, Any]:
        await dependencies.workspaces.cleanup(
            state.get("baseline_workspace"), state.get("candidate_workspace")
        )
        event: RunEvent = {"node": "finalize", "message": "Workflow finalizado."}
        await dependencies.events.publish(state["analysis_id"], event)
        return {"finalized": True, "events": [event]}

    def after_validation(state: AnalysisState) -> str:
        if _has_error(state, "INVALID_REQUEST"):
            return "apply_quality_gate"
        return "fetch_pull_request"

    def after_fetch(state: AnalysisState) -> str:
        if _has_error(state, "GITHUB_UNAVAILABLE"):
            return "apply_quality_gate"
        return "prepare_workspaces"

    def after_scan(state: AnalysisState) -> str:
        if state.get("secret_scan", {}).get("detected"):
            return "apply_quality_gate"
        return "analyze_change"

    def after_analysis(state: AnalysisState) -> str:
        if state.get("errors"):
            return "apply_quality_gate"
        findings = state.get("analysis_output", {}).get("findings", [])
        return "generate_candidate_fix" if findings else "evaluate_acceptance_criteria"

    def after_patch_validation(state: AnalysisState) -> str:
        if state.get("patch_valid"):
            return "run_baseline_regression"
        return "evaluate_acceptance_criteria"

    graph = StateGraph(AnalysisState)
    graph.add_node("validate_request", validate_request)
    graph.add_node("fetch_pull_request", fetch_pull_request)
    graph.add_node("prepare_workspaces", prepare_workspaces)
    graph.add_node("build_context", build_context_node)
    graph.add_node("scan_context", scan_context)
    graph.add_node("analyze_change", analyze_change)
    graph.add_node("generate_candidate_fix", generate_candidate_fix)
    graph.add_node("validate_patch_shape", validate_patch_shape_node)
    graph.add_node("run_baseline_regression", run_baseline_regression)
    graph.add_node("run_candidate_validation", run_candidate_validation)
    graph.add_node("evaluate_acceptance_criteria", evaluate_acceptance_criteria)
    graph.add_node("apply_quality_gate", apply_quality_gate)
    graph.add_node("persist_report", persist_report)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "validate_request")
    graph.add_conditional_edges("validate_request", after_validation)
    graph.add_conditional_edges("fetch_pull_request", after_fetch)
    graph.add_edge("prepare_workspaces", "build_context")
    graph.add_edge("build_context", "scan_context")
    graph.add_conditional_edges("scan_context", after_scan)
    graph.add_conditional_edges("analyze_change", after_analysis)
    graph.add_edge("generate_candidate_fix", "validate_patch_shape")
    graph.add_conditional_edges("validate_patch_shape", after_patch_validation)
    graph.add_edge("run_baseline_regression", "run_candidate_validation")
    graph.add_edge("run_candidate_validation", "evaluate_acceptance_criteria")
    graph.add_edge("evaluate_acceptance_criteria", "apply_quality_gate")
    graph.add_edge("apply_quality_gate", "persist_report")
    graph.add_edge("persist_report", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def patch_hash(patch: str) -> str:
    """Stable hash for persistence adapters without retaining executable behavior."""
    return hashlib.sha256(patch.encode()).hexdigest()
