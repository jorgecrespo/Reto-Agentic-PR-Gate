from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class DecisionStatus(StrEnum):
    READY = "READY"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RuleOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AcceptanceStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class PullRequestRef:
    owner: str
    repository: str
    number: int
    url: str

    @classmethod
    def parse(cls, raw_url: str) -> PullRequestRef:
        parsed = urlparse(raw_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise ValueError("La URL debe pertenecer a https://github.com.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 4 or parts[2] != "pull" or not parts[3].isdigit():
            raise ValueError(
                "La URL debe tener el formato https://github.com/{owner}/{repo}/pull/{number}."
            )
        owner, repository, _, number = parts
        if any(value in {".", ".."} for value in (owner, repository)):
            raise ValueError("Owner y repositorio inválidos.")
        return cls(
            owner=owner,
            repository=repository,
            number=int(number),
            url=f"https://github.com/{owner}/{repository}/pull/{number}",
        )


@dataclass(frozen=True)
class GateFacts:
    head_sha_current: bool | None
    context_complete: bool | None
    tests_executed: bool | None
    tests_passed: bool | None
    critical_findings: int
    secrets_detected: bool | None
    required_criteria_evaluated: bool | None
    required_criteria_passed: bool | None
    patch_applied: bool | None
    regression_reproduced: bool | None
    regression_fixed: bool | None
    suite_passed: bool | None
    business_logic_changed: bool
    tests_changed: bool
    pr_is_draft: bool
    no_newer_pr: bool | None


@dataclass(frozen=True)
class GateRuleResult:
    rule_id: str
    outcome: RuleOutcome
    message: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateDecision:
    status: DecisionStatus
    target_stage: str
    policy_version: str
    summary: str
    rules: tuple[GateRuleResult, ...]

    @property
    def blocking_reasons(self) -> tuple[GateRuleResult, ...]:
        return tuple(rule for rule in self.rules if rule.outcome is RuleOutcome.FAIL)

    @property
    def not_evaluated_rules(self) -> tuple[GateRuleResult, ...]:
        return tuple(rule for rule in self.rules if rule.outcome is RuleOutcome.UNKNOWN)
