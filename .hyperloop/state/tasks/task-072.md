---
id: task-072
title: Backend API Alignment — test UI list auto-refresh after KG and data source
  creation
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps: []
round: 0
branch: hyperloop/task-072
pr: https://github.com/openshift-hyperfleet/kartograph/pull/536
pr_title: 'test(ui): verify UI list reloads automatically after KG and data source
  creation'
pr_description: "## What & Why\n\nThe `experience.spec.md` spec (Requirement: Backend\
  \ API Alignment,\nScenario: Resource operations succeed end-to-end) requires:\n\n\
  > AND the UI reflects the updated state without requiring a manual refresh\n\nBoth\
  \ implementations are already correct:\n\n- `src/dev-ui/app/pages/knowledge-graphs/index.vue`\
  \ — `handleCreate()` calls\n  `await loadKnowledgeGraphs()` after successful creation\
  \ (line 148).\n- `src/dev-ui/app/pages/data-sources/index.vue` — `approveOntology()`\
  \ calls\n  `await loadDataSources()` after successful creation (line 570).\n\nHowever,\
  \ the existing tests in `knowledge-graphs.test.ts` and `data-sources.test.ts`\n\
  use inline-replicated logic functions that strip out the refresh call. Neither test\n\
  suite verifies that the list-loading function is invoked after a successful mutation.\n\
  If a developer removes the `await loadKnowledgeGraphs()` or `await loadDataSources()`\n\
  call, no test catches the regression.\n\nThis PR closes the gap with structural\
  \ source-file tests (using `readFileSync`) — the\nsame pattern already used in `mutations-console.test.ts`\
  \ and `mutations-submission.test.ts`.\n\n## Spec Requirements Satisfied\n\n**Requirement:\
  \ Backend API Alignment — Scenario: Resource operations succeed end-to-end**\nfrom\
  \ `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\n> GIVEN\
  \ a user performs any create, read, update, or delete operation via the UI\n> WHEN\
  \ the operation is submitted\n> THEN the corresponding backend API call succeeds\
  \ (2xx response)\n> AND the UI reflects the updated state without requiring a manual\
  \ refresh\n\nThe \"AND the UI reflects the updated state\" clause is the specific\
  \ condition\nunder test. The parent-context URL requirements are covered by task-068.\n\
  \n## Key Design Decisions\n\n- **Structural tests via `readFileSync`**: Reading\
  \ the `.vue` source and asserting\n  that `await loadKnowledgeGraphs()` and `await\
  \ loadDataSources()` are present in\n  the correct context. This pattern is established\
  \ in `mutations-console.test.ts`\n  lines 43–54. It is simpler than mounting the\
  \ component and avoids Nuxt composable\n  mocking complexity.\n- **Test-only PR**:\
  \ No production code changes. The implementations are already\n  correct.\n- **Added\
  \ to existing test files**: KG refresh test goes in\n  `knowledge-graphs.test.ts`;\
  \ data source refresh test goes in\n  `data-sources.test.ts`.\n\n## Files Affected\n\
  \n- `src/dev-ui/app/tests/knowledge-graphs.test.ts` — new describe block\n  \"Backend\
  \ API Alignment — KG creation: UI list reloads without manual refresh\"\n- `src/dev-ui/app/tests/data-sources.test.ts`\
  \ — new describe block\n  \"Backend API Alignment — data source creation: UI list\
  \ reloads without manual refresh\"\n\n## How to Verify\n\n```bash\ncd src/dev-ui\n\
  pnpm test -- knowledge-graphs   # new describe block passes\npnpm test -- data-sources\
  \       # new describe block passes\npnpm test                       # no regressions\n\
  ```\n\n## Caveats\n\n- Structural tests are brittle to refactoring (rename of `loadKnowledgeGraphs`\n\
  \  would break the test), but this is acceptable given the pattern already used\n\
  \  in the codebase.\n- No dependency on other tasks; this is an orthogonal test-only\
  \ addition."
---
