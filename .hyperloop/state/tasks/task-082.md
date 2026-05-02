---
id: task-082
title: "Data Sources UI — persist ontology edits to backend after extraction"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): persist post-extraction ontology edits via PATCH on data source"
pr_description: |
  ## What & Why

  The spec requires:

  > **Requirement: Ontology Design — Scenario: Ontology change after initial extraction**
  > GIVEN a knowledge graph with completed extraction
  > WHEN the user modifies the ontology
  > THEN the system warns that this will trigger a full re-extraction
  > AND the user must confirm before the change is applied

  The Data Sources page (`src/dev-ui/app/pages/data-sources/index.vue`) already
  implements the warning dialog — the user sees an amber alert and must click a
  confirmation button before the ontology editor opens. However, the `closeOntologyEditor`
  handler that fires when the user clicks "Save" inside the post-extraction editor
  **does not call the backend**. It closes the dialog and clears local state, silently
  discarding all edits. The changes are never persisted.

  The backend exposes:

  ```
  PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}
  ```

  which accepts an `ontology` field alongside `name` and `credentials`. This task
  wires the post-extraction ontology editor's save action to that endpoint.

  ## Spec Requirements Satisfied

  **Requirement: Ontology Design — Scenario: Ontology change after initial extraction**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > WHEN the user modifies the ontology
  > THEN the system warns that this will trigger a full re-extraction
  > AND the user must confirm before the change is applied

  The warning and confirmation are already present. This task satisfies the "change is
  applied" clause — i.e., the confirmed and reviewed ontology is actually persisted.

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**:

  > WHEN the user performs any create, read, **update**, or **delete** operation via the UI
  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  Saving an ontology is an update operation. Currently it produces no API call at all.

  ## Key Design Decisions

  - **Save path**: `PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}`
    with body `{ ontology: { node_types: [...], edge_types: [...] } }`. The data source
    record already carries `knowledge_graph_id`, so the URL can be constructed directly.

  - **Trigger on "Apply & Save" only**: the save call fires only after the user has
    reviewed and clicked the final "Apply" button in the ontology editor dialog — not
    on individual type edits. The existing two-step UX (review → confirm) is preserved.

  - **Re-extraction trigger**: the spec says extraction begins only after ontology
    approval. The PATCH response from the backend may include a sync status transition.
    The UI should refresh the data source list after a successful PATCH so the new sync
    status appears.

  - **Saving state**: a `savingOntology` ref gates the Apply button and shows a spinner.
    On success, `editOntologyOpen` is set to `false` and the data source list reloads.
    On failure, the dialog stays open with an error toast.

  - **No structural changes to the warning flow**: the re-extraction warning dialog and
    its confirmation logic are untouched. This task only extends `closeOntologyEditor`
    (or a new `saveOntology` handler it calls) to include the PATCH call.

  - **TDD first**: all logic tests and structural tests are written before implementation.

  ## Files Affected

  - `src/dev-ui/app/tests/data-sources.test.ts` — new test group for ontology-save logic
    and structural checks.
  - `src/dev-ui/app/pages/data-sources/index.vue` — extend `closeOntologyEditor` (or add
    `saveOntology`) with PATCH call, `savingOntology` state, error handling, and list
    refresh on success.

  ## How to Verify

  1. `cd src/dev-ui && npm run test` — all new tests pass, no regressions.
  2. Open the Data Sources page with a data source in `completed` sync state.
  3. Click **Edit Ontology** → re-extraction warning appears.
  4. Click **I Understand, Open Editor** → ontology editor opens with current types.
  5. Edit a node type label and click **Apply** (or equivalent save button).
  6. Verify a `PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}` request
     is made with the updated `ontology` body (inspect Network tab).
  7. Verify the dialog closes and a success toast appears.
  8. Verify the data source list refreshes (the data source card re-fetches its state).
  9. Simulate a 500 error from the PATCH → error toast appears; dialog stays open.

  ## TDD Cycle

  1. Write logic tests for `saveOntology`: happy path PATCH call with ontology payload,
     list refresh on success, dialog close on success — RED.
  2. Write logic test: PATCH failure → error toast, dialog stays open, `savingOntology`
     reset — RED.
  3. Write structural tests: `savingOntology` state declared, PATCH call present,
     Apply button calls `saveOntology` — RED.
  4. Implement `savingOntology` ref and extend `closeOntologyEditor` / add `saveOntology`
     in `data-sources/index.vue` — GREEN.
  5. Run `cd src/dev-ui && npm run test` — all pass.
  6. Commit atomically.

  ## Caveats

  - The exact shape of the `ontology` payload (field names, nesting) must match the
    backend `DataSourceUpdateRequest` schema. Verify against the OpenAPI spec or
    management context's Pydantic model before writing the test fixtures.
  - If the backend initiates a re-sync automatically on PATCH (ontology change), the
    data source will transition to `pending`/`ingesting` state. The list refresh will
    surface this, which is the correct UX.
  - The simulated AI ontology proposal (hardcoded `GITHUB_PROPOSAL_NODES/EDGES` in the
    wizard step 4) is out of scope for this task. Wiring the real AI proposal endpoint
    depends on the Extraction context (blocked on AIHCM-174).
---
