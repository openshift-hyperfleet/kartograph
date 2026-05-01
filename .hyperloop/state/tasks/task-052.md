---
id: task-052
title: Audit and implement Design Language — OKLCH tokens, typography, border radius, elevation
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Design Language** — 4 scenarios from `specs/ui/experience.spec.md`:

### Scenario: Color theme
> GIVEN the Kartograph color palette
> THEN colors are defined as OKLCH CSS custom properties
> AND the primary/brand color is warm amber/orange (`oklch(0.5768 0.2469 29.23)` light, `oklch(0.6857 0.1560 17.57)` dark)
> AND neutral grays form the background, card, and border palette
> AND destructive actions use a coral/red accent
> AND chart/data visualization uses a 5-color palette (amber, blue, purple, yellow, green)

### Scenario: Typography
> GIVEN any text in the UI
> THEN the system font stack is used (no custom fonts)
> AND body text uses `text-sm` (0.875rem)
> AND section headers use uppercase `text-[11px]` with `tracking-wider`
> AND font weights are limited to regular (400), medium (500), and semibold (600)

### Scenario: Border radius
> GIVEN any rounded element
> THEN border radius scales from a base of `0.625rem` (10px)
> AND cards use `rounded-xl`, buttons and inputs use `rounded-md`, badges use `rounded-full`

### Scenario: Elevation
> GIVEN depth/layering
> THEN cards use `shadow-sm` and buttons use `shadow-xs`
> AND depth is minimal — the UI is predominantly flat

## Context

The Design Language requirement was added to `specs/ui/experience.spec.md` in commit
`21b516b59` — **after** task-014 (which implemented the design system) completed against
spec commit `85d49a379a`. The Component library scenario (shadcn/vue, CVA, Lucide) is
assumed implemented by task-014. The 4 scenarios above were never explicitly verified
against the actual implementation.

This task audits the CSS config for exact conformance and implements any gaps.

## Changes Required

### 1. Audit CSS / Tailwind configuration

Read the following files:

- `src/dev-ui/app/assets/css/tailwind.css` (or `main.css` / `globals.css`) — CSS custom
  property definitions
- `src/dev-ui/tailwind.config.ts` — Tailwind theme extension
- Any shadcn/vue component overrides (e.g., `src/dev-ui/app/components/ui/`)

For each scenario, verify:

**Color theme:**
- `--primary` (light): `oklch(0.5768 0.2469 29.23)` — warm amber/orange
- `--primary` (dark): `oklch(0.6857 0.1560 17.57)`
- Background, card, border, and popover use neutral gray OKLCH values
- `--destructive` uses a coral/red OKLCH value
- `--chart-1` through `--chart-5` define the 5-color palette (amber, blue, purple,
  yellow, green) as OKLCH values

**Typography:**
- No `font-family` custom font is loaded (no Google Fonts, no @font-face for custom fonts)
- Default body prose uses `text-sm` (0.875rem) — verify in the base layer or layout
- Section nav/group headers use `text-[11px] tracking-wider uppercase` — verify in
  `layouts/default.vue` or equivalent heading component
- No font weights outside 400, 500, 600 are used in custom components

**Border radius:**
- CSS variable `--radius` is set to `0.625rem` (10px)
- Cards (`.card`, `Card.vue`) use `rounded-xl`
- Buttons (`Button.vue`) and inputs (`Input.vue`) use `rounded-md`
- Badges (`Badge.vue`) use `rounded-full`

**Elevation:**
- Card components use `shadow-sm`
- Button components use `shadow-xs`
- No large shadows (`shadow-md`, `shadow-lg`, `shadow-xl`) appear on cards or buttons

### 2. Write audit tests

Write tests in `src/dev-ui/app/tests/design-language.test.ts` **before** making
any fixes. Each test should mount the relevant component and assert class presence.

