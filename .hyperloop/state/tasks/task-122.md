---
id: task-122
title: UI Sync Monitoring — Progress, History, and Manual Trigger
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-121]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add sync monitoring — progress, history, logs, and manual trigger"
pr_description: |
  ## What and Why

  Allows users to observe and control the sync lifecycle for each data source.
  Without this, users have no visibility into whether ingestion succeeded, is
  running, or failed — a critical gap for a data platform.

  This task depends on task-121 (data source creation) so that the Data Source
  detail page exists to host the sync monitoring UI.

  **⚠️ Backend dependency**: This task requires the Ingestion bounded context
  (`src/api/ingestion/`) which is **not yet implemented**. The UI can be built
  against mock/stub API responses and finalized once the backend is available.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Sync Monitoring** from
  `specs/ui/experience.spec.md`.

  Specifically:
  - **Active sync progress**: phase indicator (ingesting → extracting → applying)
    with a progress bar or spinner; auto-refreshes via polling or SSE.
  - **Sync history**: table showing completed sync runs with status (completed/failed),
    start timestamp, end timestamp, and duration; sorted newest-first.
  - **Sync logs**: expandable log viewer for a selected run; shows detailed log
    lines for that run (in-progress or completed).
  - **Manual sync trigger**: "Sync Now" button visible only to users with `manage`
    permission; triggers `POST /api/ingestion/data-sources/{id}/sync` and immediately
    shows the new run's progress.

  ## Design Decisions

  - Progress uses a `usePolling` composable (polling interval: 3 s) rather than
    WebSockets to avoid requiring server-side streaming infrastructure during initial
    development. When SSE/WebSocket support lands, the composable can be swapped.
  - The phase indicator is a stepper component (Ingesting → Extracting → Applying)
    with the active phase highlighted.
  - Sync logs are fetched lazily when the user expands a run row (not pre-loaded
    for all runs).
  - "Sync Now" is guarded by the same `manage` permission check as member management.

  ## Backend APIs Required (pending Ingestion implementation)

  - `GET /api/ingestion/data-sources/{id}/syncs` — list sync runs
  - `GET /api/ingestion/data-sources/{id}/syncs/{run_id}` — run detail + status
  - `GET /api/ingestion/data-sources/{id}/syncs/{run_id}/logs` — run logs
  - `POST /api/ingestion/data-sources/{id}/sync` — trigger manual sync

  ## Files / Areas Affected

  - `src/ui/pages/data/DataSourceDetailPage.vue` — add sync monitoring section
  - `src/ui/components/sync/SyncProgressStepper.vue`
  - `src/ui/components/sync/SyncHistoryTable.vue`
  - `src/ui/components/sync/SyncLogViewer.vue`
  - `src/ui/composables/useSyncRuns.ts`
  - `src/ui/composables/usePolling.ts`

  ## How to Verify

  1. Data source with an in-progress sync shows phase stepper with active phase
  2. Completed/failed runs appear in the history table with correct status and duration
  3. Expanding a run row fetches and displays its logs
  4. "Sync Now" button triggers a new run and the stepper immediately reflects it
  5. Users without `manage` permission do not see the "Sync Now" button

  ## Caveats

  Until the Ingestion backend is implemented, this task should build against a
  mock service layer (`src/ui/mocks/syncApi.ts`) using realistic fixture data so
  the UI can be fully developed and tested in isolation. The mock will be replaced
  with real API calls once the backend lands.
---
