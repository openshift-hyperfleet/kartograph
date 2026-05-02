---
id: task-076
title: Mutations Console — test that permission=edit is passed to KG list API
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps:
  - task-074
round: 0
branch: null
pr: null
pr_title: "test(ui): verify permission=edit query param in Mutations Console KG list API call"
pr_description: |
  ## What & Why

  The **Mutations Console — Scenario: Knowledge graph selection** requirement in
  `experience.spec.md` states explicitly:

  > AND the selector lists all knowledge graphs the user has `edit` permission on
  > within the current workspace

  Task-074 added a workspace selector and verified that `workspace_id` is passed
  as a query parameter to the KG list API call. The production code at
  `src/dev-ui/app/pages/graph/mutations.vue` (line ~150) already passes both
  parameters correctly:

  ```typescript
  { query: { permission: 'edit', workspace_id: selectedWorkspaceId.value } },
  ```

  However, `src/dev-ui/app/tests/mutations-workspace-selector.test.ts` only
  verifies `workspace_id`:

  ```typescript
  it('passes workspace_id to the knowledge-graphs API call', () => {
    // Spec: "within the current workspace" — must filter the KG list by workspace
    expect(mutVue).toMatch(/workspace_id|workspaceId/)
  })
  ```

  The `permission: 'edit'` parameter is never verified in any test. Without this
  test, a developer could remove or change the permission parameter without a failing
  test — silently breaking the spec requirement that only KGs the user can *edit* are
  shown (not all KGs they can *read*).

  ## Spec Requirements Satisfied

  **Requirement: Mutations Console — Scenario: Knowledge graph selection**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > AND the selector lists all knowledge graphs the user has `edit` permission on
  > within the current workspace

  Specifically the "edit permission" clause, which task-074 acknowledged in its
  description (`GET /management/knowledge-graphs?workspace_id={id}&permission=edit`)
  but did not test.

  ## Key Design Decisions

  - **Test file**: Extend `src/dev-ui/app/tests/mutations-workspace-selector.test.ts`
    with one additional structural assertion in the existing
    "Mutations Console — workspace selector structural checks" describe block.

  - **Assertion**: `expect(mutVue).toContain("permission: 'edit'")` or
    `expect(mutVue).toMatch(/permission.*edit|edit.*permission/)` — either form
    verifies the parameter is present in the source.

  - **No production code change required**: The production code in `mutations.vue`
    already passes `permission: 'edit'`. This task adds only the missing test.

  - **Why `permission: 'edit'` matters at the UI layer**: The backend uses SpiceDB
    to enforce authorization at submission time. But passing `permission: 'edit'` to
    the management API allows the backend to filter the returned list at *query* time
    (showing only editable KGs), which provides a better UX and prevents the user from
    selecting a KG they cannot edit only to receive a 403 at submission. The UI is
    responsible for sending this parameter correctly.

  ## Files Affected

  - `src/dev-ui/app/tests/mutations-workspace-selector.test.ts` — add one test
    assertion to the "workspace selector structural checks" describe block:

    ```typescript
    it('passes permission=edit to the knowledge-graphs API call', () => {
      // Spec: "the selector lists all knowledge graphs the user has `edit` permission on"
      // The UI must pass permission=edit so the backend returns only KGs the user can edit.
      expect(mutVue).toMatch(/permission.*edit|edit.*permission/)
    })
    ```

  No other files are changed.

  ## How to Verify

  1. Run `cd src/dev-ui && pnpm test` — new test passes green.
  2. Temporarily change `permission: 'edit'` in `mutations.vue` to `permission: 'read'`
     — the new test turns red.
  3. Restore the original value — test goes green again.

  ## TDD Cycle

  1. Add the test to `mutations-workspace-selector.test.ts` (GREEN immediately,
     since the production code already has `permission: 'edit'`).
  2. Optionally do a mutation test (change to `'read'` → red; restore → green).
  3. Commit atomically.

  ## Caveats

  - This task depends on task-074 landing first, as this task extends the test
    file that task-074 introduces.
  - If a future task changes the permission model (e.g., removes client-side
    permission filtering entirely), this test will serve as an explicit reminder
    that removing `permission: 'edit'` is a spec-breaking change.
  - The change is a single test assertion (< 10 lines). No architectural review needed.
---
