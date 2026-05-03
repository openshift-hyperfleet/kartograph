---
id: task-091
title: "UI: Backend API alignment — verify all CRUD operations use correct routes and parent context"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(ui): ensure all resource CRUD operations call correct API routes with required parent context"
pr_description: |
  ## What & Why

  The **Backend API Alignment** requirement was added to `specs/ui/experience.spec.md`:

  > The system SHALL successfully complete all resource operations by correctly
  > integrating with the backend REST API.

  with two concrete scenarios:

  **Scenario: Resource operations succeed end-to-end**
  > GIVEN a user performs any create, read, update, or delete operation via the UI
  > WHEN the operation is submitted
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  **Scenario: Parent context is preserved**
  > GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a workspace)
  > WHEN the user creates or lists that resource
  > THEN the UI includes the parent context required by the API
  > AND the operation succeeds

  The backend REST API uses scoped (nested) routes for resources that belong to a
  parent entity. When the UI calls the wrong route — e.g., `POST /management/data-sources`
  instead of `POST /management/knowledge-graphs/{kg_id}/data-sources` — the API
  returns a 4xx and the UI operation silently fails. This requirement makes the
  parent-context contract explicit for every UI page.

  ## What This PR Does

  ### 1. Audit all CRUD operations in `src/dev-ui/app/pages/`

  For each page, verify that every `apiFetch()` call uses the correct backend route.
  Cross-reference against the management, IAM, and graph API route definitions in
  `src/api/`.

  Key resources and their expected route patterns:

  | Resource | Create route | List route | Update/Delete route |
  |---|---|---|---|
  | Knowledge Graph | `POST /management/workspaces/{workspace_id}/knowledge-graphs` | `GET /management/knowledge-graphs` | `PATCH/DELETE /management/knowledge-graphs/{id}` |
  | Data Source | `POST /management/knowledge-graphs/{kg_id}/data-sources` | via KG listing | `PATCH/DELETE /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` |
  | Workspace | `POST /iam/workspaces` (tenant-scoped via header) | `GET /iam/workspaces` | `PATCH/DELETE /iam/workspaces/{id}` |
  | Group | `POST /iam/workspaces/{workspace_id}/groups` | `GET /iam/workspaces/{workspace_id}/groups` | per-group routes |
  | API Key | `POST /iam/api-keys` | `GET /iam/api-keys` | `DELETE /iam/api-keys/{id}` |

  For each call, verify:
  - The route path includes all required parent path parameters.
  - The request body does NOT duplicate path parameters (e.g., no `workspace_id`
    in body when it is already in the path).
  - After a successful mutation (2xx), the UI reloads or updates the local state
    so the user sees the change without a manual refresh.

  ### 2. Fix any mismatched routes or missing parent context

  For each gap found:
  1. Write a test that exercises the operation and asserts the correct URL is called.
  2. Update the `apiFetch()` call to use the correct route.
  3. Confirm the test passes.

  The test strategy for Vue pages depends on the project's existing test tooling
  (Vitest + Vue Test Utils, or Playwright for E2E). Use whichever is already in
  place for `src/dev-ui/app/tests/`.

  ### 3. Verify UI state refresh after mutations

  For each CRUD page, confirm that a successful API response triggers a state
  reload (e.g., calls `loadKnowledgeGraphs()` after create). If a page updates
  state optimistically or without refetching, confirm the displayed data matches
  what the API returned.

  Specifically check:
  - Create operations: newly-created item appears in the list after submit.
  - Update operations: edited item reflects the new values immediately.
  - Delete operations: removed item disappears from the list without a page refresh.

  ### 4. Pages to audit (minimum scope)

  - `src/dev-ui/app/pages/knowledge-graphs/index.vue` — KG CRUD (create, list, edit, delete)
  - `src/dev-ui/app/pages/data-sources/index.vue` — data source wizard and CRUD
  - `src/dev-ui/app/pages/workspaces/index.vue` — workspace CRUD
  - `src/dev-ui/app/pages/groups/index.vue` — group CRUD
  - `src/dev-ui/app/pages/api-keys/index.vue` — API key lifecycle
  - `src/dev-ui/app/pages/graph/mutations.vue` — mutation submission

  ## Files Affected

  - `src/dev-ui/app/pages/**/*.vue` — any pages with incorrect API routes or
    missing parent context (identified during audit)
  - `src/dev-ui/app/tests/**/*.test.ts` — new or updated tests asserting correct
    API routes for each CRUD operation
  - `src/dev-ui/app/composables/**/*.ts` — any composables with incorrect route
    construction

  ## How to Verify

  1. For each audited page, confirm `apiFetch()` calls match the backend route
     table above.
  2. Run existing dev-ui tests: `cd src/dev-ui && pnpm test` — all pass.
  3. Spin up `make instance-up`, log in, and manually perform create/update/delete
     on each page. Confirm no 4xx errors appear in the browser console.
  4. Confirm the UI updates without a manual page refresh after each operation.

  ## Design Decisions

  - **Audit first**: do not change routes speculatively. Read the backend API
    route definitions (FastAPI routers) before updating any frontend call.
  - **No behavior changes**: this task is purely about correctness of integration.
    If a route is already correct, leave it alone.
  - **State refresh strategy**: prefer explicit reload (`loadXxx()`) over
    optimistic updates unless the page already uses an established pattern.

  ## Gap Analysis

  The requirement was added because at least one UI page was observed calling an
  unscoped route where the backend requires a scoped (parent-context) route. The
  exact page(s) must be identified during the audit. Known correct patterns (from
  prior review):

  | Page | Create route | Status |
  |---|---|---|
  | `knowledge-graphs/index.vue` | `POST /management/workspaces/${workspaceId}/knowledge-graphs` | ✅ |
  | `data-sources/index.vue` | `POST /management/knowledge-graphs/${kgId}/data-sources` | ✅ |
  | `data-sources/index.vue` | `PATCH/DELETE /management/knowledge-graphs/${kgId}/data-sources/${dsId}` | ✅ |

  Remaining pages (workspaces, groups, API keys, mutations) must be audited
  against the backend route table.

  ## TDD Cycle

  1. For each page, write a test that mocks `apiFetch` and asserts the expected
     URL — RED (or GREEN if already correct).
  2. Fix any incorrect routes — GREEN.
  3. Confirm no regressions: `cd src/dev-ui && pnpm test`.
  4. Commit atomically per page or per logical group.
---
