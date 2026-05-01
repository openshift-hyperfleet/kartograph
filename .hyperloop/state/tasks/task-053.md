---
id: task-053
title: Cross-page copy-to-clipboard and mutation feedback consistency audit
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
  - task-015
  - task-050
  - task-051
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Interaction Principles** — 2 scenarios from `specs/ui/experience.spec.md`:

### Scenario: Copy-to-clipboard
> GIVEN any identifier, configuration snippet, or secret
> THEN a copy button is provided
> AND a toast confirms the copy action

### Scenario: Mutation feedback
> GIVEN a write operation (create, update, delete)
> THEN a toast notification confirms success or reports failure
> AND validation errors are shown inline on form fields

## Context

The copy-to-clipboard and mutation feedback requirements are cross-cutting patterns that
must be present on **every page** that exposes identifiers or performs writes.

- task-014 (complete) implemented IAM pages but was written against spec commit `85d49a379a`
  — before the Interaction Principles requirement was added in `21b516b59`.
- task-015, task-050, task-051 address individual page gaps but do not conduct a
  systematic cross-page audit of copy buttons and mutation toasts.
- task-043 explicitly includes copy-to-clipboard for type slugs in the ontology editor.
- task-051 explicitly includes copy behavior on the MCP page.

This task audits **all remaining pages** for copy button + toast consistency and
mutation feedback (toast on success/failure + inline validation errors), and implements
any gaps found.

## Pages to Audit

For **copy-to-clipboard**, check every page that exposes identifiers or snippets:

| Page | Resource | Expected copy target |
|------|----------|----------------------|
| `pages/workspaces/index.vue` | Workspace ID | `ws-<id>` string |
| `pages/groups/index.vue` | Group ID | `grp-<id>` string |
| `pages/api-keys/index.vue` | Key ID (not secret) | `key-<id>` string |
| `pages/tenants/index.vue` | Tenant ID | `ten-<id>` string |
| `pages/knowledge-graphs/index.vue` | Knowledge graph ID | `kg-<id>` string |
| `pages/data-sources/index.vue` | Data source ID | `ds-<id>` string |
| `pages/query/index.vue` | Query results (optional) | Table cell value |
| `pages/integrate/mcp.vue` | MCP snippet, API key | Already covered by task-051 |

For **mutation feedback**, check every page that performs writes:

| Page | Operations | Expected feedback |
|------|------------|-------------------|
| `pages/workspaces/index.vue` | Create, Update name, Delete | Success/error toast; inline field errors |
| `pages/groups/index.vue` | Create, Add/remove members, Delete | Success/error toast; inline field errors |
| `pages/api-keys/index.vue` | Create, Revoke | Success/error toast |
| `pages/tenants/index.vue` | (admin operations if any) | Success/error toast |
| `pages/knowledge-graphs/index.vue` | Create, Delete | Success/error toast; inline field errors |
| `pages/data-sources/index.vue` | Create, Trigger sync | Success/error toast (covered by task-015, verify) |

## Changes Required

### 1. Audit existing tests

For each page listed above, read the corresponding test file and verify:

1. **Copy-to-clipboard:** Does a test assert that a copy button exists adjacent to each
   identifier? Does it assert that `navigator.clipboard.writeText` was called with the
   correct value? Does it assert that a toast appeared after copying?

2. **Mutation feedback:** Does a test assert that a success toast appears after each
   successful write? Does a test assert an error toast when the API call fails? Does a
   test verify that inline validation errors appear on form fields when required fields
   are empty?

### 2. Write missing tests (TDD before implementation)

For each gap found, write tests **before** touching the implementation.

**Copy-to-clipboard pattern:**
```typescript
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

// Setup
const writeText = vi.fn()
Object.assign(navigator, { clipboard: { writeText } })

it('copies workspace ID to clipboard and shows toast', async () => {
  const wrapper = await mountWorkspacesPage()
  const copyButton = wrapper.find('[data-testid="copy-workspace-id"]')
  await userEvent.click(copyButton.element)
  expect(writeText).toHaveBeenCalledWith('ws-test-id-123')
  // Assert toast (check for toast element or Sonner call)
  expect(wrapper.find('[data-testid="toast"]').text()).toContain('Copied')
})
```

**Mutation success toast:**
```typescript
it('shows success toast after creating a workspace', async () => {
  mockFetch.mockResolvedValueOnce({ id: 'ws-new', name: 'My Workspace' })
  await userEvent.click(wrapper.find('[data-testid="create-workspace-submit"]').element)
  expect(wrapper.find('[role="status"]').text()).toContain('Workspace created')
})
```

**Mutation error toast:**
```typescript
it('shows error toast when API call fails', async () => {
  mockFetch.mockRejectedValueOnce(new Error('Network error'))
  await userEvent.click(wrapper.find('[data-testid="create-workspace-submit"]').element)
  expect(wrapper.find('[role="alert"]').text()).toContain('Failed')
})
```

**Inline validation:**
```typescript
it('shows inline error when name is empty on submit', async () => {
  await userEvent.click(wrapper.find('[data-testid="create-workspace-submit"]').element)
  expect(wrapper.find('[data-testid="name-error"]').text()).toContain('required')
})
```

### 3. Fix implementation gaps

For pages where copy buttons are missing:
- Add a `<Button variant="ghost" size="icon">` adjacent to each displayed ID
- The click handler calls `navigator.clipboard.writeText(id)` then fires a toast:
  ```typescript
  import { toast } from 'vue-sonner'
  
  async function copyId(id: string) {
    await navigator.clipboard.writeText(id)
    toast.success('Copied to clipboard')
  }
  ```

For pages where mutation toasts are missing:
- After each successful API call, call `toast.success('Resource created')` or the
  equivalent resource-specific message
- Wrap API calls in try/catch; in the catch block call `toast.error('Failed: ' + err.message)`

For pages where inline validation is missing:
- Use the form validation pattern from existing working pages (e.g., check that
  `name.trim().length > 0` before submitting; display an error message beneath the field)

## Acceptance Criteria

- Every resource ID displayed on all audited pages has an adjacent copy button.
- Clicking any copy button calls `navigator.clipboard.writeText` with the correct ID.
- A success toast ("Copied to clipboard" or equivalent) appears after each copy.
- Every write operation (create/update/delete) on all audited pages shows a success
  toast on 2xx response and an error toast on failure.
- Required form fields show inline validation errors when submitted empty.
- All new and existing tests in the affected test files pass:
  `cd src/dev-ui && pnpm test`
- No regressions in task-050 API alignment fixes or task-051 MCP page audit.

## Dependencies

- **task-015** must be complete: knowledge graph and data source pages must be in their
  final form before auditing for copy buttons and mutation feedback.
- **task-050** must be complete: API endpoints must be correct before testing that
  success/error toasts fire for the right operations.
- **task-051** must be complete: MCP page is explicitly excluded from this audit (already
  covered); task-051 must be complete to avoid test file conflicts.

## TDD Cycle

1. Read all page components and their test files — determine PASS/FAIL per scenario
   and per page.
2. Write failing tests in each affected test file for each gap.
3. Fix implementation in the affected pages to make tests pass.
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
5. Commit atomically; one commit per page or logical group of changes.
