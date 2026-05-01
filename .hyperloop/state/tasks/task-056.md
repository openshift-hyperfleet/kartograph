---
id: task-056
title: Audit and verify Dark Mode — header toggle and session-persistent preference
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Dark Mode** — both scenarios from `specs/ui/experience.spec.md`:

### Scenario: Toggle
> GIVEN the user interface
> THEN a dark mode toggle is available in the header
> AND the preference persists across sessions

## Context

The Dark Mode requirement was in the original spec (`774c6c8eb`) — present since the
very first spec commit. task-014 (complete) implemented the design system and navigation.
The `useColorMode` composable and a Moon/Sun toggle button appear to be implemented in
`default.vue` (lines 827–836). Tests exist in
`src/dev-ui/app/tests/color-mode.test.ts`.

However, **no task has formally verified** every spec scenario against the actual
implementation, and the existing tests verify the *logic* inline (not that the toggle is
in the header). This task closes that gap.

## Current Implementation (to verify line-by-line)

### `src/dev-ui/app/composables/useColorMode.ts`

```typescript
const isDark = ref(false)

export function useColorMode() {
  function toggle() {
    isDark.value = !isDark.value
    localStorage.setItem('kartograph-color-mode', isDark.value ? 'dark' : 'light')
    applyMode()
  }

  onMounted(() => {
    const stored = localStorage.getItem('kartograph-color-mode')
    if (stored === 'dark') isDark.value = true
    else if (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      isDark.value = true
    }
    applyMode()
  })

  watch(isDark, applyMode)
  return { isDark, toggle }
}
```

### `src/dev-ui/app/layouts/default.vue` (lines ~827–836)

```html
<!-- Dark mode toggle -->
<Button variant="ghost" size="icon" @click="toggleColorMode">
  <Sun v-if="isDark" class="size-4" />
  <Moon v-else class="size-4" />
</Button>
```

## Changes Required

### 1. Verify every spec scenario line by line

Read the following files:

- `src/dev-ui/app/composables/useColorMode.ts`
- `src/dev-ui/app/layouts/default.vue`

**Scenario: Toggle is available in the header:**
- [ ] A button (or equivalent interactive element) calling `toggleColorMode` is rendered
     inside the header region of `default.vue` (not the sidebar, not a settings page)
- [ ] The button shows the Moon icon when in light mode, Sun icon when in dark mode
- [ ] The button is accessible (has `aria-label` or `title` indicating its purpose)

**Scenario: Preference persists across sessions:**
- [ ] `toggle()` writes `'dark'` or `'light'` to `localStorage.setItem('kartograph-color-mode', ...)`
- [ ] `onMounted` reads `localStorage.getItem('kartograph-color-mode')` and applies the stored mode
- [ ] System preference fallback: when no stored value exists, `window.matchMedia('(prefers-color-scheme: dark)').matches` is checked
- [ ] `applyMode()` adds or removes the `dark` class on `document.documentElement`

### 2. Verify `color-mode.test.ts` covers all gaps

Read `src/dev-ui/app/tests/color-mode.test.ts` and confirm:

- Toggle persistence (write to localStorage): covered ✓
- Init from localStorage: covered ✓
- System preference fallback: covered ✓
- CSS class application on `documentElement`: covered ✓

**Gap: toggle button in the header** — the existing tests verify the *logic* but do not
verify that the toggle button is visually present in the header of the rendered layout.

Write one additional test before fixing any implementation:

```typescript
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

describe('Dark Mode - toggle in header', () => {
  it('default.vue renders a dark mode toggle button in the header', () => {
    const layoutContent = readFileSync(
      resolve(__dirname, '../layouts/default.vue'),
      'utf-8'
    )
    // The toggle button must call toggleColorMode
    expect(layoutContent).toContain('toggleColorMode')
    // It must use Moon and Sun icons from lucide-vue-next
    expect(layoutContent).toContain('Moon')
    expect(layoutContent).toContain('Sun')
    // The toggle must be inside the header (not a settings page)
    // Verify by checking it appears before the main </header> or in the header region
    const toggleIndex = layoutContent.indexOf('toggleColorMode')
    // Should not be -1
    expect(toggleIndex).toBeGreaterThan(-1)
  })

  it('default.vue imports useColorMode composable', () => {
    const layoutContent = readFileSync(
      resolve(__dirname, '../layouts/default.vue'),
      'utf-8'
    )
    expect(layoutContent).toContain('useColorMode')
  })

  it('useColorMode applies "dark" class to documentElement', () => {
    const composableContent = readFileSync(
      resolve(__dirname, '../composables/useColorMode.ts'),
      'utf-8'
    )
    expect(composableContent).toContain('classList.add')
    expect(composableContent).toContain("'dark'")
  })

  it('useColorMode writes to localStorage on toggle', () => {
    const composableContent = readFileSync(
      resolve(__dirname, '../composables/useColorMode.ts'),
      'utf-8'
    )
    expect(composableContent).toContain('localStorage.setItem')
    expect(composableContent).toContain('kartograph-color-mode')
  })
})
```

Add these tests to `src/dev-ui/app/tests/color-mode.test.ts` (append to the existing
file rather than creating a new one).

### 3. Fix accessibility gap (if present)

Verify that the dark mode toggle button in `default.vue` has a discoverable label:

```html
<Button
  variant="ghost"
  size="icon"
  :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
  @click="toggleColorMode"
>
  <Sun v-if="isDark" class="size-4" />
  <Moon v-else class="size-4" />
</Button>
```

Or via a tooltip (already present per existing code at lines 827–836). If a tooltip is
already present, no change is needed.

### 4. Fix any other implementation gaps

For each failing check from step 1:

**Toggle not in header** — move the toggle into the header region of `default.vue`. It
should not be inside the sidebar navigation or a settings dropdown.

**Missing `classList.add('dark')`** — the `applyMode()` function must manipulate
`document.documentElement.classList` (not just a ref) so that Tailwind's dark-mode
utilities (`:is(.dark *) { ... }`) activate.

**Missing system preference fallback** — add `window.matchMedia(...)` check in
`onMounted` when no stored value is present (see current implementation above; this
appears to already be in place).

## Acceptance Criteria

- `default.vue` renders a dark mode toggle button inside the header (not sidebar).
- The button uses Moon/Sun icons and calls `toggleColorMode`.
- Toggling writes `'dark'` or `'light'` to `localStorage('kartograph-color-mode')`.
- On mount, the stored preference is read and the correct mode is applied.
- When no stored preference exists, `window.matchMedia('(prefers-color-scheme: dark)')`
  is used as fallback.
- `applyMode()` adds/removes the `dark` class on `document.documentElement`.
- All tests in `src/dev-ui/app/tests/color-mode.test.ts` pass:
  `cd src/dev-ui && pnpm test`
- No regressions in task-014 layout or task-049 focus ring fixes.

## UI Location

- `src/dev-ui/app/composables/useColorMode.ts` — toggle logic and localStorage persistence
- `src/dev-ui/app/layouts/default.vue` — dark mode toggle button in header

## Dependencies

None. Dark mode is a CSS class concern independent of all backend tasks.

## TDD Cycle

1. Read `useColorMode.ts` and `default.vue`; verify every spec line (step 1 checklist).
2. Add missing tests to `tests/color-mode.test.ts` for any uncovered sub-check.
3. Fix any implementation gaps (accessibility label, toggle placement, etc.).
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
5. Commit atomically per conventional commit conventions.
