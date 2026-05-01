---
id: task-043
title: Add sync-run logs backend endpoint in Management context
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gap

**Requirement: Sync Monitoring — Scenario: Sync logs**
> GIVEN a sync run (in progress or completed)
> WHEN the user requests logs
> THEN detailed logs for that run are displayed

## Root Cause

The UI in `src/dev-ui/app/pages/data-sources/index.vue` already implements the
"View Logs" button and the `fetchRunLogs` function that calls:

```
GET /management/data-sources/{dsId}/sync-runs/{runId}/logs
```

It expects the response `{ logs: string[] }` and renders them in a sheet panel.

However, the backend has **no such endpoint**. The Management presentation layer
only exposes:

- `GET /knowledge-graphs/{kg_id}/data-sources`
- `POST /knowledge-graphs/{kg_id}/data-sources`
- `POST /data-sources/{ds_id}/sync`
- `GET /data-sources/{ds_id}/sync-runs`

There is no logs route. Additionally, the `DataSourceSyncRun` domain entity has no
`logs` field, and there is no database column or table for sync run log lines.

The UI's `fetchRunLogs` call always fails with a 404/500 error, and the "View Logs"
sheet shows the error state instead of actual log output.

## Changes Required

This task adds **minimal viable log storage** to the Management bounded context:
log lines as a list of strings appended to the sync run record. Ingestion and
Extraction contexts will populate these logs as they are implemented (those are
blocked on the AIHCM-174 spike); for now the endpoint returns an empty list for
any run, which is correct and allows the UI to render "No log entries for this run."

### 1. Domain Layer — `src/api/management/domain/entities/data_source_sync_run.py`

Add a `logs` field to `DataSourceSyncRun`:

```python
@dataclass
class DataSourceSyncRun:
    id: str
    data_source_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error: str | None
    created_at: datetime
    logs: list[str] = field(default_factory=list)  # NEW
```

### 2. Infrastructure — DB model and migration

Update the SQLAlchemy model for `DataSourceSyncRun` to add a `logs` column
(PostgreSQL `ARRAY(TEXT)`, nullable=False, server_default=`'{}'`):

- `src/api/management/infrastructure/models/data_source_sync_run.py`:
  Add `logs: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)`
- Generate a new Alembic migration to add the `logs` column.

Update the repository `DataSourceSyncRunRepository.find_by_data_source()` and
`DataSourceSyncRunRepository.find_by_id()` to populate the `logs` field from
the DB column when constructing domain objects.

### 3. Presentation — New models and route

**`src/api/management/presentation/data_sources/models.py`**

Add a new response model:

```python
class SyncRunLogsResponse(BaseModel):
    """Response model for sync run log lines."""
    logs: list[str] = Field(default_factory=list, description="Log lines for this sync run")
```

**`src/api/management/presentation/data_sources/routes.py`**

Add a new route:

```python
@router.get(
    "/data-sources/{ds_id}/sync-runs/{run_id}/logs",
    status_code=status.HTTP_200_OK,
)
async def get_sync_run_logs(
    ds_id: str,
    run_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    sync_run_repo: Annotated[IDataSourceSyncRunRepository, Depends(get_sync_run_repository)],
) -> SyncRunLogsResponse:
    """Get log lines for a specific sync run.

    The current user must have VIEW permission on the data source.
    Returns an empty list if no logs have been captured yet.
    """
```

The route must:
1. Verify the user has VIEW permission on the data source (via `service.get`).
2. Verify the sync run belongs to the data source.
3. Return `SyncRunLogsResponse(logs=run.logs)`.
4. Return 404 if the data source or sync run is not found.

### 4. Port — repository interface update

Update `IDataSourceSyncRunRepository` in
`src/api/management/ports/repositories.py` to add `find_by_id`:

```python
async def find_by_id(self, run_id: str) -> DataSourceSyncRun | None: ...
```

(Used by the logs route to fetch a single run and verify it belongs to the DS.)

### 5. Backend tests — `src/api/tests/`

Write integration tests (or unit tests with fakes) that cover:

1. **GET logs for own sync run returns 200 with empty list** when no logs captured.
2. **GET logs returns 404 when sync run not found**.
3. **GET logs returns 403 when user lacks VIEW permission on the data source**.
4. **GET logs returns 200 with log lines** when `DataSourceSyncRun.logs` is populated.

## TDD Cycle

1. Write backend tests first (they will fail — no route exists).
2. Add domain `logs` field and update infrastructure.
3. Add the route and models.
4. Run `make test-integration` — all new tests must pass before committing.
5. Confirm `cd src/dev-ui && pnpm test` still passes (UI tests already mock the API).