```typescript
// Color token presence (CSS custom property)
import { describe, it, expect } from 'vitest'
import { getComputedStyle } from 'happy-dom'  // or jsdom equivalent

describe('Design Language — Color theme', () => {
  it('primary CSS variable is defined in :root', () => {
    // Read CSS from the entry stylesheet and assert --primary is set to oklch(...)
    // OR: import the CSS file as a string and regex-match the property
    expect(rootCss).toContain('--primary: oklch(0.5768 0.2469 29.23)')
  })
})

// Border radius
import { mount } from '@vue/test-utils'
import Card from '@/components/ui/card/Card.vue'
import Button from '@/components/ui/button/Button.vue'
import Badge from '@/components/ui/badge/Badge.vue'

describe('Design Language — Border radius', () => {
  it('Card uses rounded-xl', () => {
    const wrapper = mount(Card)
    expect(wrapper.classes()).toContain('rounded-xl')
  })

  it('Button uses rounded-md', () => {
    const wrapper = mount(Button)
    expect(wrapper.classes()).toContain('rounded-md')
  })

  it('Badge uses rounded-full', () => {
    const wrapper = mount(Badge)
    expect(wrapper.classes()).toContain('rounded-full')
  })
})

// Elevation
describe('Design Language — Elevation', () => {
  it('Card uses shadow-sm', () => {
    const wrapper = mount(Card)
    expect(wrapper.classes()).toContain('shadow-sm')
  })

  it('Button uses shadow-xs', () => {
    const wrapper = mount(Button)
    expect(wrapper.classes()).toContain('shadow-xs')
  })
})

// Typography
import AppLayout from '@/layouts/default.vue'

describe('Design Language — Typography', () => {
  it('nav section headers use text-[11px] tracking-wider uppercase', () => {
    const wrapper = mount(AppLayout, { ... })
    const header = wrapper.find('[data-testid="nav-section-header"]')
    expect(header.classes()).toContain('uppercase')
    expect(header.classes()).toContain('tracking-wider')
  })
})
```

Adapt the test patterns to the actual component file paths found in the codebase.

### 3. Fix implementation gaps

For each failing test:

**Color theme** — Update `src/dev-ui/app/assets/css/tailwind.css` (or equivalent):

```css
:root {
  --primary: oklch(0.5768 0.2469 29.23);
  --primary-foreground: oklch(1 0 0);
  /* ... */
  --chart-1: oklch(0.75 0.15 85);   /* amber */
  --chart-2: oklch(0.65 0.18 220);  /* blue */
  --chart-3: oklch(0.6 0.2 290);    /* purple */
  --chart-4: oklch(0.8 0.18 100);   /* yellow */
  --chart-5: oklch(0.65 0.18 145);  /* green */
}

.dark {
  --primary: oklch(0.6857 0.1560 17.57);
  /* ... */
}
```

**Border radius** — Confirm `tailwind.config.ts`:
```typescript
theme: {
  extend: {
    borderRadius: {
      DEFAULT: 'var(--radius)',  // must be 0.625rem
    }
  }
}
```
And in the CSS: `--radius: 0.625rem;`

**Elevation** — Update `Card.vue`, `Button.vue` classes as needed.

**Typography** — Ensure no custom @font-face or Google Fonts import; body defaults to
the system font stack.

## Acceptance Criteria

- `--primary` in the light `:root` block is exactly `oklch(0.5768 0.2469 29.23)`.
- `--primary` in `.dark` is exactly `oklch(0.6857 0.1560 17.57)`.
- `--destructive` is a coral/red OKLCH value.
- `--chart-1` through `--chart-5` are defined as OKLCH values in the 5 named hue ranges.
- `--radius` CSS variable is `0.625rem`.
- `Card` component has `rounded-xl` and `shadow-sm` classes.
- `Button` component has `rounded-md` and `shadow-xs` classes.
- `Badge` component has `rounded-full` class.
- No custom font face is loaded; body text renders in the system font stack.
- Nav section headers in `default.vue` use `text-[11px] tracking-wider uppercase`.
- All tests in `src/dev-ui/app/tests/design-language.test.ts` pass:
  `cd src/dev-ui && pnpm test`

## UI Location

- `src/dev-ui/app/assets/css/tailwind.css` (or equivalent CSS entry) — CSS custom properties
- `src/dev-ui/tailwind.config.ts` — border radius token
- `src/dev-ui/app/components/ui/card/Card.vue` — rounded-xl, shadow-sm
- `src/dev-ui/app/components/ui/button/Button.vue` — rounded-md, shadow-xs
- `src/dev-ui/app/components/ui/badge/Badge.vue` — rounded-full
- `src/dev-ui/app/layouts/default.vue` — section header typography

## Dependencies

None. CSS token and component class changes are independent of all backend tasks.

## TDD Cycle

1. Read the CSS and component files; determine PASS/FAIL per scenario.
2. Write failing tests in `tests/design-language.test.ts` for each gap.
3. Fix CSS variables, Tailwind config, and component classes.
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
5. Commit atomically per conventional commit conventions.
