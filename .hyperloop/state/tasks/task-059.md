---
id: task-059
title: Navigation update — add Mutations Console to Explore sidebar group
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Navigation Structure — Scenario: Primary navigation** from
`specs/ui/experience.spec.md`:

> GIVEN an authenticated user
> THEN the sidebar presents navigation grouped as:
>   - **Explore** — Query Console, Schema Browser, Graph Explorer, **Mutations Console**
>   - **Data** — Knowledge Graphs, Data Sources (with sync status)
>   - **Connect** — API Keys, MCP Integration
>   - **Settings** — Workspaces, Groups, Tenants

## Gap

The spec was updated (current working tree) to add "Mutations Console" to the Explore
navigation group. The sidebar was originally implemented by task-014 (complete) against
an older spec version that listed only:

> **Explore** — Query Console, Schema Browser, Graph Explorer

The Mutations Console route (`/graph/mutations`) already exists — it is referenced in
task-048 as the cross-navigation target from the schema browser's third contextual
button. However, the sidebar navigation item linking to it has not been verified or
updated to match the amended spec.

No existing task owns the navigation sidebar update for this change.

## Scope

Read `src/dev-ui/app/layouts/default.vue` and locate the Explore nav group. Verify
whether a "Mutations Console" item pointing to `/graph/mutations` is already present.

### If the item is absent:
- Add a nav item labelled "Mutations Console" to the Explore group, positioned after
  "Graph Explorer" and before the Data group.
- Use an appropriate Lucide icon (e.g., `FileEdit` or `TerminalSquare`).
- The item must link to `/graph/mutations`.

### If the item is present but incorrectly ordered or labelled:
- Reorder and/or relabel to match the spec exactly.

## Changes Required

### 1. `src/dev-ui/app/tests/default.layout.test.ts`

Write (or extend) tests **before** touching the layout (TDD):

1. **Mutations Console appears in Explore group:**
   Assert that the sidebar contains a nav item labelled "Mutations Console" inside the
   "Explore" section — not in any other section.

2. **Mutations Console links to `/graph/mutations`:**
   Assert that the nav item's `href` or router link target is `/graph/mutations`.

3. **Explore group order:**
   Assert that the Explore items appear in the order: Query Console, Schema Browser,
   Graph Explorer, Mutations Console.

### 2. `src/dev-ui/app/layouts/default.vue`

Add or verify the Mutations Console nav item in the Explore group, ensuring correct
position, label, icon, and route target.

## Acceptance Criteria

- The sidebar Explore group lists: Query Console, Schema Browser, Graph Explorer,
  Mutations Console — in that order.
- The Mutations Console nav item links to `/graph/mutations`.
- The item uses a Lucide icon consistent with the design system (shadcn/vue, Lucide Vue Next).
- Tests assert presence, link target, and order.
- All tests pass: `cd src/dev-ui && pnpm test`
- No regressions in task-014 navigation structure.

## UI Location

- `src/dev-ui/app/layouts/default.vue` — sidebar nav groups
- `src/dev-ui/app/tests/default.layout.test.ts` — nav structure tests

## TDD Cycle

1. Read `layouts/default.vue` — verify whether the Mutations Console nav item already exists.
2. Read `tests/default.layout.test.ts` — identify any existing Explore group tests.
3. Write failing tests (presence, link, order).
4. Add or fix the nav item in `default.vue`.
5. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
6. Commit atomically per conventional commit conventions.
