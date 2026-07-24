from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pr_gate.application.models import AnalysisOutput, FixOutput
from pr_gate.infrastructure.context import ContextLimits, build_context_bundle
from pr_gate.infrastructure.github import PullRequestSnapshot
from pr_gate.infrastructure.llm import LLMError, OpenAILLMGateway
from pr_gate.infrastructure.patches import PatchValidationError, validate_patch_shape
from pr_gate.infrastructure.runner import CommandResult, DockerRunner
from pr_gate.infrastructure.workspaces import WorkspaceManager, Workspaces

_SECRET = re.compile(r"(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", re.I)
_SENSITIVE_PATH = re.compile(r"(?:^|/)(?:\.env|id_rsa|.*\.pem)$", re.I)


@dataclass(frozen=True)
class ValidationEvidence:
    baseline: CommandResult | None
    candidate: CommandResult | None
    suite: CommandResult | None
    lint: CommandResult | None
    patch_applied: bool | None
    regression_reproduced: bool | None
    regression_fixed: bool | None
    suite_passed: bool | None


@dataclass(frozen=True)
class WorkflowEvidence:
    snapshot: PullRequestSnapshot
    context: str
    secrets_detected: bool
    analysis: AnalysisOutput | None
    fix: FixOutput | None
    validation: ValidationEvidence
    limitations: tuple[str, ...]


def build_context(snapshot: PullRequestSnapshot, max_characters: int = 40_000) -> tuple[str, bool]:
    bundle = build_context_bundle(snapshot, ContextLimits(max_total_characters=max_characters))
    return bundle.prompt, bundle.secrets_detected


def _profile_prefixes(
    profile: dict[str, Any], key: str, fallback: tuple[str, ...]
) -> tuple[str, ...]:
    paths = profile.get(key)
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        return fallback
    return tuple(path.removesuffix("**") for path in paths)


async def run_candidate_validation(
    snapshot: PullRequestSnapshot,
    fix: FixOutput,
    profile: dict[str, Any],
) -> ValidationEvidence:
    allowed = tuple(str(path).removesuffix("**") for path in profile["allowed_paths"])
    source_allowed = _profile_prefixes(profile, "allowed_source_paths", allowed)
    test_allowed = _profile_prefixes(profile, "allowed_test_paths", allowed)
    try:
        validate_patch_shape(fix.patch, source_allowed)
        if not fix.regression_test_patch.strip():
            raise PatchValidationError("La propuesta debe incluir un test de regresión.")
        validate_patch_shape(fix.regression_test_patch, test_allowed)
    except PatchValidationError:
        return ValidationEvidence(None, None, None, None, False, None, None, None)
    manager = WorkspaceManager()
    workspaces: Workspaces | None = None
    try:
        workspaces = await manager.prepare(snapshot)
        baseline_applied = await manager.apply_patch(workspaces.baseline, fix.regression_test_patch)
        candidate_source = await manager.apply_patch(workspaces.candidate, fix.patch)
        candidate_test = await manager.apply_patch(workspaces.candidate, fix.regression_test_patch)
        if not (baseline_applied and candidate_source and candidate_test):
            return ValidationEvidence(None, None, None, None, False, None, None, None)
        runner = DockerRunner(timeout_seconds=int(profile["timeout_seconds"]))
        regression_command = tuple(
            str(value) for value in profile.get("regression_test_command", profile["test_command"])
        )
        test_command = tuple(str(value) for value in profile["test_command"])
        lint_command = tuple(str(value) for value in profile["lint_command"])
        baseline = await runner.run(workspaces.baseline, "baseline-regression", regression_command)
        candidate = await runner.run(
            workspaces.candidate, "candidate-regression", regression_command
        )
        suite = await runner.run(workspaces.candidate, "candidate-suite", test_command)
        lint = await runner.run(workspaces.candidate, "candidate-lint", lint_command)
        infrastructure = any(
            result.infrastructure_error or result.timed_out
            for result in (baseline, candidate, suite, lint)
        )
        return ValidationEvidence(
            baseline,
            candidate,
            suite,
            lint,
            True,
            False if infrastructure else baseline.exit_code != 0,
            False if infrastructure else candidate.exit_code == 0,
            False if infrastructure else suite.exit_code == 0 and lint.exit_code == 0,
        )
    finally:
        manager.cleanup(workspaces)


async def gather_evidence(
    snapshot: PullRequestSnapshot, profile: dict[str, Any]
) -> WorkflowEvidence:
    context, secrets_detected = build_context(snapshot)
    if secrets_detected:
        return WorkflowEvidence(
            snapshot,
            context,
            True,
            None,
            None,
            ValidationEvidence(None, None, None, None, None, None, None, None),
            ("Se detectó un secreto potencial en el diff.",),
        )
    try:
        gateway = OpenAILLMGateway()
        analysis = await gateway.analyze(context)
        if not analysis.findings:
            return WorkflowEvidence(
                snapshot,
                context,
                False,
                analysis,
                None,
                ValidationEvidence(None, None, None, None, None, None, None, None),
                ("No existe un hallazgo confirmado para proponer una corrección.",),
            )
        fix = await gateway.propose_fix(context)
        validation = await run_candidate_validation(snapshot, fix, profile)
        return WorkflowEvidence(snapshot, context, False, analysis, fix, validation, ())
    except LLMError as error:
        return WorkflowEvidence(
            snapshot,
            context,
            False,
            None,
            None,
            ValidationEvidence(None, None, None, None, None, None, None, None),
            (str(error),),
        )
