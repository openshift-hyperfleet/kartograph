---
id: task-067
title: Design language — fix font-bold violations in QueryResultsPanel keyboard shortcut badges
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps:
  - task-066
round: 0
branch: null
pr: null
pr_title: "fix(ui): replace font-bold with font-semibold in QueryResultsPanel keyboard shortcut badges"
pr_description: |
  ## What & Why

  The `experience.spec.md` Design Language requirement states:

  > **Scenario: Typography**
  > - GIVEN any text in the UI
  > - AND font weights are limited to regular (400), medium (500), and semibold (600)

  Three keyboard shortcut indicator badges in `QueryResultsPanel.vue` (lines 279, 286, 293)
  use `font-bold` (font-weight: 700), violating the explicit cap of semibold (600) for all
  UI text.

  Task-066 fixed `font-bold` violations in all page files and added regression tests for
  pages. It explicitly deferred component files in its caveats:

  > "Non-page component files (components/graph/, components/query/, components/settings/)
  > are not scanned by this PR — a follow-up can extend the regression tests if future
  > violations are found there."

  This PR is that follow-up. It fixes the three violations in `QueryResultsPanel.vue` and
  extends the regression tests to cover all non-page component `.vue` files.

  ## Spec Requirements Satisfied

  **Requirement: Design Language — Scenario: Typography** from
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN any text in the UI
  > THEN the system font stack is used (no custom fonts)
  > AND font weights are limited to regular (400), medium (500), and semibold (600)

  The phrase "any text in the UI" includes keyboard shortcut indicator badges in component
  files, not only page headings. All three `font-bold` occurrences in `QueryResultsPanel`
  are therefore out of compliance.

  ## Key Design Decisions

  - **`font-bold` → `font-semibold`**: The affected spans are `text-[10px]` numeric
    keyboard shortcut labels shown only when the user holds Alt. At 10px the weight
    difference between 700 and 600 is minimal but the spec is explicit. `font-semibold`
    still produces legible, visually distinct labels.
  - **Regression tests extend to components**: New tests in `design-language.test.ts`
    scan all `.vue` files under `app/components/` using `readFileSync` + `<template>`
    extraction (same technique used by task-066 for pages). This catches future
    reintroductions anywhere in the component tree.
  - **Scope is components only**: Page files are already guarded by task-066's tests.
    This PR adds the complementary component coverage, completing the full-UI audit.

  ## Files Affected

  **Implementation fix:**
  - `src/dev-ui/app/components/query/QueryResultsPanel.vue` — replace all three
    `font-bold` occurrences with `font-semibold` inside the `<template>` block (lines
    279, 286, 293).

  **Test additions:**
  - `src/dev-ui/app/tests/design-language.test.ts` — add a new `describe` block that
    enumerates all `.vue` files under `app/components/` recursively and asserts none
    contain `font-bold` in their `<template>` section.

  ## How to Verify

  1. Open the Query Console (`/query`) and execute any query that returns results.
  2. Hold the Alt key — the Tab labels show numeric badges (1, 2, 3).
  3. Inspect the badge spans in DevTools → Computed → `font-weight` should be `600`.
  4. Run `cd src/dev-ui && pnpm test` — new component typography tests pass; no
     regressions in task-066's page typography tests or any other test.
  5. `grep -r "font-bold" src/dev-ui/app/components/ src/dev-ui/app/pages/` → zero
     matches.

  ## Caveats

  - Depends on task-066 landing first, since this PR extends the testing pattern
    established there and should not duplicate the page-scan logic.
  - The fix is purely cosmetic at `text-[10px]` — no functional or accessibility
    regression expected.
  - Only component `.vue` files are added to the regression tests; layout files
    (`app/layouts/`) are not scanned by either task-066 or this PR. The layout
    (`default.vue`) does not use `font-bold` (confirmed by grep), so this is a
    known acceptable scope limit.
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

### Three `font-bold` occurrences in `QueryResultsPanel.vue`

