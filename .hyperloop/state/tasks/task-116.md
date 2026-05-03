---
id: task-116
title: Ontology design wizard — tests for intent/proposal/approval + implement re-extraction
  warning
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps:
- task-115
round: 0
branch: hyperloop/task-116
pr: https://github.com/openshift-hyperfleet/kartograph/pull/588
pr_title: 'feat(ui): add ontology design wizard tests and implement re-extraction
  warning'
pr_description: "## What & Why\n\nThe data source wizard in `src/dev-ui/app/pages/data-sources/index.vue`\
  \ includes\na full 4-step ontology design flow. Steps 3 and 4 cover:\n\n- **Step\
  \ 3 — Intent description**: the user types free text about what problems\n  they\
  \ want to solve with the data source.\n- **Step 4 — Proposed ontology**: the system\
  \ presents a set of proposed node\n  and edge types for the user to review, edit,\
  \ and approve.\n\n`ontology-add-types.test.ts` (task-063) covers the **individual\
  \ type editing**\nlogic (adding, validating, and saving new types). The remaining\
  \ spec scenarios\nhave no tests and one scenario has no implementation at all.\n\
  \n### Spec gaps addressed\n\n`specs/ui/experience.spec.md` — **Requirement: Ontology\
  \ Design**:\n\n| Scenario | Status |\n|---|---|\n| Intent description | Implemented\
  \ (Step 3), **no test** |\n| Agent-proposed ontology | Partially implemented (hardcoded\
  \ GitHub proposal), **no test** |\n| Ontology review and approval | Implemented\
  \ (`approvingOntology` state), **no test** |\n| Individual type editing | Covered\
  \ by `ontology-add-types.test.ts` |\n| Ontology change after initial extraction\
  \ | **Not implemented, no test** |\n\nThe \"Agent-proposed ontology\" scenario says\
  \ the proposal comes from an AI agent.\nThe current implementation uses a hardcoded\
  \ `GITHUB_PROPOSAL_NODES / GITHUB_PROPOSAL_EDGES`\narray (a placeholder until the\
  \ Extraction context is ready). Tests should verify\nthe UI correctly presents these\
  \ proposals regardless of their origin.\n\nThe \"Ontology change after initial extraction\"\
  \ scenario is **not implemented**:\nwhen a user edits ontology for a data source\
  \ that has already had a completed\nsync run, the UI should warn them and require\
  \ confirmation before proceeding.\nThis PR implements that warning and tests it.\n\
  \n## What This Change Does\n\n### Part A — Tests for existing behavior\n\nNew file:\
  \ `src/dev-ui/app/tests/ontology-wizard-flow.test.ts`\n\n#### Step 3 — Intent description\n\
  \n**`test_intent_validation_requires_non_empty_text`**\n- With `intentText` empty,\
  \ advancing to step 4 sets `intentError` and blocks.\n- With `intentText` non-empty,\
  \ advancing succeeds and clears `intentError`.\n\n**`test_intent_text_is_not_persisted_after_wizard_close`**\n\
  - After the wizard is closed/reset, `intentText` and `intentError` return to\n \
  \ their initial empty values.\n\n#### Step 4 — Proposed ontology display\n\n**`test_github_proposal_populates_nodes_and_edges`**\n\
  - Verify that when the adapter is `'github'` and the wizard advances to step 4,\n\
  \  `proposedNodes` is populated with the hardcoded `GITHUB_PROPOSAL_NODES` array\n\
  \  and `proposedEdges` is populated from `GITHUB_PROPOSAL_EDGES`.\n- Pin the expected\
  \ node labels: `['Repository', 'Issue', 'PullRequest', 'Commit', 'User']`.\n- This\
  \ is a regression guard: if someone accidentally removes or renames a\n  proposal,\
  \ the test will catch it.\n\n**`test_ontology_ready_flag_set_after_scan_completes`**\n\
  - After the \"scan\" simulation completes (the `scanningOntology` flag goes false),\n\
  \  `ontologyReady` is true and the approval button is enabled.\n\n#### Approval\
  \ flow\n\n**`test_approval_calls_api_with_correct_ontology_payload`**\n- Mock the\
  \ API call made when `approvingOntology` fires.\n- Assert the payload includes `node_types`\
  \ and `edge_types` arrays derived from\n  `proposedNodes` and `proposedEdges`.\n\
  - Assert the payload does NOT include transient edit state (`editing`, `editLabel`,\
  \ etc.).\n\n**`test_approval_closes_wizard_on_success`**\n- After successful API\
  \ call, `wizardOpen` becomes false and `wizardStep` resets to 1.\n\n**`test_approval_shows_error_on_api_failure`**\n\
  - When the API call rejects, a toast or error message is shown and `wizardOpen`\n\
  \  remains true (wizard stays open so user can retry).\n\n### Part B — Implement\
  \ and test re-extraction warning\n\n**Spec scenario:**\n> GIVEN a knowledge graph\
  \ with completed extraction\n> WHEN the user modifies the ontology\n> THEN the system\
  \ warns that this will trigger a full re-extraction\n> AND the user must confirm\
  \ before the change is applied\n\n**Detection logic** (implement in `data-sources/index.vue`):\n\
  - A data source has \"completed extraction\" when `sync_runs` contains at least\n\
  \  one entry with `status === 'completed'`.\n- Expose a computed `hasCompletedExtraction`\
  \ that checks this.\n\n**Warning UI** (implement in `data-sources/index.vue`):\n\
  - When `hasCompletedExtraction` is true and the user clicks to edit the ontology\n\
  \  (e.g., clicks \"Edit Ontology\" on an existing data source, or opens the\n  type\
  \ editor in step 4 while `hasCompletedExtraction` is set), show an\n  `AlertDialog`\
  \ with:\n  - Title: \"Modifying the ontology will trigger a full re-extraction\"\
  \n  - Body: Explanation that all data will be re-extracted and re-applied.\n  -\
  \ Buttons: \"Cancel\" and \"Confirm and edit\".\n- Only proceed to the edit view\
  \ when the user clicks \"Confirm and edit\".\n\n**Tests** (in `src/dev-ui/app/tests/ontology-wizard-flow.test.ts`):\n\
  \n**`test_has_completed_extraction_false_when_no_sync_runs`**\n- A data source with\
  \ `sync_runs: []` returns false from `hasCompletedExtraction`.\n\n**`test_has_completed_extraction_false_when_all_runs_failed`**\n\
  - A data source with sync runs all having `status: 'failed'` returns false.\n\n\
  **`test_has_completed_extraction_true_when_any_run_completed`**\n- A data source\
  \ with one `status: 'completed'` run returns true even if other\n  runs failed.\n\
  \n**`test_re_extraction_warning_shown_before_ontology_edit`**\n- Mock `hasCompletedExtraction`\
  \ returning true.\n- Simulate user clicking the edit ontology button.\n- Assert\
  \ that the re-extraction `AlertDialog` is shown (e.g., the dialog's\n  `open` prop\
  \ is true).\n- Assert that the edit view is NOT shown yet (user must confirm first).\n\
  \n**`test_edit_proceeds_after_confirmation`**\n- User clicks \"Confirm and edit\"\
  \ in the AlertDialog.\n- Assert the dialog closes and the type editor is now visible.\n\
  \n**`test_edit_cancelled_leaves_ontology_unchanged`**\n- User clicks \"Cancel\"\
  \ in the AlertDialog.\n- Assert the dialog closes and the type editor is NOT shown.\n\
  - Assert `proposedNodes` and `proposedEdges` are unchanged.\n\n## Files / Areas\
  \ Affected\n\n- `src/dev-ui/app/pages/data-sources/index.vue` — add `hasCompletedExtraction`\n\
  \  computed, re-extraction `AlertDialog`, and guard on the edit ontology trigger\n\
  - `src/dev-ui/app/tests/ontology-wizard-flow.test.ts` (new) — all tests above\n\n\
  ## How to Verify\n\n```bash\ncd src/dev-ui && pnpm test -- ontology-wizard-flow\n\
  ```\n\nAll tests should pass green. To verify the warning UI manually:\n1. Start\
  \ the dev instance: `make instance-up`\n2. Create a data source and complete a sync\
  \ run.\n3. Open the data source detail and click \"Edit Ontology\".\n4. Confirm\
  \ the AlertDialog appears before entering the editor.\n\n## Caveats\n\n- The \"\
  Agent-proposed ontology\" scenario tests use the hardcoded\n  `GITHUB_PROPOSAL_NODES\
  \ / GITHUB_PROPOSAL_EDGES` arrays as the \"proposal\".\n  When the Extraction context\
  \ is implemented (AIHCM-174), these arrays will be\n  replaced by an API call. The\
  \ tests should be updated at that point.\n- The `hasCompletedExtraction` check assumes\
  \ `sync_runs` is always populated\n  when a data source is fetched. If the backend\
  \ omits `sync_runs` from the\n  list endpoint (for performance), the page may need\
  \ to fetch sync runs\n  separately on demand — verify the current API response shape\
  \ before\n  implementing.\n- This task depends on task-115 (wizard steps 1-2 tests)\
  \ to ensure the\n  test setup patterns are consistent across the wizard test suite."
---
