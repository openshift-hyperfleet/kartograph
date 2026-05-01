---
id: task-042
title: Fix sync-run phase status types and display labels in UI
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gap

**Requirement: Sync Monitoring — Scenario: Active sync progress**
> GIVEN a data source with a sync in progress
> WHEN the user views the data source
> THEN they see the current sync status (ingesting, extracting, applying)
> AND a progress indicator appropriate to the current phase

## Root Cause

The backend `DataSourceSyncRun` domain entity defines the following valid status values:

```python
VALID_STATUSES = frozenset(
    {"pending", "ingesting", "ai_extracting", "applying", "completed", "failed"}
)
```

The `SyncRunResponse` serialises the status field verbatim from the domain — so the
API actually returns `"ingesting"`, `"ai_extracting"`, and `"applying"` for in-progress
runs. The value `"running"` is never returned by the backend.

However, the UI in `src/dev-ui/app/pages/data-sources/index.vue` defines:

```typescript
interface SyncRun {
  status: 'pending' | 'running' | 'completed' | 'failed'
  ...
}
```

This type omits `'ingesting' | 'ai_extracting' | 'applying'` and includes `'running'`
which the backend never emits. As a result:

- TypeScript silently accepts backend `'ingesting'` because the field is typed as a
  union of strings, but the badge logic has no case for it.
- The badge shows raw status strings like `"ai_extracting"` instead of
  human-readable labels ("Extracting").
- The phase progress indicator doesn't distinguish the three in-progress phases.

The tests in `src/dev-ui/app/tests/sync-monitoring-extended.test.ts` test with
`'running'` status which is never sent by the backend — those tests are inadvertently
testing against a fiction.

Also, the `SyncRunResponse` model description in
`src/api/management/presentation/data_sources/models.py` incorrectly documents the
status field as "pending, running, completed, failed" instead of the actual values.

## Changes Required

### 1. `src/dev-ui/app/tests/sync-monitoring-extended.test.ts`

Write tests **before** updating the implementation:

1. **Phase label for `ingesting`**: Assert `getSyncPhaseLabel('ingesting') === 'Ingesting'`.
2. **Phase label for `ai_extracting`**: Assert `getSyncPhaseLabel('ai_extracting') === 'Extracting'`.
3. **Phase label for `applying`**: Assert `getSyncPhaseLabel('applying') === 'Applying'`.
4. **`isActiveSyncPhase` for `ingesting`**: Assert `true`.
5. **`isActiveSyncPhase` for `ai_extracting`**: Assert `true`.
6. **`isActiveSyncPhase` for `applying`**: Assert `true`.
7. **`isActiveSyncPhase` for `running`**: Assert `false` (it is not a real status).
8. **Badge variant for `ingesting`**: Assert `'secondary'` (in-progress).
9. **Badge variant for `ai_extracting`**: Assert `'secondary'` (in-progress).
10. **Badge variant for `applying`**: Assert `'secondary'` (in-progress).

Update existing tests that use `'running'` status to use real backend statuses
(`'ingesting'`, `'ai_extracting'`, or `'applying'`) as appropriate.

### 2. `src/dev-ui/app/pages/data-sources/index.vue`

- Update `SyncRun.status` type:
  ```typescript
  interface SyncRun {
    status: 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'
    ...
  }
  ```
- Add a `syncPhaseLabel` helper that maps each status to a user-readable string:
  ```typescript
  function syncPhaseLabel(status: SyncRun['status']): string {
    const labels: Record<SyncRun['status'], string> = {
      pending:      'Pending',
      ingesting:    'Ingesting',
      ai_extracting: 'Extracting',
      applying:     'Applying',
      completed:    'Completed',
      failed:       'Failed',
    }
    return labels[status] ?? status
  }
  ```
- Update the sync history badge display to use `syncPhaseLabel(run.status)` as the
  badge text instead of `run.status`.
- Update the top-level data source badge (current sync indicator) to also use
  `syncPhaseLabel`.
- Update `isActiveSyncPhase` helper to include `'ingesting' | 'ai_extracting' | 'applying'`
  (and remove `'running'`).

### 3. `src/api/management/presentation/data_sources/models.py`

Fix the `SyncRunResponse.status` field description from:
```python
status: str = Field(..., description="Sync run status (pending, running, completed, failed)")
```
to:
```python
status: str = Field(..., description="Sync run status (pending, ingesting, ai_extracting, applying, completed, failed)")
```

## TDD Cycle

1. Write the new and updated tests in `sync-monitoring-extended.test.ts`
   (they will fail because `getSyncPhaseLabel('ingesting')` returns `'Unknown'`).
2. Update `data-sources/index.vue` with the corrected type and helper function.
3. Fix the `SyncRunResponse` description in `models.py`.
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
