# ADR-003: Read-only GitHub integration

## Context

The MVP analyzes external pull requests.

## Decision

Only read GitHub metadata, diffs, checks, and archives.

## Consequences

The product never creates commits, comments, approvals, merges, or deployments.

## Alternatives

Write operations were deferred beyond the challenge scope.
