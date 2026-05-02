---
id: task-079
title: Knowledge Graphs UI — add inline edit (rename/re-describe) and delete with
  confirmation
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps: []
round: 1
branch: hyperloop/task-079
pr: https://github.com/openshift-hyperfleet/kartograph/pull/543
pr_title: 'feat(ui): add edit and delete operations to Knowledge Graphs page'
pr_description: "## What & Why\n\nThe spec requires:\n\n> **Backend API Alignment\
  \ — Scenario: Resource operations succeed end-to-end**\n> GIVEN an authenticated\
  \ user\n> WHEN the user performs any **create, read, update, or delete** operation\
  \ via the UI\n> THEN the corresponding backend API call succeeds (2xx response)\n\
  > AND the UI reflects the updated state without requiring a manual refresh\n\nThe\
  \ Knowledge Graphs page (`src/dev-ui/app/pages/knowledge-graphs/index.vue`)\ncurrently\
  \ implements only **Create** and **Read**. Both **Update** and **Delete**\nare missing\
  \ from the UI despite the backend having the routes:\n\n- `PATCH /management/knowledge-graphs/{kg_id}`\
  \ — update name/description\n- `DELETE /management/knowledge-graphs/{kg_id}` — delete\
  \ with cascade\n\nEach KG card shows only \"Add Data Source\" and \"Query\" action\
  \ buttons. There is no\nway for a user to rename a KG or delete it — making the\
  \ \"update\" and \"delete\"\nclauses of the Backend API Alignment scenario unreachable.\n\
  \nThis PR adds:\n1. An **Edit** button on each KG card that opens a pre-filled dialog\
  \ to rename/re-describe.\n2. A **Delete** button that opens an `AlertDialog` confirmation\
  \ warning of cascade deletion.\n\nBoth operations refresh the list on success (satisfying\
  \ \"UI reflects the updated\nstate without requiring a manual refresh\").\n\n##\
  \ Spec Requirements Satisfied\n\n**Requirement: Backend API Alignment — Scenario:\
  \ Resource operations succeed end-to-end**\nfrom `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> WHEN the user performs any create, read, **update**, or **delete** operation\
  \ via the UI\n> THEN the corresponding backend API call succeeds (2xx response)\n\
  > AND the UI reflects the updated state without requiring a manual refresh\n\n##\
  \ Key Design Decisions\n\n- **Edit dialog (not inline)**: A modal dialog pre-filled\
  \ with the existing name and\n  description matches the established create-dialog\
  \ pattern. Inline editing\n  (contenteditable) is harder to test and inconsistent\
  \ with the rest of the UI.\n\n- **AlertDialog for delete**: shadcn/vue `AlertDialog`\
  \ is the correct component for\n  destructive confirmations. The dialog body warns\
  \ explicitly that all connected\n  data sources will also be deleted (cascade).\n\
  \n- **Optimistic refresh**: Both `handleEdit` and `handleDelete` call `loadKnowledgeGraphs()`\n\
  \  inside the `try` block after a successful API call — identical to the `handleCreate`\n\
  \  pattern already in the file.\n\n- **Frontend-only**: No backend changes. Both\
  \ endpoints exist and are tested.\n\n- **TDD first**: Unit tests for `handleEdit`\
  \ and `handleDelete` logic (validation,\n  API call shape, refresh, error handling)\
  \ and structural tests verifying the Vue\n  template contains the expected elements\
  \ — all written before implementation.\n\n## Files Affected\n\n- `src/dev-ui/app/tests/knowledge-graphs.test.ts`\
  \ — new test groups for edit and\n  delete behaviour (logic tests + one structural\
  \ test group).\n- `src/dev-ui/app/pages/knowledge-graphs/index.vue` — add edit state,\
  \ delete state,\n  `handleEdit`, `handleDelete`, edit dialog, delete `AlertDialog`,\
  \ and per-card action\n  buttons.\n\n## How to Verify\n\n1. `cd src/dev-ui && npm\
  \ run test` — all new tests pass.\n2. Open the Knowledge Graphs page with at least\
  \ one KG.\n3. Click the **Edit** (pencil) button → dialog opens pre-filled with\
  \ name and description.\n4. Change the name and click Save → list refreshes with\
  \ new name; success toast shown.\n5. Click the **Delete** (trash) button → AlertDialog\
  \ appears with cascade warning.\n6. Click Confirm → KG disappears from list; success\
  \ toast shown.\n7. During delete, clicking Cancel aborts without any API call.\n\
  8. Trigger a name conflict (duplicate name) → 409 error toast appears.\n\n## TDD\
  \ Cycle\n\n1. Write unit tests for `handleEdit` and `handleDelete` (RED).\n2. Write\
  \ structural tests for edit dialog and delete AlertDialog in the Vue file (RED).\n\
  3. Implement edit/delete state, handlers, dialogs, and per-card buttons (GREEN).\n\
  4. Run `cd src/dev-ui && npm run test` — all pass.\n5. Commit atomically."
---
