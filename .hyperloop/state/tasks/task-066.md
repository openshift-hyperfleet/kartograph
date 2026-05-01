---
id: task-066
title: Design language — fix font weight violations in page headers and add regression
  tests
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: 'fix(ui): replace font-bold with font-semibold in page headers to comply
  with design language spec'
pr_description: "## What & Why\n\nThe `experience.spec.md` Design Language requirement\
  \ states:\n\n> **Scenario: Typography**\n> - GIVEN any text in the UI\n> - AND font\
  \ weights are limited to regular (400), medium (500), and semibold (600)\n\nEvery\
  \ page-level `<h1>` heading across the dev-UI currently uses the Tailwind class\n\
  `font-bold` (font-weight: 700). This violates the spec's explicit cap of semibold\
  \ (600)\nacross **all** text in the UI.\n\nThe existing typography tests in `design-language.test.ts`\
  \ verify that the `Button` and\n`Badge` UI components do not use `font-bold`, but\
  \ they do not scan page files — leaving\nthe violation undetected by CI.\n\nThis\
  \ PR fixes all violations and adds regression tests that will catch future\nreintroductions.\n\
  \n## Spec Requirements Satisfied\n\n**Requirement: Design Language — Scenario: Typography**\
  \ from\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> GIVEN any text in the UI\n> THEN the system font stack is used (no custom fonts)\n\
  > AND body text uses `text-sm` (0.875rem)\n> AND section headers use uppercase `text-[11px]`\
  \ with `tracking-wider`\n> AND font weights are limited to regular (400), medium\
  \ (500), and semibold (600)\n\nThe constraint \"font weights are limited to regular\
  \ (400), medium (500), and semibold\n(600)\" applies to **any text in the UI**,\
  \ which includes page-level headings.\n\n## Key Design Decisions\n\n- **`font-bold`\
  \ → `font-semibold`**: Page titles are already `text-2xl` — the visual\n  weight\
  \ difference between semibold (600) and bold (700) at 24px is subtle, and the\n\
  \  design is intentionally flat and restrained. `font-semibold` is the heaviest\
  \ weight\n  permitted by the spec and still produces a clearly prominent heading.\n\
  - **Keep `tracking-tight`**: The `tracking-tight` modifier on page headings is\n\
  \  independent of font weight and should be retained for visual consistency.\n-\
  \ **Regression tests scan all page files**: New tests in `design-language.test.ts`\
  \ read\n  each page `.vue` file via `readFileSync` and assert that `font-bold` does\
  \ not appear\n  in template content. This is the same source-inspection approach\
  \ used by the existing\n  typography tests for `Button` and `Badge`.\n\n## Files\
  \ Affected\n\n**Implementation fixes** (replace `font-bold` with `font-semibold`\
  \ in `<h1>` elements):\n\n- `src/dev-ui/app/pages/api-keys/index.vue`\n- `src/dev-ui/app/pages/data-sources/index.vue`\n\
  - `src/dev-ui/app/pages/graph/explorer.vue`\n- `src/dev-ui/app/pages/graph/mutations.vue`\n\
  - `src/dev-ui/app/pages/graph/schema.vue`\n- `src/dev-ui/app/pages/groups/index.vue`\n\
  - `src/dev-ui/app/pages/integrate/mcp.vue`\n- `src/dev-ui/app/pages/knowledge-graphs/index.vue`\n\
  - `src/dev-ui/app/pages/query/index.vue`\n- `src/dev-ui/app/pages/tenants/index.vue`\n\
  - `src/dev-ui/app/pages/workspaces/index.vue`\n- `src/dev-ui/app/pages/index.vue`\
  \ (two occurrences: the page title h1 and a\n  stat card value div that also uses\
  \ `font-bold`)\n\n**Test additions** (new describe block in the existing test file):\n\
  \n- `src/dev-ui/app/tests/design-language.test.ts` — add a describe block that reads\n\
  \  each page file and asserts no `font-bold` class is present. The block must cover\
  \ all\n  11 page files listed above.\n\n## How to Verify\n\n1. Open any page in\
  \ the running dev-UI and inspect the page title (`<h1>`):\n   DevTools → Computed\
  \ → font-weight should read `600`, not `700`.\n2. Run `cd src/dev-ui && pnpm test`\
  \ — the new regression tests pass; no existing\n   tests regress.\n3. Search the\
  \ repo: `grep -r \"font-bold\" src/dev-ui/app/pages/` should return zero\n   matches\
  \ (once this PR lands).\n\n## Caveats\n\n- **Only page files are in scope**: UI\
  \ component files (`components/ui/`) are already\n  guarded by the existing tests\
  \ for `Button` and `Badge`. Non-page component files\n  (`components/graph/`, `components/query/`,\
  \ `components/settings/`) are not scanned\n  by this PR — a follow-up can extend\
  \ the regression tests if future violations are\n  found there.\n- `font-bold` IS\
  \ permitted for contrast-testing fixture data or inline code samples\n  if any exist\
  \ — the tests should use a template-section-scoped check to avoid\n  false positives\
  \ from `<script>` blocks that reference the string as a Tailwind class\n  name in\
  \ logic (unlikely but possible).\n- This change has no backend dependency and no\
  \ API contract implications.\n\n## TDD Cycle\n\n1. **Write failing tests first**\
  \ — add the new describe block to\n   `design-language.test.ts` that asserts no\
  \ `font-bold` in each page file.\n   Run `pnpm test` → tests **fail** for all 11\
  \ page files (RED).\n2. **Fix implementation** — replace `font-bold` with `font-semibold`\
  \ across all 11\n   page files.\n3. **Run tests** → all tests **pass** (GREEN).\n\
  4. **Commit atomically** with a conventional commit message."
---
