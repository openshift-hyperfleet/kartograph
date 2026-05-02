---
id: task-081
title: Data Sources UI — add delete and connection-config update for existing data
  sources
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps:
- task-080
round: 0
branch: hyperloop/task-081
pr: https://github.com/openshift-hyperfleet/kartograph/pull/547
pr_title: 'feat(ui): add delete and credential-update operations to Data Sources page'
pr_description: "## What & Why\n\nThe spec requires:\n\n> **Backend API Alignment\
  \ — Scenario: Resource operations succeed end-to-end**\n> GIVEN an authenticated\
  \ user\n> WHEN the user performs any **create, read, update, or delete** operation\
  \ via the UI\n> THEN the corresponding backend API call succeeds (2xx response)\n\
  > AND the UI reflects the updated state without requiring a manual refresh\n\nThe\
  \ Data Sources page (`src/dev-ui/app/pages/data-sources/index.vue`) currently\n\
  implements **Create** (4-step wizard) and **Read** (list with sync history and ontology\n\
  edit). Both **connection-config Update** and **Delete** are missing from the UI\
  \ despite\nthe backend exposing the routes:\n\n- `PATCH /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}`\
  \ — update name\n  and/or credentials\n- `DELETE /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}`\
  \ — remove data\n  source and its sync history\n\nEach data source card currently\
  \ shows three actions: \"Edit Ontology\", \"Trigger Sync\",\nand \"View Logs\" (inside\
  \ sync history rows). There is no way for a user to:\n- Update expired credentials\
  \ (e.g., a GitHub PAT that has rotated)\n- Remove a data source they no longer want\n\
  \nThis PR adds:\n1. An **Edit Config** button on each data source card that opens\
  \ a side panel to update\n   the name and/or credentials (access token) for the\
  \ data source.\n2. A **Delete** button that opens an `AlertDialog` confirmation\
  \ warning about loss of\n   sync history.\n\nBoth operations refresh the data source\
  \ list on success (satisfying \"UI reflects the\nupdated state without requiring\
  \ a manual refresh\").\n\n## Spec Requirements Satisfied\n\n**Requirement: Backend\
  \ API Alignment — Scenario: Resource operations succeed end-to-end**\nfrom `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> WHEN the user performs any create, read, **update**, or **delete** operation\
  \ via the UI\n> THEN the corresponding backend API call succeeds (2xx response)\n\
  > AND the UI reflects the updated state without requiring a manual refresh\n\n**Requirement:\
  \ Data Source Connection — Scenario: Credential handling**:\n\n> GIVEN credentials\
  \ provided during data source setup\n> WHEN the data source is saved\n> THEN credentials\
  \ are encrypted and stored server-side\n> AND the plaintext is never persisted in\
  \ the browser\n\nThe credential-update flow must also honour this: the new credential\
  \ is submitted to\nthe backend (PATCH) immediately; it is never stored in component\
  \ state beyond the\nephemeral input value.\n\n## Key Design Decisions\n\n- **Edit\
  \ Config as a side Sheet (not inline)**: credentials are sensitive; a Sheet\n  keeps\
  \ them isolated and makes it clear the user is in \"edit credentials\" mode.\n \
  \ This follows the existing pattern used by the Workspace and Group detail panels.\n\
  \n- **Credential masking**: the edit form shows an empty token input (placeholder\n\
  \  `\"Leave blank to keep existing\"`) so the current credential is never exposed\
  \ in\n  the browser. Only a new value, when entered, is submitted via PATCH.\n\n\
  - **AlertDialog for delete**: uses the `AlertDialog` component added by `task-080`.\n\
  \  The confirmation body warns that all sync history will be permanently removed.\n\
  \n- **data-source-id preserved in list**: after PATCH, the local `dataSources` array\n\
  \  entry is updated in-place so the UI does not flicker to a loading state.\n\n\
  - **Frontend-only for delete/PATCH UI**: both backend routes exist and are tested.\n\
  \  No backend changes are required.\n\n- **kg_id from data source record**: each\
  \ `DataSourceResponse` already includes\n  `knowledge_graph_id` — the edit and delete\
  \ handlers use this to construct the\n  correct nested API path.\n\n- **TDD first**:\
  \ all logic tests and structural tests are written before any\n  implementation\
  \ changes to the Vue file.\n\n## Files Affected\n\n- `src/dev-ui/app/tests/data-sources.test.ts`\
  \ — new test groups for edit-config and\n  delete behaviour (logic tests and structural\
  \ checks).\n- `src/dev-ui/app/pages/data-sources/index.vue` — add edit-config Sheet\
  \ state,\n  delete AlertDialog state, `openEditConfig`, `handleEditConfig`, `openDeleteDs`,\n\
  \  `handleDeleteDs`, and the corresponding template sections. Add Edit Config and\n\
  \  Delete buttons to the per-data-source action row.\n\n## How to Verify\n\n1. `cd\
  \ src/dev-ui && npm run test` — all new tests pass.\n2. Open the Data Sources page\
  \ with at least one data source.\n3. Click **Edit Config** → Sheet opens with the\
  \ data source name pre-filled and an\n   empty token field.\n4. Enter a new name\
  \ and/or a new token, click Save → PATCH is called; list refreshes\n   with the\
  \ new name; success toast appears.\n5. Leave the token field empty and save → PATCH\
  \ is called with only `name`; token is\n   unchanged on the backend.\n6. Click **Delete**\
  \ → AlertDialog appears warning that sync history will be lost.\n7. Click Confirm\
  \ → DELETE is called; data source disappears from list; success toast.\n8. Click\
  \ Cancel on the delete dialog → no API call is made.\n9. Trigger a PATCH or DELETE\
  \ with a network error → error toast appears; UI state\n   resets correctly.\n\n\
  ## TDD Cycle\n\n1. Write logic tests for `handleEditConfig` (validation, PATCH call,\
  \ refresh, credential\n   masking, error) — RED.\n2. Write logic tests for `handleDeleteDs`\
  \ (confirm, cancel, DELETE call, refresh,\n   error) — RED.\n3. Write structural\
  \ tests verifying Edit Config Sheet and delete AlertDialog are present\n   in the\
  \ template — RED.\n4. Implement `openEditConfig`, `handleEditConfig`, `openDeleteDs`,\
  \ `handleDeleteDs` and\n   the two template additions — GREEN.\n5. Run `cd src/dev-ui\
  \ && npm run test` — all pass.\n6. Commit atomically.\n\n## Caveats\n\n- The adapter\
  \ type is immutable after creation; the Edit Config sheet does NOT expose\n  a field\
  \ for adapter type.\n- The current credential (access token) is never fetched from\
  \ the backend for display\n  (it is stored encrypted). The token input is always\
  \ empty on open. This is correct\n  per the spec's credential-handling scenario.\n\
  - If the user opens the Edit Config sheet and saves without entering a token, the\
  \ PATCH\n  body should omit `credentials` entirely (not send an empty string) so\
  \ the backend\n  preserves the existing credential. This must be verified in the\
  \ logic tests.\n- `task-080` (AlertDialog component) must be merged before this\
  \ task begins."
---
