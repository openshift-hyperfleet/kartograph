---
id: task-057
title: Audit interaction principles — progressive disclosure and inline actions
spec_ref: specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3
status: not-started
phase: null
deps:
  - task-050
  - task-053
round: 0
branch: null
pr: null
pr_title: "fix(ui): enforce progressive disclosure and inline-action patterns across all pages"
pr_description: |
  ## What & Why

  Audits two **Interaction Principles** scenarios from `specs/ui/experience.spec.md`
  not covered by other tasks: progressive disclosure (summary → detail on demand) and
  inline actions (edit in-place, not on a separate page). These patterns directly
  affect perceived UI quality and the "minimal friction" goal stated in the spec purpose.

  ## Spec Requirements Satisfied

  - **Scenario: Progressive disclosure** — Complex information pages show a summary by
    default; detail is revealed on demand via expand, drill-in, or sheet.
  - **Scenario: Inline actions over navigation** — Editable resources (workspace name,
    group name) are edited in-place or in a side panel, not on a separate edit page.

  ## Key Design Decisions

  - Detail reveal uses `<Collapsible>` or `<Sheet>` components from shadcn/vue.
  - Inline editing uses the pattern: click label → becomes `<Input>` → blur/Enter saves.
    Alternatively, a side-panel `<Sheet>` opens with a minimal edit form.
  - No separate `/edit` routes are introduced for resources covered by this requirement.

  ## Files Affected

  - Workspace, group, and user list pages in `src/dev-ui/app/pages/`
  - Data source and KG detail panels
  - `src/dev-ui/app/tests/interaction-principles.test.ts` — spec scenario tests

  ## How to Verify

  1. On the Workspaces page, click a workspace name → edit in-place or sheet opens.
  2. On the sync history panel, complex log entries show a summary; detail revealed on expand.
  3. `cd src/dev-ui && pnpm test` passes.

  ## Caveats

  Depends on task-050 (API alignment) and task-053 (copy/feedback) completing first so
  the pages this task audits are in their correct final state.
---

## Spec Coverage

**Requirement: Interaction Principles** — 2 scenarios from `specs/ui/experience.spec.md`
that are not covered by any existing task (task-049 covers focus indicators, task-053
covers copy-to-clipboard and mutation feedback, task-054 covers keyboard shortcuts):

### Scenario: Progressive disclosure
> GIVEN complex information
> THEN the UI shows a summary by default
> AND detail is revealed on demand (expand, drill-in, sheet)

### Scenario: Inline actions over navigation
> GIVEN an editable resource (workspace name, group name)
> THEN editing happens in-place or in a side panel
> AND the user is not navigated to a separate edit page

## Context

These two scenarios were added to the spec in commit `21b516b59` — after task-014
(which implemented IAM pages) was marked complete. No subsequent task has explicitly
verified either scenario against the actual implementation.

The patterns were presumably implemented in practice (IAM pages use `<Sheet>` panels;
data source/KG pages use expandable rows), but there has been no formal per-scenario
verification or test coverage requirement placed on them.

## Pages to Audit

**Progressive disclosure** — check every page that presents list data with per-item
detail:

| Page | Expected disclosure pattern |
|------|----------------------------|
| `pages/workspaces/index.vue` | Workspace members shown in an expandable section or side panel, not all inline |
| `pages/groups/index.vue` | Group members shown on demand (expand or panel) |
| `pages/api-keys/index.vue` | Key metadata (creation date, last used) visible in compact list; no overflow by default |
| `pages/knowledge-graphs/index.vue` | KG details revealed on row expand or side panel |
| `pages/data-sources/index.vue` | Sync history revealed on row expand; logs revealed on "View Logs" action |
| `pages/graph/schema.vue` | Type properties revealed on expand (already implemented by task-016) |
| `pages/graph/explorer.vue` | Node properties shown in a card; neighbors revealed on "expand" action |

**Inline actions over navigation** — check every page that allows editing a resource:

| Page | Editable resource | Expected pattern |
|------|-------------------|-----------------|
| `pages/workspaces/index.vue` | Workspace name | In-place edit or side sheet; NOT `/workspaces/{id}/edit` navigation |
| `pages/groups/index.vue` | Group name | In-place edit or side sheet; NOT `/groups/{id}/edit` navigation |
| `pages/api-keys/index.vue` | Revoke action | Confirmation dialog inline; NOT a separate page |
| `pages/knowledge-graphs/index.vue` | KG name / description | In-place or side sheet |
| `pages/data-sources/index.vue` | Data source name | In-place or side sheet |

## Changes Required

### 1. Audit implementation (determine PASS/FAIL per scenario per page)

Read the following files and verify:

**Progressive disclosure checks:**
- [ ] Workspace member list is hidden by default; revealed by an expand toggle or sheet trigger
- [ ] Group member list is hidden by default; revealed on demand
- [ ] KG detail (description, workspace) is summarized in the list row; expanded view shows more
- [ ] Data source sync history is collapsed by default; a click or expand reveals the runs
- [ ] Data source sync logs are not shown inline — a "View Logs" action opens a sheet (task-044
     already implements this; verify it actually satisfies progressive disclosure)
- [ ] Schema browser type properties are hidden by default; clicking a type row reveals them
     (task-016 complete; confirm this pattern holds)
- [ ] No page renders all detail fields in an always-expanded state for every list item

**Inline actions checks:**
- [ ] Workspace name edit does not navigate to a separate URL (e.g., no `router.push('/workspaces/edit')`)
- [ ] Group name edit does not navigate to a separate URL
- [ ] All dialogs and edit panels are `<Dialog>`, `<Sheet>`, or inline `<input>` — never a
     full-page route change
- [ ] Confirm that no `<router-link to=".../{id}/edit">` or `navigateTo('.../{id}/edit')`
     exists in any IAM or management page component

### 2. Audit existing tests for scenario coverage

Read the following test files and confirm whether they assert the disclosure/inline patterns:

- `src/dev-ui/app/tests/workspace-management.test.ts`
- `src/dev-ui/app/tests/api-keys.test.ts`
- (any group management test file)

For each gap, write tests **before** fixing implementation.

**Progressive disclosure test patterns:**

```typescript
// Example — workspace members are NOT shown until expanded
describe('Interaction Principles — Progressive disclosure', () => {
  it('workspace member list is hidden by default', async () => {
    const wrapper = await mountWorkspacesPage()
    // Before expanding, member list is not visible
    expect(wrapper.find('[data-testid="workspace-members-list"]').exists()).toBe(false)
  })

  it('workspace member list is revealed after clicking expand', async () => {
    const wrapper = await mountWorkspacesPage()
    await userEvent.click(wrapper.find('[data-testid="expand-workspace"]').element)
    expect(wrapper.find('[data-testid="workspace-members-list"]').exists()).toBe(true)
  })

  it('sync history rows are collapsed by default on the data sources page', async () => {
    const wrapper = await mountDataSourcesPage()
    expect(wrapper.find('[data-testid="sync-run-history"]').isVisible()).toBe(false)
  })
})
```

**Inline actions test patterns:**

```typescript
// Example — workspace name edit opens a sheet, not a page navigation
describe('Interaction Principles — Inline actions', () => {
  it('editing a workspace name opens a sheet instead of navigating', async () => {
    const navigateTo = vi.fn()
    const wrapper = await mountWorkspacesPage({ navigateTo })
    await userEvent.click(wrapper.find('[data-testid="edit-workspace-name"]').element)
    // navigateTo must NOT have been called with an /edit route
    expect(navigateTo).not.toHaveBeenCalledWith(expect.stringContaining('/edit'))
    // The edit panel/dialog must be visible
    expect(wrapper.find('[data-testid="workspace-edit-panel"]').exists()).toBe(true)
  })

  it('editing a group name opens a sheet instead of navigating', async () => {
    const navigateTo = vi.fn()
    const wrapper = await mountGroupsPage({ navigateTo })
    await userEvent.click(wrapper.find('[data-testid="edit-group-name"]').element)
    expect(navigateTo).not.toHaveBeenCalledWith(expect.stringContaining('/edit'))
    expect(wrapper.find('[data-testid="group-edit-panel"]').exists()).toBe(true)
  })
})
```

