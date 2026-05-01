---
id: task-057
title: Audit interaction style — progressive disclosure and inline editing across all pages
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
  - task-015
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Interaction Principles** — 2 scenarios from `specs/ui/experience.spec.md`:

### Scenario: Progressive disclosure
> GIVEN complex information
> THEN the UI shows a summary by default
> AND detail is revealed on demand (expand, drill-in, sheet)

### Scenario: Inline actions over navigation
> GIVEN an editable resource (workspace name, group name)
> THEN editing happens in-place or in a side panel
> AND the user is not navigated to a separate edit page

## Context

The Interaction Principles requirement was added in spec commit `21b516b59`. The
"interaction principles gaps" intake pass (f3641b927) created tasks for 4 of the 6
Interaction Principles scenarios:

- Focus indicators → task-049
- Copy-to-clipboard + mutation feedback → task-053
- Keyboard shortcuts → task-054

The remaining 2 scenarios — progressive disclosure and inline actions over navigation —
were never tasked. They are behavioral requirements with testable GIVEN/WHEN/THEN
conditions, not design guidelines.

**task-014 (complete)** implemented the IAM pages and uses sheet/panel patterns
(e.g., workspace detail in a side panel, member list collapsed by default). However,
that task was written before the Interaction Principles requirement existed, and no
test explicitly asserts:
- that resources default to a summary view with detail revealed on interaction
- that editing a resource name does not navigate to a separate `/edit` route

**task-015 (not-started)** implements the knowledge graph and data source pages.
These pages must also conform to both scenarios before this audit can be comprehensive.
Hence the dependency on task-015.

## Pages to Audit

### Progressive disclosure — pages with "complex information"

| Page | Complex resource | Summary (default) | Detail (on demand) |
|------|-----------------|-------------------|--------------------|
| `pages/workspaces/index.vue` | Workspace with members | Workspace name + member count | Member list in side panel |
| `pages/groups/index.vue` | Group with members | Group name + member count | Member list in side panel |
| `pages/knowledge-graphs/index.vue` | KG with data sources | KG name + DS count + last sync | DS list / sync status on expand |
| `pages/data-sources/index.vue` | DS with sync history | DS name + last-sync status | Full sync run history on expand |
| `pages/query/index.vue` | Query result set | Row count + execution time | Full result table |

### Inline actions — pages with editable resources

| Page | Resource | Edit action | Prohibited pattern |
|------|----------|-------------|-------------------|
| `pages/workspaces/index.vue` | Workspace name | In-place input or side sheet | No `/workspaces/{id}/edit` navigation |
| `pages/groups/index.vue` | Group name | In-place input or side sheet | No `/groups/{id}/edit` navigation |

## Changes Required

### 1. Audit existing tests (TDD: read tests before code)

Read the following test files:

- `src/dev-ui/app/tests/workspace-management.test.ts`
- `src/dev-ui/app/tests/group-management.test.ts` (or `groups.test.ts`)
- `src/dev-ui/app/tests/knowledge-graphs.test.ts`
- `src/dev-ui/app/tests/data-sources.test.ts`

For each file, check:

**Progressive disclosure:**
1. Is there a test asserting that the detail panel/member list is hidden by default?
2. Is there a test asserting it becomes visible after a user action (click expand, select
   item, etc.)?
3. Is the detail revealed via a sheet, drawer, or inline expand — NOT a page navigation?

**Inline actions:**
1. Is there a test asserting that clicking "Edit" on a workspace/group name does NOT
   call `navigateTo` or change the route?
2. Is there a test asserting that an editable input (or `contenteditable`) appears
   in-place after clicking the edit action?

### 2. Write missing tests (TDD before implementation)

For each gap found in step 1, write tests **before** touching the implementation.

**Progressive disclosure — workspace detail:**

```typescript
// src/dev-ui/app/tests/workspace-management.test.ts
import { mount } from '@vue/test-utils'
import WorkspacesPage from '@/pages/workspaces/index.vue'

describe('Interaction Principles — Progressive disclosure', () => {
  it('member list is hidden until a workspace is selected', async () => {
    const wrapper = mount(WorkspacesPage, { /* provide mocked composables */ })
    // No workspace selected → detail panel not visible
    expect(wrapper.find('[data-testid="workspace-member-list"]').exists()).toBe(false)
  })

  it('member list appears in side panel after selecting a workspace', async () => {
    const wrapper = mount(WorkspacesPage, { /* ... */ })
    const workspaceRow = wrapper.find('[data-testid="workspace-row"]')
    await workspaceRow.trigger('click')
    // Detail revealed without page navigation
    expect(wrapper.find('[data-testid="workspace-member-list"]').isVisible()).toBe(true)
  })
})
```

**Inline actions — workspace name editing:**

