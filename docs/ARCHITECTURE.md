# Architecture

## Purpose

DayZ server status monitor with online/queue tracking, historical statistics and activity graphs.

## Boundary

The public repository documents only the system boundary. The production edition contains private implementation details, persistence schemas, operational thresholds, adapters, credentials and deployment configuration.

## Components

- **Discord interaction layer** — buttons, forms, commands and/or event listeners.
- **Domain service layer** — validates state and executes the project-specific workflow.
- **Persistence/integration layer** — private production storage and external adapters.
- **Observability layer** — staff logs, error handling and operational feedback.

## Workflow

1. Query game server
2. Normalize status snapshot
3. Persist time-series data
4. Render public status summary
5. Generate historical report on demand

## Why the implementation is private

The production code is a commercial/private implementation. The portfolio edition intentionally prevents direct deployment while still documenting the engineering scope.
