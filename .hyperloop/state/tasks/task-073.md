---
id: task-073
title: Sync Monitoring — sync history, log viewer, and manual trigger
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps:
  - task-064
round: 0
branch: null
pr: null
pr_title: "feat(ui): add sync history table, log viewer, and manual trigger to data source view"
pr_description: |
  ## What & Why

  The Sync Monitoring requirement in `experience.spec.md` has four scenarios. The active
  sync progress indicator (animated phase badge) is handled by task-064. The remaining
  three scenarios have no task coverage:

  1. **Sync history** — the user must see all past sync runs with status, timestamps,
     and duration when viewing a data source.
  2. **Sync logs** — the user must be able to request detailed logs for any sync run
     (in-progress or completed) and have them displayed.
  3. **Manual sync trigger** — a user with `manage` permission on the data source must
     be able to trigger a sync on demand; a new run begins and progress is shown.

  Without these three features the data source detail page is silent after a sync
  completes — the user cannot review what happened, inspect failures, or re-run a sync
  without an external tool.

  ## Spec Requirements Satisfied

  **Requirement: Sync Monitoring — Scenario: Sync history**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN a data source with completed syncs
  > WHEN the user views the data source
  > THEN they see a history of sync runs with status (completed, failed), timestamps,
  > and duration

  **Requirement: Sync Monitoring — Scenario: Sync logs**

  > GIVEN a sync run (in progress or completed)
  > WHEN the user requests logs
  > THEN detailed logs for that run are displayed

  **Requirement: Sync Monitoring — Scenario: Manual sync trigger**

  > GIVEN a data source the user has manage permission on
  > WHEN the user triggers a sync
  > THEN a new sync run begins and progress is shown

  ## Key Design Decisions

  - **Sync history table**: rendered in the data source detail page below the active sync
    indicator (task-064). Columns: status (via `SyncPhaseIndicator`), started-at
    (formatted relative time), finished-at, and duration (computed from timestamps).
    Completed and failed runs show static badges; active runs already have animated
    indicators from task-064.
  - **Log viewer**: uses progressive disclosure — each sync run row has a "View Logs"
    button that opens a side sheet (`Sheet` from shadcn/vue) containing the log lines.
    The sheet fetches logs on demand; a spinner is shown while loading. Log lines are
    rendered in a monospace `pre` block with overflow-y scroll.
  - **Manual trigger button**: placed in the data source card header area (next to the
    sync status badge). Visible only when the user has `manage` permission on the data
    source. Clicking it calls `POST /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}/sync`
    (or equivalent API endpoint as defined in the management/ingestion spec). On success
    a toast confirms and the active sync indicator appears. On failure a toast reports
    the error.
  - **Permission guard**: the trigger button is gated on a `canManage` computed flag
    derived from the data source's permission field or a separate authorization check.
    If the user lacks permission the button is hidden (not disabled) to avoid confusion.
  - **Interaction principles**: log viewer uses a side sheet (not a new page) per the
    "inline actions over navigation" principle. Toast feedback on trigger success/failure.

  ## Files Affected

  - `src/dev-ui/app/pages/data-sources/index.vue` — add sync history table, log-viewer
    trigger button per row, and manual sync trigger button in card header.
  - `src/dev-ui/app/components/data-sources/SyncLogViewer.vue` — new: side-sheet
    component that fetches and renders log lines for a given sync run ID.
  - `src/dev-ui/app/composables/api/useSyncApi.ts` (or equivalent) — `fetchSyncLogs(runId)`
    and `triggerSync(kgId, dsId)` composable functions.
  - `src/dev-ui/app/tests/sync-monitoring-extended.test.ts` — new test file (TDD-first)
    covering all three scenarios with pure logic tests and structural source-file checks.

  ## How to Verify

  1. Open a data source that has at least one completed sync run.
  2. Verify the sync history table shows: status badge, started-at timestamp,
     finished-at timestamp, and duration (e.g., "1m 23s").
  3. Click "View Logs" on a completed run — the side sheet opens and shows log lines.
  4. For an in-progress run, "View Logs" shows a spinner then log lines as they load.
  5. As a user with `manage` permission, verify the "Trigger Sync" button is visible
     in the card header; click it and confirm a new sync run appears with active state.
  6. As a user without `manage` permission, verify the button is absent.
  7. Run `cd src/dev-ui && pnpm test` — all tests in `sync-monitoring-extended.test.ts`
     pass with no regressions.

  ## TDD Cycle

  1. Create `src/dev-ui/app/tests/sync-monitoring-extended.test.ts` with tests for:
     - `formatDuration(startedAt, finishedAt)` returns human-readable duration string
     - `formatDuration` with null finishedAt (in-progress run) returns elapsed time
     - `canTriggerSync(permissions)` returns true only when user has `manage` permission
     - Structural: `data-sources/index.vue` contains `View Logs` string
     - Structural: `data-sources/index.vue` contains `Trigger Sync` string
     - Structural: `data-sources/index.vue` contains `canManage` guard for trigger button
  2. Create `SyncLogViewer.vue` component.
  3. Add `fetchSyncLogs` and `triggerSync` to the API composable.
  4. Add history table, log button, and trigger button to `data-sources/index.vue`.
  5. Run `cd src/dev-ui && pnpm test` (GREEN).
  6. Commit atomically.

  ## Caveats

  - Depends on task-064 (which adds `SyncPhaseIndicator` and establishes the sync run
    history rows in the data source page). task-073 extends those rows with the log
    button and adds the trigger button and history table columns.
  - The exact API endpoint for fetching sync logs and triggering a sync must match
    the management/ingestion spec. If those endpoints are not yet implemented on the
    backend, the composable should be written with a clear stub that makes the expected
    HTTP call (so the backend can be wired in without UI changes).
  - Log volume could be large; the log viewer should cap initial display at ~500 lines
    with a "load more" affordance for very long runs.
