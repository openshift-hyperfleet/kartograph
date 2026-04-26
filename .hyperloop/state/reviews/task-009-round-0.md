---
task_id: task-009
round: 0
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review — task-009 (Data Sources)

Reviewed against: `specs/management/data-sources.spec.md`
Branch: `hyperloop/task-009`
Implementation commit: `9e47efb5` (GET/PATCH/DELETE routes + schedule support)

---

## Requirement Coverage

### Requirement: Data Source Creation

#### Scenario: Successful creation — COVERED
- Domain: `DataSource.create()` generates ULID, sets `knowledge_graph_id`, `tenant_id`,
  defaults to `ScheduleType.MANUAL`.
- Service: `DataSourceService.create()` checks `Permission.EDIT` on KG before creating.
- Route: `POST /knowledge-graphs/{kg_id}/data-sources` returns 201.
- Tests: `test_create_sets_all_fields`, `test_create_sets_default_manual_schedule`,
  `test_create_checks_edit_permission_on_kg`, `test_create_data_source_returns_201`.

#### Scenario: Creation with credentials — COVERED
- Service stores credentials at `datasource/{id}/credentials` via `secret_store.store()`.
- `DataSourceResponse` omits `credentials_path`; raw credentials never returned.
- Tests: `test_create_stores_credentials_when_provided`, `test_create_data_source_with_credentials`.

#### Scenario: Duplicate name within knowledge graph — PARTIAL
- Repo correctly raises `DuplicateDataSourceNameError` on `IntegrityError` with
  `uq_data_sources_kg_name`. Integration test `test_duplicate_name_in_same_kg_raises_error`
  verifies repo-layer behavior.
- GAP: `DuplicateDataSourceNameError(Exception)` is NOT caught in the `create_data_source`
  route handler. It falls through to `except Exception` and returns HTTP 500. The spec says
  "rejected with a duplicate name error"; returning 500 is not a meaningful rejection to the client.
- GAP: No unit test at the service or route level exercises this failure path or asserts
  the HTTP response code.

---

### Requirement: Data Source Name Validation

#### Scenario: Valid name — COVERED
- `DataSource._validate_name()` enforces 1-100 characters.
- Pydantic models enforce `min_length=1, max_length=100`.
- Tests: `test_create_accepts_name_exactly_100_chars`, `test_create_accepts_single_char_name`.

#### Scenario: Empty or oversized name — COVERED
- Domain raises `InvalidDataSourceNameError`; Pydantic raises 422 at deserialization.
- Tests: `test_create_rejects_empty_name`, `test_create_rejects_name_over_100_chars`,
  `test_update_connection_rejects_empty_name`, `test_create_data_source_requires_name` (422).

---

### Requirement: Schedule Configuration

#### Scenario: Manual schedule — COVERED
- `Schedule(ScheduleType.MANUAL)` accepts `value=None`.
- Tests: `test_manual_schedule_without_value`, `test_create_sets_default_manual_schedule`.

#### Scenario: Cron schedule — COVERED
- `Schedule(ScheduleType.CRON, value="0 * * * *")` is valid.
- Tests: `test_cron_schedule_with_value`, `test_update_with_schedule_type_updates_schedule`.

#### Scenario: Interval schedule — COVERED
- `Schedule(ScheduleType.INTERVAL, value="PT1H")` is valid.
- Tests: `test_interval_schedule_with_value`, `test_update_schedule_to_interval`.

#### Scenario: Missing schedule value — PARTIAL
- `Schedule.__post_init__()` raises `InvalidScheduleError` for CRON/INTERVAL without a value.
  Value-object tests `test_cron_schedule_without_value_raises`,
  `test_interval_schedule_without_value_raises` cover domain behavior.
- GAP: `InvalidScheduleError(Exception)` is NOT caught in the `update_data_source` route
  handler. It falls through to `except Exception` and returns HTTP 500. The spec says
  "rejected with a validation error"; 500 is not a validation error response (422 would be correct).
- GAP: No unit test at the service or route level sends PATCH with `schedule_type=cron` and
  no `schedule_value` and asserts the HTTP response code.

---

### Requirement: Data Source Retrieval

#### Scenario: Authorized retrieval — COVERED
- Service `get()` checks `Permission.VIEW`; `DataSourceResponse` excludes raw credentials.
- Tests: `test_get_data_source_returns_200`, `test_get_returns_aggregate_on_success`.

#### Scenario: Unauthorized or non-existent — COVERED
- Service returns `None` for both missing and unauthorized; route returns 404 in both cases.
- Tests: `test_get_data_source_returns_404_when_not_found`,
  `test_get_returns_none_when_not_found`, `test_get_returns_none_when_permission_denied`.

---

### Requirement: Data Source Update

#### Scenario: Update connection config — COVERED
- `DataSourceService.update()` accepts name, connection_config, raw_credentials, schedule.
- `UpdateDataSourceRequest` has no `credentials_path` field; client cannot set it directly.
- Credentials stored at system-managed path `datasource/{id}/credentials`.
- Tests: `test_update_data_source_returns_200`, `test_update_data_source_calls_service_correctly`,
  `test_update_data_source_with_credentials`, `test_update_stores_credentials_when_provided`.

