from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pr_gate.application.models import AnalysisOutput, FindingOutput, FixOutput
from pr_gate.domain.types import PullRequestRef
from pr_gate.graph.builder import (
    AnalysisState,
    GraphDependencies,
    _workspace_fix_context,
    build_graph,
)
from pr_gate.infrastructure.github import PullRequestSnapshot


@dataclass
class FakePullRequests:
    unavailable: bool = False
    secret: bool = False

    async def fetch_snapshot(self, ref: PullRequestRef) -> PullRequestSnapshot:
        if self.unavailable:
            raise RuntimeError("GitHub no disponible")
        return PullRequestSnapshot(
            ref=ref,
            title="Change",
            body="",
            draft=False,
            base_sha="a" * 40,
            head_sha="b" * 40,
            files=(
                {
                    "filename": "app/orders.py",
                    "patch": (
                        "+ api_key = 'abcdefghijklmnop'"
                        if self.secret
                        else "+ total = request.unit_price"
                    ),
                },
            ),
            clone_url="https://github.com/acme/shop.git",
        )

    async def fetch_current_head_sha(self, ref: PullRequestRef) -> str:
        return "b" * 40


@dataclass
class FakeLLM:
    finding: bool = True
    severity: str = "critical"
    valid_patch: bool = True
    usage: dict[str, int | float | None] | None = field(
        default_factory=lambda: {"input_tokens": 11, "output_tokens": 7, "estimated_cost": 0.01}
    )

    async def analyze(self, context: str) -> AnalysisOutput:
        findings = []
        if self.finding:
            findings.append(
                FindingOutput(
                    title="Client price",
                    category="security",
                    severity=self.severity,
                    file_path="app/orders.py",
                    start_line=1,
                    end_line=1,
                    evidence_excerpt="request.unit_price",
                    explanation="Untrusted input",
                    impact="Price manipulation",
                    recommended_action="Use catalog price",
                    confidence=1,
                )
            )
        return AnalysisOutput(summary="analysis", findings=findings)

    async def propose_fix(self, context: str, feedback: str | None = None) -> FixOutput:
        return FixOutput(
            finding_index=0,
            summary="fix",
            patch=(
                "diff --git a/app/orders.py b/app/orders.py\n--- a/app/orders.py\n"
                "+++ b/app/orders.py\n@@ -1 +1 @@\n-a\n+b\n"
                if self.valid_patch
                else "not a diff"
            ),
            regression_test_patch=(
                "diff --git a/app/test_orders.py b/app/test_orders.py\n"
                "--- a/app/test_orders.py\n+++ b/app/test_orders.py\n"
                "@@ -1 +1 @@\n-a\n+b\n"
            ),
            modified_paths=["app/orders.py", "app/test_orders.py"],
        )


@dataclass
class FakeWorkspaces:
    patch_applies: bool = True
    cleaned: bool = False
    prepare_fails: bool = False

    async def prepare(self, snapshot: PullRequestSnapshot) -> tuple[str, str]:
        if self.prepare_fails:
            raise RuntimeError("No fue posible preparar el snapshot del PR.")
        return ("/tmp/baseline", "/tmp/candidate")

    async def apply_patch(self, workspace: str, patch: str) -> bool:
        return self.patch_applies

    async def cleanup(
        self, baseline_workspace: str | None, candidate_workspace: str | None
    ) -> None:
        self.cleaned = True


@dataclass
class FakeRunner:
    infrastructure: bool = False

    async def run(self, workspace: str, phase: str) -> dict[str, object]:
        if self.infrastructure:
            return {"exit_code": None, "infrastructure_error": True, "timed_out": False}
        exit_code = 1 if phase == "baseline-regression" else 0
        return {"exit_code": exit_code, "infrastructure_error": False, "timed_out": False}


@dataclass
class FakeRepository:
    persisted: list[AnalysisState] = field(default_factory=list)

    async def persist(self, state: AnalysisState) -> None:
        self.persisted.append(state)


@dataclass
class FakeEvents:
    published: list[tuple[str, str]] = field(default_factory=list)

    async def publish(self, analysis_id: str, event: dict[str, str]) -> None:
        self.published.append((analysis_id, event["node"]))


def dependencies(
    *,
    finding: bool = True,
    severity: str = "critical",
    unavailable: bool = False,
    secret: bool = False,
    valid_patch: bool = True,
    infrastructure: bool = False,
    prepare_fails: bool = False,
) -> tuple[GraphDependencies, FakeRepository, FakeWorkspaces, FakeEvents]:
    repository = FakeRepository()
    workspaces = FakeWorkspaces(prepare_fails=prepare_fails)
    events = FakeEvents()
    return (
        GraphDependencies(
            pull_requests=FakePullRequests(unavailable=unavailable, secret=secret),
            llm=FakeLLM(finding=finding, severity=severity, valid_patch=valid_patch),
            workspaces=workspaces,
            runner=FakeRunner(infrastructure=infrastructure),
            repository=repository,
            events=events,
            allowed_patch_prefixes=("app/",),
        ),
        repository,
        workspaces,
        events,
    )


def request(url: str = "https://github.com/acme/shop/pull/1") -> AnalysisState:
    return {
        "analysis_id": "analysis-1",
        "request": {
            "pull_request_url": url,
            "acceptance_criteria": [{"id": "AC-1", "text": "Works", "required": True}],
        },
    }


