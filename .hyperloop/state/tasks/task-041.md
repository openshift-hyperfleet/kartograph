---
id: task-041
title: Fix backend API response format — data sources and sync runs
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gap

**Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
> GIVEN a user performs any create, read, update, or delete operation via the UI
> WHEN the operation is submitted
> THEN the corresponding backend API call succeeds (2xx response)
> AND the UI reflects the updated state without requiring a manual refresh

**Requirement: Sync Monitoring — Scenario: Sync history**
> GIVEN a data source with completed syncs
> WHEN the user views the data source
> THEN they see a history of sync runs with status (completed, failed), timestamps, and duration

Both FAIL against current implementation in `src/dev-ui/app/pages/data-sources/index.vue`.

## Root Cause

Two backend endpoints return JSON arrays directly, but the UI wraps them in
incorrectly-typed objects and accesses non-existent properties, so the UI always
gets `undefined` and falls back to `[]`.

### Bug 1 — Data source list response mismatch

Backend route: `GET /management/knowledge-graphs/{kg_id}/data-sources`
Backend return type: `list[DataSourceResponse]` → serialises as JSON array `[...]`

Current UI code in `loadDataSources()`:
```typescript
const dsResult = await apiFetch<{ data_sources: DataSourceItem[] }>(
  `/management/knowledge-graphs/${kg.id}/data-sources`
)
const sources = dsResult.data_sources ?? []   // ← ALWAYS undefined → []
```

`dsResult` is an array; accessing `.data_sources` on it returns `undefined`.
Data sources are never displayed even when the backend has data.

**Fix:**
```typescript
const sources = await apiFetch<DataSourceItem[]>(
  `/management/knowledge-graphs/${kg.id}/data-sources`
)
// sources is already the array
```

### Bug 2 — Sync run list response mismatch

Backend route: `GET /management/data-sources/{ds_id}/sync-runs`
Backend return type: `list[SyncRunResponse]` → serialises as JSON array `[...]`

Current UI code in `loadDataSources()`:
```typescript
const runResult = await apiFetch<{ sync_runs: SyncRun[] }>(
  `/management/data-sources/${ds.id}/sync-runs`
)
ds.sync_runs = runResult.sync_runs ?? []   // ← ALWAYS undefined → []
```

Sync run history is never shown even when runs exist in the backend.

**Fix:**
```typescript
ds.sync_runs = await apiFetch<SyncRun[]>(
  `/management/data-sources/${ds.id}/sync-runs`
)
```

## Changes Required

### 1. `src/dev-ui/app/tests/data-sources.test.ts`

Write tests **before** fixing the implementation:

1. **Data source list: parses API array response correctly**
   Assert that when the API returns `[{ id: 'ds-1', name: 'my-repo', ... }]`
   (a JSON array, NOT `{ data_sources: [...] }`), the `loadDataSources` function
   correctly populates `dataSources` with all items.

2. **Sync run list: parses API array response correctly**
   Assert that when the API returns `[{ id: 'run-1', status: 'completed', ... }]`
   (a JSON array, NOT `{ sync_runs: [...] }`), each data source's `sync_runs`
   field is populated correctly.

3. **Data source list falls back to empty array on API error (unchanged)**
   Verify the existing graceful-degradation behaviour is preserved.

4. **Sync run list falls back to empty array on API error (unchanged)**
   Verify the existing graceful-degradation behaviour is preserved.

### 2. `src/dev-ui/app/pages/data-sources/index.vue`

- In `loadDataSources()`, change the data source fetch to expect a direct array:
  ```typescript
  const sources = await apiFetch<DataSourceItem[]>(
    `/management/knowledge-graphs/${kg.id}/data-sources`
  )
  ```
- In the same loop, change the sync-run fetch to expect a direct array:
  ```typescript
  ds.sync_runs = await apiFetch<SyncRun[]>(
    `/management/data-sources/${ds.id}/sync-runs`
  ) ?? []
  ```
- Remove the now-incorrect `{ data_sources: [...] }` and `{ sync_runs: [...] }`
  wrapper types.

## TDD Cycle

1. Write the new tests in `tests/data-sources.test.ts` (they will fail against the
   current code because `dsResult.data_sources` is always `undefined`).
2. Fix `pages/data-sources/index.vue` to use the correct array response types.
3. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
