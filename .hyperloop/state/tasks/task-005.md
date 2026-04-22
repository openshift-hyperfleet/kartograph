---
id: task-005
title: "Ingestion — Sync lifecycle state machine"
spec_ref: specs/ingestion/sync-lifecycle.spec.md
status: not-started
phase: null
deps: [task-002, task-004]
round: 0
branch: null
pr: null
---

## Summary

This task implements the event-driven sync lifecycle state machine for the Ingestion context. It handles domain events flowing through the outbox and transitions sync run status through its defined states. It also implements scheduled sync triggering.

Depends on `task-002` (data source trigger endpoint that publishes `SyncStarted`) and `task-004` (adapters that the ingestion service orchestrates).

## Scope

### State Machine

| Event | Status Transition |
|-------|------------------|
| `SyncStarted` | → `ingesting` |
| `JobPackageProduced` | → `ai_extracting` |
| `IngestionFailed` | → `failed` |
| `MutationLogProduced` | → `applying` |
| `ExtractionFailed` | → `failed` |
| `MutationsApplied` | → `completed` (update `last_sync_at`) |
| `MutationApplicationFailed` | → `failed` |

Terminal states (`completed`, `failed`): no further transitions.

### Outbox Event Handlers

Register handlers in the outbox's composite handler registry. Each handler must be idempotent.

**`SyncStartedHandler`**:
- Update sync run status → `ingesting`
- Trigger `IngestionService.run()` asynchronously (via background task or queue)

**`JobPackageProducedHandler`**:
- Update sync run status → `ai_extracting`
- Create extraction job record
- Signal Extraction context to process the JobPackage (publish event or direct call; stub if Extraction not yet implemented)

**`IngestionFailedHandler`**:
- Update sync run status → `failed` with error message

**`MutationLogProducedHandler`**:
- Update sync run status → `applying`
- Signal Graph context to apply the mutation log

**`MutationsAppliedHandler`**:
- Update sync run status → `completed`
- Update `last_sync_at` on the data source

**`ExtractionFailedHandler` / `MutationApplicationFailedHandler`**:
- Update sync run status → `failed` with error message

### Domain Events

Define in `ingestion/domain/events.py` (or extend existing event modules):
- `SyncStarted(data_source_id, sync_run_id, sync_mode)`
- `JobPackageProduced(data_source_id, sync_run_id, package_path)`
- `IngestionFailed(data_source_id, sync_run_id, error)`
- `MutationLogProduced(sync_run_id, mutation_log_path)`
- `MutationsApplied(sync_run_id)`
- `MutationApplicationFailed(sync_run_id, error)`
- `ExtractionFailed(sync_run_id, error)`

### Staleness Detection

Add `last_synced_at` property awareness: nodes with `last_synced_at` older than data source's `last_sync_at` are considered stale. Document the staleness contract — actual node removal is downstream (Graph context or Extraction). No API endpoint needed here.

### Scheduled Sync Triggering

Implement a scheduler component that:
- Reads active data sources with `CRON` or `INTERVAL` schedules
- Fires sync triggers at the appropriate time (publish `SyncStarted` event)
- Runs as a background task within the application lifecycle (started in `lifespan`)

The scheduler MUST be idempotent in multi-instance deployments (use advisory locks or a `next_scheduled_at` column to prevent double-triggering).

### Wiring

Register all event handlers in `infrastructure/outbox/` (following the pattern in existing outbox handler modules). Start the scheduler in `main.py` lifespan.

## TDD Notes

Write unit tests first under `tests/unit/ingestion/test_sync_lifecycle.py`:
- State machine transitions: given event, assert correct status
- Terminal state protection: assert no transition from `completed` or `failed`
- Handler idempotency: call handler twice, assert single status update

Write integration tests under `tests/integration/ingestion/test_sync_lifecycle.py`:
- Full sync flow: trigger → SyncStarted → IngestionService runs → JobPackageProduced → status transitions
- Failure path: adapter failure → IngestionFailed → status = failed
