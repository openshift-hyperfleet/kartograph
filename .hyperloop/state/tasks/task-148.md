---
id: task-148
title: UI Sync Monitoring — progress, history, logs, manual trigger
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps:
- task-147
round: 0
branch: hyperloop/task-148
pr: null
pr_title: 'feat(ui): add sync monitoring with progress indicators, history, and logs'
pr_description: "## What and Why\n\nAfter connecting a data source, users need visibility\
  \ into what's happening:\nis the sync running, what phase is it in, has it ever\
  \ completed successfully,\nand what went wrong when it fails? This task builds the\
  \ sync monitoring panels\nthat surface that information, integrated into the data\
  \ source detail view built\nin task-147.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Sync Monitoring — Scenario: Active sync progress**\n  \"current\
  \ sync status (ingesting, extracting, applying); progress indicator\n  appropriate\
  \ to the current phase\"\n\n- **Requirement: Sync Monitoring — Scenario: Sync history**\n\
  \  \"history of sync runs with status (completed, failed), timestamps, and duration\"\
  \n\n- **Requirement: Sync Monitoring — Scenario: Sync logs**\n  \"detailed logs\
  \ for a sync run (in progress or completed)\"\n\n- **Requirement: Sync Monitoring\
  \ — Scenario: Manual sync trigger**\n  \"user with manage permission can trigger\
  \ a sync; new sync run begins and\n  progress is shown\"\n\n- **Requirement: Backend\
  \ API Alignment — Scenario: Resource operations succeed end-to-end**\n  Sync status:\
  \ `GET /data-sources/{id}/sync-runs` (list, latest first)\n  Sync logs: `GET /data-sources/{id}/sync-runs/{run_id}/logs`\n\
  \  Trigger sync: `POST /data-sources/{id}/sync/trigger`\n\n## Key Design Decisions\n\
  \n- **Data source detail view** (`/data/data-sources/{id}`): This page was stubbed\n\
  \  in task-146 as a tab on the KG detail. This task fills the \"Sync Status\" tab\n\
  \  with real content.\n- **Active sync panel**: Shown only when the latest sync\
  \ run has status\n  `in_progress`. Displays phase badge (`ingesting` / `extracting`\
  \ / `applying`)\n  and an indeterminate progress bar. Polls `GET /data-sources/{id}/sync-runs`\n\
  \  every 10 seconds while active.\n- **Sync history table**: All completed and failed\
  \ runs in a table with columns:\n  Status (badge), Started At, Duration, Entities\
  \ Processed. Clicking a row opens\n  the log panel.\n- **Log panel**: A `<LogViewer>`\
  \ component renders the log entries as a monospace\n  scrollable list. Loaded on\
  \ demand from `GET /sync-runs/{run_id}/logs`. Auto-scrolls\n  to bottom for active\
  \ runs; stays at position for completed runs.\n- **Manual trigger**: \"Trigger Sync\"\
  \ button visible to users with `manage` permission.\n  Calls `POST /data-sources/{id}/sync/trigger`.\
  \ On success, the active sync panel\n  appears and polling begins. Confirm before\
  \ triggering if a sync is already running\n  (AlertDialog: \"A sync is already in\
  \ progress. Start a new one anyway?\").\n\n## What Files Are Affected\n\n- **New**:\
  \ `src/ui/components/sync/SyncStatusPanel.vue`\n- **New**: `src/ui/components/sync/SyncHistoryTable.vue`\n\
  - **New**: `src/ui/components/sync/LogViewer.vue`\n- **New**: `src/ui/components/sync/TriggerSyncButton.vue`\n\
  - **New**: `src/ui/composables/useSyncMonitoring.ts`\n- **Modified**: `src/ui/pages/data/data-sources/[id].vue`\
  \ (fill Sync Status tab)\n- **New**: `src/ui/tests/unit/SyncStatusPanel.test.ts`\n\
  - **New**: `src/ui/tests/unit/useSyncMonitoring.test.ts`\n\n## How to Verify\n\n\
  ```bash\nmake instance-up\nsource .instances/$(basename $(pwd))/.env.instance\n\
  cd src/ui && npm run dev\n# 1. Navigate to data source detail (/data/data-sources/{id})\n\
  # 2. Trigger a sync — active sync panel appears with phase badge\n# 3. Wait for\
  \ completion — sync appears in history table with duration\n# 4. Click a history\
  \ row — log viewer opens with log entries\n# 5. Trigger another sync — confirmation\
  \ dialog if one is already running\n```\n\nUnit tests:\n```bash\ncd src/ui && npm\
  \ run test:unit -- sync\n# SyncStatusPanel: renders phase correctly; hides when\
  \ no active run\n# SyncHistoryTable: sorts by timestamp desc; opens log viewer on\
  \ row click\n# useSyncMonitoring: polls when active; stops polling on completion/error\n\
  ```\n\n## Caveats\n\n- Polling is intentional (not WebSockets) to keep infrastructure\
  \ simple.\n  Poll interval is 10 seconds for active runs; stop polling when status\n\
  \  changes to `completed` or `failed`.\n- The `GET /sync-runs/{run_id}/logs` endpoint\
  \ must support pagination if there\n  are many log lines. For now, fetch all logs\
  \ at once; add pagination if the\n  response size becomes a concern.\n- The \"ingesting\
  \ / extracting / applying\" phase values must match the backend's\n  status enum.\
  \ Verify against `management/presentation/data_sources/models.py`."
---
