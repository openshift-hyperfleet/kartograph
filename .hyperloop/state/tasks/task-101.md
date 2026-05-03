---
id: task-101
title: Implement post-KG-creation data source prompt in UI
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-040]
round: 0
branch: null
pr: null
pr_title: "feat(ui): prompt user to add first data source after knowledge graph creation"
pr_description: |
  ## What & Why

  The **Knowledge Graph Creation** requirement in `specs/ui/experience.spec.md`
  specifies a guided post-creation flow:

  > "AND the user is prompted to add their first data source"

  Currently `src/dev-ui/app/pages/knowledge-graphs/index.vue` creates a knowledge
  graph but drops the user back to the KG list with no onboarding prompt. The spec
  requires the UI to actively guide users toward the next step (adding a data source)
  immediately after creation.

  This is distinct from task-040 ("Fix KG creation — workspace selector and correct
  API endpoint"), which corrects the API call. This task adds the UX flow that runs
  _after_ a successful creation response.

  Task-071 ("Knowledge Graph Creation — test post-creation data source prompt") is
  the test-only counterpart; this task provides the implementation.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md` — **Requirement: Knowledge Graph Creation**:
  - Scenario: *Create knowledge graph* —
    "AND the user is prompted to add their first data source"

  ## Design

  After a successful `POST /management/knowledge-graphs` response:

  1. Show a modal or inline banner on the KG detail view (or KG list entry for the
     new KG) with text such as:
     **"Your knowledge graph was created. Add a data source to start building your
     graph."**
     With a primary action button: **"Add Data Source →"** that navigates to the
     data source creation flow scoped to the new KG.
  2. A secondary **"Skip for now"** link dismisses the prompt.
  3. The prompt does NOT appear when the user revisits the KG later.

  Implementation options (pick one based on existing page patterns):
  - **Option A**: After the `createKG` call resolves, push a query param
    `?created=true&kg_id=<id>` and render an `AlertBanner` on the list page when
    this param is present.
  - **Option B**: Show a success `Dialog` / `Sheet` immediately after creation with
    an "Add Data Source" CTA.

  The preferred option follows whichever pattern is already used on adjacent pages
  (check `data-sources/index.vue` and `workspaces/index.vue` for precedent).

  ## Files Affected

  - `src/dev-ui/app/pages/knowledge-graphs/index.vue`
    — add post-creation prompt (banner or dialog after successful create call)
  - `src/dev-ui/app/components/` (optional)
    — extract a reusable `PostCreationPrompt` component if similar prompts
      are needed elsewhere (data sources, workspaces)

  ## Tests

  Vitest / Vue Test Utils unit test in
  `src/dev-ui/app/tests/` (or adjacent `__tests__/`):
  - `test_post_creation_prompt_shown_after_kg_created`: mock the API response,
    trigger the create form submission, assert the prompt/banner is visible
  - `test_post_creation_prompt_add_data_source_navigates`: click "Add Data Source →",
    assert `useRouter().push` called with the correct data-source creation route
    scoped to the new KG id
  - `test_post_creation_prompt_skip_dismisses`: click "Skip for now", assert prompt
    is hidden and user remains on the KG list

  See task-071 for the associated test spec.

  ## How to Verify

  1. Start the dev environment: `make dev` (or `make instance-up`)
  2. Navigate to `/knowledge-graphs`
  3. Create a new knowledge graph
  4. Confirm the post-creation prompt appears with "Add Data Source" CTA
  5. Click "Add Data Source →" — confirm navigation to the data source creation form
     with the new KG pre-selected
  6. Create a second knowledge graph, click "Skip for now" — confirm dismissal

  ## Caveats

  - If task-040 is not complete, the KG creation API call may fail due to missing
    workspace context. This task depends on task-040.
  - The prompt state should NOT be persisted across sessions — it should only appear
    immediately after the create action in the same navigation context.
  - Do NOT add the prompt to the API key or workspace creation flows without a
    separate task — keep this scoped to knowledge graphs only.
---
