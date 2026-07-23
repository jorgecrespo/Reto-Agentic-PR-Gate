# ADR-001: Directed LangGraph workflow

## Context

The review flow needs named stages, observable progress and deterministic routing.

## Decision

Use a directed LangGraph state graph with typed state and small nodes.

## Consequences

Nodes can be tested independently. This intentionally excludes autonomous navigation and tool selection.

## Alternatives

An autonomous agent was rejected because it would weaken reproducibility and command control.
