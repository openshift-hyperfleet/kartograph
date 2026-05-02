---
id: task-083
title: Data Sources UI — live sync status polling for active syncs
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps: []
round: 2
branch: hyperloop/task-083
pr: https://github.com/openshift-hyperfleet/kartograph/pull/546
pr_title: 'feat(ui): poll sync status while a data source sync is active'
pr_description: "## What & Why\n\nThe spec requires:\n\n> **Requirement: Sync Monitoring\
  \ — Scenario: Active sync progress**\n> GIVEN a data source with a sync in progress\n\
  > WHEN the user views the data source\n> THEN they see the current sync status (ingesting,\
  \ extracting, applying)\n> AND a progress indicator appropriate to the current phase\n\
  \nThe Data Sources page currently loads sync state once on mount (and after a manual\n\
  sync trigger) but never refreshes automatically. A user watching an active sync\
  \ is\nshown a frozen status badge — they must navigate away and back to see progress.\n\
  \nThe backend transitions a sync through phases: `pending` → `ingesting` →\n`ai_extracting`\
  \ → `applying` → `completed` (or `failed`). Without polling, the UI\ncannot display\
  \ these transitions as they happen.\n\nThis task adds a polling mechanism: while\
  \ any data source has an active sync\n(status in `{ pending, ingesting, ai_extracting,\
  \ applying }`), the page re-fetches\nthe full data source list every 5 seconds.\
  \ Polling stops automatically once all\nsyncs reach a terminal state (`completed`\
  \ or `failed`).\n\n## Spec Requirements Satisfied\n\n**Requirement: Sync Monitoring\
  \ — Scenario: Active sync progress**\nfrom `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> THEN they see the **current** sync status (ingesting, extracting, applying)\n\
  > AND a progress indicator appropriate to the current phase\n\nThe word \"current\"\
  \ implies live feedback, not a one-time snapshot. Polling at a\n5-second cadence\
  \ is the minimum viable implementation before WebSocket support\nis available.\n\
  \n## Key Design Decisions\n\n- **Poll interval: 5 seconds** — short enough to show\
  \ phase transitions in near\n  real-time; long enough to avoid hammering the backend.\n\
  \n- **Active sync detection**: after every data load, compute\n  `hasActiveSyncs\
  \ = dataSources.some(ds => ACTIVE_STATUSES.includes(ds.sync_status))`.\n  `ACTIVE_STATUSES\
  \ = ['pending', 'ingesting', 'ai_extracting', 'applying']`.\n\n- **Start/stop logic**:\n\
  \  - On mount: if `hasActiveSyncs`, start the poll interval.\n  - After each poll\
  \ tick: if `!hasActiveSyncs`, clear the interval.\n  - On `onUnmounted`: always\
  \ clear the interval (prevent memory leaks when navigating\n    away).\n  - After\
  \ a manual sync trigger: data sources always reload, which restarts the\n    poll\
  \ if the triggered sync is now active.\n\n- **Single interval, not stacked**: use\
  \ a single `setInterval` ref, guarded by a\n  check so a second interval is never\
  \ created if one already exists.\n\n- **No separate polling composable**: the logic\
  \ is small enough to live inline in\n  `data-sources/index.vue`. If the pattern\
  \ is later reused across pages, extract\n  to `composables/usePolling.ts`.\n\n-\
  \ **TDD first**: all logic is extracted into pure functions (or minimal reactive\n\
  \  refs) so unit tests can exercise poll start/stop without mounting the Vue component.\n\
  \n## Files Affected\n\n- `src/dev-ui/app/tests/data-sources.test.ts` — new test\
  \ group for polling logic:\n  active status detection, interval start/stop, cleanup\
  \ on unmount.\n- `src/dev-ui/app/pages/data-sources/index.vue` — add `ACTIVE_STATUSES`,\n\
  \  `hasActiveSyncs` computed, `startPolling`, `stopPolling`, `pollInterval` ref,\n\
  \  `onMounted` poll-start guard, `onUnmounted` cleanup.\n\n## How to Verify\n\n\
  1. `cd src/dev-ui && npm run test` — all new tests pass, no regressions.\n2. Start\
  \ a sync on a data source (`POST /management/data-sources/{id}/sync`).\n3. Navigate\
  \ to the Data Sources page while the sync is in progress.\n4. Observe the sync status\
  \ badge updating through phases without any manual\n   interaction (watch Network\
  \ tab — a GET request fires every ~5 seconds).\n5. When the sync reaches `completed`\
  \ or `failed`, verify the polling stops\n   (no further GET requests).\n6. Navigate\
  \ to another page while a sync is active, then back — verify polling\n   resumes\
  \ correctly on re-mount.\n7. Navigate away while a sync is active — verify no further\
  \ GET requests fire\n   (interval was cleared on unmount).\n\n## TDD Cycle\n\n1.\
  \ Write unit tests for `ACTIVE_STATUSES` detection: given a list of data sources\n\
  \   with mixed statuses, `hasActiveSyncs` is `true` iff at least one is active —\
  \ RED.\n2. Write unit tests for poll start/stop logic using `vi.useFakeTimers()`:\
  \ interval\n   fires `loadDataSources` at 5-second cadence, stops when `hasActiveSyncs`\
  \ is\n   false — RED.\n3. Write unit test: cleanup — `stopPolling` clears the interval\
  \ ref — RED.\n4. Implement `ACTIVE_STATUSES`, `hasActiveSyncs` computed, `startPolling`,\n\
  \   `stopPolling`, and integrate with `onMounted`/`onUnmounted`/`watch` in\n   `data-sources/index.vue`\
  \ — GREEN.\n5. Run `cd src/dev-ui && npm run test` — all pass.\n6. Commit atomically.\n\
  \n## Caveats\n\n- The polling calls the same `loadDataSources` function used on\
  \ mount, which fetches\n  all KGs and then all data sources per KG (current N+1\
  \ pattern). If the data source\n  list is large this will be chatty. A future improvement\
  \ is a dedicated\n  `GET /management/data-sources/active-syncs` endpoint. This is\
  \ out of scope here.\n- If the user has the browser tab in the background, `setInterval`\
  \ may throttle.\n  This is acceptable for now; a `visibilitychange` listener to\
  \ pause/resume polling\n  is a follow-up improvement.\n- Polling does NOT apply\
  \ to the sync logs sheet — logs are fetched on demand only."
---
