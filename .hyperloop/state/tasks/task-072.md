---
id: task-072
title: Backend API Alignment — test UI list auto-refresh after KG and data source creation
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): verify UI list reloads automatically after KG and data source creation"
pr_description: |
  ## What & Why

  The `experience.spec.md` spec (Requirement: Backend API Alignment,
  Scenario: Resource operations succeed end-to-end) requires:

  > AND the UI reflects the updated state without requiring a manual refresh

  Both implementations are already correct:

  - `src/dev-ui/app/pages/knowledge-graphs/index.vue` — `handleCreate()` calls
    `await loadKnowledgeGraphs()` after successful creation (line 148).
  - `src/dev-ui/app/pages/data-sources/index.vue` — `approveOntology()` calls
    `await loadDataSources()` after successful creation (line 570).

  However, the existing tests in `knowledge-graphs.test.ts` and `data-sources.test.ts`
  use inline-replicated logic functions that strip out the refresh call. Neither test
  suite verifies that the list-loading function is invoked after a successful mutation.
  If a developer removes the `await loadKnowledgeGraphs()` or `await loadDataSources()`
  call, no test catches the regression.

  This PR closes the gap with structural source-file tests (using `readFileSync`) — the
  same pattern already used in `mutations-console.test.ts` and `mutations-submission.test.ts`.

  ## Spec Requirements Satisfied

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN a user performs any create, read, update, or delete operation via the UI
  > WHEN the operation is submitted
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  The "AND the UI reflects the updated state" clause is the specific condition
  under test. The parent-context URL requirements are covered by task-068.

  ## Key Design Decisions

  - **Structural tests via `readFileSync`**: Reading the `.vue` source and asserting
    that `await loadKnowledgeGraphs()` and `await loadDataSources()` are present in
    the correct context. This pattern is established in `mutations-console.test.ts`
    lines 43–54. It is simpler than mounting the component and avoids Nuxt composable
    mocking complexity.
  - **Test-only PR**: No production code changes. The implementations are already
    correct.
  - **Added to existing test files**: KG refresh test goes in
    `knowledge-graphs.test.ts`; data source refresh test goes in
    `data-sources.test.ts`.

  ## Files Affected

  - `src/dev-ui/app/tests/knowledge-graphs.test.ts` — new describe block
    "Backend API Alignment — KG creation: UI list reloads without manual refresh"
  - `src/dev-ui/app/tests/data-sources.test.ts` — new describe block
    "Backend API Alignment — data source creation: UI list reloads without manual refresh"

  ## How to Verify

  ```bash
  cd src/dev-ui
  pnpm test -- knowledge-graphs   # new describe block passes
  pnpm test -- data-sources       # new describe block passes
  pnpm test                       # no regressions
  ```

  ## Caveats

  - Structural tests are brittle to refactoring (rename of `loadKnowledgeGraphs`
    would break the test), but this is acceptable given the pattern already used
    in the codebase.
  - No dependency on other tasks; this is an orthogonal test-only addition.
---

## Spec Coverage

**Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> AND the UI reflects the updated state without requiring a manual refresh

## Current State

### Knowledge Graph creation — list refresh is implemented but not tested

`src/dev-ui/app/pages/knowledge-graphs/index.vue` — `handleCreate()`:

```typescript
await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
  method: 'POST',
  body: { name: createName.value.trim(), description: ... },
})
toast.success(...)
createDialogOpen.value = false
await loadKnowledgeGraphs()   // ← refreshes list — NOT tested
```

`src/dev-ui/app/tests/knowledge-graphs.test.ts` — the existing inline
`handleCreate()` function (lines 80–107) omits the `loadKnowledgeGraphs()` call.
A developer could delete `await loadKnowledgeGraphs()` from the Vue component
and all existing tests would still pass.

### Data source creation — list refresh is implemented but not tested

`src/dev-ui/app/pages/data-sources/index.vue` — `approveOntology()`:

