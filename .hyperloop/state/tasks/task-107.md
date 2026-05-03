---
id: task-107
title: "Backend API alignment audit: verify and fix all CRUD operations with parent-context scoping"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(ui): backend API alignment — correct parent-context scoping for all CRUD operations"
pr_description: |
  ## What & Why

  The **Backend API Alignment** requirement in `specs/ui/experience.spec.md` states:

  > "GIVEN a user performs any create, read, update, or delete operation via the UI
  > WHEN the operation is submitted THEN the corresponding backend API call succeeds
  > (2xx response) AND the UI reflects the updated state without requiring a manual
  > refresh"

  > "GIVEN a resource that is scoped to a parent (e.g., a knowledge graph within a
  > workspace) WHEN the user creates or lists that resource THEN the UI includes the
  > parent context required by the API AND the operation succeeds"

  The dev-ui frontend has grown organically alongside backend API development. Some
  pages still use stale endpoint paths, missing required request body fields, or
  omit parent-context identifiers (e.g., creating a knowledge graph without a
  `workspace_id`, or listing data sources without a `knowledge_graph_id`). This
  causes silent failures or broken UI state.

  This task is a focused audit-and-fix pass across all UI CRUD operations to ensure
  every frontend call matches the current backend API contract.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Backend API Alignment** — Scenario: *Resource operations succeed end-to-end*
  - **Requirement: Backend API Alignment** — Scenario: *Parent context is preserved*

  ## What This Change Does

  ### Audit Process

  For each page and its CRUD operations, verify:
  1. The HTTP method and endpoint path match `GET /openapi.json` or backend route
     definitions in `src/api/`.
  2. All required request body fields are sent (check against Pydantic schemas).
  3. All required parent-context path parameters are included (e.g.,
     `workspace_id`, `knowledge_graph_id`).
  4. After a successful write, the UI's reactive state is updated without a full
     page reload (optimistic update or re-fetch).
  5. Error responses (4xx, 5xx) are caught and surfaced to the user via toast.

  ### Pages to Audit

  | Page | Key Operations | Known Risk |
  |------|---------------|------------|
  | `/knowledge-graphs` | Create KG, List KGs | `workspace_id` required in create body |
  | `/data-sources` | Create DS, List DS, Delete DS | `knowledge_graph_id` scoping |
  | `/workspaces` | Create workspace, List workspaces | `parent_workspace_id` (optional) |
  | `/groups` | Create group, Add member, Remove member | Member role field |
  | `/api-keys` | Create key, Revoke key | `expires_at` format |
  | `/tenants` | List tenants, Create tenant | Tenant-level operations |
  | `/query` | Execute query | `knowledge_graph_id` optional param |
  | `/graph/mutations` | Submit mutations | `knowledge_graph_id` required |
  | `/graph/schema` | Fetch ontology | Tenant-scoped endpoint |
  | `/graph/explorer` | Search nodes, Get neighbors | Correct AGE graph param |

  ### Fixes Expected

  Based on prior task history (task-040 fixed KG creation workspace scoping), the
  following are likely still broken:
  - Data source create/list: parent `knowledge_graph_id` may be hardcoded or missing
  - Mutations console submit: `knowledge_graph_id` body field alignment with backend
  - API key revoke: PATCH vs DELETE method check

  Each fix follows the pattern: update the API call in the composable or page,
  confirm the backend accepts the corrected request, add or update a test.

  ### Reactive State After Write

  For each write operation, verify the list/detail view updates without a reload:
  - Preferred: mutate the reactive state directly after a successful response
    (e.g., push the new item into the list array, or splice the deleted item out)
  - Acceptable: re-fetch the list from the API after the write (if the list is
    small and the extra request is negligible)

  ## Files / Areas Affected

  - `src/dev-ui/app/composables/` — API client composables (one per resource domain)
  - `src/dev-ui/app/pages/` — page components that call CRUD operations
  - `src/dev-ui/app/types/` — TypeScript type definitions (align with backend schemas)

  ## Tests

  Vitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:
  - One test per CRUD operation verifying the correct HTTP method, path, and body
    fields are sent (use `vi.mock` or `msw` to intercept API calls):
    - `test_kg_create_includes_workspace_id_in_body`
    - `test_data_source_list_includes_kg_id_param`
    - `test_mutations_submit_includes_kg_id`
    - `test_api_key_revoke_uses_correct_method_and_path`
    - _(one test per page/operation identified in the audit)_
  - `test_write_operation_updates_reactive_list_without_reload`: after a create
    call, assert the new item appears in the list without navigating away or
    manually refreshing

  ## How to Verify

  1. Start a full dev instance: `make dev`
  2. For each page in the audit table above:
     - Open the browser DevTools Network tab
     - Perform the create, list, update, and delete operations
     - Confirm each request returns 2xx
     - Confirm the UI updates reactively without a reload
  3. Check the browser console for any uncaught API errors

  ## Caveats

  - This task is an audit-and-fix pass, not a feature addition. If a bug is
    discovered that requires a new backend endpoint, open a separate task for
    the backend change rather than expanding scope here.
  - Some parent-context scoping depends on the active tenant/workspace being
    set in global state (see task-102). Verify that the global state is
    correctly initialized before making API calls.
  - The Ingestion context (sync operations) is intentionally excluded from this
    audit since the backend is not yet implemented.
---
