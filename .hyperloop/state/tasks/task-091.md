---
id: task-091
title: 'UI: Backend API alignment — verify all CRUD operations use correct routes
  and parent context'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps: []
round: 0
branch: hyperloop/task-091
pr: https://github.com/openshift-hyperfleet/kartograph/pull/557
pr_title: 'fix(ui): ensure all resource CRUD operations call correct API routes with
  required parent context'
pr_description: "## What & Why\n\nThe **Backend API Alignment** requirement was added\
  \ to `specs/ui/experience.spec.md`:\n\n> The system SHALL successfully complete\
  \ all resource operations by correctly\n> integrating with the backend REST API.\n\
  \nwith two concrete scenarios:\n\n**Scenario: Resource operations succeed end-to-end**\n\
  > GIVEN a user performs any create, read, update, or delete operation via the UI\n\
  > WHEN the operation is submitted\n> THEN the corresponding backend API call succeeds\
  \ (2xx response)\n> AND the UI reflects the updated state without requiring a manual\
  \ refresh\n\n**Scenario: Parent context is preserved**\n> GIVEN a resource that\
  \ is scoped to a parent (e.g., a knowledge graph within a workspace)\n> WHEN the\
  \ user creates or lists that resource\n> THEN the UI includes the parent context\
  \ required by the API\n> AND the operation succeeds\n\nThe backend REST API uses\
  \ scoped (nested) routes for resources that belong to a\nparent entity. When the\
  \ UI calls the wrong route — e.g., `POST /management/data-sources`\ninstead of `POST\
  \ /management/knowledge-graphs/{kg_id}/data-sources` — the API\nreturns a 4xx and\
  \ the UI operation silently fails. This requirement makes the\nparent-context contract\
  \ explicit for every UI page.\n\n## What This PR Does\n\n### 1. Audit all CRUD operations\
  \ in `src/dev-ui/app/pages/`\n\nFor each page, verify that every `apiFetch()` call\
  \ uses the correct backend route.\nCross-reference against the management, IAM,\
  \ and graph API route definitions in\n`src/api/`.\n\nKey resources and their expected\
  \ route patterns:\n\n| Resource | Create route | List route | Update/Delete route\
  \ |\n|---|---|---|---|\n| Knowledge Graph | `POST /management/workspaces/{workspace_id}/knowledge-graphs`\
  \ | `GET /management/knowledge-graphs` | `PATCH/DELETE /management/knowledge-graphs/{id}`\
  \ |\n| Data Source | `POST /management/knowledge-graphs/{kg_id}/data-sources` |\
  \ via KG listing | `PATCH/DELETE /management/knowledge-graphs/{kg_id}/data-sources/{ds_id}`\
  \ |\n| Workspace | `POST /iam/workspaces` (tenant-scoped via header) | `GET /iam/workspaces`\
  \ | `PATCH/DELETE /iam/workspaces/{id}` |\n| Group | `POST /iam/workspaces/{workspace_id}/groups`\
  \ | `GET /iam/workspaces/{workspace_id}/groups` | per-group routes |\n| API Key\
  \ | `POST /iam/api-keys` | `GET /iam/api-keys` | `DELETE /iam/api-keys/{id}` |\n\
  \nFor each call, verify:\n- The route path includes all required parent path parameters.\n\
  - The request body does NOT duplicate path parameters (e.g., no `workspace_id`\n\
  \  in body when it is already in the path).\n- After a successful mutation (2xx),\
  \ the UI reloads or updates the local state\n  so the user sees the change without\
  \ a manual refresh.\n\n### 2. Fix any mismatched routes or missing parent context\n\
  \nFor each gap found:\n1. Write a test that exercises the operation and asserts\
  \ the correct URL is called.\n2. Update the `apiFetch()` call to use the correct\
  \ route.\n3. Confirm the test passes.\n\nThe test strategy for Vue pages depends\
  \ on the project's existing test tooling\n(Vitest + Vue Test Utils, or Playwright\
  \ for E2E). Use whichever is already in\nplace for `src/dev-ui/app/tests/`.\n\n\
  ### 3. Verify UI state refresh after mutations\n\nFor each CRUD page, confirm that\
  \ a successful API response triggers a state\nreload (e.g., calls `loadKnowledgeGraphs()`\
  \ after create). If a page updates\nstate optimistically or without refetching,\
  \ confirm the displayed data matches\nwhat the API returned.\n\nSpecifically check:\n\
  - Create operations: newly-created item appears in the list after submit.\n- Update\
  \ operations: edited item reflects the new values immediately.\n- Delete operations:\
  \ removed item disappears from the list without a page refresh.\n\n### 4. Pages\
  \ to audit (minimum scope)\n\n- `src/dev-ui/app/pages/knowledge-graphs/index.vue`\
  \ — KG CRUD (create, list, edit, delete)\n- `src/dev-ui/app/pages/data-sources/index.vue`\
  \ — data source wizard and CRUD\n- `src/dev-ui/app/pages/workspaces/index.vue` —\
  \ workspace CRUD\n- `src/dev-ui/app/pages/groups/index.vue` — group CRUD\n- `src/dev-ui/app/pages/api-keys/index.vue`\
  \ — API key lifecycle\n- `src/dev-ui/app/pages/graph/mutations.vue` — mutation submission\n\
  \n## Files Affected\n\n- `src/dev-ui/app/pages/**/*.vue` — any pages with incorrect\
  \ API routes or\n  missing parent context (identified during audit)\n- `src/dev-ui/app/tests/**/*.test.ts`\
  \ — new or updated tests asserting correct\n  API routes for each CRUD operation\n\
  - `src/dev-ui/app/composables/**/*.ts` — any composables with incorrect route\n\
  \  construction\n\n## How to Verify\n\n1. For each audited page, confirm `apiFetch()`\
  \ calls match the backend route\n   table above.\n2. Run existing dev-ui tests:\
  \ `cd src/dev-ui && pnpm test` — all pass.\n3. Spin up `make instance-up`, log in,\
  \ and manually perform create/update/delete\n   on each page. Confirm no 4xx errors\
  \ appear in the browser console.\n4. Confirm the UI updates without a manual page\
  \ refresh after each operation.\n\n## Design Decisions\n\n- **Audit first**: do\
  \ not change routes speculatively. Read the backend API\n  route definitions (FastAPI\
  \ routers) before updating any frontend call.\n- **No behavior changes**: this task\
  \ is purely about correctness of integration.\n  If a route is already correct,\
  \ leave it alone.\n- **State refresh strategy**: prefer explicit reload (`loadXxx()`)\
  \ over\n  optimistic updates unless the page already uses an established pattern.\n\
  \n## Gap Analysis\n\nThe requirement was added because at least one UI page was\
  \ observed calling an\nunscoped route where the backend requires a scoped (parent-context)\
  \ route. The\nexact page(s) must be identified during the audit. Known correct patterns\
  \ (from\nprior review):\n\n| Page | Create route | Status |\n|---|---|---|\n| `knowledge-graphs/index.vue`\
  \ | `POST /management/workspaces/${workspaceId}/knowledge-graphs` | ✅ |\n| `data-sources/index.vue`\
  \ | `POST /management/knowledge-graphs/${kgId}/data-sources` | ✅ |\n| `data-sources/index.vue`\
  \ | `PATCH/DELETE /management/knowledge-graphs/${kgId}/data-sources/${dsId}` | ✅\
  \ |\n\nRemaining pages (workspaces, groups, API keys, mutations) must be audited\n\
  against the backend route table.\n\n## TDD Cycle\n\n1. For each page, write a test\
  \ that mocks `apiFetch` and asserts the expected\n   URL — RED (or GREEN if already\
  \ correct).\n2. Fix any incorrect routes — GREEN.\n3. Confirm no regressions: `cd\
  \ src/dev-ui && pnpm test`.\n4. Commit atomically per page or per logical group."
---
