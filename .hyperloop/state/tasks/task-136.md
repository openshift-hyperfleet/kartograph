---
id: task-136
title: "Mutations Console KG selector — component test for edit-permission workspace-scoped KG loading"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-131]
round: 0
branch: null
pr: null
pr_title: "test(ui): add component test for mutations console KG selector workspace-scoped loading"
pr_description: |
  ## What and Why

  The Mutations Console spec requires:

  > **Scenario: Knowledge graph selection**
  > - GIVEN the mutations console
  > - THEN a knowledge graph selector is displayed before the user can submit
  > - AND the selector lists all knowledge graphs the user has `edit` permission
  >   on within the current workspace
  > - AND no submission is possible until a knowledge graph is selected
  > - AND the selected knowledge graph is used as the target for the mutation
  >   submission

  The critical phrase is **"within the current workspace"** with **`edit`
  permission**. The implementation in `pages/graph/mutations.vue` calls:

  ```javascript
  apiFetch('/management/knowledge-graphs', {
    query: { permission: 'edit', workspace_id: selectedWorkspaceId.value },
  })
  ```

  This is the correct API call. But the **existing tests do not verify it**:

  - `mutations-kg-selector.test.ts` tests the pure `isSubmitDisabled()` and
    `buildMutationsUrl()` logic functions — it never makes an API call and does
    not mount the Vue component.
  - `api-alignment.test.ts` verifies URL construction patterns but not the
    mutations console's KG-list-loading behavior specifically.

  Without a component-level test that verifies the API URL used to fetch KGs,
  a developer could change `permission: 'edit'` to `permission: 'view'` (or
  drop the `workspace_id` filter), and no existing test would catch the
  regression. This spec requirement — edit permission, workspace-scoped — is
  security-adjacent: users should only see KGs they can mutate, within the
  workspace they have selected.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Mutations Console — Scenario: Knowledge graph selection**:
    "the selector lists all knowledge graphs the user has `edit` permission on
    within the current workspace"
  - **Requirement: Mutations Console — Scenario: Knowledge graph selection**:
    "no submission is possible until a knowledge graph is selected"
  - **Requirement: Backend API Alignment — Scenario: Parent context is preserved**:
    "the UI includes the parent context required by the API AND the operation
    succeeds"

  ## What This Change Does

  Creates a new test file
  `src/dev-ui/app/tests/mutations-kg-loading.test.ts` with three focused tests.
  All tests read the actual source file content (same pattern as
  `mutations-submission.test.ts`) to verify implementation contracts:

  ### `TestMutationsKGSelectorLoading`

  **`test_kg_list_requests_edit_permission`**

  Read `pages/graph/mutations.vue` source and assert it contains:
  ```
  permission: 'edit'
  ```
  within the KG-loading code path. This confirms the API call uses the
  `edit` permission filter, not `view`.

  **`test_kg_list_scoped_to_selected_workspace`**

  Read `pages/graph/mutations.vue` source and assert it contains:
  ```
  workspace_id: selectedWorkspaceId.value
  ```
  (or equivalent) in the KG-loading API call. This confirms the `workspace_id`
  query parameter is included, scoping the KG list to the current workspace.

  **`test_kg_list_reloaded_when_workspace_changes`**

  Read `pages/graph/mutations.vue` source and assert that:
  1. `loadKnowledgeGraphs` (or equivalent) is called inside a `watch` on
     `selectedWorkspaceId`.
  2. `selectedKnowledgeGraphId` (or equivalent) is reset to `''` when the
     workspace changes — preventing a stale KG selection from the previous
     workspace from being used.

  **`test_submission_disabled_without_kg_selection`**

  Read `pages/graph/mutations.vue` and assert that the submit button's
  `:disabled` binding references both `selectedKnowledgeGraphId` (or equivalent)
  and `editorContent` (or equivalent), confirming the UI gate exists in the
  template.

  **`test_submission_scoped_to_selected_kg`**

  Read `composables/useMutationSubmission.ts` and assert that the
  `submit(knowledgeGraphId, ...)` function call propagates `knowledgeGraphId`
  into the API request URL path (e.g., the URL contains
  `/graph/knowledge-graphs/${knowledgeGraphId}/mutations`).

  ## Files / Areas Affected

  - `src/dev-ui/app/tests/mutations-kg-loading.test.ts` — new test file

  ## How to Verify

  ```bash
  cd src/dev-ui && pnpm test mutations-kg-loading
  ```

  All five tests must pass. Regression checks:
  1. Change `permission: 'edit'` to `permission: 'view'` in `mutations.vue`
     and confirm `test_kg_list_requests_edit_permission` fails.
  2. Remove `workspace_id: selectedWorkspaceId.value` from the API call
     and confirm `test_kg_list_scoped_to_selected_workspace` fails.
  3. Remove the KG reset from the workspace `watch` and confirm
     `test_kg_list_reloaded_when_workspace_changes` fails.

  ## Implementation Notes for the Agent

  - Use `readFileSync` to read the source file, as done in
    `mutations-submission.test.ts`. No component mounting is required — the
    tests verify structural constraints on the source code.
  - Locate the exact variable names in `mutations.vue` before writing assertions:
    `selectedWorkspaceId`, `selectedKnowledgeGraphId`, `loadKnowledgeGraphs`.
  - The `watch(selectedWorkspaceId, ...)` pattern in `mutations.vue` resets
    `selectedKnowledgeGraphId.value = ''` when the workspace changes — look for
    this in the source.
  - Write tests FIRST (TDD). If any assertion fails, fix the production code
    in `mutations.vue` or `useMutationSubmission.ts`, not the test.
  - Do not duplicate assertions from `mutations-kg-selector.test.ts` (which
    covers `isSubmitDisabled()` and URL construction logic) — focus these tests
    on the loading API contract.

  ## Caveats

  - These are source-reading tests (structural constraints), not runtime
    tests. They are fast (no DOM, no network) but may need updating if
    variable names change during a refactor — treat a test failure as a signal
    to verify the renamed code still satisfies the spec.
  - Depends on task-131 for the floating indicator persistence test to be
    complete so the mutations console test suite is coherent; mark as a soft
    dependency (can run independently but should be sequenced after task-131
    in planning).
---