---

### Requirement: Data Source Immutability After Deletion

#### Scenario: Mutation after deletion — COVERED
- Domain: `update_connection()`, `update_schedule()`, `request_sync()` all raise
  `AggregateDeletedError` when `_deleted=True`.
  Tests: `test_update_connection_raises_after_deletion`,
  `test_update_schedule_raises_after_deletion`, `test_request_sync_raises_after_deletion`.
- Service level: after `delete()`, the DS row is removed from DB; subsequent `update()` or
  `trigger_sync()` finds `None` from the repo and raises `ValueError` ("not found") which maps
  to 404. Covered by `test_update_raises_value_error_when_not_found` and
  `test_trigger_sync_raises_value_error_when_not_found`.

---

### Requirement: Data Source Deletion

#### Scenario: Successful deletion — COVERED
- Service deletes credentials first (`secret_store.delete()`), marks for deletion, calls
  `_ds_repo.delete()` which also persists `DataSourceDeleted` event via outbox.
- Route returns 204 No Content.
- Tests: `test_delete_removes_credentials_if_path_exists`, `test_delete_data_source_returns_204`,
  `test_delete_data_source_returns_403_when_unauthorized`,
  `test_delete_data_source_returns_404_when_not_found`.

---

### Requirement: Sync Triggering

#### Scenario: Trigger sync — COVERED
- Service creates `DataSourceSyncRun(status="pending")` and calls `ds.request_sync()` which
  emits `DataSourceSyncRequested`.
- Tests: `test_trigger_sync_creates_sync_run_and_saves_ds`,
  `test_trigger_sync_returns_201_with_sync_run`.

---

### Requirement: Sync Run Tracking

#### Scenario: Sync lifecycle — COVERED
- `DataSourceSyncRun` entity tracks: status (pending/running/completed/failed), started_at,
  completed_at, error. DB CHECK constraint enforces valid status values.
- Tests (integration): `test_saves_and_retrieves_sync_run`, `test_saves_completed_sync_run`,
  `test_saves_failed_sync_run`, `test_updates_sync_run_status`.

#### Scenario: Cascade deletion — COVERED
- `DataSourceSyncRunModel` FK has `ondelete="CASCADE"`.
- Tests (integration): `test_sync_runs_deleted_when_data_source_deleted`.

---

### Requirement: Permission Inheritance

#### Scenario: Inherited access — COVERED
- SpiceDB schema: `data_source.view = knowledge_graph->view`,
  `data_source.edit = knowledge_graph->edit`,
  `data_source.manage = knowledge_graph->manage`.
- Tests (integration): `test_kg_editor_can_view_data_source`,
  `test_kg_editor_can_edit_data_source`, `test_workspace_admin_can_manage_data_source`,
  `test_workspace_member_can_view_data_source`, `test_workspace_member_cannot_edit_data_source`,
  `test_user_without_kg_access_cannot_view_data_source`,
  plus `TestDataSourceDirectKGGrantInheritance` tests.

---

## Verdict: FAIL

Two SHALL scenarios lack proper HTTP-layer error translation AND route/service-level test coverage.
15 of 17 scenarios are fully implemented and tested; 2 are PARTIAL.

---

### Fix 1 — Duplicate Name Rejection (Data Source Creation)

In `management/presentation/data_sources/routes.py`, add explicit handling in
`create_data_source` before the generic `except Exception` clause:

```python
from management.ports.exceptions import DuplicateDataSourceNameError

except DuplicateDataSourceNameError as e:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(e),
    )
```

Add a unit test in `tests/unit/management/presentation/test_data_sources_routes.py`:

```python
def test_create_data_source_returns_409_on_duplicate_name(self, test_client, mock_ds_service):
    from management.ports.exceptions import DuplicateDataSourceNameError
    mock_ds_service.create.side_effect = DuplicateDataSourceNameError(
        "Data source 'GitHub Repos' already exists in knowledge graph"
    )
    response = test_client.post(
        "/management/knowledge-graphs/01JPQRST1234567890ABCDEFKG/data-sources",
        json={"name": "GitHub Repos", "adapter_type": "github", "connection_config": {}},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
```

---

### Fix 2 — Missing Schedule Value Rejection (Schedule Configuration)

In `management/presentation/data_sources/routes.py`, add explicit handling in
`update_data_source` before the generic `except Exception` clause:

```python
from management.domain.exceptions import InvalidScheduleError

except InvalidScheduleError as e:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(e),
    )
```

Add a unit test in `tests/unit/management/presentation/test_data_sources_routes.py`:

```python
def test_update_data_source_returns_422_for_cron_without_value(
    self, test_client, mock_ds_service, sample_data_source
):
    from management.domain.exceptions import InvalidScheduleError
    mock_ds_service.update.side_effect = InvalidScheduleError(
        "cron schedule requires a value"
    )
    response = test_client.patch(
        f"/management/data-sources/{sample_data_source.id.value}",
        json={"schedule_type": "cron"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
```