---

## Spec Coverage

**Requirement: Sync Monitoring** from `specs/ui/experience.spec.md`:

Three of four scenarios in this requirement have no task:

### Scenario: Sync history

> GIVEN a data source with completed syncs
> WHEN the user views the data source
> THEN they see a history of sync runs with status (completed, failed), timestamps, and duration

The data source page currently renders sync run rows (as noted in task-064, which
adds animated indicators to those rows). However, no task verifies that **timestamps**
and **duration** are displayed — the spec requires both, not just status. The
`sync-monitoring-extended.test.ts` file does not yet exist.

### Scenario: Sync logs

> GIVEN a sync run (in progress or completed)
> WHEN the user requests logs
> THEN detailed logs for that run are displayed

No task covers the log viewer feature. No `SyncLogViewer` component exists.

### Scenario: Manual sync trigger

> GIVEN a data source the user has manage permission on
> WHEN the user triggers a sync
> THEN a new sync run begins and progress is shown

No task covers the trigger button. No `triggerSync` API call exists in the UI.

## Gap Summary

| Scenario             | Task | Status        |
|----------------------|------|---------------|
| Active sync progress | 064  | not-started   |
| Sync history         | —    | **no task**   |
| Sync logs            | —    | **no task**   |
| Manual sync trigger  | —    | **no task**   |

## Scope

### TDD — write tests first

