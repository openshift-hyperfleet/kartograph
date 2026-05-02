---
id: task-075
title: Backend API Alignment — test UI state refresh after CRUD operations
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): verify UI auto-refresh after CRUD — Backend API Alignment scenario"
pr_description: |
  ## What & Why

  The `experience.spec.md` spec defines a **Backend API Alignment** requirement as the
  first and most fundamental requirement. It contains two scenarios; this task addresses
  the one that currently has no test coverage:

  > **Scenario: Resource operations succeed end-to-end**
  > - GIVEN a user performs any create, read, update, or delete operation via the UI
  > - WHEN the operation is submitted
  > - THEN the corresponding backend API call succeeds (2xx response)
  > - AND the UI reflects the updated state without requiring a manual refresh

  The "AND the UI reflects the updated state without requiring a manual refresh" clause
  is specifically about the pattern where, after a successful create/update/delete, the
  component calls its list-loading function (`loadKnowledgeGraphs`, `loadDataSources`,
  `loadWorkspaces`, `loadApiKeys`, etc.) so the user immediately sees the new state
  without having to press F5.

  ### What already exists

  Individual CRUD operations have tests verifying:
  - The API call is made with the correct URL and payload ✓
  - The dialog closes (`createDialogOpen.value = false`) ✓
  - A success toast is shown ✓
  - The error path sets `creating = false` ✓

  ### What is missing

  **No test verifies that after a successful operation, the appropriate list-refresh
  function is called.** For example:

  | Page                  | Operation       | Expected refresh call      | Tested? |
  |-----------------------|-----------------|---------------------------|---------|
  | `knowledge-graphs`    | Create KG       | `loadKnowledgeGraphs()`   | ❌      |
  | `data-sources`        | Create DS       | `loadDataSources()`        | ❌      |
  | `api-keys`            | Create key      | `loadApiKeys()`            | ❌      |
  | `api-keys`            | Revoke key      | `loadApiKeys()`            | ❌      |
  | `workspaces`          | Create workspace| `loadWorkspaces()`         | ❌      |
  | `data-sources`        | Trigger sync    | `loadDataSources()`        | ❌      |

  Without these tests, a regression where a developer removes the refresh call would
  go undetected — the user would have to manually reload the page to see the new state,
  directly violating the spec scenario.

  ### The second scenario ("Parent context is preserved") is already covered

  - `knowledge-graphs.test.ts` line 101: workspace_id in KG creation URL ✓
  - `data-sources.test.ts` line 1175: kg_id in data source creation URL ✓
  - `mutations-kg-selector.test.ts`: KG-scoped mutations URL ✓

  Only the "UI reflects the updated state" scenario needs new tests.

  ## Spec Requirements Satisfied

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > AND the UI reflects the updated state without requiring a manual refresh

  ## Key Design Decisions

  - **Test strategy**: Pure logic tests that replicate the exact `handleCreate`/`handleRevoke`/
    `triggerSync` function signatures from each page component and verify the list-refresh
    function is called after API success. This mirrors the approach used in
    `knowledge-graphs.test.ts` lines 70–163 (API call test) but adds a spy on the
    refresh function.

  - **One test file per page** (extend existing files rather than creating new ones):
    - `knowledge-graphs.test.ts` — add describe block for "list refresh after create"
    - `data-sources.test.ts` — add describe block for "list refresh after create" and
      "list refresh after sync trigger"
    - `api-keys.test.ts` — add describe blocks for "list refresh after create" and
      "list refresh after revoke"
    - `workspace-management.test.ts` — add describe block for "list refresh after create"

  - **Pattern for each test**:
    ```typescript
    it('calls loadKnowledgeGraphs() after successful KG creation', async () => {
      const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new' })
      const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)
      const createName = { value: 'My Graph' }
      const selectedWorkspaceId = { value: 'ws-1' }
      const creating = { value: false }
      const createDialogOpen = { value: true }

      async function handleCreate() {
        if (!selectedWorkspaceId.value || !createName.value.trim()) return
        creating.value = true
        try {
          await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
            method: 'POST',
            body: { name: createName.value.trim() },
          })
          createDialogOpen.value = false
          await loadKnowledgeGraphs()   // ← this is what we're testing
        } finally {
          creating.value = false
        }
      }

      await handleCreate()
      expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
    })
    ```

  - **Negative case**: verify that if the API throws, the refresh function is NOT called
    (preserves stale list state; error is surfaced by the error path toast).

  ## Files Affected

  - `src/dev-ui/app/tests/knowledge-graphs.test.ts` — extend with "list refresh after
    create" describe block (2–3 tests)
  - `src/dev-ui/app/tests/data-sources.test.ts` — extend with "list refresh after
    create/trigger" describe block (2–3 tests)
  - `src/dev-ui/app/tests/api-keys.test.ts` — extend with "list refresh after
    create/revoke" describe block (2–3 tests)
  - `src/dev-ui/app/tests/workspace-management.test.ts` — extend with "list refresh
    after create" describe block (1–2 tests)

  No production code changes are expected. If a test fails it indicates a regression in
  the component where the refresh call was removed; the fix is to restore it in the `.vue`
  file, not to remove the test.

  ## How to Verify

  1. Run `cd src/dev-ui && pnpm test` — all new tests pass green.
  2. Temporarily remove `await loadKnowledgeGraphs()` from `handleCreate()` in
     `knowledge-graphs/index.vue` — the corresponding test should turn red.
  3. Restore the call — tests go green again.
  4. Repeat for each page to confirm the tests are non-trivially tied to the
     implementation.

  ## TDD Cycle

  1. Write all new tests (RED — they currently pass vacuously because the tests don't
     exist yet; but once written, they should pass green immediately since the production
     code already calls the refresh functions).
  2. Run `cd src/dev-ui && pnpm test` — confirm all new tests pass.
  3. Optionally do a mutation test (remove one refresh call, verify red).
  4. Commit atomically.

  ## Caveats

  - This task is deliberately narrow: it only adds tests. No new UI behavior is required.
  - The production code already contains the refresh calls; the task formalizes them as
    verified spec requirements.
  - If any test fails on first run (meaning a refresh call IS missing in the production
    code), that should be treated as a bug to fix in the same PR.
---
