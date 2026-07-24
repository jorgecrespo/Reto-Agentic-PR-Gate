from __future__ import annotations

import hashlib
import json
import logging
import operator
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from pr_gate.application.acceptance import (
    AcceptanceCriterion,
)
from pr_gate.application.acceptance import (
    evaluate_acceptance_criteria as evaluate_acceptance,
)
from pr_gate.application.models import AnalysisOutput, FixOutput
from pr_gate.application.report import AnalysisReport
from pr_gate.domain.gate import evaluate_quality_gate
from pr_gate.domain.types import GateFacts, PullRequestRef
from pr_gate.infrastructure.context import build_context_bundle
from pr_gate.infrastructure.github import PullRequestSnapshot
from pr_gate.infrastructure.patches import (
    PatchValidationError,
    normalize_hunk_counts,
    validate_patch_shape,
)
from pr_gate.infrastructure.security import scan_and_redact


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
    prepare_workspaces_next: Literal["build_context", "apply_quality_gate"]
    context_bundle: str
    context_complete: bool | None
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
    cleanup_succeeded: bool
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
    async def persist(self, report: AnalysisReport) -> None: ...


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
    allowed_source_patch_prefixes: tuple[str, ...] = ()
    allowed_test_patch_prefixes: tuple[str, ...] = ()


logger = logging.getLogger(__name__)
_ADDED_TEST_DEF = re.compile(r"^\+\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", re.MULTILINE)


def _event(node: str, message: str) -> dict[str, list[RunEvent]]:
    return {"events": [{"node": node, "message": message}]}


def _error(code: str, message: str) -> dict[str, list[WorkflowError]]:
    return {"errors": [{"code": code, "message": message}]}


def _prefixes(value: tuple[str, ...], fallback: tuple[str, ...]) -> tuple[str, ...]:
    return value or fallback


def _is_test_path(path: str) -> bool:
    normalized = path.lstrip("/")
    return normalized == "tests" or normalized.startswith("tests/") or "/tests/" in normalized


def _business_logic_changed(snapshot: dict[str, Any], source_prefixes: tuple[str, ...]) -> bool:
    files = snapshot.get("files", [])
    return any(
        isinstance(item, dict)
        and isinstance(item.get("filename"), str)
        and any(str(item["filename"]).startswith(prefix) for prefix in source_prefixes)
        for item in files
    )


def _finding_sort_key(finding: dict[str, Any]) -> tuple[int, float, int]:
    severity_priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    severity = severity_priority.get(str(finding.get("severity", "")).lower(), 0)
    confidence = finding.get("confidence")
    parsed_confidence = confidence if isinstance(confidence, int | float) else 0.0
    evidence = 1 if finding.get("file_path") and finding.get("evidence_excerpt") else 0
    return severity, float(parsed_confidence), evidence


def _regression_test_name(fix: dict[str, Any]) -> str | None:
    configured = fix.get("regression_test_name")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    patch = str(fix.get("regression_test_patch", ""))
    match = _ADDED_TEST_DEF.search(patch)
    return match.group(1) if match else None


def _contains_test(result: dict[str, Any], key: str, test_name: str | None) -> bool:
    tests = result.get(key)
    return bool(test_name and isinstance(tests, list) and test_name in tests)


def _tests_from_results(results: list[Any], key: str) -> tuple[str, ...]:
    collected: list[str] = []
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get(key), list):
            continue
        for test in result[key]:
            if isinstance(test, str) and test not in collected:
                collected.append(test)
    return tuple(collected)


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
    context, _, _ = _workspace_context_and_secret_evidence(state, max_characters)
    return context


def _workspace_context_and_secret_evidence(
    state: AnalysisState, max_characters: int = 20_000
) -> tuple[str, list[dict[str, Any]], bool]:
    workspace = Path(str(state.get("candidate_workspace", "")))
    if not workspace.is_dir():
        return "", [], False
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
    secret_evidence: list[dict[str, Any]] = []
    detected = False
    remaining = max_characters
    for relative_path in sorted(paths):
        candidate = (workspace / relative_path).resolve()
        if not candidate.is_relative_to(workspace.resolve()) or not candidate.is_file():
            continue
        content = candidate.read_text(errors="replace")
        file_scan = scan_and_redact(content)
        detected = detected or file_scan.detected
        secret_evidence.extend(_secret_evidence_for_file(relative_path, content))
        content = file_scan.redacted_text
        excerpt = content[:remaining]
        sections.append(f"<workspace_file path={relative_path}>\n{excerpt}\n</workspace_file>")
        remaining -= len(excerpt)
        if remaining <= 0:
            break
    return "\n".join(sections), secret_evidence, detected