Create `src/dev-ui/app/tests/sync-monitoring-extended.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Pure logic: duration formatting ────────────────────────────────────────────
//
// Spec: "THEN they see a history of sync runs with status (completed, failed),
// timestamps, and duration"

/**
 * Format elapsed seconds into a human-readable duration string.
 * e.g. 83 → "1m 23s", 45 → "45s", 3661 → "1h 1m"
 */
function formatDuration(startedAt: string, finishedAt: string | null): string {
  const start = new Date(startedAt).getTime()
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  const rem = secs % 60
  if (mins < 60) return rem > 0 ? `${mins}m ${rem}s` : `${mins}m`
  const hrs = Math.floor(mins / 60)
  const remMins = mins % 60
  return remMins > 0 ? `${hrs}h ${remMins}m` : `${hrs}h`
}

describe('Sync history — formatDuration()', () => {
  it('formats seconds-only duration', () => {
    const start = new Date('2025-01-01T10:00:00Z').toISOString()
    const end   = new Date('2025-01-01T10:00:45Z').toISOString()
    expect(formatDuration(start, end)).toBe('45s')
  })

  it('formats minutes and seconds duration', () => {
    const start = new Date('2025-01-01T10:00:00Z').toISOString()
    const end   = new Date('2025-01-01T10:01:23Z').toISOString()
    expect(formatDuration(start, end)).toBe('1m 23s')
  })

  it('formats exact minutes (no trailing "0s")', () => {
    const start = new Date('2025-01-01T10:00:00Z').toISOString()
    const end   = new Date('2025-01-01T10:02:00Z').toISOString()
    expect(formatDuration(start, end)).toBe('2m')
  })

  it('formats hours and minutes for long runs', () => {
    const start = new Date('2025-01-01T10:00:00Z').toISOString()
    const end   = new Date('2025-01-01T11:01:00Z').toISOString()
    expect(formatDuration(start, end)).toBe('1h 1m')
  })

  it('uses current time when finishedAt is null (in-progress run)', () => {
    // Result should be a non-empty string and not throw
    const start = new Date(Date.now() - 30_000).toISOString()
    const result = formatDuration(start, null)
    expect(result).toMatch(/^\d+(s|m|h)/)
  })
})

// ── Pure logic: trigger permission guard ───────────────────────────────────────
//
// Spec: "GIVEN a data source the user has manage permission on"
// Only users with manage permission see the trigger button.

function canTriggerSync(userPermissions: string[]): boolean {
  return userPermissions.includes('manage')
}

describe('Manual sync trigger — canTriggerSync()', () => {
  it('returns true when user has manage permission', () => {
    expect(canTriggerSync(['read', 'manage'])).toBe(true)
  })

  it('returns false when user only has read permission', () => {
    expect(canTriggerSync(['read'])).toBe(false)
  })

  it('returns false for empty permissions array', () => {
    expect(canTriggerSync([])).toBe(false)
  })
})

// ── Structural: verify implementation in data-sources/index.vue ───────────────

describe('Sync Monitoring — data-sources/index.vue structural checks', () => {
  const dsVue = readFileSync(
    resolve(__dirname, '../pages/data-sources/index.vue'),
    'utf-8',
  )

  it('renders "View Logs" affordance for sync runs', () => {
    // Spec: "WHEN the user requests logs THEN detailed logs are displayed"
    expect(dsVue).toContain('View Logs')
  })

  it('renders "Trigger Sync" button for manual sync trigger', () => {
    // Spec: "WHEN the user triggers a sync THEN a new sync run begins"
    expect(dsVue).toContain('Trigger Sync')
  })

  it('guards Trigger Sync button behind a canManage (or equivalent) check', () => {
    // Spec: "GIVEN a data source the user has manage permission on"
    // The button must be conditional on a permission check — not always visible.
    expect(dsVue).toMatch(/canManage|hasManagePermission|manage.*permission/i)
  })

  it('displays duration for each sync run row', () => {
    // Spec: "they see a history of sync runs with ... duration"
    expect(dsVue).toMatch(/duration|formatDuration/i)
  })
})
```

### Implementation

#### 1. `formatDuration` and `canTriggerSync` utilities

Add `formatDuration` and `canTriggerSync` to a shared utility module (or inline in
`data-sources/index.vue`) so tests can import them directly.

#### 2. `SyncLogViewer.vue` component

