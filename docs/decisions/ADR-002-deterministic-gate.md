# ADR-002: Deterministic quality gate

## Context

The final PR to QA decision requires verifiable evidence.

## Decision

Evaluate structured facts in a pure policy engine. The LLM may propose evidence but cannot decide the status.

## Consequences

The gate is unit-testable without models, databases, or network access.

## Alternatives

LLM-only approval was rejected because it cannot prove validations were run.
