---
id: task-101
title: Implement post-KG-creation data source prompt in UI
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps:
- task-040
round: 0
branch: hyperloop/task-101
pr: https://github.com/openshift-hyperfleet/kartograph/pull/567
pr_title: 'feat(ui): prompt user to add first data source after knowledge graph creation'
pr_description: "## What & Why\n\nThe **Knowledge Graph Creation** requirement in\
  \ `specs/ui/experience.spec.md`\nspecifies a guided post-creation flow:\n\n> \"\
  AND the user is prompted to add their first data source\"\n\nCurrently `src/dev-ui/app/pages/knowledge-graphs/index.vue`\
  \ creates a knowledge\ngraph but drops the user back to the KG list with no onboarding\
  \ prompt. The spec\nrequires the UI to actively guide users toward the next step\
  \ (adding a data source)\nimmediately after creation.\n\nThis is distinct from task-040\
  \ (\"Fix KG creation — workspace selector and correct\nAPI endpoint\"), which corrects\
  \ the API call. This task adds the UX flow that runs\n_after_ a successful creation\
  \ response.\n\nTask-071 (\"Knowledge Graph Creation — test post-creation data source\
  \ prompt\") is\nthe test-only counterpart; this task provides the implementation.\n\
  \n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md` — **Requirement:\
  \ Knowledge Graph Creation**:\n- Scenario: *Create knowledge graph* —\n  \"AND the\
  \ user is prompted to add their first data source\"\n\n## Design\n\nAfter a successful\
  \ `POST /management/knowledge-graphs` response:\n\n1. Show a modal or inline banner\
  \ on the KG detail view (or KG list entry for the\n   new KG) with text such as:\n\
  \   **\"Your knowledge graph was created. Add a data source to start building your\n\
  \   graph.\"**\n   With a primary action button: **\"Add Data Source →\"** that\
  \ navigates to the\n   data source creation flow scoped to the new KG.\n2. A secondary\
  \ **\"Skip for now\"** link dismisses the prompt.\n3. The prompt does NOT appear\
  \ when the user revisits the KG later.\n\nImplementation options (pick one based\
  \ on existing page patterns):\n- **Option A**: After the `createKG` call resolves,\
  \ push a query param\n  `?created=true&kg_id=<id>` and render an `AlertBanner` on\
  \ the list page when\n  this param is present.\n- **Option B**: Show a success `Dialog`\
  \ / `Sheet` immediately after creation with\n  an \"Add Data Source\" CTA.\n\nThe\
  \ preferred option follows whichever pattern is already used on adjacent pages\n\
  (check `data-sources/index.vue` and `workspaces/index.vue` for precedent).\n\n##\
  \ Files Affected\n\n- `src/dev-ui/app/pages/knowledge-graphs/index.vue`\n  — add\
  \ post-creation prompt (banner or dialog after successful create call)\n- `src/dev-ui/app/components/`\
  \ (optional)\n  — extract a reusable `PostCreationPrompt` component if similar prompts\n\
  \    are needed elsewhere (data sources, workspaces)\n\n## Tests\n\nVitest / Vue\
  \ Test Utils unit test in\n`src/dev-ui/app/tests/` (or adjacent `__tests__/`):\n\
  - `test_post_creation_prompt_shown_after_kg_created`: mock the API response,\n \
  \ trigger the create form submission, assert the prompt/banner is visible\n- `test_post_creation_prompt_add_data_source_navigates`:\
  \ click \"Add Data Source →\",\n  assert `useRouter().push` called with the correct\
  \ data-source creation route\n  scoped to the new KG id\n- `test_post_creation_prompt_skip_dismisses`:\
  \ click \"Skip for now\", assert prompt\n  is hidden and user remains on the KG\
  \ list\n\nSee task-071 for the associated test spec.\n\n## How to Verify\n\n1. Start\
  \ the dev environment: `make dev` (or `make instance-up`)\n2. Navigate to `/knowledge-graphs`\n\
  3. Create a new knowledge graph\n4. Confirm the post-creation prompt appears with\
  \ \"Add Data Source\" CTA\n5. Click \"Add Data Source →\" — confirm navigation to\
  \ the data source creation form\n   with the new KG pre-selected\n6. Create a second\
  \ knowledge graph, click \"Skip for now\" — confirm dismissal\n\n## Caveats\n\n\
  - If task-040 is not complete, the KG creation API call may fail due to missing\n\
  \  workspace context. This task depends on task-040.\n- The prompt state should\
  \ NOT be persisted across sessions — it should only appear\n  immediately after\
  \ the create action in the same navigation context.\n- Do NOT add the prompt to\
  \ the API key or workspace creation flows without a\n  separate task — keep this\
  \ scoped to knowledge graphs only."
---
