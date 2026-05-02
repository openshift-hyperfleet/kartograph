---
id: task-082
title: Data Sources UI — persist ontology edits to backend after extraction
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps: []
round: 0
branch: hyperloop/task-082
pr: https://github.com/openshift-hyperfleet/kartograph/pull/545
pr_title: 'feat(ui): persist post-extraction ontology edits via PATCH on data source'
pr_description: "## What & Why\n\nThe spec requires:\n\n> **Requirement: Ontology\
  \ Design — Scenario: Ontology change after initial extraction**\n> GIVEN a knowledge\
  \ graph with completed extraction\n> WHEN the user modifies the ontology\n> THEN\
  \ the system warns that this will trigger a full re-extraction\n> AND the user must\
  \ confirm before the change is applied\n\nThe Data Sources page (`src/dev-ui/app/pages/data-sources/index.vue`)\
  \ already\nimplements the warning dialog — the user sees an amber alert and must\
  \ click a\nconfirmation button before the ontology editor opens. However, the `closeOntologyEditor`\n\
  handler that fires when the user clicks \"Save\" inside the post-extraction editor\n\
  **does not call the backend**. It closes the dialog and clears local state, silently\n\
  discarding all edits. The changes are never persisted.\n\nThe backend exposes:\n\
  \n```\nPATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}\n```\n\n\
  which accepts an `ontology` field alongside `name` and `credentials`. This task\n\
  wires the post-extraction ontology editor's save action to that endpoint.\n\n##\
  \ Spec Requirements Satisfied\n\n**Requirement: Ontology Design — Scenario: Ontology\
  \ change after initial extraction**\nfrom `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> WHEN the user modifies the ontology\n> THEN the system warns that this will\
  \ trigger a full re-extraction\n> AND the user must confirm before the change is\
  \ applied\n\nThe warning and confirmation are already present. This task satisfies\
  \ the \"change is\napplied\" clause — i.e., the confirmed and reviewed ontology\
  \ is actually persisted.\n\n**Requirement: Backend API Alignment — Scenario: Resource\
  \ operations succeed end-to-end**:\n\n> WHEN the user performs any create, read,\
  \ **update**, or **delete** operation via the UI\n> THEN the corresponding backend\
  \ API call succeeds (2xx response)\n> AND the UI reflects the updated state without\
  \ requiring a manual refresh\n\nSaving an ontology is an update operation. Currently\
  \ it produces no API call at all.\n\n## Key Design Decisions\n\n- **Save path**:\
  \ `PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}`\n  with body\
  \ `{ ontology: { node_types: [...], edge_types: [...] } }`. The data source\n  record\
  \ already carries `knowledge_graph_id`, so the URL can be constructed directly.\n\
  \n- **Trigger on \"Apply & Save\" only**: the save call fires only after the user\
  \ has\n  reviewed and clicked the final \"Apply\" button in the ontology editor\
  \ dialog — not\n  on individual type edits. The existing two-step UX (review → confirm)\
  \ is preserved.\n\n- **Re-extraction trigger**: the spec says extraction begins\
  \ only after ontology\n  approval. The PATCH response from the backend may include\
  \ a sync status transition.\n  The UI should refresh the data source list after\
  \ a successful PATCH so the new sync\n  status appears.\n\n- **Saving state**: a\
  \ `savingOntology` ref gates the Apply button and shows a spinner.\n  On success,\
  \ `editOntologyOpen` is set to `false` and the data source list reloads.\n  On failure,\
  \ the dialog stays open with an error toast.\n\n- **No structural changes to the\
  \ warning flow**: the re-extraction warning dialog and\n  its confirmation logic\
  \ are untouched. This task only extends `closeOntologyEditor`\n  (or a new `saveOntology`\
  \ handler it calls) to include the PATCH call.\n\n- **TDD first**: all logic tests\
  \ and structural tests are written before implementation.\n\n## Files Affected\n\
  \n- `src/dev-ui/app/tests/data-sources.test.ts` — new test group for ontology-save\
  \ logic\n  and structural checks.\n- `src/dev-ui/app/pages/data-sources/index.vue`\
  \ — extend `closeOntologyEditor` (or add\n  `saveOntology`) with PATCH call, `savingOntology`\
  \ state, error handling, and list\n  refresh on success.\n\n## How to Verify\n\n\
  1. `cd src/dev-ui && npm run test` — all new tests pass, no regressions.\n2. Open\
  \ the Data Sources page with a data source in `completed` sync state.\n3. Click\
  \ **Edit Ontology** → re-extraction warning appears.\n4. Click **I Understand, Open\
  \ Editor** → ontology editor opens with current types.\n5. Edit a node type label\
  \ and click **Apply** (or equivalent save button).\n6. Verify a `PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}`\
  \ request\n   is made with the updated `ontology` body (inspect Network tab).\n\
  7. Verify the dialog closes and a success toast appears.\n8. Verify the data source\
  \ list refreshes (the data source card re-fetches its state).\n9. Simulate a 500\
  \ error from the PATCH → error toast appears; dialog stays open.\n\n## TDD Cycle\n\
  \n1. Write logic tests for `saveOntology`: happy path PATCH call with ontology payload,\n\
  \   list refresh on success, dialog close on success — RED.\n2. Write logic test:\
  \ PATCH failure → error toast, dialog stays open, `savingOntology`\n   reset — RED.\n\
  3. Write structural tests: `savingOntology` state declared, PATCH call present,\n\
  \   Apply button calls `saveOntology` — RED.\n4. Implement `savingOntology` ref\
  \ and extend `closeOntologyEditor` / add `saveOntology`\n   in `data-sources/index.vue`\
  \ — GREEN.\n5. Run `cd src/dev-ui && npm run test` — all pass.\n6. Commit atomically.\n\
  \n## Caveats\n\n- The exact shape of the `ontology` payload (field names, nesting)\
  \ must match the\n  backend `DataSourceUpdateRequest` schema. Verify against the\
  \ OpenAPI spec or\n  management context's Pydantic model before writing the test\
  \ fixtures.\n- If the backend initiates a re-sync automatically on PATCH (ontology\
  \ change), the\n  data source will transition to `pending`/`ingesting` state. The\
  \ list refresh will\n  surface this, which is the correct UX.\n- The simulated AI\
  \ ontology proposal (hardcoded `GITHUB_PROPOSAL_NODES/EDGES` in the\n  wizard step\
  \ 4) is out of scope for this task. Wiring the real AI proposal endpoint\n  depends\
  \ on the Extraction context (blocked on AIHCM-174)."
---
