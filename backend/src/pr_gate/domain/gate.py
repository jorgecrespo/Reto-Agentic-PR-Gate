from __future__ import annotations

from .types import DecisionStatus, GateDecision, GateFacts, GateRuleResult, RuleOutcome


def _result(rule_id: str, value: bool | None, message: str) -> GateRuleResult:
    outcome = (
        RuleOutcome.UNKNOWN if value is None else RuleOutcome.PASS if value else RuleOutcome.FAIL
    )
    return GateRuleResult(rule_id=rule_id, outcome=outcome, message=message)


def evaluate_quality_gate(facts: GateFacts, policy_version: str = "1.0.0") -> GateDecision:
    """Evaluate only verified facts; unknown mandatory controls take precedence."""
    rules = (
        _result("GATE-001", facts.head_sha_current, "El análisis debe corresponder al SHA actual."),
        _result("GATE-002", facts.context_complete, "El contexto mínimo debe estar disponible."),
        _result("GATE-003", facts.tests_executed, "Los tests obligatorios deben ejecutarse."),
        _result("GATE-004", facts.tests_passed, "Los tests obligatorios deben aprobar."),
        _result("GATE-005", facts.critical_findings == 0, "No debe haber hallazgos críticos."),
        _result(
            "GATE-006",
            not facts.secrets_detected if facts.secrets_detected is not None else None,
            "No deben detectarse secretos.",
        ),
        _result(
            "GATE-007",
            facts.required_criteria_evaluated,
            "Los criterios obligatorios deben evaluarse.",
        ),
        _result(
            "GATE-008", facts.required_criteria_passed, "Los criterios obligatorios deben aprobar."
        ),
        _result("GATE-009", facts.patch_applied, "El parche debe aplicarse."),
        _result("GATE-010", facts.regression_reproduced, "El test debe reproducir el defecto."),
        _result("GATE-011", facts.regression_fixed, "El test debe aprobar con el parche."),
        _result("GATE-012", facts.suite_passed, "La suite candidate debe aprobar."),
        _result(
            "GATE-013",
            not facts.business_logic_changed or facts.tests_changed,
            "Cambios de lógica requieren tests.",
        ),
        _result("GATE-014", not facts.pr_is_draft, "El PR no debe ser draft."),
        _result("GATE-015", facts.no_newer_pr, "No debe existir una revisión más nueva del PR."),
    )
    mandatory_unknown = any(rule.outcome is RuleOutcome.UNKNOWN for rule in rules[:12])
    mandatory_fail = any(rule.outcome is RuleOutcome.FAIL for rule in rules[:12])
    conditional_fail = any(rule.outcome is RuleOutcome.FAIL for rule in rules[12:14])
    newer_revision_unknown = rules[14].outcome is RuleOutcome.UNKNOWN
    newer_revision_fail = rules[14].outcome is RuleOutcome.FAIL
    if mandatory_unknown or newer_revision_unknown or newer_revision_fail:
        status, summary = (
            DecisionStatus.INCONCLUSIVE,
            "Falta evidencia para evaluar controles obligatorios.",
        )
    elif mandatory_fail:
        status, summary = DecisionStatus.BLOCKED, "El cambio incumple controles bloqueantes."
    elif conditional_fail:
        status, summary = (
            DecisionStatus.CONDITIONAL,
            "El cambio requiere una condición explícita antes de QA.",
        )
    else:
        status, summary = DecisionStatus.READY, "El cambio puede avanzar a QA según la política."
    return GateDecision(
        status=status,
        target_stage="QA",
        policy_version=policy_version,
        summary=summary,
        rules=rules,
    )
