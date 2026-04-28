---
task_id: audit-specs/management/data-sources.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Spec Alignment Audit — specs/management/data-sources.spec.md

Worker: spec-alignment-reviewer
Date: 2026-04-28

---

## Gaps in Completed Work

### GAP 1: No HTTP endpoint for single Data Source retrieval (Requirement: Data Source Retrieval)
- **Spec**: "WHEN the user requests it by ID, THEN the data source details are returned (without raw credentials)"
- **Code**: `DataSourceService.get()` exists at `src/api/management/application/services/data_source_service.py:183` but no HTTP route exposes it.
- **Routes file** (`src/api/management/presentation/data_sources/routes.py`): Only 4 routes are registered — `GET /knowledge-graphs/{kg_id}/data-sources` (list), `POST /knowledge-graphs/{kg_id}/data-sources` (create), `POST /data-sources/{ds_id}/sync` (trigger sync), `GET /data-sources/{ds_id}/sync-runs` (list sync runs).
- **Missing**: `GET /data-sources/{ds_id}` route.
- **No test** for this route exists in `src/api/tests/unit/management/presentation/test_data_sources_routes.py`.

### GAP 2: No HTTP endpoint for Data Source update (Requirement: Data Source Update)
- **Spec**: "WHEN the user updates the name, connection config, or raw credentials, THEN the data source metadata is updated"
- **Code**: `DataSourceService.update()` exists at `src/api/management/application/services/data_source_service.py:266` but no HTTP route exposes it.
- **Missing**: `PUT /data-sources/{ds_id}` or `PATCH /data-sources/{ds_id}` route and corresponding `UpdateDataSourceRequest` model.
- **No test** for an update route exists in `src/api/tests/unit/management/presentation/test_data_sources_routes.py`.

### GAP 3: No HTTP endpoint for Data Source deletion (Requirement: Data Source Deletion)
- **Spec**: "WHEN the user deletes the data source, THEN the encrypted credentials are deleted first, AND the data source is deleted, AND authorization relationships are cleaned up"
- **Code**: `DataSourceService.delete()` exists at `src/api/management/application/services/data_source_service.py:343` but no HTTP route exposes it.
- **Missing**: `DELETE /data-sources/{ds_id}` route.
- **No test** for a delete route exists in `src/api/tests/unit/management/presentation/test_data_sources_routes.py`.

### GAP 4: Duplicate name error returns HTTP 500 instead of a meaningful client error (Requirement: Duplicate name within knowledge graph)
- **Spec**: "WHEN a user attempts to create another with the same name, THEN the request is rejected with a duplicate name error"
- **Code**: The repository raises `DuplicateDataSourceNameError` (defined in `src/api/management/ports/exceptions.py:20`, raised in `src/api/management/infrastructure/repositories/data_source_repository.py:112`). The service does not catch it. The create route at `src/api/management/presentation/data_sources/routes.py:128-132` catches it as the generic `Exception` handler and returns HTTP 500 ("Failed to create data source"). No dedicated catch for `DuplicateDataSourceNameError` exists in either the service or the route.
- The client receives no actionable "duplicate name" signal — only a generic 500 error.

---

## Aligned Requirements (verified)

- Data source creation with ULID id, MANUAL schedule default, KG/tenant association, credential encryption at `datasource/{id}/credentials` — all correct.
- Name validation (1–100 chars) enforced at domain aggregate layer.
- Schedule configuration (MANUAL/CRON/INTERVAL) with missing-value validation — correct.
- Retrieval logic (returns None for unauthorized or missing, no existence leakage) — correct in service layer.
- Update immutability after deletion (`AggregateDeletedError`) and sync immutability — correct.
- Delete: credentials deleted first, then DS deleted, then `DataSourceDeleted` event written to outbox for SpiceDB cleanup — correct.
- Sync triggering: sync run created with status "pending", `DataSourceSyncRequested` event emitted via outbox — correct.
- Sync run tracking: status/started_at/completed_at/error fields present in `DataSourceSyncRun` entity and `DataSourceSyncRunModel`.
- Cascade deletion of sync runs: `ON DELETE CASCADE` FK on `data_source_sync_runs.data_source_id` — correct.
- Permission inheritance: SpiceDB schema `data_source.view/edit/manage = knowledge_graph->view/edit/manage` — correct and integration-tested.
- All 326 unit tests pass.