### 3. Fix implementation gaps

**Progressive disclosure gap** — if a page renders all detail inline for every list item:
- Move detail (member list, sync history, property list) into a collapsible section
  using the shadcn/vue `Collapsible` component or a `v-show` toggle:

```vue
<Collapsible v-model:open="isExpanded[workspace.id]">
  <CollapsibleTrigger as-child>
    <Button variant="ghost" size="sm" data-testid="expand-workspace">
      <ChevronRight :class="isExpanded[workspace.id] ? 'rotate-90' : ''" class="h-4 w-4" />
    </Button>
  </CollapsibleTrigger>
  <CollapsibleContent>
    <div data-testid="workspace-members-list">
      <!-- member rows -->
    </div>
  </CollapsibleContent>
</Collapsible>
```

**Inline actions gap** — if any page navigates to a separate edit URL:
- Replace `navigateTo('/workspaces/' + id + '/edit')` with:
  ```typescript
  editingWorkspaceId.value = id
  editSheetOpen.value = true
  ```
- Ensure an `<Sheet>` or `<Dialog>` is already present on the page to handle the edit
  (most IAM pages implemented by task-014 already use this pattern)

### 4. Static search — confirm no `/edit` route navigations exist

Run a targeted search across all `src/dev-ui/app/pages/` Vue files to confirm no
component navigates to a path ending in `/edit` or `/new` as a full-page route for
resource editing:

```bash
grep -rn "navigateTo.*\/edit\|router.push.*\/edit" src/dev-ui/app/pages/
```

If any results appear, convert each to an in-place sheet/dialog pattern and write a test
that asserts the navigation does not occur.

## Acceptance Criteria

- No page renders all detail fields in an always-expanded state for every list item;
  at minimum workspace members, group members, and sync run history are hidden by default.
- Clicking an expand toggle reveals the detail without a page navigation.
- Editing a workspace name or group name does not call `navigateTo` with an `/edit` path;
  the edit UI opens in a `<Sheet>` or `<Dialog>` on the same page.
- No `navigateTo('.../{id}/edit')` calls exist anywhere in `src/dev-ui/app/pages/`.
- Tests in the relevant test files assert the disclosure and inline-action patterns.
- All tests pass: `cd src/dev-ui && pnpm test`
- No regressions in task-050 API alignment fixes or task-053 copy/mutation audit.

## UI Location

- `src/dev-ui/app/pages/workspaces/index.vue` — member list disclosure, name edit panel
- `src/dev-ui/app/pages/groups/index.vue` — member list disclosure, name edit panel
- `src/dev-ui/app/pages/api-keys/index.vue` — compact list, revoke confirmation inline
- `src/dev-ui/app/pages/knowledge-graphs/index.vue` — KG detail disclosure
- `src/dev-ui/app/pages/data-sources/index.vue` — sync history collapse (verified by task-044)
- `src/dev-ui/app/pages/graph/explorer.vue` — neighbor expansion (verified by task-016)

## Dependencies

- **task-050** must be complete: IAM pages must be in their final API-aligned state before
  auditing interaction patterns on the same components.
- **task-053** must be complete: the copy-to-clipboard and mutation feedback audit touches
  the same page files; task-057 should layer on top without conflicts.

## TDD Cycle

1. Read each page component; check the disclosure and inline-action patterns (step 1 checklist).
2. Run static search for `/edit` route navigations.
3. Read existing test files; identify gaps.
4. Write missing tests in the relevant test files (they will fail if patterns are absent).
5. Fix any implementation gaps (collapsible sections, sheet-based edit panels).
6. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
7. Commit atomically per conventional commit conventions.
