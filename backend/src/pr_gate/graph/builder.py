from __future__ import annotations

import hashlib
import operator
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Protocol, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

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
from pr_gate.infrastructure.patches import (
    PatchValidationError,
    normalize_hunk_counts,
    validate_patch_shape,
)


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
    secret_scan: dict[str, Any]
    secret_evidence: list[dict[str, Any]]
    analysis_output: dict[str, Any]
    candidate_fix: dict[str, Any]
    fix_attempts: int
    patch_feedback: str
    patch_valid: bool
    original_validation: dict[str, Any]
    baseline_validation: dict[str, Any]
    candidate_validation: dict[str, Any]
    acceptance_results: list[dict[str, Any]]
    gate_decision: dict[str, Any]
    llm_usage: dict[str, int | float | None]
    finalized: bool
    events: Annotated[list[RunEvent], operator.add]
    errors: Annotated[list[WorkflowError], operator.add]


class PullRequestProvider(Protocol):
    async def fetch_snapshot(self, ref: PullRequestRef) -> PullRequestSnapshot: ...

    async def fetch_current_head_sha(self, ref: PullRequestRef) -> str: ...


class LLMGateway(Protocol):
    async def analyze(self, context: str) -> AnalysisOutput: ...

    async def propose_fix(self, context: str, feedback: str | None = None) -> FixOutput: ...


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


def _workspaces_ready(state: AnalysisState) -> bool:
    return bool(state.get("baseline_workspace")) and bool(state.get("candidate_workspace"))


def _workspace_fix_context(state: AnalysisState, max_characters: int = 20_000) -> str:
    workspace = Path(str(state.get("candidate_workspace", "")))
    if not workspace.is_dir():
        return ""
    paths = {
        str(item.get("filename"))
        for item in state.get("pr_snapshot", {}).get("files", [])
        if isinstance(item, dict) and isinstance(item.get("filename"), str)
    }
    tests = workspace / "tests"
    if tests.is_dir():
        paths.update(
            path.relative_to(workspace).as_posix()
            for path in sorted(tests.rglob("*.py"))[:10]
            if path.is_file()
        )
    sections: list[str] = []
    remaining = max_characters
    for relative_path in sorted(paths):
        candidate = (workspace / relative_path).resolve()
        if not candidate.is_relative_to(workspace.resolve()) or not candidate.is_file():
            continue
        content = candidate.read_text(errors="replace")
        excerpt = content[:remaining]
        sections.append(f"<workspace_file path={relative_path}>\n{excerpt}\n</workspace_file>")
        remaining -= len(excerpt)
        if remaining <= 0:
            break
    return "\n".join(sections)


def _usage_from_gateway(gateway: Any) -> dict[str, int | float | None] | None:
    usage = getattr(gateway, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "estimated_cost": usage.get("estimated_cost"),
        }
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "estimated_cost": getattr(usage, "estimated_cost", None),
    }


