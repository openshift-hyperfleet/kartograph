---
id: task-050
title: Backend API alignment audit — IAM and explore page CRUD operations
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Backend API Alignment** from `specs/ui/experience.spec.md` (added in
`97bf3eeef chore(spec): require UI alignment to api route`):

### Scenario: Resource operations succeed end-to-end
> GIVEN a user performs any create, read, update, or delete operation via the UI
> WHEN the operation is submitted
> THEN the corresponding backend API call succeeds (2xx response)
> AND the UI reflects the updated state without requiring a manual refresh

### Scenario: Parent context is preserved
> GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a workspace)
> WHEN the user creates or lists that resource
> THEN the UI includes the parent context required by the API
> AND the operation succeeds

## Context

Tasks **task-040** and **task-041** address known specific API integration failures for
knowledge graphs and data sources respectively. However, those tasks are scoped to the
known defects — they do not constitute a comprehensive verification of the Backend API
Alignment requirement across **all** implemented resources.

The IAM management pages (workspaces, groups, API keys, tenants) and explore pages
(query console, schema browser, graph explorer) were implemented in **task-014** (complete)
and **task-016** (complete). Neither of those tasks explicitly validated that every CRUD
operation calls the correct backend endpoint, sends required parent context, and triggers
a UI refresh. This task closes that gap.

## Scope

Resources to audit and verify:

| Resource | Page | Operations |
|----------|------|------------|
| Workspaces | `pages/workspaces/index.vue` | List, Create (optional parent), Update name, Delete |
| Groups | `pages/groups/index.vue` | List, Create, Add/remove members, Delete |
| API Keys | `pages/api-keys/index.vue` | List, Create, Revoke |
| Tenants | `pages/tenants/index.vue` | List (read-only for most users) |
| Query console | `pages/query/index.vue` | Execute query (POST to query endpoint) |
| Schema browser | `pages/graph/schema.vue` | Read schema types |
| Graph explorer | `pages/graph/explorer.vue` | Search nodes, expand neighbors |

**Not in scope** (covered by other tasks):
- Knowledge graph creation endpoint fix → task-040
- Data source list / sync run response format → task-041
- Data source creation wizard → task-015 (implements from scratch)
- Ontology design flow → task-043

## Changes Required

### 1. Audit existing test files (TDD: read tests before code)

Read the following test files and check each CRUD operation:

- `src/dev-ui/app/tests/workspace-management.test.ts`
- `src/dev-ui/app/tests/api-keys.test.ts`
- `src/dev-ui/app/tests/query-history.test.ts`
- `src/dev-ui/app/tests/schema-browser.test.ts`
- `src/dev-ui/app/tests/graph-explorer.test.ts`
- `src/dev-ui/app/tests/default.layout.test.ts` (tenant selector)

For each test file, verify:
1. Does each CRUD operation assert the **exact API endpoint URL** (not just that
   _some_ fetch was called)?
2. For workspace creation with an optional parent: does the request include
   `parent_id` when a parent is selected?
3. Does each mutation (create/update/delete) result in a **UI state refresh**
   without a manual page reload (i.e., the reactive list is updated in place)?

### 2. Write missing alignment tests

For each gap found in step 1, write tests in the relevant test file **before** touching
implementation. Each test must assert:

```typescript
// Example pattern — workspace creation with parent
expect(mockFetch).toHaveBeenCalledWith(
  expect.stringContaining('/management/workspaces'),
  expect.objectContaining({
    method: 'POST',
    body: expect.objectContaining({ parent_id: 'ws-parent-123' }),
  })
)
```

And for UI refresh:

```typescript
// After create, the list is populated without a page reload
await userEvent.click(createButton)
expect(screen.getByText('new-workspace-name')).toBeInTheDocument()
```

### 3. Fix implementation gaps

For any resource where the test reveals an API alignment failure:

a. **Wrong endpoint URL** — update the `apiFetch` call to use the correct route.
b. **Missing parent context** — ensure the parent ID is passed in the request body
   or URL path as required by the backend API spec.
c. **No UI refresh after mutation** — ensure the reactive data ref is updated after
   the successful API call (no `window.location.reload()` or manual page refresh).

### 4. Verify `useIamApi.ts` composable endpoints

Read `src/dev-ui/app/composables/api/useIamApi.ts` and verify the function
signatures and endpoint strings match the actual backend routes:

- `listWorkspaces()` → `GET /iam/workspaces`
- `createWorkspace(name, parentId?)` → `POST /iam/workspaces`
- `listGroups()` → `GET /iam/groups`
- `createGroup(name)` → `POST /iam/groups`
- `listApiKeys()` → `GET /iam/api-keys`
- `createApiKey(name, expiresAt?)` → `POST /iam/api-keys`
- `revokeApiKey(id)` → `DELETE /iam/api-keys/{id}` or `POST /iam/api-keys/{id}/revoke`

Correct any mismatch between the composable's URLs and the actual backend routes.

## Acceptance Criteria

- Every CRUD operation in workspace, group, API key, tenant, query console, schema
  browser, and graph explorer pages calls the documented backend endpoint (verified
  by test assertions on the exact URL).
- Workspace creation with a selected parent sends `parent_id` to the API.
- Every mutation results in a reactive UI update (no manual refresh required).
- All existing and new tests in the affected test files pass:
  `cd src/dev-ui && pnpm test`
- No regressions in task-014 or task-016 functionality.

## TDD Cycle

1. Read existing test files and identify gaps (step 1 above).
2. Write failing tests for each gap (step 2).
3. Fix implementation to make tests pass (step 3).
4. Confirm composable endpoint strings are correct (step 4).
5. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
6. Commit atomically per conventional commit conventions.