**Location:** `src/dev-ui/app/components/data-sources/SyncLogViewer.vue`

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Loader2 } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  runId: string | null
  dataSourceName: string
}>()

const emit = defineEmits<{ 'update:open': [boolean] }>()

const logs = ref<string[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

watch(
  () => props.open,
  async (val) => {
    if (!val || !props.runId) return
    loading.value = true
    error.value = null
    logs.value = []
    try {
      // GET /management/.../sync-runs/{runId}/logs
      const res = await apiFetch(`/management/sync-runs/${props.runId}/logs`)
      logs.value = res.lines ?? []
    } catch (e: any) {
      error.value = e.message ?? 'Failed to load logs'
    } finally {
      loading.value = false
    }
  },
)
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent class="w-[600px] sm:max-w-2xl overflow-y-auto">
      <SheetHeader>
        <SheetTitle>Sync Logs — {{ dataSourceName }}</SheetTitle>
      </SheetHeader>
      <div class="mt-4">
        <div v-if="loading" class="flex items-center gap-2 text-muted-foreground text-sm">
          <Loader2 class="size-4 animate-spin" />
          Loading logs…
        </div>
        <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
        <pre v-else class="text-xs font-mono leading-relaxed whitespace-pre-wrap overflow-x-auto max-h-[70vh]">
          <template v-if="logs.length">{{ logs.join('\n') }}</template>
          <span v-else class="text-muted-foreground">No log output for this run.</span>
        </pre>
      </div>
    </SheetContent>
  </Sheet>
</template>
```

#### 3. API composable additions

Add to `src/dev-ui/app/composables/api/useSyncApi.ts` (create if not present):

```typescript
export function useSyncApi() {
  const { apiFetch } = useApiClient()

  async function fetchSyncLogs(runId: string): Promise<{ lines: string[] }> {
    return apiFetch(`/management/sync-runs/${runId}/logs`)
  }

  async function triggerSync(kgId: string, dsId: string): Promise<void> {
    await apiFetch(
      `/management/knowledge-graphs/${kgId}/data-sources/${dsId}/sync`,
      { method: 'POST' },
    )
  }

  return { fetchSyncLogs, triggerSync }
}
```

#### 4. `data-sources/index.vue` additions

- Add `formatDuration` utility inline or imported.
- Add `canManage` computed ref derived from the data source's permissions.
- Extend each sync run row: add "View Logs" button + duration column.
- Add "Trigger Sync" button (v-if="canManage") in the data source card header.
- Wire `SyncLogViewer` sheet with `logViewerOpen` / `selectedRunId` refs.
- On trigger button click: call `triggerSync(kgId, dsId)`, show toast, refresh
  the data source to display the new active run.

## Acceptance Criteria

- The sync history table (on the data source detail/list view) shows each run's
  status, started-at time, finished-at time, and formatted duration.
- A "View Logs" button on each row opens a side sheet with log lines for that run.
  A spinner shows while logs load; an error message is shown on failure.
- A "Trigger Sync" button appears in the card header for users with `manage` permission.
  Clicking it POSTs to the sync endpoint, shows a success toast, and reveals the
  new active run in the history list.
- Users without `manage` permission do not see the "Trigger Sync" button.
- All tests in `src/dev-ui/app/tests/sync-monitoring-extended.test.ts` pass.
- `cd src/dev-ui && pnpm test` exits 0 with no regressions.

## TDD Cycle

1. Create `src/dev-ui/app/tests/sync-monitoring-extended.test.ts` with tests above (RED).
2. Add `formatDuration` / `canTriggerSync` utilities (GREEN for pure logic tests).
3. Create `SyncLogViewer.vue` and `useSyncApi.ts`.
4. Add history columns, log button, trigger button to `data-sources/index.vue`.
5. Structural tests go GREEN.
6. Run full suite: `cd src/dev-ui && pnpm test`.
7. Commit atomically.