def _merge_usage(
    current: dict[str, int | float | None] | None, update: dict[str, int | float | None] | None
) -> dict[str, int | float | None] | None:
    if update is None:
        return current
    if current is None:
        return dict(update)
    merged: dict[str, int | float | None] = {
        "input_tokens": current.get("input_tokens"),
        "output_tokens": current.get("output_tokens"),
        "estimated_cost": current.get("estimated_cost"),
    }
    for key in ("input_tokens", "output_tokens"):
        current_value = merged.get(key)
        update_value = update.get(key)
        if isinstance(current_value, int) and isinstance(update_value, int):
            merged[key] = current_value + update_value
        elif current_value is None:
            merged[key] = update_value
    current_cost = merged.get("estimated_cost")
    update_cost = update.get("estimated_cost")
    if isinstance(current_cost, (int, float)) and isinstance(update_cost, (int, float)):
        merged["estimated_cost"] = float(current_cost) + float(update_cost)
    elif current_cost is None:
        merged["estimated_cost"] = update_cost
    return merged


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
                "prepare_workspaces_next": "apply_quality_gate",
                **_event("prepare_workspaces", "No fue posible preparar workspaces."),
                **_error("WORKSPACE_UNAVAILABLE", str(error)),
            }
        return {
            "prepare_workspaces_next": "build_context",
            "baseline_workspace": baseline,
            "candidate_workspace": candidate,
            **_event("prepare_workspaces", "Workspaces efímeros preparados."),
        }

    def after_prepare(state: AnalysisState) -> str:
        return str(state.get("prepare_workspaces_next", "build_context"))

    def route_after_prepare(state: AnalysisState) -> Command[Any]:
        return Command(goto=state.get("prepare_workspaces_next", "build_context"))

    async def build_context_node(state: AnalysisState) -> dict[str, Any]:
        if not _workspaces_ready(state):
            return {
                "context_bundle": "",
                "context_complete": None,
                "context_excluded": ["workspace unavailable"],
                "secret_scan": {"detected": None},
                "secret_evidence": [],
                **_event("build_context", "Contexto omitido por falta de workspaces."),
            }
        bundle = build_context_bundle(_snapshot_from_state(state))
        workspace_context = _workspace_fix_context(state)
        return {
            "context_bundle": (
                f"{bundle.prompt}\n{workspace_context}" if workspace_context else bundle.prompt
            ),
            "secret_scan": {"detected": bundle.secrets_detected},
            "secret_evidence": [
                {
                    "path": item.path,
                    "start_line": item.start_line,
                    "end_line": item.end_line,
                    "kinds": list(item.kinds),
                }
                for item in bundle.secret_evidence
            ],
            "context_complete": bundle.complete,
            "context_excluded": list(bundle.excluded),
            **_event("build_context", "Contexto acotado construido."),
        }

    async def scan_context(state: AnalysisState) -> dict[str, Any]:
        if not _workspaces_ready(state):
            return {
                "secret_scan": {"detected": None},
                **_event("scan_context", "Escaneo omitido por falta de workspaces."),
            }
        secret_found = bool(state.get("secret_scan", {}).get("detected"))
        return {
            "secret_scan": {"detected": secret_found},
            **_event("scan_context", "Contexto saneado."),
        }

    async def run_original_validation(state: AnalysisState) -> dict[str, Any]:
        suite = await dependencies.runner.run(state["baseline_workspace"], "pr-suite")
        lint = await dependencies.runner.run(state["baseline_workspace"], "pr-lint")
        infrastructure = any(
            bool(result.get("infrastructure_error") or result.get("timed_out"))
            for result in (suite, lint)
        )
        return {
            "original_validation": {
                "tests_executed": not infrastructure,
                "suite_passed": None
                if infrastructure
                else suite.get("exit_code") == 0 and lint.get("exit_code") == 0,
                "results": [suite, lint],
            },
            **_event("run_original_validation", "Suite del PR actual ejecutada."),
        }

    async def analyze_change(state: AnalysisState) -> dict[str, Any]:
        try:
            output = await dependencies.llm.analyze(state["context_bundle"])
        except RuntimeError as error:
            return {
                **_event("analyze_change", "El análisis estructurado no estuvo disponible."),
                **_error("LLM_UNAVAILABLE", str(error)),
            }
        usage = _usage_from_gateway(dependencies.llm)
        return {
            "analysis_output": output.model_dump(),
            **(
                {"llm_usage": _merge_usage(state.get("llm_usage"), usage)}
                if usage is not None
                else {}
            ),
            **_event("analyze_change", "Cambio analizado."),
        }

    async def generate_candidate_fix(state: AnalysisState) -> dict[str, Any]:
        try:
            feedback = state.get("patch_feedback")
            fix = (
                await dependencies.llm.propose_fix(state["context_bundle"], str(feedback))
                if feedback
                else await dependencies.llm.propose_fix(state["context_bundle"])
            )
        except RuntimeError as error:
            return {
                **_event("generate_candidate_fix", "No fue posible proponer corrección."),
                **_error("LLM_UNAVAILABLE", str(error)),
            }
        usage = _usage_from_gateway(dependencies.llm)
        fix_data = fix.model_dump()
        fix_data["patch"] = normalize_hunk_counts(str(fix_data["patch"]))
        fix_data["regression_test_patch"] = normalize_hunk_counts(
            str(fix_data["regression_test_patch"])
        )
        return {
            "candidate_fix": fix_data,
            "fix_attempts": int(state.get("fix_attempts", 0)) + 1,
            **(
                {"llm_usage": _merge_usage(state.get("llm_usage"), usage)}
                if usage is not None
                else {}
            ),
            **_event("generate_candidate_fix", "Corrección propuesta."),
        }

    async def validate_patch_shape_node(state: AnalysisState) -> dict[str, Any]:
        fix = state["candidate_fix"]
        try:
            validate_patch_shape(str(fix["patch"]), dependencies.allowed_patch_prefixes)
            regression_patch = str(fix["regression_test_patch"])
            if regression_patch:
                validate_patch_shape(regression_patch, dependencies.allowed_patch_prefixes)
        except PatchValidationError as error:
            message = str(error)
            if int(state.get("fix_attempts", 0)) < 2:
                return {
                    "patch_valid": False,
                    "patch_feedback": message,
                    **_event(
                        "validate_patch_shape",
                        "El parche es inválido; se solicitará una corrección.",
                    ),
                }
            return {
                "patch_valid": False,
                **_event("validate_patch_shape", "El parche no es aplicable dentro del perfil."),
                **_error("INVALID_PATCH", message),
            }
        return {"patch_valid": True, **_event("validate_patch_shape", "Forma de parche válida.")}

    async def run_baseline_regression(state: AnalysisState) -> dict[str, Any]:
        fix = state["candidate_fix"]
        regression_patch = str(fix["regression_test_patch"])
        applied = (
            await dependencies.workspaces.apply_patch(state["baseline_workspace"], regression_patch)
            if regression_patch
            else True
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
        regression_patch = str(fix["regression_test_patch"])
        source_applied = await dependencies.workspaces.apply_patch(
            state["candidate_workspace"], str(fix["patch"])
        )
        test_applied = (
            await dependencies.workspaces.apply_patch(
                state["candidate_workspace"], regression_patch
            )
            if regression_patch
            else True
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
        suite_passed = state.get("original_validation", {}).get("suite_passed")
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
        original_validation = state.get("original_validation", {})
        candidate_validation = state.get("candidate_validation", {})
        baseline = state.get("baseline_validation", {})
        criteria = state.get("acceptance_results")
        if criteria is None:
            reason = "Omitido porque el análisis no alcanzó la validación de criterios."
            if state.get("secret_scan", {}).get("detected"):
                reason = "Omitido porque se detectó un secreto potencial en el cambio."
            criteria = [
                {
                    "id": str(item["id"]),
                    "text": str(item["text"]),
                    "required": bool(item.get("required", True)),
                    "status": "NOT_EVALUATED",
                    "evidence": [],
                    "source": "NOT_EXECUTED",
                    "reason": reason,
                }
                for item in state.get("request", {}).get("acceptance_criteria", [])
            ]
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
                context_complete=state.get("context_complete")
                if "context_complete" in state
                else None,
                tests_executed=original_validation.get("tests_executed"),
                tests_passed=original_validation.get("suite_passed"),
                critical_findings=critical,
                secrets_detected=state.get("secret_scan", {}).get("detected"),
                required_criteria_evaluated=all(
                    item["status"] != "NOT_EVALUATED" for item in required
                ),
                required_criteria_passed=all(item["status"] == "PASSED" for item in required),
                patch_applied=candidate_validation.get("patch_applied"),
                regression_reproduced=baseline.get("reproduced"),
                regression_fixed=candidate_validation.get("regression_fixed"),
                suite_passed=candidate_validation.get("suite_passed"),
                business_logic_changed=bool(analysis.get("findings")),
                tests_changed=bool(state.get("candidate_fix")),
                pr_is_draft=bool(state.get("pr_snapshot", {}).get("draft", False)),
                no_newer_pr=sha_current,
                evidence_by_rule=(
                    ("GATE-001", ("github:head-sha",)),
                    ("GATE-015", ("github:head-sha",)),
                    ("GATE-003", ("validation:pr-suite",)),
                    (
                        "GATE-007",
                        tuple(
                            evidence for item in criteria for evidence in item.get("evidence", [])
                        ),
                    ),
                ),
            )
        )

        def rule_data(rule: Any) -> dict[str, Any]:
            return {
                "id": rule.rule_id,
                "outcome": str(rule.outcome),
                "message": rule.message,
                "evidence_ids": list(rule.evidence_ids),
            }

        secret_detected = bool(state.get("secret_scan", {}).get("detected"))
        required_actions = list(decision.required_actions)
        if secret_detected:
            required_actions = [
                "Retirar el secreto potencial del cambio.",
                "Rotar o revocar el secreto si corresponde a una credencial real.",
                "Actualizar el PR y ejecutar un nuevo análisis.",
            ]
        elif analysis.get("findings"):
            required_actions = [
                "Revisar o aplicar la corrección propuesta al PR.",
                "Actualizar el PR y ejecutar un nuevo análisis sobre el nuevo SHA.",
            ]
        candidate_status = (
            "VALIDATED"
            if candidate_validation.get("patch_applied")
            and candidate_validation.get("regression_fixed")
            and candidate_validation.get("suite_passed")
            else "FAILED"
            if candidate_validation
            else "NOT_PROPOSED"
        )
        return {
            "acceptance_results": criteria,
            "gate_decision": {
                "status": str(decision.status),
                "summary": decision.summary,
                "policy_version": decision.policy_version,
                "rules": [rule_data(rule) for rule in decision.rules],
                "blocking_reasons": [rule_data(rule) for rule in decision.blocking_reasons],
                "warnings": [rule_data(rule) for rule in decision.warnings],
                "not_evaluated_rules": [rule_data(rule) for rule in decision.not_evaluated_rules],
                "required_actions": required_actions,
            },
            "candidate_validation": {**candidate_validation, "status": candidate_status},
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
        if not _workspaces_ready(state):
            return "apply_quality_gate"
        if state.get("secret_scan", {}).get("detected"):
            return "apply_quality_gate"
        return "run_original_validation"

    def after_analysis(state: AnalysisState) -> str:
        if state.get("errors"):
            return "apply_quality_gate"
        findings = state.get("analysis_output", {}).get("findings", [])
        return "generate_candidate_fix" if findings else "evaluate_acceptance_criteria"

    def after_patch_validation(state: AnalysisState) -> str:
        if state.get("patch_valid"):
            return "run_baseline_regression"
        if int(state.get("fix_attempts", 0)) < 2:
            return "generate_candidate_fix"
        return "evaluate_acceptance_criteria"

    graph = StateGraph(AnalysisState)
    graph.add_node("validate_request", validate_request)
    graph.add_node("fetch_pull_request", fetch_pull_request)
    graph.add_node("prepare_workspaces", prepare_workspaces)
    graph.add_node("route_after_prepare", route_after_prepare)
    graph.add_node("build_context", build_context_node)
    graph.add_node("scan_context", scan_context)
    graph.add_node("run_original_validation", run_original_validation)
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
    graph.add_edge("prepare_workspaces", "route_after_prepare")
    graph.add_edge("build_context", "scan_context")
    graph.add_conditional_edges("scan_context", after_scan)
    graph.add_edge("run_original_validation", "analyze_change")
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
