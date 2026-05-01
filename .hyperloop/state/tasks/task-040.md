---
id: task-040
title: Fix KG creation — workspace selector and correct API endpoint
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gaps

Two distinct failures in `specs/ui/experience.spec.md`:

1. **Requirement: Backend API Alignment — Scenario: Parent context is preserved**
   > GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a workspace)
   > WHEN the user creates or lists that resource
   > THEN the UI includes the parent context required by the API

2. **Requirement: Knowledge Graph Creation — Scenario: Create knowledge graph**
   > AND the knowledge graph is created within the current workspace

Both FAIL against the current implementation in `src/dev-ui/app/pages/knowledge-graphs/index.vue`.

## Root Cause

The backend route for creating a knowledge graph is:

```
POST /management/workspaces/{workspace_id}/knowledge-graphs
```

The current UI calls:

```typescript
await apiFetch('/management/knowledge-graphs', {
  method: 'POST',
  body: { name: ..., description: ... },
})
```

This is the wrong endpoint — no workspace ID in the path. The backend will return 404
or 405 (no such route). The create dialog also has no workspace selector, so the user
cannot specify which workspace the knowledge graph belongs to.

The test in `src/dev-ui/app/tests/knowledge-graphs.test.ts` incorrectly asserts
against `'/management/knowledge-graphs'` — the test must be corrected to match the
real backend route.

## Changes Required

### 1. `src/dev-ui/app/pages/knowledge-graphs/index.vue`

- Add a `workspaces` ref populated by `listWorkspaces()` on mount and on tenant change.
- Add a workspace selector (dropdown / select) to the Create Knowledge Graph dialog.
  - The user must pick a workspace before the Create button is enabled.
  - If only one workspace exists, pre-select it automatically.
- Change the `handleCreate` API call URL from:
  ```
  POST /management/knowledge-graphs
  ```
  to:
  ```
  POST /management/workspaces/{selectedWorkspaceId}/knowledge-graphs
  ```
- The workspace_id field must be validated (required) before submission.

### 2. `src/dev-ui/app/tests/knowledge-graphs.test.ts`

Write (or fix) tests **before** updating the implementation:

1. **Workspace loading on mount:** Assert that `listWorkspaces()` is called and
   populates the workspace list; assert the workspace selector is pre-populated.

2. **Create API call with workspace context:** Assert that `apiFetch` is called with
   the workspace-scoped URL:
   ```
   /management/workspaces/ws-123/knowledge-graphs
   ```
   NOT `/management/knowledge-graphs`.

3. **Workspace required validation:** Assert that `handleCreate` does not proceed
   if no workspace is selected (returns early with a validation error).

4. **Auto-select single workspace:** Assert that when only one workspace exists it is
   automatically selected so the user does not need to interact with the dropdown.

5. **Existing (incorrect) test:** Update the `'calls POST /management/knowledge-graphs with name and description'`
   test to assert the workspace-scoped URL is used instead.

## TDD Cycle

1. Write/fix tests in `tests/knowledge-graphs.test.ts` (they will fail initially).
2. Update `pages/knowledge-graphs/index.vue` to load workspaces, show selector, and
   post to the correct workspace-scoped URL.
3. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
