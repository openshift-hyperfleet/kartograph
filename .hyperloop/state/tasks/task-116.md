---
id: task-116
title: "Ontology design wizard — tests for intent/proposal/approval + implement re-extraction warning"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-115]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add ontology design wizard tests and implement re-extraction warning"
pr_description: |
  ## What & Why

  The data source wizard in `src/dev-ui/app/pages/data-sources/index.vue` includes
  a full 4-step ontology design flow. Steps 3 and 4 cover:

  - **Step 3 — Intent description**: the user types free text about what problems
    they want to solve with the data source.
  - **Step 4 — Proposed ontology**: the system presents a set of proposed node
    and edge types for the user to review, edit, and approve.

  `ontology-add-types.test.ts` (task-063) covers the **individual type editing**
  logic (adding, validating, and saving new types). The remaining spec scenarios
  have no tests and one scenario has no implementation at all.

  ### Spec gaps addressed

  `specs/ui/experience.spec.md` — **Requirement: Ontology Design**:

  | Scenario | Status |
  |---|---|
  | Intent description | Implemented (Step 3), **no test** |
  | Agent-proposed ontology | Partially implemented (hardcoded GitHub proposal), **no test** |
  | Ontology review and approval | Implemented (`approvingOntology` state), **no test** |
  | Individual type editing | Covered by `ontology-add-types.test.ts` |
  | Ontology change after initial extraction | **Not implemented, no test** |

  The "Agent-proposed ontology" scenario says the proposal comes from an AI agent.
  The current implementation uses a hardcoded `GITHUB_PROPOSAL_NODES / GITHUB_PROPOSAL_EDGES`
  array (a placeholder until the Extraction context is ready). Tests should verify
  the UI correctly presents these proposals regardless of their origin.

  The "Ontology change after initial extraction" scenario is **not implemented**:
  when a user edits ontology for a data source that has already had a completed
  sync run, the UI should warn them and require confirmation before proceeding.
  This PR implements that warning and tests it.

  ## What This Change Does

  ### Part A — Tests for existing behavior

  New file: `src/dev-ui/app/tests/ontology-wizard-flow.test.ts`

  #### Step 3 — Intent description

  **`test_intent_validation_requires_non_empty_text`**
  - With `intentText` empty, advancing to step 4 sets `intentError` and blocks.
  - With `intentText` non-empty, advancing succeeds and clears `intentError`.

  **`test_intent_text_is_not_persisted_after_wizard_close`**
  - After the wizard is closed/reset, `intentText` and `intentError` return to
    their initial empty values.

  #### Step 4 — Proposed ontology display

  **`test_github_proposal_populates_nodes_and_edges`**
  - Verify that when the adapter is `'github'` and the wizard advances to step 4,
    `proposedNodes` is populated with the hardcoded `GITHUB_PROPOSAL_NODES` array
    and `proposedEdges` is populated from `GITHUB_PROPOSAL_EDGES`.
  - Pin the expected node labels: `['Repository', 'Issue', 'PullRequest', 'Commit', 'User']`.
  - This is a regression guard: if someone accidentally removes or renames a
    proposal, the test will catch it.

  **`test_ontology_ready_flag_set_after_scan_completes`**
  - After the "scan" simulation completes (the `scanningOntology` flag goes false),
    `ontologyReady` is true and the approval button is enabled.

  #### Approval flow

  **`test_approval_calls_api_with_correct_ontology_payload`**
  - Mock the API call made when `approvingOntology` fires.
  - Assert the payload includes `node_types` and `edge_types` arrays derived from
    `proposedNodes` and `proposedEdges`.
  - Assert the payload does NOT include transient edit state (`editing`, `editLabel`, etc.).

  **`test_approval_closes_wizard_on_success`**
  - After successful API call, `wizardOpen` becomes false and `wizardStep` resets to 1.

  **`test_approval_shows_error_on_api_failure`**
  - When the API call rejects, a toast or error message is shown and `wizardOpen`
    remains true (wizard stays open so user can retry).

  ### Part B — Implement and test re-extraction warning

  **Spec scenario:**
  > GIVEN a knowledge graph with completed extraction
  > WHEN the user modifies the ontology
  > THEN the system warns that this will trigger a full re-extraction
  > AND the user must confirm before the change is applied

  **Detection logic** (implement in `data-sources/index.vue`):
  - A data source has "completed extraction" when `sync_runs` contains at least
    one entry with `status === 'completed'`.
  - Expose a computed `hasCompletedExtraction` that checks this.

  **Warning UI** (implement in `data-sources/index.vue`):
  - When `hasCompletedExtraction` is true and the user clicks to edit the ontology
    (e.g., clicks "Edit Ontology" on an existing data source, or opens the
    type editor in step 4 while `hasCompletedExtraction` is set), show an
    `AlertDialog` with:
    - Title: "Modifying the ontology will trigger a full re-extraction"
    - Body: Explanation that all data will be re-extracted and re-applied.
    - Buttons: "Cancel" and "Confirm and edit".
  - Only proceed to the edit view when the user clicks "Confirm and edit".

  **Tests** (in `src/dev-ui/app/tests/ontology-wizard-flow.test.ts`):

  **`test_has_completed_extraction_false_when_no_sync_runs`**
  - A data source with `sync_runs: []` returns false from `hasCompletedExtraction`.

  **`test_has_completed_extraction_false_when_all_runs_failed`**
  - A data source with sync runs all having `status: 'failed'` returns false.

  **`test_has_completed_extraction_true_when_any_run_completed`**
  - A data source with one `status: 'completed'` run returns true even if other
    runs failed.

  **`test_re_extraction_warning_shown_before_ontology_edit`**
  - Mock `hasCompletedExtraction` returning true.
  - Simulate user clicking the edit ontology button.
  - Assert that the re-extraction `AlertDialog` is shown (e.g., the dialog's
    `open` prop is true).
  - Assert that the edit view is NOT shown yet (user must confirm first).

  **`test_edit_proceeds_after_confirmation`**
  - User clicks "Confirm and edit" in the AlertDialog.
  - Assert the dialog closes and the type editor is now visible.

  **`test_edit_cancelled_leaves_ontology_unchanged`**
  - User clicks "Cancel" in the AlertDialog.
  - Assert the dialog closes and the type editor is NOT shown.
  - Assert `proposedNodes` and `proposedEdges` are unchanged.

  ## Files / Areas Affected

  - `src/dev-ui/app/pages/data-sources/index.vue` — add `hasCompletedExtraction`
    computed, re-extraction `AlertDialog`, and guard on the edit ontology trigger
  - `src/dev-ui/app/tests/ontology-wizard-flow.test.ts` (new) — all tests above

  ## How to Verify

  ```bash
  cd src/dev-ui && pnpm test -- ontology-wizard-flow
  ```

  All tests should pass green. To verify the warning UI manually:
  1. Start the dev instance: `make instance-up`
  2. Create a data source and complete a sync run.
  3. Open the data source detail and click "Edit Ontology".
  4. Confirm the AlertDialog appears before entering the editor.

  ## Caveats

  - The "Agent-proposed ontology" scenario tests use the hardcoded
    `GITHUB_PROPOSAL_NODES / GITHUB_PROPOSAL_EDGES` arrays as the "proposal".
    When the Extraction context is implemented (AIHCM-174), these arrays will be
    replaced by an API call. The tests should be updated at that point.
  - The `hasCompletedExtraction` check assumes `sync_runs` is always populated
    when a data source is fetched. If the backend omits `sync_runs` from the
    list endpoint (for performance), the page may need to fetch sync runs
    separately on demand — verify the current API response shape before
    implementing.
  - This task depends on task-115 (wizard steps 1-2 tests) to ensure the
    test setup patterns are consistent across the wizard test suite.
---
