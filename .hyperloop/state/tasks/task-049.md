---
id: task-049
title: Fix focus ring inconsistencies — ring-2 → ring-[3px] on custom interactive elements
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Interaction Principles — Scenario: Focus indicators** from
`specs/ui/experience.spec.md`:

> GIVEN an interactive element receiving focus
> THEN a 3px ring in the primary color at 50% opacity is shown
> AND native outlines are suppressed in favor of the ring

## Current State (PARTIAL FAIL)

The shadcn/vue component library components are **correct** — they consistently apply:

```
outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50
```

For example: `Input.vue`, `Button.vue`, `Textarea.vue`, `SelectTrigger.vue` all use
`focus-visible:ring-[3px]` with `ring-ring/50`.

However, several **manually-written interactive elements** (outside the component library)
use `focus-visible:ring-2` (2 Tailwind units = 8px) instead of `ring-[3px]` (3px).
This violates the spec requirement and creates visual inconsistency within the product.

### Affected elements

| File | Line(s) | Current | Correct |
|------|---------|---------|---------|
| `src/dev-ui/app/layouts/default.vue` | 394, 407 | `focus-visible:ring-2` | `focus-visible:ring-[3px]` |
| `src/dev-ui/app/layouts/default.vue` | 638 | `focus-visible:ring-2` | `focus-visible:ring-[3px]` |
| `src/dev-ui/app/pages/integrate/mcp.vue` | 605, 685 | `focus-visible:ring-2` | `focus-visible:ring-[3px]` |
| `src/dev-ui/app/pages/tenants/index.vue` | 333 | `focus-visible:ring-2` | `focus-visible:ring-[3px]` |

`default.vue` lines 394 and 407 affect the tenant selector interactive items in the sidebar.
Line 638 is in the mobile sidebar sheet. The MCP page (605, 685) affects copy and tab
interactive elements. `tenants/index.vue` line 333 affects tenant action buttons.

## Changes Required

### 1. `src/dev-ui/app/tests/focus-ring.test.ts`

Write tests **before** fixing the implementation (TDD):

1. **Tenant selector items use ring-[3px]:**
   Mount the `default.vue` layout (or the isolated tenant selector component). Assert that
   the tenant dropdown items have Tailwind class `focus-visible:ring-[3px]` in their class
   list, NOT `focus-visible:ring-2`.

2. **MCP page interactive elements use ring-[3px]:**
   Mount `integrate/mcp.vue`. Assert that the copy button and tab trigger elements have
   `focus-visible:ring-[3px]`, NOT `focus-visible:ring-2`.

3. **Tenants page action buttons use ring-[3px]:**
   Mount `tenants/index.vue`. Assert that the action buttons have `focus-visible:ring-[3px]`,
   NOT `focus-visible:ring-2`.

> **Note:** If mounting the full layout is impractical in unit tests, add snapshot tests
> or DOM inspection for the rendered class attribute on the relevant elements.

### 2. `src/dev-ui/app/layouts/default.vue`

Replace all occurrences of `focus-visible:ring-2` with `focus-visible:ring-[3px]`:

- Line 394 (tenant selector dropdown item)
- Line 407 (tenant selector dropdown item)
- Line 638 (mobile sidebar sheet interactive element)

Verify that `ring-ring/50` opacity modifier is present alongside each ring class. If any
element uses `focus-visible:ring-2 focus-visible:ring-ring/50`, update to
`focus-visible:ring-[3px] focus-visible:ring-ring/50`.

### 3. `src/dev-ui/app/pages/integrate/mcp.vue`

Replace all occurrences of `focus-visible:ring-2` with `focus-visible:ring-[3px]`:

- Line 605 (copy button / tab trigger)
- Line 685 (copy button / tab trigger)

### 4. `src/dev-ui/app/pages/tenants/index.vue`

Replace all occurrences of `focus-visible:ring-2` with `focus-visible:ring-[3px]`:

- Line 333 (tenant action button)

## Acceptance Criteria

- All manually-written interactive elements use `focus-visible:ring-[3px]` (not `ring-2`).
- `ring-ring/50` is present on every updated element to maintain the 50% opacity requirement.
- `outline-none` or `outline-ring/50` is present on each element to suppress native outlines.
- Visual inspection: focusing any affected element shows a 3px ring at 50% opacity in the
  primary color, consistent with shadcn/vue components.
- All tests in `focus-ring.test.ts` pass: `cd src/dev-ui && pnpm test`.

## UI Location

- `src/dev-ui/app/layouts/default.vue` — sidebar tenant selector, mobile sheet
- `src/dev-ui/app/pages/integrate/mcp.vue` — MCP integration page copy buttons
- `src/dev-ui/app/pages/tenants/index.vue` — tenant management page action buttons

## Dependencies

None. This task can start immediately — it requires no backend changes and does not
depend on any other UI task.

## TDD Cycle

1. Write tests in `src/dev-ui/app/tests/focus-ring.test.ts` — they will fail because
   the affected elements currently have `focus-visible:ring-2`.
2. Replace `ring-2` → `ring-[3px]` in the three affected files.
3. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
4. Commit atomically per conventional commit conventions.
