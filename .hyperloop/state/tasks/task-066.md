---
id: task-066
title: Design language — fix font weight violations in page headers and add regression tests
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(ui): replace font-bold with font-semibold in page headers to comply with design language spec"
pr_description: |
  ## What & Why

  The `experience.spec.md` Design Language requirement states:

  > **Scenario: Typography**
  > - GIVEN any text in the UI
  > - AND font weights are limited to regular (400), medium (500), and semibold (600)

  Every page-level `<h1>` heading across the dev-UI currently uses the Tailwind class
  `font-bold` (font-weight: 700). This violates the spec's explicit cap of semibold (600)
  across **all** text in the UI.

  The existing typography tests in `design-language.test.ts` verify that the `Button` and
  `Badge` UI components do not use `font-bold`, but they do not scan page files — leaving
  the violation undetected by CI.

  This PR fixes all violations and adds regression tests that will catch future
  reintroductions.

  ## Spec Requirements Satisfied

  **Requirement: Design Language — Scenario: Typography** from
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN any text in the UI
  > THEN the system font stack is used (no custom fonts)
  > AND body text uses `text-sm` (0.875rem)
  > AND section headers use uppercase `text-[11px]` with `tracking-wider`
  > AND font weights are limited to regular (400), medium (500), and semibold (600)

  The constraint "font weights are limited to regular (400), medium (500), and semibold
  (600)" applies to **any text in the UI**, which includes page-level headings.

  ## Key Design Decisions

  - **`font-bold` → `font-semibold`**: Page titles are already `text-2xl` — the visual
    weight difference between semibold (600) and bold (700) at 24px is subtle, and the
    design is intentionally flat and restrained. `font-semibold` is the heaviest weight
    permitted by the spec and still produces a clearly prominent heading.
  - **Keep `tracking-tight`**: The `tracking-tight` modifier on page headings is
    independent of font weight and should be retained for visual consistency.
  - **Regression tests scan all page files**: New tests in `design-language.test.ts` read
    each page `.vue` file via `readFileSync` and assert that `font-bold` does not appear
    in template content. This is the same source-inspection approach used by the existing
    typography tests for `Button` and `Badge`.

  ## Files Affected

  **Implementation fixes** (replace `font-bold` with `font-semibold` in `<h1>` elements):

  - `src/dev-ui/app/pages/api-keys/index.vue`
  - `src/dev-ui/app/pages/data-sources/index.vue`
  - `src/dev-ui/app/pages/graph/explorer.vue`
  - `src/dev-ui/app/pages/graph/mutations.vue`
  - `src/dev-ui/app/pages/graph/schema.vue`
  - `src/dev-ui/app/pages/groups/index.vue`
  - `src/dev-ui/app/pages/integrate/mcp.vue`
  - `src/dev-ui/app/pages/knowledge-graphs/index.vue`
  - `src/dev-ui/app/pages/query/index.vue`
  - `src/dev-ui/app/pages/tenants/index.vue`
  - `src/dev-ui/app/pages/workspaces/index.vue`
  - `src/dev-ui/app/pages/index.vue` (two occurrences: the page title h1 and a
    stat card value div that also uses `font-bold`)

  **Test additions** (new describe block in the existing test file):

  - `src/dev-ui/app/tests/design-language.test.ts` — add a describe block that reads
    each page file and asserts no `font-bold` class is present. The block must cover all
    11 page files listed above.

  ## How to Verify

  1. Open any page in the running dev-UI and inspect the page title (`<h1>`):
     DevTools → Computed → font-weight should read `600`, not `700`.
  2. Run `cd src/dev-ui && pnpm test` — the new regression tests pass; no existing
     tests regress.
  3. Search the repo: `grep -r "font-bold" src/dev-ui/app/pages/` should return zero
     matches (once this PR lands).

  ## Caveats

  - **Only page files are in scope**: UI component files (`components/ui/`) are already
    guarded by the existing tests for `Button` and `Badge`. Non-page component files
    (`components/graph/`, `components/query/`, `components/settings/`) are not scanned
    by this PR — a follow-up can extend the regression tests if future violations are
    found there.
  - `font-bold` IS permitted for contrast-testing fixture data or inline code samples
    if any exist — the tests should use a template-section-scoped check to avoid
    false positives from `<script>` blocks that reference the string as a Tailwind class
    name in logic (unlikely but possible).
  - This change has no backend dependency and no API contract implications.

  ## TDD Cycle

  1. **Write failing tests first** — add the new describe block to
     `design-language.test.ts` that asserts no `font-bold` in each page file.
     Run `pnpm test` → tests **fail** for all 11 page files (RED).
  2. **Fix implementation** — replace `font-bold` with `font-semibold` across all 11
     page files.
  3. **Run tests** → all tests **pass** (GREEN).
  4. **Commit atomically** with a conventional commit message.
---

## Spec Coverage

**Requirement: Design Language — Scenario: Typography** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN any text in the UI
> THEN the system font stack is used (no custom fonts)
> AND body text uses `text-sm` (0.875rem)
> AND section headers use uppercase `text-[11px]` with `tracking-wider`
> AND font weights are limited to regular (400), medium (500), and semibold (600)