def test_workspace_fix_context_includes_changed_files_and_existing_tests(tmp_path) -> None:
    app = tmp_path / "app"
    tests = tmp_path / "tests"
    app.mkdir()
    tests.mkdir()
    (app / "orders.py").write_text("total = item.unit_price\n")
    (tests / "test_orders.py").write_text("def test_catalog_price(): ...\n")

    context = _workspace_fix_context(
        {
            "candidate_workspace": str(tmp_path),
            "pr_snapshot": {"files": [{"filename": "app/orders.py"}]},
        }
    )

    assert "<workspace_file path=app/orders.py>" in context
    assert "<workspace_file path=tests/test_orders.py>" in context


@pytest.mark.asyncio
async def test_ready_workflow_uses_all_validation_nodes_and_persists() -> None:
    deps, repository, workspaces, events = dependencies(severity="low")
    result = await build_graph(deps).ainvoke(request())
    assert result["gate_decision"]["status"] == "READY"
    assert result["llm_usage"] == {"input_tokens": 22, "output_tokens": 14, "estimated_cost": 0.02}
    assert [event["node"] for event in result["events"]] == [
        "validate_request",
        "fetch_pull_request",
        "prepare_workspaces",
        "build_context",
        "scan_context",
        "run_original_validation",
        "analyze_change",
        "generate_candidate_fix",
        "validate_patch_shape",
        "run_baseline_regression",
        "run_candidate_validation",
        "evaluate_acceptance_criteria",
        "apply_quality_gate",
        "persist_report",
        "finalize",
    ]
    assert len(repository.persisted) == 1
    assert repository.persisted[0]["llm_usage"] == {
        "input_tokens": 22,
        "output_tokens": 14,
        "estimated_cost": 0.02,
    }
    assert workspaces.cleaned
    assert events.published[-1] == ("analysis-1", "finalize")


@pytest.mark.asyncio
async def test_no_finding_is_blocked_without_requesting_a_fix() -> None:
    deps, repository, workspaces, _ = dependencies(finding=False)
    result = await build_graph(deps).ainvoke(request())
    assert result["gate_decision"]["status"] == "READY"
    assert "candidate_fix" not in result
    assert len(repository.persisted) == 1
    assert workspaces.cleaned


@pytest.mark.asyncio
async def test_invalid_patch_is_inconclusive_and_skips_runner() -> None:
    deps, _, _, _ = dependencies(valid_patch=False)
    result = await build_graph(deps).ainvoke(request())
    assert result["gate_decision"]["status"] == "BLOCKED"
    assert any(error["code"] == "INVALID_PATCH" for error in result["errors"])


@pytest.mark.asyncio
async def test_secret_routing_skips_llm_and_candidate_validation() -> None:
    deps, _, _, _ = dependencies(secret=True)
    result = await build_graph(deps).ainvoke(request())
    assert result["secret_scan"]["detected"] is True
    assert "analysis_output" not in result
    assert result["candidate_validation"]["status"] == "NOT_PROPOSED"
    assert result["secret_evidence"] == [
        {"path": "app/orders.py", "start_line": 1, "end_line": 1, "kinds": ["api_key"]}
    ]
    assert result["acceptance_results"][0]["status"] == "NOT_EVALUATED"
    assert result["gate_decision"]["required_actions"][0] == (
        "Retirar el secreto potencial del cambio."
    )


@pytest.mark.asyncio
async def test_github_failure_is_inconclusive() -> None:
    deps, repository, _, _ = dependencies(unavailable=True)
    result = await build_graph(deps).ainvoke(request())
    assert result["gate_decision"]["status"] == "INCONCLUSIVE"
    assert any(error["code"] == "GITHUB_UNAVAILABLE" for error in result["errors"])
    assert len(repository.persisted) == 1


@pytest.mark.asyncio
async def test_workspace_failure_short_circuits_before_context_and_llm() -> None:
    deps, repository, workspaces, _ = dependencies(prepare_fails=True)
    result = await build_graph(deps).ainvoke(request())
    assert result["gate_decision"]["status"] == "INCONCLUSIVE"
    assert [event["node"] for event in result["events"]] == [
        "validate_request",
        "fetch_pull_request",
        "prepare_workspaces",
        "build_context",
        "scan_context",
        "apply_quality_gate",
        "persist_report",
        "finalize",
    ]
    assert "llm_usage" not in result
    assert len(repository.persisted) == 1
    assert workspaces.cleaned


@pytest.mark.asyncio
async def test_critical_finding_is_blocked() -> None:
    deps, _, _, _ = dependencies(severity="critical")
    result = await build_graph(deps).ainvoke(request())
    assert result["gate_decision"]["status"] == "BLOCKED"


@pytest.mark.asyncio
async def test_infrastructure_failure_is_inconclusive() -> None:
    deps, _, _, _ = dependencies(infrastructure=True)
    result = await build_graph(deps).ainvoke(request())
    assert result["gate_decision"]["status"] == "INCONCLUSIVE"


@pytest.mark.asyncio
async def test_invalid_request_is_inconclusive_without_calling_github() -> None:
    deps, _, _, _ = dependencies()
    result = await build_graph(deps).ainvoke(request("bad"))
    assert result["gate_decision"]["status"] == "INCONCLUSIVE"
    assert any(error["code"] == "INVALID_REQUEST" for error in result["errors"])
