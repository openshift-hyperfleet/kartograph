---
id: task-070
title: Keyboard shortcut discoverability — test tooltip and kbd hints
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps: []
round: 3
branch: hyperloop/task-070
pr: https://github.com/openshift-hyperfleet/kartograph/pull/534
pr_title: 'test(ui): verify keyboard shortcuts are discoverable via tooltip and kbd
  hints'
pr_description: "## What & Why\n\nThe `experience.spec.md` spec contains an **Interaction\
  \ Principles —\nScenario: Keyboard shortcuts** requirement:\n\n> **Scenario: Keyboard\
  \ shortcuts**\n> GIVEN a power-user action (execute query, focus search)\n> THEN\
  \ a keyboard shortcut is available (Ctrl/Cmd+Enter, /)\n> AND the shortcut is discoverable\
  \ via tooltip or documentation\n\nThe last clause — **discoverable via tooltip or\
  \ documentation** — is not tested\nanywhere in the current test suite.\n\nThe implementation\
  \ already satisfies it:\n- **Query console** (`pages/query/index.vue`): The Execute\
  \ button has a\n  `<TooltipContent><p>Ctrl+Enter</p></TooltipContent>` and a `<kbd>Enter</kbd>`\n\
  \  hint that appears when Ctrl is held.\n- **Schema browser** (`pages/graph/schema.vue`):\
  \ The search input has a\n  placeholder `\"Filter types and properties...  (/ to\
  \ focus)\"` and a\n  `<kbd>Ctrl+K</kbd>` chip shown on `sm+` screens.\n\nThe functional\
  \ aspects (shortcuts fire correctly) are tested in\n`query-history.test.ts` and\
  \ `schema-browser.test.ts`. What is missing is any\nassertion that the **discoverability\
  \ hints** (tooltip content, kbd element,\nplaceholder text) are present in the templates.\n\
  \n## Spec Requirements Satisfied\n\n**Requirement: Interaction Principles — Scenario:\
  \ Keyboard shortcuts** from\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> AND the shortcut is discoverable via tooltip or documentation\n\n## Key Design\
  \ Decisions\n\n- **Template string matching (static analysis)**: Read the Vue SFC\
  \ files as\n  strings and assert the presence of the tooltip/kbd/placeholder content.\
  \ This\n  is the established codebase pattern used throughout `mutations-console.test.ts`,\n\
  \  `schema-browser.test.ts`, `design-language.test.ts`, etc.\n- **Separate describe\
  \ blocks per page**: Each page's discoverability hints are\n  isolated so failures\
  \ point immediately to the affected file.\n- **No production code changes**: All\
  \ hints are already present; the task is\n  purely test coverage.\n\n## Files Affected\n\
  \n- `src/dev-ui/app/tests/interaction-principles.test.ts` — add a new\n  `describe`\
  \ block \"Interaction Principles — Keyboard shortcut discoverability\"\n  with assertions\
  \ for query console and schema browser.\n\n## How to Verify\n\n1. Run `cd src/dev-ui\
  \ && pnpm test -- interaction-principles` — new describe\n   block passes.\n2. Run\
  \ `cd src/dev-ui && pnpm test` — no regressions.\n3. Confirm tests reference the\
  \ spec scenario in their comments.\n\n## Caveats\n\n- No production code changes.\
  \ The implementation already satisfies the spec.\n- Graph Explorer does not have\
  \ a search keyboard shortcut hint in the current\n  implementation — no assertion\
  \ is added for it (the spec only mentions\n  \"execute query\" and \"focus search\"\
  \ as examples)."
---
