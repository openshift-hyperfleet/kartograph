---
id: task-083
title: "Data Sources UI — live sync status polling for active syncs"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): poll sync status while a data source sync is active"
pr_description: |
  ## What & Why

  The spec requires:

  > **Requirement: Sync Monitoring — Scenario: Active sync progress**
  > GIVEN a data source with a sync in progress
  > WHEN the user views the data source
  > THEN they see the current sync status (ingesting, extracting, applying)
  > AND a progress indicator appropriate to the current phase

  The Data Sources page currently loads sync state once on mount (and after a manual
  sync trigger) but never refreshes automatically. A user watching an active sync is
  shown a frozen status badge — they must navigate away and back to see progress.

  The backend transitions a sync through phases: `pending` → `ingesting` →
  `ai_extracting` → `applying` → `completed` (or `failed`). Without polling, the UI
  cannot display these transitions as they happen.

  This task adds a polling mechanism: while any data source has an active sync
  (status in `{ pending, ingesting, ai_extracting, applying }`), the page re-fetches
  the full data source list every 5 seconds. Polling stops automatically once all
  syncs reach a terminal state (`completed` or `failed`).

  ## Spec Requirements Satisfied

  **Requirement: Sync Monitoring — Scenario: Active sync progress**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > THEN they see the **current** sync status (ingesting, extracting, applying)
  > AND a progress indicator appropriate to the current phase

  The word "current" implies live feedback, not a one-time snapshot. Polling at a
  5-second cadence is the minimum viable implementation before WebSocket support
  is available.

  ## Key Design Decisions

  - **Poll interval: 5 seconds** — short enough to show phase transitions in near
    real-time; long enough to avoid hammering the backend.

  - **Active sync detection**: after every data load, compute
    `hasActiveSyncs = dataSources.some(ds => ACTIVE_STATUSES.includes(ds.sync_status))`.
    `ACTIVE_STATUSES = ['pending', 'ingesting', 'ai_extracting', 'applying']`.

  - **Start/stop logic**:
    - On mount: if `hasActiveSyncs`, start the poll interval.
    - After each poll tick: if `!hasActiveSyncs`, clear the interval.
    - On `onUnmounted`: always clear the interval (prevent memory leaks when navigating
      away).
    - After a manual sync trigger: data sources always reload, which restarts the
      poll if the triggered sync is now active.

  - **Single interval, not stacked**: use a single `setInterval` ref, guarded by a
    check so a second interval is never created if one already exists.

  - **No separate polling composable**: the logic is small enough to live inline in
    `data-sources/index.vue`. If the pattern is later reused across pages, extract
    to `composables/usePolling.ts`.

  - **TDD first**: all logic is extracted into pure functions (or minimal reactive
    refs) so unit tests can exercise poll start/stop without mounting the Vue component.

  ## Files Affected

  - `src/dev-ui/app/tests/data-sources.test.ts` — new test group for polling logic:
    active status detection, interval start/stop, cleanup on unmount.
  - `src/dev-ui/app/pages/data-sources/index.vue` — add `ACTIVE_STATUSES`,
    `hasActiveSyncs` computed, `startPolling`, `stopPolling`, `pollInterval` ref,
    `onMounted` poll-start guard, `onUnmounted` cleanup.

  ## How to Verify

  1. `cd src/dev-ui && npm run test` — all new tests pass, no regressions.
  2. Start a sync on a data source (`POST /management/data-sources/{id}/sync`).
  3. Navigate to the Data Sources page while the sync is in progress.
  4. Observe the sync status badge updating through phases without any manual
     interaction (watch Network tab — a GET request fires every ~5 seconds).
  5. When the sync reaches `completed` or `failed`, verify the polling stops
     (no further GET requests).
  6. Navigate to another page while a sync is active, then back — verify polling
     resumes correctly on re-mount.
  7. Navigate away while a sync is active — verify no further GET requests fire
     (interval was cleared on unmount).

  ## TDD Cycle

  1. Write unit tests for `ACTIVE_STATUSES` detection: given a list of data sources
     with mixed statuses, `hasActiveSyncs` is `true` iff at least one is active — RED.
  2. Write unit tests for poll start/stop logic using `vi.useFakeTimers()`: interval
     fires `loadDataSources` at 5-second cadence, stops when `hasActiveSyncs` is
     false — RED.
  3. Write unit test: cleanup — `stopPolling` clears the interval ref — RED.
  4. Implement `ACTIVE_STATUSES`, `hasActiveSyncs` computed, `startPolling`,
     `stopPolling`, and integrate with `onMounted`/`onUnmounted`/`watch` in
     `data-sources/index.vue` — GREEN.
  5. Run `cd src/dev-ui && npm run test` — all pass.
  6. Commit atomically.

  ## Caveats

  - The polling calls the same `loadDataSources` function used on mount, which fetches
    all KGs and then all data sources per KG (current N+1 pattern). If the data source
    list is large this will be chatty. A future improvement is a dedicated
    `GET /management/data-sources/active-syncs` endpoint. This is out of scope here.
  - If the user has the browser tab in the background, `setInterval` may throttle.
    This is acceptable for now; a `visibilitychange` listener to pause/resume polling
    is a follow-up improvement.
  - Polling does NOT apply to the sync logs sheet — logs are fetched on demand only.
---