def _secret_evidence_for_file(path: str, content: str) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, line in enumerate(content.splitlines(), start=1):
        scan = scan_and_redact(line)
        if scan.detected:
            evidence.append(
                {
                    "path": path,
                    "start_line": index,
                    "end_line": index,
                    "kinds": list(scan.matches),
                }
            )
    return evidence


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


def _usage_from_response(response: Any) -> dict[str, int | float | None] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
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
        workspace_context, workspace_secret_evidence, workspace_secret_detected = (
            _workspace_context_and_secret_evidence(state)
        )
        combined_context = (
            f"{bundle.prompt}\n{workspace_context}" if workspace_context else bundle.prompt
        )
        combined_scan = scan_and_redact(combined_context)
        return {
            "context_bundle": combined_scan.redacted_text,
            "secret_scan": {
                "detected": bundle.secrets_detected
                or workspace_secret_detected
                or combined_scan.detected
            },
            "secret_evidence": [
                {
                    "path": item.path,
                    "start_line": item.start_line,
                    "end_line": item.end_line,
                    "kinds": list(item.kinds),
                }
                for item in bundle.secret_evidence
            ]
            + workspace_secret_evidence,
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
        suite_infrastructure = bool(suite.get("infrastructure_error") or suite.get("timed_out"))
        lint_infrastructure = bool(lint.get("infrastructure_error") or lint.get("timed_out"))
        return {
            "original_validation": {
                "tests_executed": not suite_infrastructure,
                "tests_passed": None if suite_infrastructure else suite.get("exit_code") == 0,
                "lint_executed": not lint_infrastructure,
                "lint_passed": None if lint_infrastructure else lint.get("exit_code") == 0,
                "results": [suite, lint],
            },
            **_event("run_original_validation", "Suite del PR actual ejecutada."),
        }

    async def analyze_change(state: AnalysisState) -> dict[str, Any]:
        try:
            if hasattr(dependencies.llm, "analyze_with_usage"):
                response = await dependencies.llm.analyze_with_usage(state["context_bundle"])
                output = response.output
                usage = _usage_from_response(response)
            else:
                output = await dependencies.llm.analyze(state["context_bundle"])
                usage = _usage_from_gateway(dependencies.llm)
        except RuntimeError as error:
            return {
                **_event("analyze_change", "El análisis estructurado no estuvo disponible."),
                **_error("LLM_UNAVAILABLE", str(error)),
            }
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
            findings = state.get("analysis_output", {}).get("findings", [])
            selected_index, selected_finding = max(
                enumerate(findings), key=lambda item: _finding_sort_key(item[1]), default=(0, {})
            )
            fix_context = (
                f"{state['context_bundle']}\n<selected_finding>\n"
                f"{json.dumps(selected_finding)}\n</selected_finding>"
            )
            if hasattr(dependencies.llm, "propose_fix_with_usage"):
                response = await dependencies.llm.propose_fix_with_usage(
                    fix_context, str(feedback) if feedback else None
                )
                fix = response.output
                usage = _usage_from_response(response)
            else:
                fix = (
                    await dependencies.llm.propose_fix(fix_context, str(feedback))
                    if feedback
                    else await dependencies.llm.propose_fix(fix_context)
                )
                usage = _usage_from_gateway(dependencies.llm)
        except RuntimeError as error:
            return {
                **_event("generate_candidate_fix", "No fue posible proponer corrección."),
                **_error("LLM_UNAVAILABLE", str(error)),
            }
        fix_data = fix.model_dump()
        fix_data["patch"] = normalize_hunk_counts(str(fix_data["patch"]))
        fix_data["regression_test_patch"] = normalize_hunk_counts(
            str(fix_data["regression_test_patch"])
        )
        selected_finding_id = (
            selected_finding.get("id", selected_index)
            if isinstance(selected_finding, dict)
            else selected_index
        )
        return {
            "candidate_fix": {
                **fix_data,
                "selected_finding_id": str(selected_finding_id),
            },
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
            source_prefixes = dependencies.allowed_source_patch_prefixes
            test_prefixes = dependencies.allowed_test_patch_prefixes
            if not source_prefixes or not test_prefixes:
                raise PatchValidationError(
                    "El perfil debe declarar rutas separadas para código y tests."
                )
            source_patch = str(fix["patch"])
            if not source_patch.strip():
                raise PatchValidationError("La propuesta debe incluir una corrección de código.")
            source_paths = validate_patch_shape(source_patch, source_prefixes)
            if any(_is_test_path(path) for path in source_paths):
                raise PatchValidationError("El parche de código no puede modificar tests.")
            regression_patch = str(fix["regression_test_patch"])
            if not regression_patch.strip():
                raise PatchValidationError("La propuesta debe incluir un test de regresión.")
            test_paths = validate_patch_shape(regression_patch, test_prefixes)
            if not test_paths or not all(_is_test_path(path) for path in test_paths):
                raise PatchValidationError(
                    "El parche de regresión solamente puede modificar archivos de tests."
                )
            if _regression_test_name(fix) is None:
                raise PatchValidationError(
                    "El parche de regresión debe agregar o declarar un test objetivo."
                )
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
        applied = await dependencies.workspaces.apply_patch(
            state["baseline_workspace"], regression_patch
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
        target_test = _regression_test_name(fix)
        reproduced = (
            classification == "ASSERTION_FAILURE"
            and _contains_test(result, "failed_tests", target_test)
            if isinstance(classification, str)
            else None
        )
        return {
            "baseline_validation": {
                "executed": not infrastructure,
                "reproduced": None if infrastructure else reproduced,
                "target_test": target_test,
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
        test_applied = await dependencies.workspaces.apply_patch(
            state["candidate_workspace"], regression_patch
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
        regression_infrastructure = bool(
            regression.get("infrastructure_error") or regression.get("timed_out")
        )
        suite_infrastructure = bool(suite.get("infrastructure_error") or suite.get("timed_out"))
        lint_infrastructure = bool(lint.get("infrastructure_error") or lint.get("timed_out"))
        test_infrastructure = regression_infrastructure or suite_infrastructure
        target_test = _regression_test_name(fix)
        regression_executed = _contains_test(regression, "executed_tests", target_test)
        regression_failed = _contains_test(regression, "failed_tests", target_test)
        return {
            "candidate_validation": {
                "patch_applied": True,
                "tests_executed": not test_infrastructure,
                "target_test": target_test,
                "target_test_executed": None if regression_infrastructure else regression_executed,
                "regression_fixed": None
                if regression_infrastructure
                else regression.get("exit_code") == 0
                and regression_executed
                and not regression_failed,
                "tests_passed": None if suite_infrastructure else suite.get("exit_code") == 0,
                "lint_executed": not lint_infrastructure,
                "lint_passed": None if lint_infrastructure else lint.get("exit_code") == 0,
                "results": list(results),
            },
            **_event("run_candidate_validation", "Candidate validado con comandos administrados."),
        }

    async def evaluate_acceptance_criteria(state: AnalysisState) -> dict[str, Any]:
        criteria = state["request"].get("acceptance_criteria", [])
        original_validation = state.get("original_validation", {})
        validation_results = original_validation.get("results", [])
        tests_passed = original_validation.get("tests_passed")
        evaluations = evaluate_acceptance(
            tuple(
                AcceptanceCriterion(
                    str(item["id"]),
                    str(item["text"]),
                    bool(item.get("required", True)),
                    tuple(str(test) for test in item.get("validation_tests", [])),
                )
                for item in criteria
            ),
            tests_passed,
            _tests_from_results(validation_results, "executed_tests"),
            _tests_from_results(validation_results, "failed_tests"),
        )
        results = [
            {
                "id": item.criterion_id,
                "text": next(str(c["text"]) for c in criteria if c["id"] == item.criterion_id),
                "required": next(
                    bool(c.get("required", True)) for c in criteria if c["id"] == item.criterion_id
                ),
                "validation_tests": next(
                    list(c.get("validation_tests", []))
                    for c in criteria
                    if c["id"] == item.criterion_id
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
        baseline_validation = state.get("baseline_validation", {})
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
                    "validation_tests": list(item.get("validation_tests", [])),
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
                analysis_completed=(
                    "analysis_output" in state and not _has_error(state, "LLM_UNAVAILABLE")
                ),
                tests_executed=original_validation.get("tests_executed"),
                tests_passed=original_validation.get("tests_passed"),
                lint_executed=original_validation.get("lint_executed"),
                lint_passed=original_validation.get("lint_passed"),
                critical_findings=critical,
                secrets_detected=state.get("secret_scan", {}).get("detected"),
                required_criteria_evaluated=all(
                    item["status"] != "NOT_EVALUATED" for item in required
                ),
                required_criteria_passed=all(item["status"] == "PASSED" for item in required),
                business_logic_changed=_business_logic_changed(
                    snapshot,
                    _prefixes(
                        dependencies.allowed_source_patch_prefixes,
                        dependencies.allowed_patch_prefixes,
                    ),
                ),
                tests_changed=any(
                    isinstance(item, dict) and _is_test_path(str(item.get("filename", "")))
                    for item in snapshot.get("files", [])
                ),
                pr_is_draft=bool(state.get("pr_snapshot", {}).get("draft", False)),
                no_newer_pr=sha_current,
                evidence_by_rule=(
                    ("GATE-001", ("github:head-sha",)),
                    ("GATE-015", ("github:head-sha",)),
                    ("GATE-003", ("validation:pr-suite",)),
                    ("GATE-017", ("validation:pr-lint",)),
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
        if not candidate_validation:
            candidate_status = "NOT_PROPOSED"
        elif candidate_validation.get("patch_applied") is False:
            candidate_status = "REJECTED"
        elif (
            candidate_validation.get("tests_executed") is False
            or candidate_validation.get("target_test_executed") is False
        ):
            candidate_status = "INCONCLUSIVE"
        elif baseline_validation.get("reproduced") is not True:
            candidate_status = "INCONCLUSIVE"
        elif (
            candidate_validation.get("patch_applied")
            and candidate_validation.get("regression_fixed")
            and candidate_validation.get("tests_passed")
            and candidate_validation.get("lint_passed")
        ):
            candidate_status = "VALIDATED"
        else:
            candidate_status = "REJECTED"
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
        await dependencies.repository.persist(AnalysisReport.from_state(state))
        return _event("persist_report", "Informe persistido.")

    async def finalize(state: AnalysisState) -> dict[str, Any]:
        try:
            await dependencies.workspaces.cleanup(
                state.get("baseline_workspace"), state.get("candidate_workspace")
            )
            cleanup_succeeded = True
            errors: dict[str, list[WorkflowError]] = {"errors": []}
        except Exception as error:
            logger.exception("Workspace cleanup failed")
            cleanup_succeeded = False
            errors = _error("CLEANUP_FAILED", str(error))
        event: RunEvent = {"node": "finalize", "message": "Workflow finalizado."}
        return {
            "finalized": True,
            "cleanup_succeeded": cleanup_succeeded,
            **errors,
            "events": [event],
        }

    def publish_events(node: Any) -> Any:
        async def wrapped(state: AnalysisState) -> dict[str, Any]:
            update: dict[str, Any] = await node(state)
            analysis_id = str(update.get("analysis_id", state.get("analysis_id", "")))
            if analysis_id:
                for event in update.get("events", []):
                    try:
                        await dependencies.events.publish(analysis_id, event)
                    except RuntimeError:
                        logger.exception("Progress event publishing failed for %s", analysis_id)
            return update

        return wrapped

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
    graph.add_node("validate_request", publish_events(validate_request))
    graph.add_node("fetch_pull_request", publish_events(fetch_pull_request))
    graph.add_node("prepare_workspaces", publish_events(prepare_workspaces))
    graph.add_node("build_context", publish_events(build_context_node))
    graph.add_node("scan_context", publish_events(scan_context))
    graph.add_node("run_original_validation", publish_events(run_original_validation))
    graph.add_node("analyze_change", publish_events(analyze_change))
    graph.add_node("generate_candidate_fix", publish_events(generate_candidate_fix))
    graph.add_node("validate_patch_shape", publish_events(validate_patch_shape_node))
    graph.add_node("run_baseline_regression", publish_events(run_baseline_regression))
    graph.add_node("run_candidate_validation", publish_events(run_candidate_validation))
    graph.add_node("evaluate_acceptance_criteria", publish_events(evaluate_acceptance_criteria))
    graph.add_node("apply_quality_gate", publish_events(apply_quality_gate))
    graph.add_node("persist_report", publish_events(persist_report))
    graph.add_node("finalize", publish_events(finalize))
    graph.add_edge(START, "validate_request")
    graph.add_conditional_edges("validate_request", after_validation)
    graph.add_conditional_edges("fetch_pull_request", after_fetch)
    graph.add_conditional_edges("prepare_workspaces", after_prepare)
    graph.add_edge("build_context", "scan_context")
    graph.add_conditional_edges("scan_context", after_scan)
    graph.add_edge("run_original_validation", "analyze_change")
    graph.add_conditional_edges("analyze_change", after_analysis)
    graph.add_edge("generate_candidate_fix", "validate_patch_shape")
    graph.add_conditional_edges("validate_patch_shape", after_patch_validation)
    graph.add_edge("run_baseline_regression", "run_candidate_validation")
    graph.add_edge("run_candidate_validation", "evaluate_acceptance_criteria")
    graph.add_edge("evaluate_acceptance_criteria", "apply_quality_gate")
    graph.add_edge("apply_quality_gate", "finalize")
    graph.add_edge("finalize", "persist_report")
    graph.add_edge("persist_report", END)
    return graph.compile()


def patch_hash(patch: str) -> str:
    """Stable hash for persistence adapters without retaining executable behavior."""
    return hashlib.sha256(patch.encode()).hexdigest()
