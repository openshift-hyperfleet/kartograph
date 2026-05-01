---
id: task-067
title: Design language — fix font-bold violations in QueryResultsPanel keyboard shortcut
  badges
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps:
- task-066
round: 0
branch: hyperloop/task-067
pr: https://github.com/openshift-hyperfleet/kartograph/pull/529
pr_title: 'fix(ui): replace font-bold with font-semibold in QueryResultsPanel keyboard
  shortcut badges'
pr_description: "## What & Why\n\nThe `experience.spec.md` Design Language requirement\
  \ states:\n\n> **Scenario: Typography**\n> - GIVEN any text in the UI\n> - AND font\
  \ weights are limited to regular (400), medium (500), and semibold (600)\n\nThree\
  \ keyboard shortcut indicator badges in `QueryResultsPanel.vue` (lines 279, 286,\
  \ 293)\nuse `font-bold` (font-weight: 700), violating the explicit cap of semibold\
  \ (600) for all\nUI text.\n\nTask-066 fixed `font-bold` violations in all page files\
  \ and added regression tests for\npages. It explicitly deferred component files\
  \ in its caveats:\n\n> \"Non-page component files (components/graph/, components/query/,\
  \ components/settings/)\n> are not scanned by this PR — a follow-up can extend the\
  \ regression tests if future\n> violations are found there.\"\n\nThis PR is that\
  \ follow-up. It fixes the three violations in `QueryResultsPanel.vue` and\nextends\
  \ the regression tests to cover all non-page component `.vue` files.\n\n## Spec\
  \ Requirements Satisfied\n\n**Requirement: Design Language — Scenario: Typography**\
  \ from\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> GIVEN any text in the UI\n> THEN the system font stack is used (no custom fonts)\n\
  > AND font weights are limited to regular (400), medium (500), and semibold (600)\n\
  \nThe phrase \"any text in the UI\" includes keyboard shortcut indicator badges\
  \ in component\nfiles, not only page headings. All three `font-bold` occurrences\
  \ in `QueryResultsPanel`\nare therefore out of compliance.\n\n## Key Design Decisions\n\
  \n- **`font-bold` → `font-semibold`**: The affected spans are `text-[10px]` numeric\n\
  \  keyboard shortcut labels shown only when the user holds Alt. At 10px the weight\n\
  \  difference between 700 and 600 is minimal but the spec is explicit. `font-semibold`\n\
  \  still produces legible, visually distinct labels.\n- **Regression tests extend\
  \ to components**: New tests in `design-language.test.ts`\n  scan all `.vue` files\
  \ under `app/components/` using `readFileSync` + `<template>`\n  extraction (same\
  \ technique used by task-066 for pages). This catches future\n  reintroductions\
  \ anywhere in the component tree.\n- **Scope is components only**: Page files are\
  \ already guarded by task-066's tests.\n  This PR adds the complementary component\
  \ coverage, completing the full-UI audit.\n\n## Files Affected\n\n**Implementation\
  \ fix:**\n- `src/dev-ui/app/components/query/QueryResultsPanel.vue` — replace all\
  \ three\n  `font-bold` occurrences with `font-semibold` inside the `<template>`\
  \ block (lines\n  279, 286, 293).\n\n**Test additions:**\n- `src/dev-ui/app/tests/design-language.test.ts`\
  \ — add a new `describe` block that\n  enumerates all `.vue` files under `app/components/`\
  \ recursively and asserts none\n  contain `font-bold` in their `<template>` section.\n\
  \n## How to Verify\n\n1. Open the Query Console (`/query`) and execute any query\
  \ that returns results.\n2. Hold the Alt key — the Tab labels show numeric badges\
  \ (1, 2, 3).\n3. Inspect the badge spans in DevTools → Computed → `font-weight`\
  \ should be `600`.\n4. Run `cd src/dev-ui && pnpm test` — new component typography\
  \ tests pass; no\n   regressions in task-066's page typography tests or any other\
  \ test.\n5. `grep -r \"font-bold\" src/dev-ui/app/components/ src/dev-ui/app/pages/`\
  \ → zero\n   matches.\n\n## Caveats\n\n- Depends on task-066 landing first, since\
  \ this PR extends the testing pattern\n  established there and should not duplicate\
  \ the page-scan logic.\n- The fix is purely cosmetic at `text-[10px]` — no functional\
  \ or accessibility\n  regression expected.\n- Only component `.vue` files are added\
  \ to the regression tests; layout files\n  (`app/layouts/`) are not scanned by either\
  \ task-066 or this PR. The layout\n  (`default.vue`) does not use `font-bold` (confirmed\
  \ by grep), so this is a\n  known acceptable scope limit."
---