```typescript
describe('Interaction Principles — Inline actions over navigation', () => {
  it('clicking Edit on workspace name does not navigate to a separate page', async () => {
    const navigateTo = vi.fn()
    const wrapper = mount(WorkspacesPage, {
      global: { provide: { navigateTo } }
    })
    const editButton = wrapper.find('[data-testid="edit-workspace-name"]')
    await editButton.trigger('click')
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('clicking Edit reveals an in-place input or opens a side sheet', async () => {
    const wrapper = mount(WorkspacesPage, { /* ... */ })
    const editButton = wrapper.find('[data-testid="edit-workspace-name"]')
    await editButton.trigger('click')
    // One of: inline input becomes visible, OR a sheet component opens
    const inlineInput = wrapper.find('[data-testid="workspace-name-input"]')
    const sheet = wrapper.find('[data-testid="edit-workspace-sheet"]')
    expect(inlineInput.exists() || sheet.exists()).toBe(true)
  })
})
```

Apply the same test patterns to `groups.test.ts` for group name editing, and to
`knowledge-graphs.test.ts` / `data-sources.test.ts` for progressive disclosure
of KG data sources and DS sync history.

### 3. Fix implementation gaps

**If a detail panel is initially rendered but not hidden:**
- Wrap it in a conditional: `v-if="selectedWorkspace !== null"` or equivalent.
- Ensure the condition is `false` on initial render.

**If clicking "Edit" navigates to a separate route:**
- Remove the `<NuxtLink>` or `navigateTo()` call.
- Replace with a reactive `isEditing` boolean that toggles an inline `<input>` or
  opens a `<Sheet>`.

  Inline edit pattern:
  ```html
  <template v-if="isEditing">
    <Input
      v-model="editName"
      data-testid="workspace-name-input"
      @keydown.enter="saveEdit"
      @keydown.escape="cancelEdit"
      @blur="saveEdit"
    />
  </template>
  <template v-else>
    <span>{{ workspace.name }}</span>
    <Button
      data-testid="edit-workspace-name"
      variant="ghost"
      size="icon"
      @click="isEditing = true"
    >
      <Pencil class="size-4" />
    </Button>
  </template>
  ```

  Sheet pattern (for more complex edits):
  ```html
  <Sheet v-model:open="editSheetOpen">
    <SheetContent data-testid="edit-workspace-sheet">
      <!-- edit form -->
    </SheetContent>
  </Sheet>
  ```

**If query results are always fully expanded:**
- Show row count and execution time by default.
- Reveal the full result table via a "Show results" toggle or keep it visible only
  after execution (already implicit in the query console flow — verify this holds).

### 4. Verify no navigation-to-separate-page patterns exist

Run a grep scan for any navigation that would violate the "inline actions" scenario:

```bash
grep -r "navigateTo.*edit" src/dev-ui/app/pages/
grep -r "NuxtLink.*edit" src/dev-ui/app/pages/
grep -rn "router.push.*edit" src/dev-ui/app/pages/
```

If any results point to workspace or group edit routes, those must be replaced with
inline editing or side-sheet patterns.

## Acceptance Criteria

**Progressive disclosure:**
- Workspace and group detail panels (member lists) are hidden when no item is selected.
- Selecting a workspace/group reveals its detail in a side panel or sheet without
  navigating away.
- KG data source list and DS sync history are collapsed (or count-only) by default and
  expanded on user action.
- At least one test per page (workspaces, groups, KGs, data sources) asserts the
  summary-first / detail-on-demand pattern.

**Inline actions over navigation:**
- Clicking "Edit" on a workspace name or group name does NOT call `navigateTo` or
  push a new route.
- After clicking "Edit", an inline `<input>` or a `<Sheet>` becomes visible in the
  same page context.
- `grep` produces no results for `navigateTo.*edit` in `pages/workspaces/` or
  `pages/groups/`.
- At least one test per page (workspaces, groups) asserts that editing is in-place or
  sheet-based.

**Tests:**
- All tests in the following files pass after changes:
  - `src/dev-ui/app/tests/workspace-management.test.ts`
  - `src/dev-ui/app/tests/group-management.test.ts`
  - `src/dev-ui/app/tests/knowledge-graphs.test.ts`
  - `src/dev-ui/app/tests/data-sources.test.ts`
- `cd src/dev-ui && pnpm test` — no regressions.

## UI Location

- `src/dev-ui/app/pages/workspaces/index.vue`
- `src/dev-ui/app/pages/groups/index.vue`
- `src/dev-ui/app/pages/knowledge-graphs/index.vue`
- `src/dev-ui/app/pages/data-sources/index.vue`
- `src/dev-ui/app/pages/query/index.vue`

## Dependencies

- **task-015** must be complete: knowledge graph and data source pages must exist in
  their final form before this audit can verify those pages conform to both scenarios.

## TDD Cycle

1. Read each page component and its test file; determine PASS/FAIL per scenario
   (step 1 audit).
2. Write failing tests for each gap (step 2).
3. Fix implementation to make tests pass (step 3).
4. Run the grep scan to confirm no edit-route navigations remain (step 4).
5. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
6. Commit atomically per conventional commit conventions.
