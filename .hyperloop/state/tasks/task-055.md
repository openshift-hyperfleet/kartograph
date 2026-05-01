---
id: task-055
title: Audit and verify Responsive Design — desktop sidebar collapsible, mobile sheet overlay
spec_ref: specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(ui): verify responsive layout — collapsible sidebar on desktop, sheet overlay on mobile"
pr_description: |
  ## What & Why

  Audits the **Responsive Design** requirement from `specs/ui/experience.spec.md`.
  task-014 implemented the initial layout; this task formally verifies both scenarios
  and fixes any gaps, ensuring the UI is usable on desktop and tablet/mobile.

  ## Spec Requirements Satisfied

  - **Scenario: Desktop layout** — Sidebar visible and collapsible at ≥lg breakpoint;
    content uses multi-column layouts where appropriate.
  - **Scenario: Tablet/mobile layout** — Sidebar collapses to a sheet overlay at narrow
    screens; layouts adapt to single-column.

  ## Key Design Decisions

  - Sidebar collapse uses `useMediaQuery('(min-width: 1024px)')` (VueUse) already in
    `default.vue`; the audit verifies it functions at both breakpoints.
  - Mobile sheet overlay uses shadcn/vue `<Sheet>` component for the sidebar drawer.
  - Content grid classes (`grid-cols-1` on mobile, `lg:grid-cols-2` on desktop) are
    verified across KG, data source, and IAM pages.

  ## Files Affected

  - `src/dev-ui/app/layouts/default.vue` — sidebar collapsible / sheet overlay
  - Page components where column layouts need fixing
  - `src/dev-ui/app/tests/responsive-layout.test.ts` — spec scenario tests

  ## How to Verify

  1. Open dev UI at desktop width → sidebar visible, content multi-column.
  2. Resize to < 1024px → sidebar hidden, hamburger opens sheet overlay.
  3. `cd src/dev-ui && pnpm test` passes.
---

## Spec Coverage

**Requirement: Responsive Design** — both scenarios from `specs/ui/experience.spec.md`:

### Scenario: Desktop layout
> GIVEN a desktop screen
> THEN the sidebar is visible and collapsible
> AND content uses multi-column layouts where appropriate

### Scenario: Tablet/mobile layout
> GIVEN a narrow screen
> THEN the sidebar collapses to a sheet overlay
> AND layouts adapt to single-column

## Context

The Responsive Design requirement was in the original spec (`774c6c8eb`) — present since
the very first spec commit. task-014 (complete) implemented the initial design system and
navigation. The sidebar collapse (`useSidebar.ts`) and mobile sheet (`default.vue`) appear
to have been implemented, and tests exist in `src/dev-ui/app/tests/responsive-design.test.ts`.

However, **no task has formally verified** every spec scenario against the actual
implementation. This task closes that gap.

## Current Implementation (to verify line-by-line)

### `src/dev-ui/app/composables/useSidebar.ts`
- `isCollapsed` ref backed by `localStorage` (`kartograph:sidebar-collapsed`)
- `isMobileOpen` ref
- `toggleCollapsed()`, `toggleMobile()`, `closeMobile()` functions

### `src/dev-ui/app/layouts/default.vue`
- Desktop sidebar: hidden on mobile (`hidden md:flex`), visible on desktop
- Collapsed sidebar width: `w-16`; expanded width: `w-64`
- `transition-all` for smooth collapse/expand animation
- Mobile hamburger menu button (`Menu` icon) triggers `isMobileOpen`
- `<Sheet>` / `<SheetContent>` overlay for mobile navigation

### `src/dev-ui/app/pages/workspaces/index.vue`
- Two-column grid on desktop when a workspace is selected
- `<Sheet>` for detail panel on mobile

## Changes Required

### 1. Verify every spec scenario line by line

Read the following files:

- `src/dev-ui/app/composables/useSidebar.ts`
- `src/dev-ui/app/layouts/default.vue`
- `src/dev-ui/app/pages/workspaces/index.vue`

