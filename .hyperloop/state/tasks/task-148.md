---
id: task-148
title: "UI Sync Monitoring — progress, history, logs, manual trigger"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-147]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add sync monitoring with progress indicators, history, and logs"
pr_description: |
  ## What and Why

  After connecting a data source, users need visibility into what's happening:
  is the sync running, what phase is it in, has it ever completed successfully,
  and what went wrong when it fails? This task builds the sync monitoring panels
  that surface that information, integrated into the data source detail view built
  in task-147.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Sync Monitoring — Scenario: Active sync progress**
    "current sync status (ingesting, extracting, applying); progress indicator
    appropriate to the current phase"

  - **Requirement: Sync Monitoring — Scenario: Sync history**
    "history of sync runs with status (completed, failed), timestamps, and duration"

  - **Requirement: Sync Monitoring — Scenario: Sync logs**
    "detailed logs for a sync run (in progress or completed)"

  - **Requirement: Sync Monitoring — Scenario: Manual sync trigger**
    "user with manage permission can trigger a sync; new sync run begins and
    progress is shown"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    Sync status: `GET /data-sources/{id}/sync-runs` (list, latest first)
    Sync logs: `GET /data-sources/{id}/sync-runs/{run_id}/logs`
    Trigger sync: `POST /data-sources/{id}/sync/trigger`

  ## Key Design Decisions

  - **Data source detail view** (`/data/data-sources/{id}`): This page was stubbed
    in task-146 as a tab on the KG detail. This task fills the "Sync Status" tab
    with real content.
  - **Active sync panel**: Shown only when the latest sync run has status
    `in_progress`. Displays phase badge (`ingesting` / `extracting` / `applying`)
    and an indeterminate progress bar. Polls `GET /data-sources/{id}/sync-runs`
    every 10 seconds while active.
  - **Sync history table**: All completed and failed runs in a table with columns:
    Status (badge), Started At, Duration, Entities Processed. Clicking a row opens
    the log panel.
  - **Log panel**: A `<LogViewer>` component renders the log entries as a monospace
    scrollable list. Loaded on demand from `GET /sync-runs/{run_id}/logs`. Auto-scrolls
    to bottom for active runs; stays at position for completed runs.
  - **Manual trigger**: "Trigger Sync" button visible to users with `manage` permission.
    Calls `POST /data-sources/{id}/sync/trigger`. On success, the active sync panel
    appears and polling begins. Confirm before triggering if a sync is already running
    (AlertDialog: "A sync is already in progress. Start a new one anyway?").

  ## What Files Are Affected

  - **New**: `src/ui/components/sync/SyncStatusPanel.vue`
  - **New**: `src/ui/components/sync/SyncHistoryTable.vue`
  - **New**: `src/ui/components/sync/LogViewer.vue`
  - **New**: `src/ui/components/sync/TriggerSyncButton.vue`
  - **New**: `src/ui/composables/useSyncMonitoring.ts`
  - **Modified**: `src/ui/pages/data/data-sources/[id].vue` (fill Sync Status tab)
  - **New**: `src/ui/tests/unit/SyncStatusPanel.test.ts`
  - **New**: `src/ui/tests/unit/useSyncMonitoring.test.ts`

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/ui && npm run dev
  # 1. Navigate to data source detail (/data/data-sources/{id})
  # 2. Trigger a sync — active sync panel appears with phase badge
  # 3. Wait for completion — sync appears in history table with duration
  # 4. Click a history row — log viewer opens with log entries
  # 5. Trigger another sync — confirmation dialog if one is already running
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- sync
  # SyncStatusPanel: renders phase correctly; hides when no active run
  # SyncHistoryTable: sorts by timestamp desc; opens log viewer on row click
  # useSyncMonitoring: polls when active; stops polling on completion/error
  ```

  ## Caveats

  - Polling is intentional (not WebSockets) to keep infrastructure simple.
    Poll interval is 10 seconds for active runs; stop polling when status
    changes to `completed` or `failed`.
  - The `GET /sync-runs/{run_id}/logs` endpoint must support pagination if there
    are many log lines. For now, fetch all logs at once; add pagination if the
    response size becomes a concern.
  - The "ingesting / extracting / applying" phase values must match the backend's
    status enum. Verify against `management/presentation/data_sources/models.py`.
---