`src/dev-ui/app/components/query/QueryResultsPanel.vue` contains three keyboard
shortcut badge spans at lines 279, 286, and 293:

```html
<!-- Line 279 — Tab 1 "Table" shortcut indicator -->
<span v-if="altHeld"
  class="mr-1 inline-flex size-4 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">
  1
</span>

<!-- Line 286 — Tab 2 "JSON" shortcut indicator -->
<span v-if="altHeld"
  class="mr-1 inline-flex size-4 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">
  2
</span>

<!-- Line 293 — Tab 3 "Graph" shortcut indicator (shown only when graph data exists) -->
<span v-if="altHeld && hasGraphElements"
  class="mr-1 inline-flex size-4 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">
  3
</span>
```

All three use `font-bold` (700 weight). The spec caps all text at semibold (600).

### No regression test covers component files

Task-066 added tests that scan page files (`app/pages/**/*.vue`) for `font-bold`. The
tests in `design-language.test.ts` do not scan `app/components/`. The three violations
above are invisible to the current test suite.

Task-066 explicitly noted this in its caveats:
> "Non-page component files (components/graph/, components/query/, components/settings/)
>  are not scanned by this PR — a follow-up can extend the regression tests if future
>  violations are found there."

This task is that follow-up.

## Scope

### TDD — write failing tests first

Add a new `describe` block to `src/dev-ui/app/tests/design-language.test.ts`:

```typescript
import { readdirSync, readFileSync } from 'fs'
import { resolve } from 'path'

// ── Scenario: Typography — font weight constraints in component files ──────────
//
// Spec: "font weights are limited to regular (400), medium (500), and semibold (600)"
// Applied to "any text in the UI" — including component template content.

const componentsDir = resolve(__dirname, '../components')

function collectVueFiles(dir: string): string[] {
  const entries = readdirSync(dir, { withFileTypes: true })
  const files: string[] = []
  for (const entry of entries) {
    const full = resolve(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...collectVueFiles(full))
    } else if (entry.name.endsWith('.vue')) {
      files.push(full)
    }
  }
  return files
}

const componentFiles = collectVueFiles(componentsDir)

describe('Design Language - typography: no font-bold (700) in component files', () => {
  for (const filePath of componentFiles) {
    const relativeName = filePath.split('/components/')[1]
    it(`components/${relativeName} does not use font-bold (max semibold per spec)`, () => {
      const content = readFileSync(filePath, 'utf-8')
      const templateMatch = content.match(/<template>([\s\S]*)<\/template>/)
      const templateContent = templateMatch ? templateMatch[1] : content
      expect(templateContent).not.toContain('font-bold')
    })
  }
})
```

Running `pnpm test` at this point → **RED** (3 failures for `QueryResultsPanel.vue`).

### Implementation — replace font-bold with font-semibold

In `src/dev-ui/app/components/query/QueryResultsPanel.vue`, replace all three
`font-bold` occurrences with `font-semibold`. The pattern is:

```
text-[10px] font-bold text-primary-foreground
```

becomes:

```
text-[10px] font-semibold text-primary-foreground
```

Running `pnpm test` after fixes → **GREEN** (all tests pass, no regressions).

## Acceptance Criteria

- `grep -r "font-bold" src/dev-ui/app/components/` returns zero matches.
- New component typography tests in `design-language.test.ts` pass.
- Task-066's page typography tests continue to pass.
- All other pre-existing tests continue to pass (`pnpm test` exits 0).
- Keyboard shortcut badges (Alt+1, Alt+2, Alt+3) in the Query Console remain
  visually legible at `font-semibold` weight.

## TDD Cycle

1. **Write failing tests first** — add the component scan describe block to
   `design-language.test.ts`. Run `pnpm test` → **RED** (3 failures in
   `QueryResultsPanel.vue`).
2. **Fix implementation** — replace the three `font-bold` occurrences with
   `font-semibold` in `QueryResultsPanel.vue`.
3. **Run tests** → all tests **pass** (GREEN).
4. **Commit atomically** with a conventional commit message.
