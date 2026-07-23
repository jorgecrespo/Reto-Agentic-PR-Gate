from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from pr_gate.domain.gate import evaluate_quality_gate
from pr_gate.domain.types import GateFacts, PullRequestRef
from pr_gate.infrastructure.github import GitHubClient, GitHubError


class AnalysisState(TypedDict, total=False):
    pull_request_url: str
    draft: bool
    head_sha: str
    context_complete: bool
    tests_executed: bool | None
    tests_passed: bool | None
    critical_findings: int
    secrets_detected: bool | None
    criteria_evaluated: bool | None
    criteria_passed: bool | None
    patch_applied: bool | None
    regression_reproduced: bool | None
    regression_fixed: bool | None
    suite_passed: bool | None
    business_logic_changed: bool
    tests_changed: bool
    error: str
    decision: str
    no_newer_pr: bool | None


async def validate_request(state: AnalysisState) -> AnalysisState:
    try:
        PullRequestRef.parse(state["pull_request_url"])
    except ValueError as error:
        return {"error": str(error), "context_complete": False}
    return {}


async def fetch_pull_request(state: AnalysisState) -> AnalysisState:
    try:
        snapshot = await GitHubClient().fetch_snapshot(
            PullRequestRef.parse(state["pull_request_url"])
        )
    except (ValueError, GitHubError) as error:
        return {"error": str(error), "context_complete": False}
    return {"draft": snapshot.draft, "head_sha": snapshot.head_sha, "context_complete": True}


def apply_quality_gate(state: AnalysisState) -> AnalysisState:
    decision = evaluate_quality_gate(
        GateFacts(
            head_sha_current=not bool(state.get("error")),
            context_complete=state.get("context_complete"),
            tests_executed=state.get("tests_executed"),
            tests_passed=state.get("tests_passed"),
            critical_findings=state.get("critical_findings", 0),
            secrets_detected=state.get("secrets_detected"),
            required_criteria_evaluated=state.get("criteria_evaluated"),
            required_criteria_passed=state.get("criteria_passed"),
            patch_applied=state.get("patch_applied"),
            regression_reproduced=state.get("regression_reproduced"),
            regression_fixed=state.get("regression_fixed"),
            suite_passed=state.get("suite_passed"),
            business_logic_changed=state.get("business_logic_changed", False),
            tests_changed=state.get("tests_changed", False),
            pr_is_draft=state.get("draft", False),
            no_newer_pr=state.get("no_newer_pr"),
        )
    )
    return {"decision": decision.status}


def route_after_validation(state: AnalysisState) -> str:
    return "apply_quality_gate" if state.get("error") else "fetch_pull_request"


def build_graph() -> Any:
    graph = StateGraph(AnalysisState)
    graph.add_node("validate_request", validate_request)
    graph.add_node("fetch_pull_request", fetch_pull_request)
    graph.add_node("apply_quality_gate", apply_quality_gate)
    graph.add_edge(START, "validate_request")
    graph.add_conditional_edges("validate_request", route_after_validation)
    graph.add_edge("fetch_pull_request", "apply_quality_gate")
    graph.add_edge("apply_quality_gate", END)
    return graph.compile()
