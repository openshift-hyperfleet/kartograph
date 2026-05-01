---
id: task-054
title: Implement keyboard shortcuts — slash-to-focus-search and discoverable Ctrl/Cmd+Enter
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
  - task-045
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Interaction Principles — Scenario: Keyboard shortcuts** from
`specs/ui/experience.spec.md`:

> GIVEN a power-user action (execute query, focus search)
> THEN a keyboard shortcut is available (Ctrl/Cmd+Enter, /)
> AND the shortcut is discoverable via tooltip or documentation

## Context

Two distinct keyboard shortcuts are required:

1. **`/` (slash)** — focuses the global search or page-level search input.
2. **`Ctrl/Cmd+Enter`** — executes the current query in the Query Console.

- task-016 (complete) implemented the Query Console, which includes a "Run" button. It
  is not confirmed whether Ctrl/Cmd+Enter is wired up or shown in a tooltip.
- task-045 (not-started) adds knowledge-graph context scoping to the Query Console.
  Since task-054 touches the query editor keyboard handling, it must wait for task-045
  to avoid conflicts.
- No task implements the `/` shortcut for search focus.

## Changes Required

### 1. Audit current state

Read the following files to determine PASS/FAIL per shortcut:

- `src/dev-ui/app/pages/query/index.vue` — is `keydown` for `Ctrl+Enter`/`Cmd+Enter`
  already handled? Does the Run button show a keyboard shortcut in its `title` or tooltip?
- `src/dev-ui/app/layouts/default.vue` — is there a global `keydown` listener for `/`
  that focuses a search input?
- `src/dev-ui/app/tests/query-history.test.ts` or similar — do tests assert keyboard shortcut behavior?

### 2. Write tests before implementing (TDD)

Write all tests in `src/dev-ui/app/tests/keyboard-shortcuts.test.ts`:

**Slash-to-focus-search:**
```typescript
import { mount } from '@vue/test-utils'
import AppLayout from '@/layouts/default.vue'
import { userEvent } from '@testing-library/user-event'

describe('Keyboard shortcuts', () => {
  it('pressing "/" focuses the search input', async () => {
    const wrapper = mount(AppLayout, { ... })
    const searchInput = wrapper.find('[data-testid="global-search-input"]')
    await userEvent.keyboard('/')
    expect(document.activeElement).toBe(searchInput.element)
  })

  it('pressing "/" when already typing in an input does not trigger search focus', async () => {
    // User typing in a form field should not re-focus search
    const wrapper = mount(AppLayout, { ... })
    const formInput = wrapper.find('input[data-testid="workspace-name-input"]')
    await formInput.element.focus()
    await userEvent.keyboard('/')
    // Focus should remain on the form input, not move to search
    expect(document.activeElement).toBe(formInput.element)
  })
})
```

**Ctrl/Cmd+Enter — query execution:**
```typescript
import QueryConsolePage from '@/pages/query/index.vue'

describe('Query Console keyboard shortcuts', () => {
  it('Ctrl+Enter executes the current query', async () => {
    const executeQuery = vi.fn()
    const wrapper = mount(QueryConsolePage, {
      global: { provide: { executeQuery } }
    })
    const editor = wrapper.find('[data-testid="query-editor"]')
    await editor.trigger('keydown', { key: 'Enter', ctrlKey: true })
    expect(executeQuery).toHaveBeenCalled()
  })

  it('Cmd+Enter executes the current query on macOS', async () => {
    const executeQuery = vi.fn()
    const wrapper = mount(QueryConsolePage, { ... })
    const editor = wrapper.find('[data-testid="query-editor"]')
    await editor.trigger('keydown', { key: 'Enter', metaKey: true })
    expect(executeQuery).toHaveBeenCalled()
  })

  it('Run button tooltip shows "Ctrl+Enter / Cmd+Enter"', async () => {
    const wrapper = mount(QueryConsolePage, { ... })
    const runButton = wrapper.find('[data-testid="run-query-button"]')
    expect(runButton.attributes('title')).toContain('Ctrl+Enter')
  })
})
```

### 3. Implement the "/" shortcut

Add a global `keydown` handler in `src/dev-ui/app/layouts/default.vue`:

```typescript
onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
})

function handleGlobalKeydown(event: KeyboardEvent) {
  // Only trigger when the user is NOT already typing in an input/textarea/select
  const tag = (event.target as HTMLElement)?.tagName?.toLowerCase()
  if (['input', 'textarea', 'select'].includes(tag)) return
  if (event.key === '/') {
    event.preventDefault()
    const searchInput = document.querySelector<HTMLInputElement>(
      '[data-testid="global-search-input"]'
    )
    searchInput?.focus()
  }
}
```

If no global search input exists in `default.vue`, add a visually subtle search input
(or a command palette trigger button) to the header with `data-testid="global-search-input"`.

### 4. Implement Ctrl/Cmd+Enter discoverability in the Query Console

In `src/dev-ui/app/pages/query/index.vue`:

**Wire the keyboard shortcut** (if not already present):
```typescript
function handleEditorKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    runQuery()
  }
}
```

**Add tooltip to the Run button:**
```html
<Button
  data-testid="run-query-button"
  title="Run query (Ctrl+Enter / Cmd+Enter)"
  @click="runQuery"
>
  <Play class="h-4 w-4" />
  Run
</Button>
```

Or use the shadcn/vue `Tooltip` component if a richer tooltip is preferred:
```html
<TooltipProvider>
  <Tooltip>
    <TooltipTrigger as-child>
      <Button data-testid="run-query-button" @click="runQuery">
        <Play class="h-4 w-4" /> Run
      </Button>
    </TooltipTrigger>
    <TooltipContent>
      Run query
      <kbd class="ml-2 font-mono text-xs">Ctrl+Enter</kbd>
    </TooltipContent>
  </Tooltip>
</TooltipProvider>
```

## Acceptance Criteria

- Pressing `/` from any non-input context focuses the global search input (or command
  palette trigger); pressing `/` while typing in a form field has no effect.
- Pressing `Ctrl+Enter` or `Cmd+Enter` in the Query Console editor triggers `runQuery()`.
- The Query Console Run button has a discoverable tooltip showing `Ctrl+Enter / Cmd+Enter`.
- All tests in `src/dev-ui/app/tests/keyboard-shortcuts.test.ts` pass:
  `cd src/dev-ui && pnpm test`
- No regressions in task-045 (KG context selector in query console) or task-016
  (query execution and history).

## UI Location

- `src/dev-ui/app/layouts/default.vue` — global `/` keydown handler
- `src/dev-ui/app/pages/query/index.vue` — Ctrl/Cmd+Enter handler and Run button tooltip

## Dependencies

- **task-045** must be complete: the KG context selector modifies the query console
  page. Keyboard shortcut wiring in the same file must happen after task-045 lands to
  avoid merge conflicts.

## TDD Cycle

1. Read `pages/query/index.vue` and `layouts/default.vue` — determine PASS/FAIL per
   shortcut.
2. Write failing tests in `tests/keyboard-shortcuts.test.ts`.
3. Implement the `/` handler in `default.vue` and Ctrl/Cmd+Enter wiring + tooltip in
   `pages/query/index.vue`.
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
5. Commit atomically per conventional commit conventions.
