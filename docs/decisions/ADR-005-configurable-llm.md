# ADR-005: Server-configured LLM profiles

## Context

The user must choose a model without receiving credentials.

## Decision

Use server-side profiles and an application gateway protocol. The initial profile uses `gpt-4.1-mini`.

## Consequences

Keys stay in environment variables and providers can be added behind adapters.

## Alternatives

Browser-provided API keys and direct domain dependencies on a provider were rejected.
