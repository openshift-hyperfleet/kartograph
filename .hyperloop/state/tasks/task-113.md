---
id: task-113
title: "Mutations Console — behavioral tests for workspace-scoped KG fetch with edit permission"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): add behavioral tests for mutations console workspace-scoped KG fetch"
pr_description: |
  ## What & Why

  The **Mutations Console** requirement in `specs/ui/experience.spec.md` specifies:

  > "GIVEN a workspace is selected WHEN the user views the mutations console THEN
  > only knowledge graphs the user has `edit` permission on within that workspace
  > are shown in the KG selector"

  The implementation is complete: `mutations.vue` calls
  `/management/knowledge-graphs` with `{ permission: 'edit', workspace_id: <id> }`
  so the backend returns only editable KGs for the selected workspace.

  The existing tests in `src/dev-ui/app/tests/mutations-workspace-selector.test.ts`
  and `mutations-kg-selector.test.ts` verify this behavior via **structural string
  search** — they read the source file and assert the strings `workspace_id` and
  `permission.*edit` appear in it. These are static analysis tests, not behavioral
  tests. They would pass even if:
  - `permission: 'view'` was sent at runtime (wrong permission),
  - `workspace_id` was included in the URL path instead of query params (API mismatch),
  - The KG fetch was triggered before a workspace was selected (fetching all KGs),
  - An unrelated code change accidentally removed the workspace scoping.

  No test currently mounts the Mutations Console component, selects a workspace, and
  asserts that the API call observable at runtime actually carries both query
  parameters with correct values.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Mutations Console** — Scenario: *KG selector shows only
    edit-permissioned KGs for the selected workspace*
  - **Requirement: Backend API Alignment** — Scenario: *Mutations console uses
    `permission=edit` and `workspace_id` query parameters when fetching KG list*

  ## What This Change Does

  Replace (or supplement) the structural string-search tests with behavioral
  component tests that mount the Mutations Console, simulate workspace selection,
  and assert on real HTTP interactions.

  ### Test: `test_kg_fetch_includes_workspace_id_and_edit_permission`

  Setup:
  1. Mount `mutations.vue` using Vitest + Vue Test Utils.
  2. Intercept `$fetch` / `useFetch` calls using MSW (Mock Service Worker) or a
     `vi.mock` of the fetch utility so API calls are captured without real network.
  3. Pre-populate the workspace selector with a test workspace (`id: "ws-123"`).

  Execution:
  - Simulate selecting workspace `"ws-123"` in the workspace dropdown.

  Assertions:
  - Exactly one API call to `/management/knowledge-graphs` was made.
  - The call includes `workspace_id=ws-123` as a query parameter.
  - The call includes `permission=edit` as a query parameter.
  - The call does NOT include `permission=view` or any other permission value.

  ### Test: `test_kg_fetch_not_triggered_before_workspace_selected`

  Setup:
  1. Mount `mutations.vue` with no workspace pre-selected.
  2. Intercept fetch calls as above.

  Execution:
  - Do not interact with the workspace selector.

  Assertions:
  - No API call to `/management/knowledge-graphs` is made (KG list is not fetched
    until a workspace is selected — prevents fetching all KGs across all workspaces).

  ### Test: `test_kg_fetch_re_triggered_when_workspace_changes`

  Setup:
  1. Mount `mutations.vue` with workspace `"ws-alpha"` pre-selected.
  2. Intercept fetch calls, returning an empty KG list for both workspaces.

  Execution:
  - Change the workspace selector to `"ws-beta"`.

  Assertions:
  - A second API call to `/management/knowledge-graphs` is made with `workspace_id=ws-beta`.
  - The KG selector is cleared/reset after the workspace changes (stale KG from
    previous workspace is not retained).

  ## Files / Areas Affected

  - `src/dev-ui/app/tests/mutations-console-kg-fetch.test.ts` (new) — the three
    behavioral test cases described above
  - `src/dev-ui/app/tests/mutations-workspace-selector.test.ts` — optionally mark
    existing structural tests as `test.skip` with a note pointing to the new
    behavioral tests, OR keep both as complementary coverage layers
  - No production code changes expected; if a test reveals a real behavioral bug
    (e.g., workspace_id not actually wired up at runtime), fix `mutations.vue` and
    note it in the PR description

  ## Tests

  The behavioral component tests ARE the deliverable. They should run with:
  ```bash
  cd src/dev-ui && pnpm test
  ```

  No infrastructure required — all API calls are mocked.

  ## How to Verify

  1. `cd src/dev-ui && pnpm test -- mutations-console-kg-fetch`
  2. Confirm all three tests pass green
  3. Temporarily change `permission: 'edit'` to `permission: 'view'` in `mutations.vue`
     and confirm `test_kg_fetch_includes_workspace_id_and_edit_permission` fails
     (validates test is not a false positive)

  ## Caveats

  - If `mutations.vue` uses `$fetch` from Nuxt's `useNuxtApp()`, mocking may require
    providing a stub Nuxt context in the test environment. Check the existing test
    setup in `vitest.config.ts` or `nuxt.config.ts` for the test environment
    configuration.
  - MSW is the preferred interceptor for fetch-based tests; if the project already
    uses a different pattern (e.g., `vi.mock('@/utils/api')`), follow that convention
    to keep the test suite consistent.
  - The `workspace_id` reactive dependency triggering a re-fetch should be tested
    via a watcher or computed — ensure the test advances `nextTick` or uses
    `flushPromises()` after changing the workspace selector value to allow the
    reactive re-fetch to complete.
---
