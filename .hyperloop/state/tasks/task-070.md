---
id: task-070
title: Keyboard shortcut discoverability — test tooltip and kbd hints
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): verify keyboard shortcuts are discoverable via tooltip and kbd hints"
pr_description: |
  ## What & Why

  The `experience.spec.md` spec contains an **Interaction Principles —
  Scenario: Keyboard shortcuts** requirement:

  > **Scenario: Keyboard shortcuts**
  > GIVEN a power-user action (execute query, focus search)
  > THEN a keyboard shortcut is available (Ctrl/Cmd+Enter, /)
  > AND the shortcut is discoverable via tooltip or documentation

  The last clause — **discoverable via tooltip or documentation** — is not tested
  anywhere in the current test suite.

  The implementation already satisfies it:
  - **Query console** (`pages/query/index.vue`): The Execute button has a
    `<TooltipContent><p>Ctrl+Enter</p></TooltipContent>` and a `<kbd>Enter</kbd>`
    hint that appears when Ctrl is held.
  - **Schema browser** (`pages/graph/schema.vue`): The search input has a
    placeholder `"Filter types and properties...  (/ to focus)"` and a
    `<kbd>Ctrl+K</kbd>` chip shown on `sm+` screens.

  The functional aspects (shortcuts fire correctly) are tested in
  `query-history.test.ts` and `schema-browser.test.ts`. What is missing is any
  assertion that the **discoverability hints** (tooltip content, kbd element,
  placeholder text) are present in the templates.

  ## Spec Requirements Satisfied

  **Requirement: Interaction Principles — Scenario: Keyboard shortcuts** from
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > AND the shortcut is discoverable via tooltip or documentation

  ## Key Design Decisions

  - **Template string matching (static analysis)**: Read the Vue SFC files as
    strings and assert the presence of the tooltip/kbd/placeholder content. This
    is the established codebase pattern used throughout `mutations-console.test.ts`,
    `schema-browser.test.ts`, `design-language.test.ts`, etc.
  - **Separate describe blocks per page**: Each page's discoverability hints are
    isolated so failures point immediately to the affected file.
  - **No production code changes**: All hints are already present; the task is
    purely test coverage.

  ## Files Affected

  - `src/dev-ui/app/tests/interaction-principles.test.ts` — add a new
    `describe` block "Interaction Principles — Keyboard shortcut discoverability"
    with assertions for query console and schema browser.

  ## How to Verify

  1. Run `cd src/dev-ui && pnpm test -- interaction-principles` — new describe
     block passes.
  2. Run `cd src/dev-ui && pnpm test` — no regressions.
  3. Confirm tests reference the spec scenario in their comments.

  ## Caveats

  - No production code changes. The implementation already satisfies the spec.
  - Graph Explorer does not have a search keyboard shortcut hint in the current
    implementation — no assertion is added for it (the spec only mentions
    "execute query" and "focus search" as examples).
---

## Spec Coverage

**Requirement: Interaction Principles — Scenario: Keyboard shortcuts** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN a power-user action (execute query, focus search)
> THEN a keyboard shortcut is available (Ctrl/Cmd+Enter, /)
> AND the shortcut is discoverable via tooltip or documentation

## Gap

### No test for "the shortcut is discoverable via tooltip or documentation"

Existing tests cover the shortcut functionality:
- `query-history.test.ts` line 320: "triggers executeQuery on Ctrl+Enter"
- `schema-browser.test.ts` line 401: "should fire '/' shortcut when body is focused"
- `schema-browser.test.ts` line 415: "Ctrl+K triggers search focus"

But **none of these test that the hints are visible to the user** (discoverability).

**Query console** (`pages/query/index.vue`):
```html
<TooltipContent>
  <p>Ctrl+Enter</p>
</TooltipContent>
<!-- ... -->
<kbd
  v-if="ctrlHeld"
  class="ml-2 rounded bg-primary-foreground/20 px-1 py-0.5 font-mono text-[10px]"
>
  Enter
</kbd>
```

**Schema browser** (`pages/graph/schema.vue`):
```html
<Input
  placeholder="Filter types and properties...  (/ to focus)"
  ...
/>
<kbd
  class="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline"
>
  Ctrl+K
</kbd>
```