**Desktop layout — sidebar visible and collapsible:**
- [ ] Sidebar element has `hidden md:flex` (hidden on mobile, flex on desktop `md+`)
- [ ] Collapsed state uses `w-16` class; expanded uses `w-64`
- [ ] Toggle button is present and calls `toggleCollapsed()`
- [ ] `transition-all` or equivalent is present for smooth animation
- [ ] `localStorage` persistence: `kartograph:sidebar-collapsed` key is read on init and
     written on toggle

**Desktop layout — multi-column layouts:**
- [ ] At least one content page (e.g., workspaces) uses `lg:grid-cols-*` for detail panel
- [ ] The multi-column class is conditional (only when detail panel is open)

**Tablet/mobile — sidebar collapses to sheet overlay:**
- [ ] `<Sheet>` or `<SheetContent>` is used for mobile navigation (not a push layout)
- [ ] Mobile hamburger button (`Menu` icon) is present in the header area and shown only
     on mobile (`md:hidden` or equivalent)
- [ ] Clicking the hamburger opens the sheet (`isMobileOpen = true`)
- [ ] Navigating to a page (route change) closes the mobile sheet (`closeMobile()`)

**Tablet/mobile — layouts adapt to single-column:**
- [ ] On mobile, workspace detail opens in `<Sheet>` instead of side panel
- [ ] No content uses fixed multi-column classes without responsive prefixes (e.g., no
     bare `grid-cols-2` that would break on mobile)

### 2. Verify `responsive-design.test.ts` covers all gaps

Read `src/dev-ui/app/tests/responsive-design.test.ts` and confirm each sub-check above
is covered by at least one test. For any gap, write the missing test **before** fixing
implementation.

Scenarios that may need additional test coverage:
- `localStorage` persistence of collapsed state (read on init + write on toggle)
- Route change closes mobile sheet (if wired up via `watch(route, closeMobile)`)
- No bare `grid-cols-2` without responsive prefix (static content audit)

### 3. Fix implementation gaps

For any scenario that fails:

**Sidebar persistence** — if `isCollapsed` is not read from `localStorage` on init:
```typescript
// useSidebar.ts
const isCollapsed = ref(localStorage.getItem('kartograph:sidebar-collapsed') === 'true')

function toggleCollapsed() {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('kartograph:sidebar-collapsed', String(isCollapsed.value))
}
```

**Route-change closes mobile sheet** — if not wired up:
```typescript
// layouts/default.vue
import { watch } from 'vue'
const route = useRoute()
watch(() => route.path, () => { closeMobile() })
```

**Missing single-column mobile fallback** — if a page uses bare `grid-cols-2`:
- Replace with `grid-cols-1 lg:grid-cols-2` (or the appropriate breakpoint)

## Acceptance Criteria

- Sidebar has `hidden md:flex` so it is hidden on `<md` screens and visible on `md+`.
- Collapsed sidebar uses `w-16`; expanded uses `w-64`; `transition-all` is present.
- Toggle button writes the new collapsed state to `localStorage`.
- Mobile hamburger button (`md:hidden` or equivalent) opens the `<Sheet>` navigation.
- Route change closes the mobile sheet (tested by `watch(route, closeMobile)`).
- At least one content page uses a responsive grid (`lg:grid-cols-*`) with mobile
  fallback to single-column.
- All tests in `src/dev-ui/app/tests/responsive-design.test.ts` pass:
  `cd src/dev-ui && pnpm test`
- No regressions in task-014 navigation or task-049 focus ring fixes.

## UI Location

- `src/dev-ui/app/composables/useSidebar.ts` — collapse/mobile state
- `src/dev-ui/app/layouts/default.vue` — sidebar, mobile sheet, hamburger button
- `src/dev-ui/app/pages/workspaces/index.vue` — multi-column grid example

## Dependencies

None. Responsive design is a CSS/layout concern independent of all backend tasks.

## TDD Cycle

1. Read each file listed above; verify every spec line (step 1 checklist).
2. Read `responsive-design.test.ts`; write missing tests for any uncovered sub-check.
3. Fix any implementation gaps.
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
5. Commit atomically per conventional commit conventions.