## Gap

### 1. All page `<h1>` elements use `font-bold` (700 weight)

`grep -rn "font-bold" src/dev-ui/app/pages/` reveals 13 occurrences across 11 page
files:

```
pages/api-keys/index.vue:294:          <h1 class="text-2xl font-bold tracking-tight">API Keys</h1>
pages/data-sources/index.vue:868:      <h1 class="text-2xl font-bold tracking-tight">Data Sources</h1>
pages/graph/explorer.vue:399:          <h1 class="text-2xl font-bold tracking-tight">Graph Explorer</h1>
pages/graph/mutations.vue:404:          <h1 class="text-2xl font-bold tracking-tight">Mutations Console</h1>
pages/graph/schema.vue:267:          <h1 class="text-2xl font-bold tracking-tight">Schema Browser</h1>
pages/groups/index.vue:322:          <h1 class="text-2xl font-bold tracking-tight">Groups</h1>
pages/integrate/mcp.vue:295:          <h1 class="text-2xl font-bold tracking-tight">MCP Integration</h1>
pages/knowledge-graphs/index.vue:180:  <h1 class="text-2xl font-bold tracking-tight">Knowledge Graphs</h1>
pages/query/index.vue:391:          <h1 class="text-2xl font-bold tracking-tight">Cypher Console</h1>
pages/tenants/index.vue:271:          <h1 class="text-2xl font-bold tracking-tight">Tenants</h1>
pages/workspaces/index.vue:397:        <h1 class="text-2xl font-bold tracking-tight">Workspaces</h1>
pages/index.vue:302:            <h1 class="text-2xl font-bold tracking-tight">Welcome to Kartograph</h1>
pages/index.vue:329:              <div class="text-2xl font-bold tracking-tight">  ← stat card value
```

`font-bold` maps to `font-weight: 700`. The spec caps all UI font weights at semibold
(600). Every page title is therefore out of compliance.

### 2. No test coverage guards page files against font-bold

`design-language.test.ts` has tests for `Button` and `Badge` UI components:

```typescript
it('button component does not use font-bold (700) or heavier', () => {
  expect(buttonContent).not.toContain('font-bold')
})
it('badge component does not use font-bold or heavier', () => {
  expect(badgeContent).not.toContain('font-bold')
})
```

Neither this file nor any other test file reads page files and checks for `font-bold`.
The regression is invisible to CI.

## Scope

### TDD — write failing tests first

Add a new `describe` block to
`src/dev-ui/app/tests/design-language.test.ts`:

```typescript
// ── Scenario: Typography — font weight constraints in page files ──────────────
//
// Spec: "font weights are limited to regular (400), medium (500), and semibold (600)"
// Applied to "any text in the UI" — including page-level <h1> headings.

import { readdirSync } from 'fs'

const pagesDir = resolve(__dirname, '../pages')

// Enumerate all .vue files recursively under pages/
function collectPageFiles(dir: string): string[] {
  const entries = readdirSync(dir, { withFileTypes: true })
  const files: string[] = []
  for (const entry of entries) {
    const full = resolve(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...collectPageFiles(full))
    } else if (entry.name.endsWith('.vue')) {
      files.push(full)
    }
  }
  return files
}

const pageFiles = collectPageFiles(pagesDir)

describe('Design Language - typography: no font-bold (700) in page files', () => {
  for (const filePath of pageFiles) {
    const relativeName = filePath.split('/pages/')[1]
    it(`pages/${relativeName} does not use font-bold (max semibold per spec)`, () => {
      const content = readFileSync(filePath, 'utf-8')
      // Extract only the <template> section to avoid false positives from
      // string literals inside <script> that name Tailwind classes
      const templateMatch = content.match(/<template>([\s\S]*)<\/template>/)
      const templateContent = templateMatch ? templateMatch[1] : content
      expect(templateContent).not.toContain('font-bold')
    })
  }
})
```

Running `pnpm test` at this point → **RED** (13 failures across 11 files).

### Implementation — replace font-bold with font-semibold

For each page file, replace every occurrence of `font-bold` inside the `<template>`
block with `font-semibold`. The pattern `text-2xl font-bold tracking-tight` becomes
`text-2xl font-semibold tracking-tight`.

Special care for `pages/index.vue`:
- The `<h1>` welcome heading: `font-bold` → `font-semibold`
- The stat card value div (`text-2xl font-bold tracking-tight` used for numeric
  counts): `font-bold` → `font-semibold`. Stat values displaying large numbers
  should still look distinct; semibold at `text-2xl` is sufficient.

Running `pnpm test` after fixes → **GREEN** (all tests pass, no regressions).

## Acceptance Criteria

- `grep -r "font-bold" src/dev-ui/app/pages/` returns zero matches.
- New tests in `design-language.test.ts` pass, covering all 11 page files.
- All pre-existing tests continue to pass (`pnpm test` exits 0).
- Page headings are visually inspected in the running app — they remain clearly
  prominent at `text-2xl font-semibold`.
