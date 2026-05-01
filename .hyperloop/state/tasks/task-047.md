---
id: task-047
title: Add sync-status badge to Data Sources sidebar nav item
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps:
  - task-041
  - task-042
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Navigation Structure — Scenario: Primary navigation** from
`specs/ui/experience.spec.md`:

> GIVEN an authenticated user
> THEN the sidebar presents navigation grouped as:
>   - **Data** — Knowledge Graphs, **Data Sources (with sync status)**

The `(with sync status)` qualifier is part of the navigation structure spec. It requires
the Data Sources sidebar nav item to visually convey whether any data sources are currently
syncing — not merely that the data source detail page shows sync info.

## Current State (FAIL)

`src/dev-ui/app/layouts/default.vue` defines the Data Sources nav item as:

```typescript
{ label: 'Data Sources', icon: Cable, to: '/data-sources' }
```

No badge, no status indicator, no reactive sync count. The nav item is
indistinguishable from any other plain link. The spec explicitly calls out
"(with sync status)" as part of the nav item's presentation.

Note: task-014 (which implemented the navigation) was completed against an earlier
spec commit but the navigation structure requirement — including this qualifier — was
present in the original spec. It was missed.

## Changes Required

### 1. `src/dev-ui/app/tests/default.layout.test.ts`

Write tests **before** fixing the implementation (TDD):

1. **Badge shows active-sync count when syncs are running:**
   Mock `apiFetch('/management/data-sources')` to return a data sources list where
   at least one has an active sync run. Assert that the Data Sources nav item renders
   a `<Badge>` with the active count (e.g., `"1"` or `"2"`).

2. **Badge is absent when no syncs are in progress:**
   Mock `apiFetch('/management/data-sources')` to return data sources with no active
   sync runs (all `completed` or `failed`). Assert no badge is rendered on the
   Data Sources nav item.

3. **Badge updates after tenant change:**
   Simulate a tenant change event. Assert that `fetchActiveSyncCount()` is called
   again and the badge reflects the new tenant's sync state.

4. **Badge is absent while tenant is unset:**
   When `hasTenant.value` is `false`, assert no fetch is triggered and the badge
   is absent.

5. **Fetch error degrades gracefully:**
   When `apiFetch` throws, assert no badge is rendered and no error is surfaced to
   the user (the sidebar loads normally without the badge).

### 2. `src/dev-ui/app/layouts/default.vue`

**Add active sync count state:**

```typescript
const activeSyncCount = ref(0)

async function fetchActiveSyncCount() {
  if (!hasTenant.value) return
  try {
    const result = await apiFetch<{ data_sources: Array<{ latest_sync_run?: { status: string } }> }>(
      '/management/data-sources'
    )
    const activeStatuses = new Set(['pending', 'ingesting', 'extracting', 'applying'])
    activeSyncCount.value = (result.data_sources ?? []).filter(
      ds => ds.latest_sync_run && activeStatuses.has(ds.latest_sync_run.status)
    ).length
  } catch {
    // Best-effort — badge is optional indicator, not critical UI
    activeSyncCount.value = 0
  }
}
```

**Wire fetch on mount and tenant change:**

```typescript
watch(currentTenantId, (id) => {
  if (id) fetchActiveSyncCount()
  else activeSyncCount.value = 0
}, { immediate: true })
```

**Update the `NavItem` for Data Sources:**

Change the static nav definition to expose the badge reactively. The simplest approach
is to make `navSections` a computed ref that reads `activeSyncCount`:

```typescript
const navSections = computed<NavSection[]>(() => [
  // ... Explore and other sections unchanged ...
  {
    title: 'Data',
    items: [
      { label: 'Knowledge Graphs', icon: BookOpen, to: '/knowledge-graphs' },
      {
        label: 'Data Sources',
        icon: Cable,
        to: '/data-sources',
        badge: activeSyncCount.value > 0 ? String(activeSyncCount.value) : undefined,
      },
    ],
  },
  // ... Connect and Settings unchanged ...
])
```

The `badge` field already exists on `NavItem` and is already rendered in the template
(both desktop expanded and mobile views). No template changes are needed beyond
ensuring `navSections` is reactive.

**Accessible label:**

When a badge is shown, add an `aria-label` to the Data Sources link:
- With badge: `"Data Sources — N active syncs"`
- Without badge: default (just the label text)

## Acceptance Criteria

- Data Sources sidebar nav item shows a numeric badge when 1 or more data sources
  have an active sync run (status is `pending`, `ingesting`, `extracting`, or `applying`).
- Badge is absent when all sync runs are `completed`, `failed`, or absent.
- Badge reflects the correct count, not just a generic "syncing" indicator.
- Badge updates when the user switches tenants.
- Fetch errors do not surface a toast or break the sidebar — the badge simply doesn't appear.
- All tests are written first and pass before committing.

## Dependencies

- **task-041** must be complete: the data sources list response format must be correct
  so the badge logic can reliably read `latest_sync_run.status`.
- **task-042** must be complete: the sync phase status type strings
  (`ingesting`, `extracting`, `applying`) must match what the backend returns, so
  the `activeStatuses` set is accurate.

## TDD Cycle

1. Write tests in `src/dev-ui/app/tests/default.layout.test.ts` (they will fail
   against the current implementation).
2. Make `navSections` a computed ref; add `activeSyncCount` state and `fetchActiveSyncCount`.
3. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
4. Commit atomically per conventional commit conventions.
