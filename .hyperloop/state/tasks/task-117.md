---
id: task-117
title: "Data source connection wizard — behavioral tests for adapter selection and connection config"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): add behavioral tests for data source connection wizard (steps 1-2)"
pr_description: |
  ## What & Why

  The data source connection wizard is fully implemented in
  `src/dev-ui/app/pages/data-sources/index.vue`. It walks the user through
  four steps:

  1. **Adapter selection** — choose GitHub, GitLab (coming soon), Jira (coming soon)
  2. **Connection configuration** — adapter-specific fields (repo URL, token, name)
  3. **Intent description** — free-text description of problems to solve
  4. **Proposed ontology** — review and approve node/edge type proposals

  Steps 3 and 4 are covered separately (task-116). Steps 1 and 2 have **no
  dedicated tests**. This PR adds behavioral tests for those steps, satisfying
  the following spec scenarios from `specs/ui/experience.spec.md`:

  - **Requirement: Data Source Connection** — Scenario: *Adapter type selection*
  - **Requirement: Data Source Connection** — Scenario: *Connection configuration*
  - **Requirement: Data Source Connection** — Scenario: *Credential handling*
  - **Requirement: Backend API Alignment** — Scenario: *Parent context is preserved*
    (data source creation includes `knowledge_graph_id`)

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:

  **Scenario: Adapter type selection**
  > GIVEN a user adding a data source to a knowledge graph
  > WHEN the flow begins
  > THEN the user selects an adapter type first (e.g., GitHub)
  > AND the form adapts to show adapter-specific fields

  **Scenario: Connection configuration**
  > GIVEN a selected adapter type (e.g., GitHub)
  > WHEN the user configures the connection
  > THEN they provide the minimum required fields (e.g., repository URL, access token)
  > AND the system infers defaults where possible (e.g., data source name from repo name)

  **Scenario: Credential handling**
  > GIVEN credentials provided during data source setup
  > WHEN the data source is saved
  > THEN credentials are encrypted and stored server-side
  > AND the plaintext is never persisted in the browser

  ## Key Behaviors to Test

  New file: `src/dev-ui/app/tests/data-source-connection-wizard.test.ts`

  Tests target pure logic functions extracted from `data-sources/index.vue`
  (following the project pattern used in `ontology-add-types.test.ts`) rather
  than mounting the full Nuxt component.

  ### Group 1: Adapter selection (Step 1)

  **`test_github_is_the_only_available_adapter`**
  - The `adapters` array has exactly one entry with `available: true`.
  - That entry has `id: 'github'` and `label: 'GitHub'`.
  - GitLab and Jira entries exist but `available: false`.
  - This is a regression guard: if a new adapter is added without updating
    the test, the test will catch it.

  **`test_unavailable_adapter_cannot_be_selected`**
  - Attempting to set `selectedAdapterId` to an adapter with `available: false`
    (e.g., `'gitlab'`) is blocked by the selection guard function.
  - The guard should return early or set an error without advancing.

  **`test_wizard_requires_adapter_and_kg_before_advancing`**
  - Calling the step-advance function with `selectedAdapterId` empty blocks
    advancement (sets a validation error or returns false).
  - Calling it with `selectedKnowledgeGraphId` empty also blocks.
  - Only when both are set does the wizard advance to step 2.

  ### Group 2: Connection configuration (Step 2)

  **`test_name_inferred_from_github_repo_url`**
  - When `connRepoUrl = 'https://github.com/acme/my-service'`, the name
    inference logic sets `connName = 'my-service'`.
  - Test the inference function directly (extract as `inferNameFromRepoUrl`
    if not already a standalone function).

  **`test_name_inference_strips_git_suffix`**
  - Input `'https://github.com/org/repo.git'` → output `'repo'` (not `'repo.git'`).

  **`test_required_fields_validation_blocks_advance`**
  - With `connRepoUrl` empty: step-advance sets `connRepoUrlError` and does not
    advance to step 3.
  - With `connName` empty (after clearing the auto-inferred value): step-advance
    sets `connNameError`.
  - With both filled: step-advance clears all errors and advances.

  **`test_token_field_is_optional`**
  - Advancing from step 2 with `connToken` empty succeeds.
  - `connTokenError` remains empty when no token is provided.

  **`test_repo_url_must_be_valid_url_format`**
  - Input `'not-a-url'` triggers `connRepoUrlError` and blocks advancement.
  - Input `'https://github.com/org/repo'` passes validation.

  ### Group 3: Credential handling

  **`test_token_is_cleared_after_data_source_creation`**
  - Mock the API call for data source creation.
  - Call the wizard completion function with `connToken = 'secret-token'`.
  - After the API call succeeds, assert `connToken === ''`.
  - Verifies the spec: "the plaintext is never persisted in the browser" — the
    token is zeroed after use so it does not linger in reactive state (which
    could be read from Vue DevTools or a memory dump).

  **`test_token_is_not_included_in_local_data_source_state`**
  - After wizard completion, the created `DataSourceItem` added to `dataSources`
    ref does not contain a `token` or `credential` property.
  - Only `id`, `name`, `adapter_type`, `knowledge_graph_id`, `last_sync_at`,
    `created_at` are present.

  ### Group 4: Parent context (Backend API Alignment)

  **`test_data_source_creation_includes_knowledge_graph_id`**
  - Mock the `$fetch` / API utility (or the management composable).
  - Set `selectedKnowledgeGraphId = 'kg-test-123'` and complete the wizard.
  - Assert the API call body includes `{ knowledge_graph_id: 'kg-test-123' }`.
  - Verifies Scenario: Parent context is preserved — the KG parent is always
    sent, never omitted.

  ## Files / Areas Affected

  - `src/dev-ui/app/tests/data-source-connection-wizard.test.ts` (new)
  - Possibly `src/dev-ui/app/pages/data-sources/index.vue` or a new
    `src/dev-ui/app/utils/dataSourceWizard.ts` — extract pure functions
    (`inferNameFromRepoUrl`, step validation logic) following the pattern
    of `src/dev-ui/app/utils/mutationConsole.ts`.

  ## How to Verify

  ```bash
  cd src/dev-ui && pnpm test -- data-source-connection-wizard
  ```

  All tests should pass. If extracting pure functions reveals a bug in the
  existing validation (e.g., URL format check is missing), fix the production
  code and document it in the PR.

  ## Caveats

  - Steps 3 and 4 (intent description and ontology review) are covered
    separately in task-116.
  - The wizard mounting approach should follow the project's established
    pattern (pure function tests over component mounting where possible).
  - The credential-clearing test requires mocking the API call. If the page
    uses Nuxt's `$fetch` directly, prefer `vi.mock` of the management
    composable rather than `$fetch` itself.
  - `inferNameFromRepoUrl` may not yet exist as a standalone function; it
    may be inlined in a `watch` handler. Extract it as part of this task.
---
