---
task_id: task-058
round: 3
role: spec-reviewer
verdict: fail
---
## Review Summary

Rebase onto `alpha` completed cleanly. All 804 tests pass after rebase.

The branch addresses two spec requirements:
1. **Navigation Structure → Primary navigation**: Mutations Console added to Explore nav
2. **Tenant and Workspace Context → Tenant selector**: All tenant-scoped pages wired with `watch(tenantVersion, ...)` to reload data on tenant switch

---

## Requirement: Navigation Structure — Primary navigation

**Status: COVERED**

- **Implementation**: `src/dev-ui/app/layouts/default.vue` includes `{ label: 'Mutations Console', icon: FileEdit, to: '/graph/mutations' }` in the `Explore` nav group alongside Query Console, Schema Browser, and Graph Explorer. The order matches the spec exactly.
- **Tests**: `app/tests/default.layout.test.ts` lines 341–373 — `describe('Default layout — Explore nav group includes Mutations Console')` — verifies presence, correct route, absence from other sections, and correct ordering. All pass.

---

## Requirement: Tenant and Workspace Context — Tenant selector

**Status: PARTIAL**

### Sub-requirement: Selector is available in the sidebar

**Status: COVERED**

- **Implementation**: `src/dev-ui/app/layouts/default.vue` exposes a tenant selector in the sidebar with `aria-label` reflecting current tenant, multi-tenant prompt, and single-tenant static display. `isSingleTenant` / `isMultiTenant` computed correctly. `switchTenant()` via `useTenant` bumps `tenantVersion`.
- **Tests**: `app/tests/default.layout.test.ts` lines 397–497 — `describe('Default layout — tenant selector in sidebar')` — covers aria-label states (loading, no-tenant, multi-tenant, single-tenant), accessible label content, and isSingleTenant/isMultiTenant computed logic.

### Sub-requirement: Switching tenants refreshes all data in the UI

The mechanism: `useTenant.ts` exposes `tenantVersion` (a monotonically-increasing counter bumped by `switchTenant()`). All tenant-scoped pages `watch(tenantVersion, ...)` to clear stale data immediately and then reload.

| Page | File | Implementation | Test Coverage |
|------|------|---------------|---------------|
| Knowledge Graphs | `pages/knowledge-graphs/index.vue` | ✅ `watch(tenantVersion)` clears + reloads | ✅ `knowledge-graphs.test.ts` — 3 dedicated tests |
| Data Sources | `pages/data-sources/index.vue` | ✅ `watch(tenantVersion)` clears + reloads | ✅ `sync-monitoring-extended.test.ts` lines 361–395 — 2 tests (clear + reload) |
| Workspaces | `pages/workspaces/index.vue` | ✅ `watch(tenantVersion)` clears + reloads | ✅ `workspace-management.test.ts` lines 1119–1190 — 3 tests |
| Groups | `pages/groups/index.vue` | ✅ `watch(tenantVersion)` clears + reloads | ✅ `groups.test.ts` lines 613–685 — 3 tests |
| API Keys | `pages/api-keys/index.vue` | ✅ `watch(tenantVersion)` clears + reloads | ✅ `api-keys.test.ts` lines 452–520 — 3 tests |
| Graph Explorer | `pages/graph/explorer.vue` | ✅ `watch(tenantVersion)` clears state + reloads node types | ✅ `graph-explorer.test.ts` lines 668–740 — 3 tests |
| Home page | `pages/index.vue` | ✅ `watch(tenantVersion)` clears stats + reloads | ✅ `index.test.ts` lines 356–430 — 3 tests |
| **Query Console** | `pages/query/index.vue` | ✅ `watch(tenantVersion)` clears `result`, `error`, `executionTime`, schema labels, then calls `fetchSchema()` + `loadKnowledgeGraphs()` | ⚠️ **PARTIAL** — `knowledge-graphs.test.ts` "Query Console - KG Selector Population" covers `loadKnowledgeGraphs` reload but does NOT test `fetchSchema()` reload, result/error/executionTime clearing, or the watch trigger itself |
| **Schema Browser** | `pages/graph/schema.vue` | ✅ `watch(tenantVersion)` clears labels + cache, then calls `fetchNodeLabels()` + `fetchEdgeLabels()` | ⚠️ **PARTIAL** — `interaction-principles.test.ts` line 600 tests label/cache clearing but does NOT test that `fetchNodeLabels()` and `fetchEdgeLabels()` are called after the tenant switch |

---

## Gaps Requiring Fix

### GAP 1 — Query Console tenant-switch test is incomplete (SHALL / FAIL)

**Spec**: "switching tenants refreshes all data in the UI"
**Task acceptance criterion**: "A test exists for each page asserting that **data is reloaded** when tenant changes."

The existing test in `knowledge-graphs.test.ts` (under "Query Console - KG Selector Population") only verifies that calling `loadKnowledgeGraphs()` manually twice results in 2 invocations. It does not:
- Simulate a `tenantVersion` change triggering the watch
- Verify `fetchSchema()` is called (the schema reload for autocomplete)
- Verify `result.value`, `error.value`, and `executionTime.value` are cleared

**Fix needed**: Add a dedicated test block in `query-history.test.ts` (or a new `app/tests/query-console-tenant.test.ts`) that simulates a `tenantVersion` increment and asserts: stale result/error/schema labels are cleared AND both `fetchSchema` and `loadKnowledgeGraphs` are invoked.

### GAP 2 — Schema Browser tenant-switch test only covers clearing, not reloading (SHALL / FAIL)

**Spec**: "switching tenants refreshes all data in the UI"
**Task acceptance criterion**: "A test exists for each page asserting that **data is reloaded** when tenant changes."

The test in `interaction-principles.test.ts` ("schema browser clears cached labels on tenant switch") verifies that `nodeLabels`, `edgeLabels`, and `schemaCache` are cleared. However, the watch handler in `pages/graph/schema.vue` also calls `fetchNodeLabels()` and `fetchEdgeLabels()` — these calls have **no test coverage**.

**Fix needed**: Add tests to `app/tests/schema-browser.test.ts` in a new "Schema Browser — tenant switch reloads data" block that verify: (1) labels cleared immediately on tenant change, and (2) `fetchNodeLabels` and `fetchEdgeLabels` are called after the clear.

---

## What Passes

- All 804 tests pass (zero failures, zero regressions).
- Implementation is complete and correct for all 9 scoped pages.
- 7 of 9 pages have comprehensive test coverage for tenant-switch reload.
- Navigation structure (Mutations Console in Explore) is fully implemented and tested.
- Tenant selector in sidebar is implemented with accessibility labels and tested.
- Stale-data-clearing-before-reload pattern is correctly implemented everywhere.