---
id: task-157
title: 'UI: Sync Monitoring (progress, history, logs, manual trigger)'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-151
- task-153
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add sync monitoring UI for data source sync lifecycle'
pr_description: "## What and Why\n\nOnce a data source is configured, users need visibility\
  \ into the sync\nlifecycle: is it running, did it succeed, how long did it take,\
  \ and what\nhappened in the logs? This task implements the Sync Monitoring views\
  \ on the\nData Source detail page.\n\n**Dependency note**: Sync Monitoring requires\
  \ the Ingestion bounded context\nto be implemented on the backend (sync lifecycle,\
  \ status API, log streaming).\nThe Ingestion context is marked \"NOT YET IMPLEMENTED\"\
  \ in the architecture.\nThis task builds the UI using stub API responses and a polling\
  \ mechanism so\nthe presentation layer is ready to connect to the real API when\
  \ Ingestion\nis available. A feature flag (`VITE_INGESTION_ENABLED`) gates stub\
  \ vs. real.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\n\
  \n### Requirement: Sync Monitoring — Active Sync Progress\n- Data Source detail\
  \ page shows a **Sync Status** section\n- When a sync is running, displays the current\
  \ phase badge:\n  **Ingesting** | **Extracting** | **Applying**\n- A progress indicator\
  \ (indeterminate spinner for phases without a\n  percentage, determinate progress\
  \ bar when the backend supplies a ratio)\n  appropriate to the current phase\n-\
  \ Phase and status are polled every 5 s while a sync is in progress\n\n### Requirement:\
  \ Sync Monitoring — Sync History\n- A **Sync History** table below the active-sync\
  \ section lists completed\n  sync runs with: status (completed ✓ / failed ✗), start\
  \ timestamp,\n  duration, and a \"View Logs\" link\n- Calls `GET /ingestion/data-sources/{id}/syncs`\
  \ (stubbed until Ingestion\n  is live)\n- Table is paginated or shows the last 10\
  \ runs with a \"Load more\" button\n\n### Requirement: Sync Monitoring — Sync Logs\n\
  - Clicking \"View Logs\" on any sync run opens a log viewer panel (bottom\n  sheet\
  \ or side panel)\n- Logs are streamed or fetched from `GET /ingestion/syncs/{run_id}/logs`\n\
  - Each log line shows timestamp, level (INFO/WARN/ERROR), and message\n- In-progress\
  \ runs update the log view in real-time (polling or SSE)\n\n### Requirement: Sync\
  \ Monitoring — Manual Sync Trigger\n- A **Sync Now** button is shown on the Data\
  \ Source detail page for users\n  with `manage` permission on the knowledge graph\n\
  - Clicking calls `POST /ingestion/data-sources/{id}/sync`\n- On success, the active-sync\
  \ progress section appears and begins polling\n- The button is disabled (with a\
  \ tooltip \"Sync already running\") while\n  a sync is in progress\n\n## Key Design\
  \ Decisions\n\n- **Polling**: a composable `useSyncStatus(dataSourceId)` polls the\
  \ status\n  endpoint every 5 s using `setInterval`; polling is paused when the tab\n\
  \  is hidden (`visibilitychange` event) and resumed on focus.\n- **Stub mode**:\
  \ `VITE_INGESTION_ENABLED=false` returns hard-coded fixture\n  data (one completed\
  \ run, one failed run) so the UI can be validated without\n  a running Ingestion\
  \ service.\n- **Log viewer**: uses a virtual list (e.g., `vue-virtual-scroller`)\
  \ to\n  handle large log outputs efficiently.\n- The \"Sync Now\" button is hidden\
  \ (not just disabled) for users without\n  `manage` permission, checked via the\
  \ `usePermissions` composable that\n  queries SpiceDB through the Management API.\n\
  \n## Files / Areas Affected\n\n- `src/ui/src/pages/data/DataSourceDetailPage.vue`\
  \ (extended from task-153\n  stub)\n- `src/ui/src/components/SyncStatusBadge.vue`\n\
  - `src/ui/src/components/SyncProgressIndicator.vue`\n- `src/ui/src/components/SyncHistoryTable.vue`\n\
  - `src/ui/src/components/SyncLogViewer.vue`\n- `src/ui/src/composables/useSyncStatus.ts`\n\
  - `src/ui/src/stores/syncRuns.ts`\n- `src/ui/src/lib/api/ingestion.ts` (stubs +\
  \ real implementation behind\n  feature flag)\n\n## How to Verify\n\nWith `VITE_INGESTION_ENABLED=false`\
  \ (stub mode):\n\n1. Navigate to a data source detail page\n2. \"Sync Now\" button\
  \ visible (for admin user)\n3. Click → active sync progress section appears; phase\
  \ cycles through\n   Ingesting → Extracting → Applying (simulated with setTimeout\
  \ in stubs)\n4. After simulated completion: Sync History table shows the run with\n\
  \   \"completed\" status, duration, and a \"View Logs\" link\n5. Click \"View Logs\"\
  \ → log viewer panel slides open with timestamped\n   log lines\n6. Verify \"Sync\
  \ Now\" is disabled while the simulated sync is running\n\nWith `VITE_INGESTION_ENABLED=true`\
  \ (requires Ingestion API running):\n\n- All of the above but calls real Ingestion\
  \ API endpoints; real log lines\n  stream from the backend.\n\n## Caveats\n\n- This\
  \ task is blocked on the Ingestion context implementation for real\n  end-to-end\
  \ verification. Stub mode allows the UI to be merged and demoed\n  independently.\n\
  - The Ingestion API contract (endpoint paths, response shapes, SSE vs.\n  polling\
  \ for logs) must be agreed before removing the stubs. The\n  `ingestion.ts` client\
  \ types should mirror the final Ingestion spec.\n- If Ingestion uses Server-Sent\
  \ Events for log streaming, the log viewer\n  composable needs to switch from polling\
  \ to an `EventSource`; the stub\n  simulates this with `setInterval`."
---
