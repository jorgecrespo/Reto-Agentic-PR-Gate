# ADR-004: Docker sandbox runner

## Context

Pull request code is untrusted.

## Decision

Run only administratively configured commands in ephemeral Docker containers with no network, non-root user, and resource limits.

## Consequences

A missing Docker daemon yields an explicit infrastructure error and an inconclusive decision.

## Alternatives

Local subprocess execution was rejected as unsafe by default.
