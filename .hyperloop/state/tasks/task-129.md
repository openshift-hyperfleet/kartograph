---
id: task-129
title: "UI: Sync Monitoring (shell — requires Ingestion implementation)"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119, task-120]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add sync monitoring UI with status, history, logs, and manual trigger"
pr_description: |
  ## What & Why

  Implements the sync monitoring section of the data source detail page. When a data
  source has an active or historical sync, users can see the current phase, a history
  table, detailed logs per sync run, and can trigger a manual sync. These views are
  also surfaced as status badges on the Knowledge Graphs / Data Sources list pages.

  Like the Ontology Design task (task-128), the backend Ingestion context is not yet
  implemented. This task builds the complete UI shell using stubs and a feature flag,
  ready to connect to real Ingestion endpoints when that context ships.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Sync Monitoring** — all four scenarios: active sync progress
    (ingesting / extracting / applying phases with progress indicator), sync history
    (completed/failed, timestamps, duration), sync logs (per run, on demand),
    manual sync trigger

  ## Data Source Detail Page — Sync Section

  The sync monitoring UI lives within the data source detail page at
  `/data/data-sources/{id}`. The sync section appears below the connection configuration.

  ### Active Sync Progress

  When a sync is in progress (`GET /ingestion/data-sources/{id}/sync/current`):
  - Phase indicator with three steps: **Ingesting** → **Extracting** → **Applying**
  - The active phase is highlighted; completed phases show a check mark
  - A phase-appropriate progress sub-text:
    - Ingesting: "Fetching changes from {source name}…"
    - Extracting: "AI agent is analyzing content…"
    - Applying: "Writing {n} graph mutations…"
  - Auto-refreshes every 5 seconds (polling) while a sync is active

  ### Sync History Table

  Always shown below the active sync (or alone when no sync is running):
  `GET /ingestion/data-sources/{id}/sync/history`

  | Column | Value |
  |---|---|
  | Status | `completed` (green check), `failed` (red X) badge |
  | Started | relative timestamp (e.g., "2 hours ago") with absolute on hover |
  | Duration | "3m 42s" |
  | Actions | "View Logs" button |

  Pagination: show last 10 sync runs; "Load more" button for earlier runs.

  ### Sync Logs

  Clicking "View Logs" opens a Sheet panel from the right:
  - Structured log lines for the selected sync run
  - `GET /ingestion/data-sources/{id}/sync/{sync_id}/logs`
  - Log lines displayed with timestamp + level (INFO / WARNING / ERROR) + message
  - Auto-scrolls to the bottom; "Scroll to top" button
  - For in-progress syncs: auto-appends new log lines every 3 seconds

  ### Manual Sync Trigger

  - "Sync Now" button in the data source detail header (only rendered when user has
    `manage` permission on the data source)
  - `POST /ingestion/data-sources/{id}/sync/trigger`
  - On success: toast "Sync started"; the active sync indicator appears within 5s

  ## Sync Status Badges (List Pages)

  On `KnowledgeGraphs.vue` (task-120) and `DataSources` list, each item that has
  an active sync shows a small animated badge: "Syncing…" with a spinner. Clicking
  the badge navigates to the data source detail page's sync section.

  ## Backend API Integration

  | Action | Endpoint (stub until Ingestion ships) |
  |---|---|
  | Get current sync | `GET /ingestion/data-sources/{id}/sync/current` |
  | Get sync history | `GET /ingestion/data-sources/{id}/sync/history` |
  | Get sync logs | `GET /ingestion/data-sources/{id}/sync/{sync_id}/logs` |
  | Trigger sync | `POST /ingestion/data-sources/{id}/sync/trigger` |

  > **Note:** The Ingestion bounded context is not yet implemented. This PR uses stub
  > fixtures and a `VITE_ENABLE_INGESTION=false` feature flag. The stub returns a
  > static sync history and a "completed" status for the demo. When Ingestion ships,
  > remove the flag and wire the real endpoints.

  ## Files / Areas Affected

  - `src/ui/src/components/sync/ActiveSyncProgress.vue`
  - `src/ui/src/components/sync/SyncHistoryTable.vue`
  - `src/ui/src/components/sync/SyncLogsSheet.vue`
  - `src/ui/src/components/sync/SyncNowButton.vue`
  - `src/ui/src/components/sync/SyncStatusBadge.vue` — small badge for list pages
  - `src/ui/src/api/ingestion.ts` — extend with sync endpoints (stub mode)
  - `src/ui/src/composables/useSyncPolling.ts` — 5s polling composable

  ## How to Verify

  With stubs enabled (`VITE_ENABLE_INGESTION=false`):
  1. Open a data source detail page → sync history table shows stub completed/failed rows
  2. Click "View Logs" → sheet opens with timestamp-level-message log lines
  3. Click "Sync Now" → toast "Sync started"; after 2s (stub delay) the active sync
     progress indicator appears with "Ingesting" phase highlighted
  4. The active sync badge appears on the KG list page for the related KG
  5. User without `manage` permission: "Sync Now" button is not rendered

  ## Caveats / Follow-up

  - Real-time log streaming (WebSocket or SSE) can replace polling in a future
    enhancement once the Ingestion backend supports it; the polling composable is
    designed to be replaced with minimal changes
  - Ingestion bounded context implementation is a separate work stream and is a hard
    dependency for full functionality
---
