---
id: task-068
title: Backend API Alignment — test data source creation uses KG-scoped endpoint
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps: []
round: 0
branch: hyperloop/task-068
pr: null
pr_title: 'test(ui): verify data source creation uses KG-scoped POST endpoint'
pr_description: "## What & Why\n\nThe `experience.spec.md` spec was updated to add\
  \ a new **Requirement: Backend API\nAlignment** with two scenarios:\n\n> **Scenario:\
  \ Resource operations succeed end-to-end**\n> GIVEN a user performs any create,\
  \ read, update, or delete operation via the UI\n> WHEN the operation is submitted\n\
  > THEN the corresponding backend API call succeeds (2xx response)\n> AND the UI\
  \ reflects the updated state without requiring a manual refresh\n\n> **Scenario:\
  \ Parent context is preserved**\n> GIVEN a resource that is scoped to a parent (e.g.,\
  \ a knowledge graph within a\n> workspace)\n> WHEN the user creates or lists that\
  \ resource\n> THEN the UI includes the parent context required by the API\n> AND\
  \ the operation succeeds\n\nAll existing resource operations are correctly implemented,\
  \ and most have explicit\nendpoint-URL assertions in the test suite. One gap remains:\
  \ the **data source\ncreation** call (`POST /management/knowledge-graphs/{kg_id}/data-sources`)\
  \ is not\nverified at the `apiFetch` level. The current test in `data-sources.test.ts`\
  \ mocks\n`createDataSource()` as a whole function, confirming `kg_id` is passed\
  \ to it, but\nnever verifying that the resulting HTTP path includes the KG ID.\n\
  \nThis PR closes that gap. It adds a dedicated test that injects a mocked `apiFetch`\n\
  directly into a `createDataSource` implementation and asserts the URL path contains\n\
  the correct parent knowledge-graph ID. No production code changes are required —\
  \ the\nimplementation is already correct.\n\n## Spec Requirements Satisfied\n\n\
  **Requirement: Backend API Alignment — Scenario: Parent context is preserved** from\n\
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\n> GIVEN\
  \ a resource that is scoped to a parent (e.g., a knowledge graph within a\n> workspace)\n\
  > WHEN the user creates or lists that resource\n> THEN the UI includes the parent\
  \ context required by the API\n\nSpecifically, the data source create operation\
  \ is scoped to a knowledge graph (the\nparent). This PR ensures there is an explicit\
  \ test asserting the KG ID appears in\nthe API path.\n\n## Coverage landscape (for\
  \ context)\n\nThe following parent-context assertions already exist in the test\
  \ suite:\n\n| Operation | Endpoint | Tested? |\n|---|---|---|\n| Create knowledge\
  \ graph | `POST /management/workspaces/{ws_id}/knowledge-graphs` | ✅ `knowledge-graphs.test.ts`\
  \ line 101 |\n| List data sources | `GET /management/knowledge-graphs/{kg_id}/data-sources`\
  \ | ✅ `data-sources.test.ts` line 596 |\n| List sync runs | `GET /management/data-sources/{ds_id}/sync-runs`\
  \ | ✅ `data-sources.test.ts` line 648 |\n| Trigger sync | `POST /management/data-sources/{ds_id}/sync`\
  \ | ✅ `sync-monitoring-extended.test.ts` line 317 |\n| Submit mutations | `POST\
  \ /graph/knowledge-graphs/{kg_id}/mutations` | ✅ task-065 (`mutations-kg-selector.test.ts`)\
  \ |\n| **Create data source** | `POST /management/knowledge-graphs/{kg_id}/data-sources`\
  \ | ❌ **missing — this PR** |\n\n## Key Design Decisions\n\n- **Test-only PR**:\
  \ No production code changes. The implementation in\n  `data-sources/index.vue`\
  \ already constructs the correct URL:\n  ```typescript\n  apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`,\
  \ { method: 'POST', ... })\n  ```\n  The tests just need to reach through to `apiFetch`\
  \ rather than mocking\n  `createDataSource` at the wrapper level.\n- **Inline function\
  \ extraction pattern**: Following the established codebase pattern\n  (see `sync-monitoring-extended.test.ts`),\
  \ extract `createDataSource` as a\n  parameterized pure function in the test that\
  \ takes `apiFetch` as a dependency.\n  This lets the test inject a `vi.fn()` mock\
  \ and assert the exact URL call.\n- **Added to `data-sources.test.ts`**: Keeps DS\
  \ creation coverage co-located with\n  DS listing and sync run tests in the same\
  \ file.\n\n## Files Affected\n\n- `src/dev-ui/app/tests/data-sources.test.ts` —\
  \ add a new `describe` block\n  \"Backend API Alignment — data source creation uses\
  \ KG-scoped endpoint\" with\n  3-4 test cases verifying the URL path, HTTP method,\
  \ and request body.\n\n## How to Verify\n\n1. Run `cd src/dev-ui && pnpm test --\
  \ data-sources` — new describe block passes.\n2. Run `cd src/dev-ui && pnpm test`\
  \ — no regressions in any other test file.\n3. Confirm the new tests are in the\
  \ \"Backend API Alignment\" section and reference\n   the spec scenario in their\
  \ comments.\n\n## Caveats\n\n- No dependency on task-065: this task covers the data\
  \ source creation endpoint,\n  which is orthogonal to the mutations endpoint fix\
  \ in task-065.\n- No production code changes means no risk of regressions — this\
  \ PR is purely\n  additive test coverage.\n- The test extraction pattern mirrors\
  \ `triggerSync()` in `sync-monitoring-extended.test.ts`,\n  which is the established\
  \ precedent for testing URL patterns in this codebase."
---