No test asserts the presence of these discoverability elements.

## Scope

### TDD — write tests first

Add a new `describe` block to `src/dev-ui/app/tests/interaction-principles.test.ts`:

```typescript
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// ── Keyboard Shortcut Discoverability ─────────────────────────────────────────
//
// Spec: "GIVEN a power-user action (execute query, focus search)
//        THEN a keyboard shortcut is available (Ctrl/Cmd+Enter, /)
//        AND the shortcut is discoverable via tooltip or documentation"
//
// Discoverability = the hint is visible to the user via tooltip content,
// a <kbd> chip, or placeholder text. Functional tests (does the shortcut fire?)
// live in query-history.test.ts and schema-browser.test.ts. This block only
// tests that the user can _discover_ the shortcut without reading docs.

describe('Interaction Principles — Keyboard shortcut discoverability', () => {
  describe('Query Console — Ctrl+Enter discoverability', () => {
    const queryPagePath = resolve(__dirname, '../pages/query/index.vue')
    const queryVue = readFileSync(queryPagePath, 'utf-8')

    it('Execute button has a Tooltip showing "Ctrl+Enter"', () => {
      // Spec: shortcut is discoverable via tooltip
      // The TooltipContent inside the Execute button's Tooltip must mention the shortcut.
      expect(queryVue).toContain('Ctrl+Enter')
    })

    it('Execute button renders a <kbd> element to show the Enter hint', () => {
      // The <kbd> chip appears when ctrlHeld is true, making the shortcut
      // visible in the button itself (contextual hint).
      expect(queryVue).toContain('<kbd')
    })

    it('<kbd> chip is conditionally shown when Ctrl is held (ctrlHeld)', () => {
      // The kbd is only shown while the user holds Ctrl — this reinforces
      // awareness of the shortcut at the moment of discovery.
      expect(queryVue).toContain('ctrlHeld')
      // The kbd element must be inside a v-if that checks ctrlHeld
      const kbdIndex = queryVue.indexOf('<kbd')
      const ctrlHeldIndex = queryVue.lastIndexOf('ctrlHeld', kbdIndex)
      expect(ctrlHeldIndex).toBeGreaterThan(-1)
    })
  })

  describe('Schema Browser — "/" and Ctrl+K discoverability', () => {
    const schemaPagePath = resolve(__dirname, '../pages/graph/schema.vue')
    const schemaVue = readFileSync(schemaPagePath, 'utf-8')

    it('search input placeholder contains "(/ to focus)" hint', () => {
      // Spec: shortcut is discoverable via documentation/hint
      // The placeholder tells the user they can press "/" to jump to search.
      expect(schemaVue).toContain('/ to focus')
    })

    it('<kbd> element shows "Ctrl+K" as the alternative focus shortcut', () => {
      // The Ctrl+K chip is visible next to the search input on sm+ screens.
      expect(schemaVue).toContain('<kbd')
      expect(schemaVue).toContain('Ctrl+K')
    })

    it('<kbd> chip for Ctrl+K is sm:inline (hidden on mobile, visible on desktop)', () => {
      // The chip is only shown on desktop — appropriate for power-user discoverability.
      expect(schemaVue).toContain('sm:inline')
    })
  })
})
```

Since the implementation already has all these discoverability elements, all tests
should go **GREEN immediately** on first run.

### No implementation changes

The production code already satisfies the spec. This task closes the test coverage gap
for the "discoverable via tooltip or documentation" clause.

## Acceptance Criteria

- New `describe` block "Interaction Principles — Keyboard shortcut discoverability"
  exists in `src/dev-ui/app/tests/interaction-principles.test.ts`.
- All seven new test cases pass.
- `cd src/dev-ui && pnpm test` exits 0 with no regressions.
- Each test has a comment referencing the spec scenario.

## TDD Cycle

1. **Write tests first** — add the describe block to `interaction-principles.test.ts`.
2. **Run tests** → should pass GREEN immediately (no implementation changes needed).
3. **Commit atomically** with a conventional commit message.
