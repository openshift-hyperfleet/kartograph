---
id: task-044
title: Implement UI — sync log viewer (Sync Monitoring > Sync logs)
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps:
  - task-014
  - task-041
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Sync Monitoring — Scenario: Sync logs** from `specs/ui/experience.spec.md`:

> GIVEN a sync run (in progress or completed)
> WHEN the user requests logs
> THEN detailed logs for that run are displayed

## Current State

The implementation already exists in `src/dev-ui/app/pages/data-sources/index.vue`:

- `viewLogs(ds, run)` — sets `selectedLogDsId`, `selectedLogRunId`, opens `logSheetOpen`
- `fetchRunLogs(dsId, runId)` — calls `GET /management/data-sources/{dsId}/sync-runs/{runId}/logs`
  and populates `runLogs` (expects `{ logs: string[] }` response)
- `closeLogs()` — clears selection and closes the sheet
- Log viewer is a side sheet (`<Sheet>`) rendered in the template at the bottom of the page
- Handles loading state, error state, empty state, and populated log lines (`<pre>` block)

Tests covering this scenario exist in `src/dev-ui/app/tests/knowledge-graphs.test.ts`
under the "FAIL 3: Sync Logs" label:
- Opens log sheet when "View Logs" is clicked
- Closes log sheet and clears selection
- Fetches logs from the correct API endpoint
- Clears previous logs when a new run is selected
- Handles log fetch failure gracefully (shows error, not crash)

## Acceptance Criteria

- Each sync run row in the sync history section has a "View Logs" button.
- Clicking "View Logs" opens a side sheet scoped to that run.
- The sheet calls `GET /management/data-sources/{ds_id}/sync-runs/{run_id}/logs`
  and displays the returned log lines verbatim.
- Loading spinner is shown while logs are fetching.
- If the API call fails, an error message is shown (not a blank sheet).
- If no log lines are returned, an "No log entries" empty state is shown.
- Closing the sheet clears `selectedLogRunId` and `runLogs`.
- All tests in the "Sync Logs" sections pass: `cd src/dev-ui && pnpm test`.

## UI Location

- `src/dev-ui/app/pages/data-sources/index.vue` — existing page
- Log sheet is the `<Sheet v-model:open="logSheetOpen">` component at the bottom of the template

## Dependencies

- **task-014** must be complete (design system and shadcn/vue Sheet component required).
- **task-041** must be complete (data source list must render correctly before sync run
  rows and their "View Logs" buttons can be reached).

## TDD Cycle

Tests already exist in `tests/knowledge-graphs.test.ts`. The implementation cycle is:

1. Run `cd src/dev-ui && pnpm test` — verify all sync logs tests pass against the existing
   implementation.
2. If tests fail, fix the implementation in `pages/data-sources/index.vue` to satisfy them.
3. If any spec scenario is missing a test, add it to `tests/knowledge-graphs.test.ts` first,
   then fix the implementation.
4. Commit atomically once all tests pass.
