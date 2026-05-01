---
id: task-040
title: Fix UI backend API alignment — correct endpoint wiring and parent context
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
- task-014
- task-016
round: 0
branch: null
pr: null
---

## Spec Gap

`specs/ui/experience.spec.md` — **Backend API Alignment** requirement (added in latest diff).

Neither task-014 nor task-016 was created with this requirement in scope (they reference
the prior spec commit `85d49a379a52479b33f9b39994d76795066899a6`). Both are marked
complete, but the completed pages have not been verified against these two scenarios.

## Requirements

### Scenario: Resource operations succeed end-to-end
- GIVEN a user performs any create, read, update, or delete operation via the UI
- WHEN the operation is submitted
- THEN the corresponding backend API call succeeds (2xx response)
- AND the UI reflects the updated state without requiring a manual refresh

### Scenario: Parent context is preserved
- GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a workspace)
- WHEN the user creates or lists that resource
- THEN the UI includes the parent context required by the API
- AND the operation succeeds

## Scope

Audit and fix the pages delivered by task-014 and task-016. task-015 (not yet started)
must depend on this task so that the correct patterns are established first.

**Pages from task-014 to audit:**
- Workspace management (create workspace, member management)
- Group management
- Tenant management
- API key management

**Pages from task-016 to audit:**
- Query console (query execution against the correct scoped knowledge graph)
- Schema browser (type listing scoped to tenant/knowledge graph)
- Graph explorer (node search scoped to tenant/knowledge graph)

## What to look for

1. **Endpoint correctness** — Is the UI calling the right REST endpoint for each
   operation? (e.g., `POST /tenants/{tenant_id}/workspaces/{workspace_id}/knowledge-graphs`
   rather than a flat `/knowledge-graphs`). Read each page component and trace every
   API call to a concrete backend route.

2. **Parent context inclusion** — For every resource that is scoped to a parent, verify
   that the parent's ID is included in the URL path or request body as the API requires.
   The most common gap: creating a knowledge graph without the `workspace_id` in the URL.

3. **Optimistic / reactive state refresh** — After a mutation succeeds, verify that the
   relevant list/detail view re-fetches or updates in-place without requiring the user to
   manually refresh the browser.

4. **Error surface** — If the API returns a non-2xx, the UI should surface a meaningful
   error (toast or inline message) rather than silently failing or throwing an uncaught
   exception.

## TDD approach

For each page under audit:
1. Write an E2E or component test (Playwright / Vitest) that exercises the scenario
   end-to-end against the running dev instance or a mock server.
2. Confirm the test fails (if the bug exists) before fixing the implementation.
3. Fix the API wiring in the Vue component / composable / API client.
4. Confirm the test passes.

Pay particular attention to the `useApi` / `useFetch` composables and any Pinia stores
that hold the active workspace or tenant context — these are the most likely places where
parent context is dropped.
