---
task_id: audit-specs/management/data-sources.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — specs/management/data-sources.spec.md

Auditor: spec-alignment-reviewer
Spec commit: 85d49a379a52479b33f9b39994d76795066899a6
Date: 2026-04-27

---

### Summary

The implementation has significant structural gaps: three of the six required HTTP
endpoints are entirely absent. Service-layer logic exists for retrieval, update, and
deletion, but none of those operations are reachable via the API. Additionally, the
HTTP error-handling layer does not translate `DuplicateDataSourceNameError` to a
proper client error, and there is no evidence that SpiceDB authorization relationships
are cleaned up on deletion.

---

### PASS — Requirements Fully Implemented

#### Schedule Configuration (CRON / INTERVAL / MANUAL)
- Domain value object `Schedule` in `management/domain/value_objects.py` enforces all
  three types; CRON and INTERVAL reject a missing value with `InvalidScheduleError`;
  MANUAL requires no value.
- Comprehensive unit tests in `tests/unit/management/test_value_objects.py` (TestSchedule
  class, lines ~135-211).

#### Name Validation (1–100 characters)
- Enforced at two layers: Pydantic schema (`presentation/data_sources/models.py`,
  `min_length=1, max_length=100`) and domain aggregate
  (`domain/aggregates/data_source.py` validation block).

#### Credentials Encryption & Storage Path
- On creation the service encrypts raw credentials and writes them to
  `datasource/{id}/credentials` (`application/services/data_source_service.py` ~164–170).
- The aggregate and response models store only the path; raw credentials are never
  returned.

#### Default Schedule on Creation
- `Schedule(schedule_type=ScheduleType.MANUAL)` is set as the default inside the
  aggregate factory method (`domain/aggregates/data_source.py` ~line 144).

#### ULID Generation
- `DataSourceId.generate()` is called inside `DataSource.create()`
  (`domain/aggregates/data_source.py` ~line 137).

#### Knowledge Graph and Tenant Association
- Both are set during `DataSource.create()` and persisted by the repository.

#### Immutability After Deletion
- Every mutation method in the aggregate (`update_connection_config`, `request_sync`,
  `record_sync_completed`) raises `AggregateDeletedError` when `self._deleted` is True
  (`domain/aggregates/data_source.py` ~lines 190–191, 226–227, 247–248).

#### Sync Triggering
- `POST /data-sources/{ds_id}/sync` route exists (`presentation/data_sources/routes.py`
  ~lines 136–184).
- Service checks MANAGE permission, creates a sync run with status "pending", and emits
  `DataSourceSyncRequested` (`application/services/data_source_service.py` ~lines 398–460;
  `domain/events/data_source.py` ~lines 72–88).

#### Sync Run Tracking (status / started_at / completed_at / error)
- All four fields present in the SQLAlchemy model
  (`infrastructure/models/data_source_sync_run.py` ~lines 45–64).
- Cascade delete is defined via `ondelete="CASCADE"` on the FK
  (`infrastructure/models/data_source_sync_run.py` ~line 42).

#### Permission Inheritance from Parent Knowledge Graph
- SpiceDB schema defines inheritance:
  ```
  data_source.view = knowledge_graph->view
  data_source.edit = knowledge_graph->edit
  data_source.manage = knowledge_graph->manage
  ```
  (`shared_kernel/authorization/spicedb/schema.zed` ~lines 138–153).
- Integration tests in `tests/integration/management/test_data_source_authorization.py`
  verify the full inheritance chain.

#### Unauthorized / Non-existent — No Distinction
- `DataSourceService.get()` returns `None` for both the "cannot view" and "does not
  exist" cases, and the service translates this to a uniform not-found response
  (`application/services/data_source_service.py` ~lines 199–213).

---

### FAIL — Gaps Against Spec

#### GAP 1 (Critical): No HTTP GET endpoint for individual data source retrieval
- **Spec**: "The system SHALL return data source details only to users with `view`
  permission."
- **Evidence**: `DataSourceService.get()` is implemented (~line 183) and checks VIEW
  permission correctly, but there is no route (`GET /data-sources/{ds_id}` or equivalent)
  in `presentation/data_sources/routes.py`. The only read route is the collection listing.
- **Impact**: The retrieval requirement is entirely unreachable via HTTP.

#### GAP 2 (Critical): No HTTP PUT/PATCH endpoint for data source update
- **Spec**: "The system SHALL allow users with `edit` permission to update data source
  connection configuration."
- **Evidence**: `DataSourceService.update()` is implemented (~lines 266–341), performs
  the EDIT permission check, handles credential re-encryption, and blocks the
  credentials_path from being set by the client. However, no HTTP route exposes this
  method in `presentation/data_sources/routes.py`.
- **Impact**: The update requirement is entirely unreachable via HTTP.

#### GAP 3 (Critical): No HTTP DELETE endpoint for data source deletion
- **Spec**: "The system SHALL allow users with `manage` permission to delete a data
  source."
- **Evidence**: `DataSourceService.delete()` is implemented (~lines 343–396) with the
  MANAGE permission check, credential deletion, and data source deletion. However, no
  HTTP route exposes this method in `presentation/data_sources/routes.py`.
- **Impact**: The deletion requirement is entirely unreachable via HTTP.

#### GAP 4 (High): `DuplicateDataSourceNameError` not handled in the HTTP layer
- **Spec**: "WHEN a user attempts to create another with the same name / THEN the
  request is rejected with a duplicate name error."
- **Evidence**: The repository raises `DuplicateDataSourceNameError` on a UniqueConstraint
  violation (`infrastructure/repositories/data_source_repository.py` ~lines 112–115), but
  the creation route (`presentation/data_sources/routes.py` ~lines 100–133) does not catch
  this exception. It falls through to the generic handler and returns HTTP 500 instead of
  a proper 409 or 422.
- **Impact**: Clients receive an opaque server error rather than an actionable duplicate-
  name response.

#### GAP 5 (Medium): SpiceDB authorization relationship cleanup not evident on deletion
- **Spec**: "WHEN the user deletes the data source / THEN … authorization relationships
  are cleaned up."
- **Evidence**: `DataSourceService.delete()` deletes credentials, marks the aggregate
  for deletion, and emits `DataSourceDeleted`. There is no explicit call to delete SpiceDB
  relationships (no `delete_relationships` / `DeleteRelationships` call) in the service or
  in any observable event handler for `DataSourceDeleted`.
- **Impact**: Stale SpiceDB tuples for deleted data sources may accumulate, potentially
  allowing ghost permission checks.

---

### File References

| File | Notes |
|------|-------|
| `management/presentation/data_sources/routes.py` | Missing GET/{id}, PUT/PATCH/{id}, DELETE/{id} routes; DuplicateDataSourceNameError unhandled |
| `management/application/services/data_source_service.py` | get(), update(), delete() exist but unexposed |
| `management/domain/aggregates/data_source.py` | Creation, immutability, ULID — all correct |
| `management/domain/value_objects.py` | Schedule validation — correct |
| `management/infrastructure/repositories/data_source_repository.py` | Raises DuplicateDataSourceNameError — correct, but not caught upstream |
| `shared_kernel/authorization/spicedb/schema.zed` | Permission inheritance — correct; cleanup on delete absent |