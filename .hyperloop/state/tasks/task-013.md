---
id: task-013
title: Implement Ingestion sync lifecycle state machine and event handlers
spec_ref: specs/ingestion/sync-lifecycle.spec.md
status: not-started
phase: null
deps: [task-012]
round: 0
branch: null
pr: null
---

## What

Implement the event-driven sync lifecycle state machine that orchestrates the ingestion pipeline and advances sync run status through defined states.

## Spec requirements (all scenarios unimplemented)

**Sync Orchestration:**
- `IngestionService.run_sync(data_source_id)`:
  - Publish `SyncStarted` event → status = `ingesting`
  - Run adapter → extract raw data
  - Run JobPackager → assemble JobPackage
  - Publish `JobPackageProduced` event
  - On adapter failure → publish `IngestionFailed` event → status = `failed`

**Lifecycle State Machine (event → status transitions):**
- `SyncStarted` → `ingesting`
- `JobPackageProduced` → `ai_extracting`
- `IngestionFailed` → `failed`
- `MutationLogProduced` → `applying`
- `ExtractionFailed` → `failed`
- `MutationsApplied` → `completed` (updates `last_sync_at`)
- `MutationApplicationFailed` → `failed`

Terminal states: `completed` and `failed` — no further transitions.

**Event-Driven Side Effects:**
- `JobPackageProduced` handler: create extraction job record, signal Extraction context.
- `MutationLogProduced` handler: create mutation job record, signal Graph context to apply mutations.
- All lifecycle events: update sync run status in DB.

**Sync Initiation:**
- Manual trigger: via `POST /data-sources/{id}/sync` (task-009) → publish `SyncStarted`, create sync run (status=`pending`).
- Scheduled trigger: CRON/INTERVAL schedules fire as if manually triggered.

**Staleness-Based Node Lifecycle:**
- Nodes with `last_synced_at` < data source's `last_sync_at` are considered stale.
- Downstream processes may remove/flag stale nodes.

## Location

New handlers in `ingestion/infrastructure/outbox/` or `infrastructure/outbox/event_sources/` registered with `CompositeEventHandler`.

Domain events in `ingestion/domain/events/`.

Lifecycle handler in `ingestion/application/services/sync_lifecycle_service.py`.

## Notes

- Depends on task-012 (IngestionService and adapter must exist first).
- The Extraction context side effects (`JobPackageProduced` → signal Extraction) are stubs for now — the Extraction context is pending the AIHCM-174 spike.
- Scheduled trigger implementation may use a simple cron job runner or background task scheduler.
