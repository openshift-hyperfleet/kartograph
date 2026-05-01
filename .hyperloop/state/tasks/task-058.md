---
id: task-058
title: Audit tenant selector — verify all tenant-scoped pages refresh on tenant switch
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
  - task-040
  - task-041
  - task-050
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Tenant and Workspace Context — Scenario: Tenant selector** from
`specs/ui/experience.spec.md`:

> GIVEN a user who belongs to multiple tenants
> THEN a tenant selector is available in the sidebar
> AND switching tenants refreshes all data in the UI

## Gap

task-014 (complete) implemented the tenant selector and its visible presence in the
sidebar. No subsequent task has formally verified the second clause — **"switching
tenants refreshes all data in the UI"** — across every page that holds tenant-scoped
data.

- task-050 audits Backend API Alignment for specific CRUD operations but does not check
  whether tenant switches trigger data refreshes on each page.
- task-047 verifies that the Data Sources sync-status badge updates on tenant change
  (one specific badge) but does not verify broader page-level refresh.
- task-045 verifies that the KG scope selector in the query console reloads on tenant
  change. This is one page, not a cross-page audit.

The "refreshes all data" clause is a cross-cutting behaviour requirement. No task owns a
systematic verification that every tenant-scoped page reacts to a tenant change.

## Scope

Every page that displays tenant-scoped data must reload its data when the active tenant
changes. The following pages and their data-loading functions are in scope:

| Page | File | Tenant-scoped data to reload |
|------|------|------------------------------|
| Knowledge Graphs | `pages/knowledge-graphs/index.vue` | KG list |
| Data Sources | `pages/data-sources/index.vue` | Data source list + sync runs |
| Workspaces | `pages/workspaces/index.vue` | Workspace list |
| Groups | `pages/groups/index.vue` | Group list |
| API Keys | `pages/api-keys/index.vue` | API key list |
| Query Console | `pages/query/index.vue` | KG scope selector (task-045) |
| Schema Browser | `pages/graph/schema.vue` | Schema type list |
| Graph Explorer | `pages/graph/explorer.vue` | Node search results / neighbours |
| Home page | `pages/index.vue` | KG count (for redirect logic and checklist) |

The tenant selector itself (`layouts/default.vue`) is assumed correct from task-014.

## Changes Required

### 1. Audit the tenant-change event mechanism

Read `src/dev-ui/app/layouts/default.vue` to identify:
- How the active tenant ID is stored (ref, Pinia store, provide/inject, localStorage)
- How tenant switches are propagated to child pages (watch, provide, event bus, etc.)
- Whether switching tenants emits any signal that pages can observe

Read `src/dev-ui/app/composables/useTenant.ts` (or the equivalent composable) to
understand the reactive tenant context.

### 2. Audit each page for tenant-change reactivity

For each page in the scope table above, read the component file and answer:

- Is there a `watch` on the tenant ID (or a reactive tenant context) that calls the
  page's data-loading function when the tenant changes?
- OR does the page mount fresh each time navigation occurs (route-level remount would
  inherently reload data)?

Record PASS / FAIL per page.

**Expected pattern (PASS):**

```typescript
// In each page component
const { currentTenantId } = useTenant()

watch(currentTenantId, (newId) => {
  if (newId) loadData()
  else clearData()
}, { immediate: true })
```

**Anti-patterns (FAIL):**
- Data is loaded only in `onMounted` with no watch on tenant change
- Data is loaded by a one-shot call without a reactive dependency on the tenant

### 3. Audit existing tests for tenant-change coverage

For each page, read the corresponding test file and check whether a test exists that:
1. Simulates a tenant change (mutates `currentTenantId` or the store)
2. Asserts that the data-loading function is called again
3. Asserts that the displayed list reflects data from the new tenant

If any page lacks this test, write it **before** fixing the implementation.

**Test pattern:**

```typescript
describe('Tenant selector — data refresh on tenant change', () => {
  it('knowledge graphs page reloads data when tenant changes', async () => {
    const { currentTenantId } = useTenant()
    mockFetch.mockResolvedValueOnce([{ id: 'kg-1', name: 'Old Tenant KG' }])
    const wrapper = await mountKnowledgeGraphsPage()

    // Simulate tenant switch
    mockFetch.mockResolvedValueOnce([{ id: 'kg-2', name: 'New Tenant KG' }])
    currentTenantId.value = 'new-tenant-id'
    await nextTick()

    // New tenant's data is loaded
    expect(wrapper.text()).toContain('New Tenant KG')
    expect(wrapper.text()).not.toContain('Old Tenant KG')
  })
})
```

Write equivalent tests for each page in the scope table.

### 4. Fix pages that do not react to tenant changes

For each FAIL page identified in step 2:

- If the page uses `onMounted` only: add a `watch` on the tenant ID that calls the
  load function. Remove `onMounted` call and replace with the `{ immediate: true }`
  watch option so it still loads on first render.

- If the component is route-remounted on tenant switch: verify this is actually the
  case (check for a route `key` binding in `default.vue` that includes the tenant ID).
  If remounting is the mechanism, add a comment explaining this and write a test that
  confirms the route key changes when tenant changes.

- Clear the displayed data immediately when tenant changes (before the new data
  arrives) to avoid showing stale data:

```typescript
watch(currentTenantId, async (newId) => {
  knowledgeGraphs.value = []  // clear immediately
  if (newId) await loadKnowledgeGraphs()
}, { immediate: true })
```

### 5. Verify tenant selector presence in the sidebar

Read `src/dev-ui/app/layouts/default.vue` and confirm:
- A tenant selector element (dropdown, combobox, or similar) is present and visible in
  the sidebar (not the main content area).
- If the user belongs to only one tenant, the selector is either hidden or displayed
  as a non-interactive label (per typical UX for single-tenant users).
- The selector is accessible (has an `aria-label` or label element).

If the selector is absent or incorrectly placed, add it. If present, add a test that
asserts its presence in the sidebar template.

## Acceptance Criteria

- The tenant selector is present in the sidebar in `layouts/default.vue`.
- Each page in the scope table has a reactive watch on the tenant ID that calls its
  data-loading function when the tenant changes.
- Switching tenants causes every page's data to reload with the new tenant's content.
- Stale data from the previous tenant is cleared before new data arrives (no flash
  of old tenant data).
- A test exists for each page asserting that data is reloaded when tenant changes.
- All tests pass: `cd src/dev-ui && pnpm test`
- No regressions in task-050 API alignment, task-045 KG scope selector, or task-047
  sync status badge.

## UI Location

- `src/dev-ui/app/layouts/default.vue` — tenant selector, tenant context propagation
- `src/dev-ui/app/composables/useTenant.ts` — tenant reactive context
- All pages in the scope table — watch wiring

## Dependencies

- **task-040** must be complete: KG creation must use the correct workspace-scoped
  endpoint before auditing tenant-level KG refresh (the KG list must be accurate first).
- **task-041** must be complete: data source list response format must be correct before
  testing that the correct data appears after a tenant switch.
- **task-050** must be complete: API endpoints for all pages must be correct before
  verifying that the right data is fetched per tenant on switch.

## TDD Cycle

1. Read `layouts/default.vue` and `useTenant.ts` — understand tenant propagation mechanism.
2. Read each page component; classify as PASS or FAIL for tenant-change reactivity.
3. Write failing tests (one per page) for tenant-change data reload.
4. Add `watch(currentTenantId, ...)` to each failing page.
5. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
6. Commit atomically per conventional commit conventions.
