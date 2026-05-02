---
id: task-078
title: Management API — add GET /management/data-sources flat list with latest_sync_run
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps: []
round: 1
branch: hyperloop/task-078
pr: https://github.com/openshift-hyperfleet/kartograph/pull/542
pr_title: 'feat(management): add GET /management/data-sources flat list endpoint with
  latest_sync_run'
pr_description: "## What & Why\n\nThe sidebar layout in `src/dev-ui/app/layouts/default.vue`\
  \ shows a count badge on\nthe \"Data Sources\" nav item indicating how many data\
  \ sources currently have an active\nsync in progress. This satisfies the spec's\
  \ Navigation Structure requirement:\n\n> **Data** — Knowledge Graphs, **Data Sources\
  \ (with sync status)**\n\nThe badge implementation calls:\n\n```typescript\nconst\
  \ result = await apiFetch<{ data_sources: Array<{ latest_sync_run?: { status: string\
  \ } }> }>(\n  '/management/data-sources'\n)\n```\n\nHowever, `GET /management/data-sources`\
  \ **does not exist** in the Management API.\nThe only data-sources list endpoint\
  \ is `GET /management/knowledge-graphs/{kg_id}/data-sources`\n(scoped to a single\
  \ KG). The sidebar silently catches the 404 and shows no badge\n(`activeSyncCount`\
  \ stays 0), so the \"(with sync status)\" clause is never satisfied.\n\nThis PR\
  \ adds the missing flat list endpoint scoped to the authenticated user's tenant,\n\
  with an embedded `latest_sync_run` object so the badge works with a single API call.\n\
  \n## Spec Requirements Satisfied\n\n**Requirement: Navigation Structure — Scenario:\
  \ Primary navigation** from\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> GIVEN an authenticated user\n> THEN the sidebar presents navigation grouped\
  \ as:\n>   - **Data** — Knowledge Graphs, **Data Sources (with sync status)**\n\n\
  The \"(with sync status)\" clause requires the sidebar nav item to reflect live\
  \ sync\nstate. Without a working backend endpoint, the badge always shows 0 and\
  \ the clause fails.\n\n**Requirement: Backend API Alignment — Scenario: Resource\
  \ operations succeed end-to-end**:\n\n> THEN the corresponding backend API call\
  \ succeeds (2xx response)\n\nThe sidebar currently calls a non-existent endpoint\
  \ (returns 404). Making it return\n2xx satisfies this scenario for the sidebar's\
  \ implicit read operation.\n\n## Key Design Decisions\n\n- **New route `GET /management/data-sources`**:\
  \ Returns all data sources accessible\n  to the current user in their tenant, across\
  \ all knowledge graphs. Access is inferred\n  from SpiceDB VIEW permission on the\
  \ parent knowledge graph (same pattern as the\n  existing KG-scoped list route).\n\
  \n- **Embedded `latest_sync_run`**: A new `DataSourceWithSyncResponse` model wraps\n\
  \  `DataSourceResponse` and adds an optional `latest_sync_run: SyncRunResponse |\
  \ None`\n  field. This avoids N+1 API calls from the sidebar and is the shape the\
  \ frontend\n  already expects.\n\n- **No pagination (V1)**: The sidebar only needs\
  \ the status of active syncs, not\n  full pagination. Returns all data sources in\
  \ the tenant. If tenant scale becomes\n  an issue, pagination can be added in a\
  \ follow-up.\n\n- **Authorization**: Only data sources belonging to knowledge graphs\
  \ the user has\n  VIEW permission on are returned — consistent with existing KG\
  \ authorization patterns.\n\n- **TDD first**: Unit tests for the service method,\
  \ integration tests for the route,\n  before any implementation.\n\n## Files Affected\n\
  \n- `src/api/management/application/services/data_source_service.py` — add\n  `list_all_for_user(user_id)`\
  \ method that fetches all KGs the user can see, then\n  all data sources for each,\
  \ plus the latest sync run per data source.\n- `src/api/management/presentation/data_sources/models.py`\
  \ — add\n  `DataSourceWithSyncResponse` model with embedded `latest_sync_run`.\n\
  - `src/api/management/presentation/data_sources/routes.py` — add\n  `GET /data-sources`\
  \ route (no KG prefix) returning\n  `{ data_sources: list[DataSourceWithSyncResponse],\
  \ count: int }`.\n- `src/api/tests/unit/management/test_data_source_service.py`\
  \ — add unit tests\n  for `list_all_for_user`.\n- `src/api/tests/integration/management/test_data_sources_routes.py`\
  \ — add\n  integration test for the new route.\n- `src/dev-ui/app/layouts/default.vue`\
  \ — update `fetchActiveSyncCount` to handle\n  the response type correctly (response\
  \ is `{ data_sources: [...] }`, not an array).\n  Also align the active status set:\
  \ use `'ai_extracting'` not `'extracting'` (task-042\n  fixes the status labels;\
  \ this endpoint should emit the canonical backend values).\n\n## How to Verify\n\
  \n1. `make test-unit` — new unit tests for `list_all_for_user` pass green.\n2. `make\
  \ instance-up && make test-integration` — new route integration tests pass.\n3.\
  \ Call `GET /management/data-sources` with a valid API key while a sync is in progress\n\
  \   — verify the response includes `latest_sync_run` with an active status.\n4.\
  \ Open the dev UI with an active sync in progress — verify the Data Sources nav\
  \ item\n   shows a numbered badge (e.g., \"1\").\n5. When all syncs are completed\
  \ or failed, verify the badge disappears.\n\n## TDD Cycle\n\n1. Write unit tests\
  \ for `list_all_for_user` (RED).\n2. Implement `list_all_for_user` in the data source\
  \ service (GREEN).\n3. Write integration test for `GET /management/data-sources`\
  \ (RED).\n4. Add the route and `DataSourceWithSyncResponse` model (GREEN).\n5. Update\
  \ the default layout to remove the silent failure (GREEN for sidebar test).\n6.\
  \ `make test-unit && make test-integration` exits 0.\n\n## Caveats\n\n- This endpoint\
  \ is additive; no existing routes are changed.\n- `latest_sync_run` is the most\
  \ recent run ordered by `created_at DESC`. If a data\n  source has never synced,\
  \ `latest_sync_run` is `null`.\n- The sidebar's active status set must use `'ai_extracting'`\
  \ not `'extracting'`\n  (the backend canonical value). The status set in `default.vue`\
  \ already uses\n  `'ai_extracting'` (`ACTIVE_SYNC_STATUSES` constant), so no frontend\
  \ change is needed\n  beyond typing alignment."
---
