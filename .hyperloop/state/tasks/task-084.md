---
id: task-084
title: "UI — Backend API Alignment: explicit test coverage for end-to-end integration scenarios"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): add explicit tests for Backend API Alignment spec scenarios"
pr_description: |
  ## What & Why

  The `specs/ui/experience.spec.md` was modified to add a new top-level requirement:

  > **Requirement: Backend API Alignment**
  > The system SHALL successfully complete all resource operations by correctly
  > integrating with the backend REST API.

  This requirement introduces two verifiable scenarios:

  1. **Resource operations succeed end-to-end** — after any create/update/delete,
     the backend call succeeds and the UI automatically reflects the updated state
     (no manual refresh needed).

  2. **Parent context is preserved** — when a resource is scoped to a parent (e.g.,
     a knowledge graph within a workspace), the UI includes the parent ID in the API
     call in the form the backend requires.

  The underlying code already satisfies these scenarios — KG creation uses the
  workspace-scoped URL path, data source creation uses the KG-scoped URL path, and
  all mutating operations reload the list on success. However, **no test currently
  exists that is explicitly named and structured around these spec scenarios**. The
  TDD mandate requires a test for every spec scenario; without them the spec's
  coverage is formally incomplete.

  This PR adds a dedicated test file (`tests/api-alignment.test.ts`) that maps
  directly to the spec's two scenarios with named `describe` blocks matching the
  GIVEN/WHEN/THEN structure.

  ## Spec Requirements Satisfied

  **Requirement: Backend API Alignment** from
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - Scenario: Resource operations succeed end-to-end
  - Scenario: Parent context is preserved

  ## Key Design Decisions

  - **Pure unit tests** — all tests use `vi.fn()` mocks; no infrastructure needed.
    The goal is to formally document and verify the API contract, not re-test the
    backend.

  - **Named after the spec scenarios** — `describe` blocks use wording from the
    spec so a future reader can trace failing tests directly to the requirement.

  - **Covers all parent-scoped create operations**:
    - `POST /management/workspaces/{workspace_id}/knowledge-graphs` (KG creation)
    - `POST /management/knowledge-graphs/{knowledge_graph_id}/data-sources`
      (data source creation)
    - `POST /management/data-sources/{data_source_id}/sync` (sync trigger)

  - **Covers UI-refresh-after-mutation**:
    - After KG create/edit/delete, `loadKnowledgeGraphs()` is called ✅
    - After workspace create/delete, list is reloaded ✅
    - After API key create/revoke, list is reloaded ✅
    - After data source create, list is reloaded ✅

  - **No changes to production code** — all gaps are in test coverage only;
    the implementation is correct.

  ## Files Affected

  - `src/dev-ui/app/tests/api-alignment.test.ts` — new test file with two `describe`
    groups mapping to the spec's two Backend API Alignment scenarios.

  ## How to Verify

  ```bash
  cd src/dev-ui && npm run test -- api-alignment
  # All tests pass, no regressions.
  ```

  ## TDD Cycle

  1. Write tests for "Resource operations succeed end-to-end":
     - KG create: mock apiFetch → resolves → verify list reload called → RED
     - KG edit: same pattern → RED
     - KG delete: same pattern → RED
     - Data source create: POST to KG-scoped path → list reload → RED
     - API key create: POST → list reload → RED
     - Workspace create: POST → list reload → RED
  2. Write tests for "Parent context is preserved":
     - KG creation URL includes workspace_id → RED
     - Data source creation URL includes knowledge_graph_id → RED
     - Sync trigger URL includes data_source_id → RED
  3. Confirm existing production code satisfies all tests → GREEN
  4. Commit atomically with conventional message.

  ## Caveats

  - Integration-level verification (actual HTTP 2xx from the running backend) is out
    of scope for unit tests; that is covered by CI integration test runs.
  - This task deliberately does NOT modify production Vue files — it is test-only.
    If a test fails RED against existing code, a separate bug-fix task should be
    raised before this task is merged.
---