```typescript
await createDataSource({ kg_id: ..., name: ..., ... })
toast.success(...)
wizardOpen.value = false
await loadDataSources()   // ← refreshes list — NOT tested
```

`src/dev-ui/app/tests/data-sources.test.ts` — the existing inline
`approveOntology()` function (around line 184) omits the `loadDataSources()` call.

## Scope

### TDD — write tests first

**File: `src/dev-ui/app/tests/knowledge-graphs.test.ts`**

Add a new `describe` block using `readFileSync` (same approach as
`mutations-console.test.ts`):

```typescript
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Backend API Alignment: KG creation list refresh ───────────────────────────
//
// Spec: "AND the UI reflects the updated state without requiring a manual refresh"
// Scenario: Resource operations succeed end-to-end
//
// After a successful knowledge graph creation, handleCreate() in
// knowledge-graphs/index.vue must call loadKnowledgeGraphs() to refresh
// the displayed list automatically without requiring a manual page reload.

describe('Backend API Alignment — KG creation: UI list reloads without manual refresh', () => {
  const kgVue = readFileSync(
    resolve(__dirname, '../pages/knowledge-graphs/index.vue'),
    'utf-8',
  )

  it('handleCreate() calls await loadKnowledgeGraphs() after successful creation', () => {
    // The implementation must include this call; without it the list stays stale
    // until the user manually navigates away and back.
    expect(kgVue).toContain('await loadKnowledgeGraphs()')
  })

  it('loadKnowledgeGraphs() is called in the try block (not just on mount)', () => {
    // Must appear inside handleCreate's try block, not only in onMounted/watch.
    // Presence of the string in the file is sufficient — structural test.
    const tryBlockIdx = kgVue.indexOf('try {')
    const loadCallIdx = kgVue.indexOf('await loadKnowledgeGraphs()')
    expect(loadCallIdx).toBeGreaterThan(tryBlockIdx)
  })
})
```

**File: `src/dev-ui/app/tests/data-sources.test.ts`**

```typescript
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Backend API Alignment: data source creation list refresh ──────────────────
//
// Spec: "AND the UI reflects the updated state without requiring a manual refresh"
// Scenario: Resource operations succeed end-to-end
//
// After approveOntology() successfully creates a data source, the page calls
// loadDataSources() to refresh the displayed list automatically.

describe('Backend API Alignment — data source creation: UI list reloads without manual refresh', () => {
  const dsVue = readFileSync(
    resolve(__dirname, '../pages/data-sources/index.vue'),
    'utf-8',
  )

  it('approveOntology() calls await loadDataSources() after successful creation', () => {
    expect(dsVue).toContain('await loadDataSources()')
  })

  it('loadDataSources() is called in approveOntology try block (not only on mount)', () => {
    // Verify it appears after the createDataSource call
    const createCallIdx = dsVue.indexOf('await createDataSource(')
    const loadCallIdx = dsVue.indexOf('await loadDataSources()')
    expect(loadCallIdx).toBeGreaterThan(createCallIdx)
  })
})
```

Since the production code already contains both `await loadKnowledgeGraphs()` and
`await loadDataSources()` in the correct positions, both test suites will go GREEN
immediately on first run.

## Acceptance Criteria

- New describe block "Backend API Alignment — KG creation: UI list reloads without
  manual refresh" exists in `src/dev-ui/app/tests/knowledge-graphs.test.ts`.
- New describe block "Backend API Alignment — data source creation: UI list reloads
  without manual refresh" exists in `src/dev-ui/app/tests/data-sources.test.ts`.
- All new tests pass.
- `cd src/dev-ui && pnpm test` exits 0 with no regressions.
- Each test has a comment referencing the spec scenario.

## TDD Cycle

1. **Write tests first** — add the new `describe` blocks to the two test files.
2. **Run tests** → should pass GREEN immediately (implementation is already correct).
3. **Commit atomically** with a conventional commit message.
