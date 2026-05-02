---
id: task-071
title: Knowledge Graph Creation — test post-creation data source prompt
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps: []
round: 0
branch: hyperloop/task-071
pr: https://github.com/openshift-hyperfleet/kartograph/pull/535
pr_title: 'test(ui): verify KG creation prompts user to add their first data source'
pr_description: "## What & Why\n\nThe `experience.spec.md` spec (Requirement: Knowledge\
  \ Graph Creation,\nScenario: Create knowledge graph) requires:\n\n> AND the user\
  \ is prompted to add their first data source\n\nThe implementation in `src/dev-ui/app/pages/knowledge-graphs/index.vue`\n\
  correctly fires a toast with a \"Add Data Source\" action button after a\nknowledge\
  \ graph is successfully created:\n\n```typescript\ntoast.success(`Knowledge graph\
  \ \"${createName.value.trim()}\" created`, {\n  description: 'Next: connect a data\
  \ source to start populating your graph.',\n  action: {\n    label: 'Add Data Source',\n\
  \    onClick: () => navigateTo('/data-sources'),\n  },\n  duration: 8000,\n})\n\
  ```\n\nHowever, the existing test in `knowledge-graphs.test.ts` (lines ~70–107)\
  \ only\nasserts the toast *title* (`'Knowledge graph \"Test Graph\" created'`).\
  \ It does not\nassert:\n- The toast `description` text (the visible prompt explaining\
  \ the next step)\n- The toast `action.label` (the \"Add Data Source\" call-to-action\
  \ button)\n- The toast `action.onClick` navigation target (`/data-sources`)\n\n\
  Without these assertions, a developer could inadvertently remove the data-source\n\
  prompt from the toast and no test would catch it.\n\nThis PR closes that gap with\
  \ a pure test addition — no production code changes.\n\n## Spec Requirements Satisfied\n\
  \n**Requirement: Knowledge Graph Creation — Scenario: Create knowledge graph** from\n\
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\n> GIVEN\
  \ a user in a workspace\n> WHEN the user creates a knowledge graph\n> THEN they\
  \ provide a name and description\n> AND the knowledge graph is created within the\
  \ current workspace\n> AND **the user is prompted to add their first data source**\n\
  \nThe existing tests cover all conditions except the final \"AND\" clause. This\
  \ PR\nadds tests for that clause.\n\n## Key Design Decisions\n\n- **Inline test\
  \ function extraction pattern**: Follow the pattern established in\n  `knowledge-graphs.test.ts`\
  \ lines 80–107 — extract `handleCreate()` as a\n  parameterised inline function\
  \ that takes `apiFetch`, `navigateTo`, and toast\n  primitives as injectable parameters.\
  \ This lets the test capture toast arguments\n  and assert their content without\
  \ mounting the full Nuxt component.\n- **Test-only PR**: No production code changes.\
  \ The implementation is already\n  correct.\n- **Added to `knowledge-graphs.test.ts`**:\
  \ Keeps KG creation coverage co-located\n  in the same file.\n\n## Files Affected\n\
  \n- `src/dev-ui/app/tests/knowledge-graphs.test.ts` — new `describe` block\n  \"\
  Knowledge Graph Creation — prompt to add first data source\"\n\n## How to Verify\n\
  \n```bash\ncd src/dev-ui\npnpm test -- knowledge-graphs   # new describe block passes\n\
  pnpm test                       # no regressions in any other test file\n```\n\n\
  ## Caveats\n\n- No dependency on tasks 065–070: this is an orthogonal test-only\
  \ addition.\n- The existing passing tests in `knowledge-graphs.test.ts` must remain\
  \ green;\n  the new describe block is purely additive."
---
