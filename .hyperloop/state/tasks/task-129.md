---
id: task-129
title: 'UI: Sync Monitoring (shell — requires Ingestion implementation)'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps:
- task-118
- task-119
- task-120
round: 0
branch: hyperloop/task-129
pr: https://github.com/openshift-hyperfleet/kartograph/pull/602
pr_title: 'feat(ui): add sync monitoring UI with status, history, logs, and manual
  trigger'
pr_description: "## What & Why\n\nImplements the sync monitoring section of the data\
  \ source detail page. When a data\nsource has an active or historical sync, users\
  \ can see the current phase, a history\ntable, detailed logs per sync run, and can\
  \ trigger a manual sync. These views are\nalso surfaced as status badges on the\
  \ Knowledge Graphs / Data Sources list pages.\n\nLike the Ontology Design task (task-128),\
  \ the backend Ingestion context is not yet\nimplemented. This task builds the complete\
  \ UI shell using stubs and a feature flag,\nready to connect to real Ingestion endpoints\
  \ when that context ships.\n\n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n\
  - **Requirement: Sync Monitoring** — all four scenarios: active sync progress\n\
  \  (ingesting / extracting / applying phases with progress indicator), sync history\n\
  \  (completed/failed, timestamps, duration), sync logs (per run, on demand),\n \
  \ manual sync trigger\n\n## Data Source Detail Page — Sync Section\n\nThe sync monitoring\
  \ UI lives within the data source detail page at\n`/data/data-sources/{id}`. The\
  \ sync section appears below the connection configuration.\n\n### Active Sync Progress\n\
  \nWhen a sync is in progress (`GET /ingestion/data-sources/{id}/sync/current`):\n\
  - Phase indicator with three steps: **Ingesting** → **Extracting** → **Applying**\n\
  - The active phase is highlighted; completed phases show a check mark\n- A phase-appropriate\
  \ progress sub-text:\n  - Ingesting: \"Fetching changes from {source name}…\"\n\
  \  - Extracting: \"AI agent is analyzing content…\"\n  - Applying: \"Writing {n}\
  \ graph mutations…\"\n- Auto-refreshes every 5 seconds (polling) while a sync is\
  \ active\n\n### Sync History Table\n\nAlways shown below the active sync (or alone\
  \ when no sync is running):\n`GET /ingestion/data-sources/{id}/sync/history`\n\n\
  | Column | Value |\n|---|---|\n| Status | `completed` (green check), `failed` (red\
  \ X) badge |\n| Started | relative timestamp (e.g., \"2 hours ago\") with absolute\
  \ on hover |\n| Duration | \"3m 42s\" |\n| Actions | \"View Logs\" button |\n\n\
  Pagination: show last 10 sync runs; \"Load more\" button for earlier runs.\n\n###\
  \ Sync Logs\n\nClicking \"View Logs\" opens a Sheet panel from the right:\n- Structured\
  \ log lines for the selected sync run\n- `GET /ingestion/data-sources/{id}/sync/{sync_id}/logs`\n\
  - Log lines displayed with timestamp + level (INFO / WARNING / ERROR) + message\n\
  - Auto-scrolls to the bottom; \"Scroll to top\" button\n- For in-progress syncs:\
  \ auto-appends new log lines every 3 seconds\n\n### Manual Sync Trigger\n\n- \"\
  Sync Now\" button in the data source detail header (only rendered when user has\n\
  \  `manage` permission on the data source)\n- `POST /ingestion/data-sources/{id}/sync/trigger`\n\
  - On success: toast \"Sync started\"; the active sync indicator appears within 5s\n\
  \n## Sync Status Badges (List Pages)\n\nOn `KnowledgeGraphs.vue` (task-120) and\
  \ `DataSources` list, each item that has\nan active sync shows a small animated\
  \ badge: \"Syncing…\" with a spinner. Clicking\nthe badge navigates to the data\
  \ source detail page's sync section.\n\n## Backend API Integration\n\n| Action |\
  \ Endpoint (stub until Ingestion ships) |\n|---|---|\n| Get current sync | `GET\
  \ /ingestion/data-sources/{id}/sync/current` |\n| Get sync history | `GET /ingestion/data-sources/{id}/sync/history`\
  \ |\n| Get sync logs | `GET /ingestion/data-sources/{id}/sync/{sync_id}/logs` |\n\
  | Trigger sync | `POST /ingestion/data-sources/{id}/sync/trigger` |\n\n> **Note:**\
  \ The Ingestion bounded context is not yet implemented. This PR uses stub\n> fixtures\
  \ and a `VITE_ENABLE_INGESTION=false` feature flag. The stub returns a\n> static\
  \ sync history and a \"completed\" status for the demo. When Ingestion ships,\n\
  > remove the flag and wire the real endpoints.\n\n## Files / Areas Affected\n\n\
  - `src/ui/src/components/sync/ActiveSyncProgress.vue`\n- `src/ui/src/components/sync/SyncHistoryTable.vue`\n\
  - `src/ui/src/components/sync/SyncLogsSheet.vue`\n- `src/ui/src/components/sync/SyncNowButton.vue`\n\
  - `src/ui/src/components/sync/SyncStatusBadge.vue` — small badge for list pages\n\
  - `src/ui/src/api/ingestion.ts` — extend with sync endpoints (stub mode)\n- `src/ui/src/composables/useSyncPolling.ts`\
  \ — 5s polling composable\n\n## How to Verify\n\nWith stubs enabled (`VITE_ENABLE_INGESTION=false`):\n\
  1. Open a data source detail page → sync history table shows stub completed/failed\
  \ rows\n2. Click \"View Logs\" → sheet opens with timestamp-level-message log lines\n\
  3. Click \"Sync Now\" → toast \"Sync started\"; after 2s (stub delay) the active\
  \ sync\n   progress indicator appears with \"Ingesting\" phase highlighted\n4. The\
  \ active sync badge appears on the KG list page for the related KG\n5. User without\
  \ `manage` permission: \"Sync Now\" button is not rendered\n\n## Caveats / Follow-up\n\
  \n- Real-time log streaming (WebSocket or SSE) can replace polling in a future\n\
  \  enhancement once the Ingestion backend supports it; the polling composable is\n\
  \  designed to be replaced with minimal changes\n- Ingestion bounded context implementation\
  \ is a separate work stream and is a hard\n  dependency for full functionality"
---
