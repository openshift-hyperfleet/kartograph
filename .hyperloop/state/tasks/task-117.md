---
id: task-117
title: Data source connection wizard — behavioral tests for adapter selection and
  connection config
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps: []
round: 1
branch: hyperloop/task-117
pr: https://github.com/openshift-hyperfleet/kartograph/pull/586
pr_title: 'test(ui): add behavioral tests for data source connection wizard (steps
  1-2)'
pr_description: "## What & Why\n\nThe data source connection wizard is fully implemented\
  \ in\n`src/dev-ui/app/pages/data-sources/index.vue`. It walks the user through\n\
  four steps:\n\n1. **Adapter selection** — choose GitHub, GitLab (coming soon), Jira\
  \ (coming soon)\n2. **Connection configuration** — adapter-specific fields (repo\
  \ URL, token, name)\n3. **Intent description** — free-text description of problems\
  \ to solve\n4. **Proposed ontology** — review and approve node/edge type proposals\n\
  \nSteps 3 and 4 are covered separately (task-116). Steps 1 and 2 have **no\ndedicated\
  \ tests**. This PR adds behavioral tests for those steps, satisfying\nthe following\
  \ spec scenarios from `specs/ui/experience.spec.md`:\n\n- **Requirement: Data Source\
  \ Connection** — Scenario: *Adapter type selection*\n- **Requirement: Data Source\
  \ Connection** — Scenario: *Connection configuration*\n- **Requirement: Data Source\
  \ Connection** — Scenario: *Credential handling*\n- **Requirement: Backend API Alignment**\
  \ — Scenario: *Parent context is preserved*\n  (data source creation includes `knowledge_graph_id`)\n\
  \n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n\n**Scenario:\
  \ Adapter type selection**\n> GIVEN a user adding a data source to a knowledge graph\n\
  > WHEN the flow begins\n> THEN the user selects an adapter type first (e.g., GitHub)\n\
  > AND the form adapts to show adapter-specific fields\n\n**Scenario: Connection\
  \ configuration**\n> GIVEN a selected adapter type (e.g., GitHub)\n> WHEN the user\
  \ configures the connection\n> THEN they provide the minimum required fields (e.g.,\
  \ repository URL, access token)\n> AND the system infers defaults where possible\
  \ (e.g., data source name from repo name)\n\n**Scenario: Credential handling**\n\
  > GIVEN credentials provided during data source setup\n> WHEN the data source is\
  \ saved\n> THEN credentials are encrypted and stored server-side\n> AND the plaintext\
  \ is never persisted in the browser\n\n## Key Behaviors to Test\n\nNew file: `src/dev-ui/app/tests/data-source-connection-wizard.test.ts`\n\
  \nTests target pure logic functions extracted from `data-sources/index.vue`\n(following\
  \ the project pattern used in `ontology-add-types.test.ts`) rather\nthan mounting\
  \ the full Nuxt component.\n\n### Group 1: Adapter selection (Step 1)\n\n**`test_github_is_the_only_available_adapter`**\n\
  - The `adapters` array has exactly one entry with `available: true`.\n- That entry\
  \ has `id: 'github'` and `label: 'GitHub'`.\n- GitLab and Jira entries exist but\
  \ `available: false`.\n- This is a regression guard: if a new adapter is added without\
  \ updating\n  the test, the test will catch it.\n\n**`test_unavailable_adapter_cannot_be_selected`**\n\
  - Attempting to set `selectedAdapterId` to an adapter with `available: false`\n\
  \  (e.g., `'gitlab'`) is blocked by the selection guard function.\n- The guard should\
  \ return early or set an error without advancing.\n\n**`test_wizard_requires_adapter_and_kg_before_advancing`**\n\
  - Calling the step-advance function with `selectedAdapterId` empty blocks\n  advancement\
  \ (sets a validation error or returns false).\n- Calling it with `selectedKnowledgeGraphId`\
  \ empty also blocks.\n- Only when both are set does the wizard advance to step 2.\n\
  \n### Group 2: Connection configuration (Step 2)\n\n**`test_name_inferred_from_github_repo_url`**\n\
  - When `connRepoUrl = 'https://github.com/acme/my-service'`, the name\n  inference\
  \ logic sets `connName = 'my-service'`.\n- Test the inference function directly\
  \ (extract as `inferNameFromRepoUrl`\n  if not already a standalone function).\n\
  \n**`test_name_inference_strips_git_suffix`**\n- Input `'https://github.com/org/repo.git'`\
  \ → output `'repo'` (not `'repo.git'`).\n\n**`test_required_fields_validation_blocks_advance`**\n\
  - With `connRepoUrl` empty: step-advance sets `connRepoUrlError` and does not\n\
  \  advance to step 3.\n- With `connName` empty (after clearing the auto-inferred\
  \ value): step-advance\n  sets `connNameError`.\n- With both filled: step-advance\
  \ clears all errors and advances.\n\n**`test_token_field_is_optional`**\n- Advancing\
  \ from step 2 with `connToken` empty succeeds.\n- `connTokenError` remains empty\
  \ when no token is provided.\n\n**`test_repo_url_must_be_valid_url_format`**\n-\
  \ Input `'not-a-url'` triggers `connRepoUrlError` and blocks advancement.\n- Input\
  \ `'https://github.com/org/repo'` passes validation.\n\n### Group 3: Credential\
  \ handling\n\n**`test_token_is_cleared_after_data_source_creation`**\n- Mock the\
  \ API call for data source creation.\n- Call the wizard completion function with\
  \ `connToken = 'secret-token'`.\n- After the API call succeeds, assert `connToken\
  \ === ''`.\n- Verifies the spec: \"the plaintext is never persisted in the browser\"\
  \ — the\n  token is zeroed after use so it does not linger in reactive state (which\n\
  \  could be read from Vue DevTools or a memory dump).\n\n**`test_token_is_not_included_in_local_data_source_state`**\n\
  - After wizard completion, the created `DataSourceItem` added to `dataSources`\n\
  \  ref does not contain a `token` or `credential` property.\n- Only `id`, `name`,\
  \ `adapter_type`, `knowledge_graph_id`, `last_sync_at`,\n  `created_at` are present.\n\
  \n### Group 4: Parent context (Backend API Alignment)\n\n**`test_data_source_creation_includes_knowledge_graph_id`**\n\
  - Mock the `$fetch` / API utility (or the management composable).\n- Set `selectedKnowledgeGraphId\
  \ = 'kg-test-123'` and complete the wizard.\n- Assert the API call body includes\
  \ `{ knowledge_graph_id: 'kg-test-123' }`.\n- Verifies Scenario: Parent context\
  \ is preserved — the KG parent is always\n  sent, never omitted.\n\n## Files / Areas\
  \ Affected\n\n- `src/dev-ui/app/tests/data-source-connection-wizard.test.ts` (new)\n\
  - Possibly `src/dev-ui/app/pages/data-sources/index.vue` or a new\n  `src/dev-ui/app/utils/dataSourceWizard.ts`\
  \ — extract pure functions\n  (`inferNameFromRepoUrl`, step validation logic) following\
  \ the pattern\n  of `src/dev-ui/app/utils/mutationConsole.ts`.\n\n## How to Verify\n\
  \n```bash\ncd src/dev-ui && pnpm test -- data-source-connection-wizard\n```\n\n\
  All tests should pass. If extracting pure functions reveals a bug in the\nexisting\
  \ validation (e.g., URL format check is missing), fix the production\ncode and document\
  \ it in the PR.\n\n## Caveats\n\n- Steps 3 and 4 (intent description and ontology\
  \ review) are covered\n  separately in task-116.\n- The wizard mounting approach\
  \ should follow the project's established\n  pattern (pure function tests over component\
  \ mounting where possible).\n- The credential-clearing test requires mocking the\
  \ API call. If the page\n  uses Nuxt's `$fetch` directly, prefer `vi.mock` of the\
  \ management\n  composable rather than `$fetch` itself.\n- `inferNameFromRepoUrl`\
  \ may not yet exist as a standalone function; it\n  may be inlined in a `watch`\
  \ handler. Extract it as part of this task."
---
