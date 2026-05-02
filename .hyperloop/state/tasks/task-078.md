---
id: task-078
title: "Management API — add GET /management/data-sources flat list with latest_sync_run"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(management): add GET /management/data-sources flat list endpoint with latest_sync_run"
pr_description: |
  ## What & Why

  The sidebar layout in `src/dev-ui/app/layouts/default.vue` shows a count badge on
  the "Data Sources" nav item indicating how many data sources currently have an active
  sync in progress. This satisfies the spec's Navigation Structure requirement:

  > **Data** — Knowledge Graphs, **Data Sources (with sync status)**

  The badge implementation calls:

  ```typescript
  const result = await apiFetch<{ data_sources: Array<{ latest_sync_run?: { status: string } }> }>(
    '/management/data-sources'
  )
  ```

  However, `GET /management/data-sources` **does not exist** in the Management API.
  The only data-sources list endpoint is `GET /management/knowledge-graphs/{kg_id}/data-sources`
  (scoped to a single KG). The sidebar silently catches the 404 and shows no badge
  (`activeSyncCount` stays 0), so the "(with sync status)" clause is never satisfied.

  This PR adds the missing flat list endpoint scoped to the authenticated user's tenant,
  with an embedded `latest_sync_run` object so the badge works with a single API call.

  ## Spec Requirements Satisfied

  **Requirement: Navigation Structure — Scenario: Primary navigation** from
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > GIVEN an authenticated user
  > THEN the sidebar presents navigation grouped as:
  >   - **Data** — Knowledge Graphs, **Data Sources (with sync status)**

  The "(with sync status)" clause requires the sidebar nav item to reflect live sync
  state. Without a working backend endpoint, the badge always shows 0 and the clause fails.

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**:

  > THEN the corresponding backend API call succeeds (2xx response)

  The sidebar currently calls a non-existent endpoint (returns 404). Making it return
  2xx satisfies this scenario for the sidebar's implicit read operation.

  ## Key Design Decisions

  - **New route `GET /management/data-sources`**: Returns all data sources accessible
    to the current user in their tenant, across all knowledge graphs. Access is inferred
    from SpiceDB VIEW permission on the parent knowledge graph (same pattern as the
    existing KG-scoped list route).

  - **Embedded `latest_sync_run`**: A new `DataSourceWithSyncResponse` model wraps
    `DataSourceResponse` and adds an optional `latest_sync_run: SyncRunResponse | None`
    field. This avoids N+1 API calls from the sidebar and is the shape the frontend
    already expects.

  - **No pagination (V1)**: The sidebar only needs the status of active syncs, not
    full pagination. Returns all data sources in the tenant. If tenant scale becomes
    an issue, pagination can be added in a follow-up.

  - **Authorization**: Only data sources belonging to knowledge graphs the user has
    VIEW permission on are returned — consistent with existing KG authorization patterns.

  - **TDD first**: Unit tests for the service method, integration tests for the route,
    before any implementation.

  ## Files Affected

  - `src/api/management/application/services/data_source_service.py` — add
    `list_all_for_user(user_id)` method that fetches all KGs the user can see, then
    all data sources for each, plus the latest sync run per data source.
  - `src/api/management/presentation/data_sources/models.py` — add
    `DataSourceWithSyncResponse` model with embedded `latest_sync_run`.
  - `src/api/management/presentation/data_sources/routes.py` — add
    `GET /data-sources` route (no KG prefix) returning
    `{ data_sources: list[DataSourceWithSyncResponse], count: int }`.
  - `src/api/tests/unit/management/test_data_source_service.py` — add unit tests
    for `list_all_for_user`.
  - `src/api/tests/integration/management/test_data_sources_routes.py` — add
    integration test for the new route.
  - `src/dev-ui/app/layouts/default.vue` — update `fetchActiveSyncCount` to handle
    the response type correctly (response is `{ data_sources: [...] }`, not an array).
    Also align the active status set: use `'ai_extracting'` not `'extracting'` (task-042
    fixes the status labels; this endpoint should emit the canonical backend values).

  ## How to Verify

  1. `make test-unit` — new unit tests for `list_all_for_user` pass green.
  2. `make instance-up && make test-integration` — new route integration tests pass.
  3. Call `GET /management/data-sources` with a valid API key while a sync is in progress
     — verify the response includes `latest_sync_run` with an active status.
  4. Open the dev UI with an active sync in progress — verify the Data Sources nav item
     shows a numbered badge (e.g., "1").
  5. When all syncs are completed or failed, verify the badge disappears.

  ## TDD Cycle

  1. Write unit tests for `list_all_for_user` (RED).
  2. Implement `list_all_for_user` in the data source service (GREEN).
  3. Write integration test for `GET /management/data-sources` (RED).
  4. Add the route and `DataSourceWithSyncResponse` model (GREEN).
  5. Update the default layout to remove the silent failure (GREEN for sidebar test).
  6. `make test-unit && make test-integration` exits 0.

  ## Caveats

  - This endpoint is additive; no existing routes are changed.
  - `latest_sync_run` is the most recent run ordered by `created_at DESC`. If a data
    source has never synced, `latest_sync_run` is `null`.
  - The sidebar's active status set must use `'ai_extracting'` not `'extracting'`
    (the backend canonical value). The status set in `default.vue` already uses
    `'ai_extracting'` (`ACTIVE_SYNC_STATUSES` constant), so no frontend change is needed
    beyond typing alignment.
---

## Spec Coverage

**Requirement: Navigation Structure — Scenario: Primary navigation** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> GIVEN an authenticated user
> THEN the sidebar presents navigation grouped as:
>   - **Data** — Knowledge Graphs, **Data Sources (with sync status)**

## Gap

### `GET /management/data-sources` does not exist

**File:** `src/dev-ui/app/layouts/default.vue`

The sidebar calls this endpoint to populate the active sync badge:

```typescript
const result = await apiFetch<{ data_sources: Array<{ latest_sync_run?: { status: string } }> }>(
  '/management/data-sources',
)
activeSyncCount.value = (result.data_sources ?? []).filter(
  (ds) => ds.latest_sync_run && ACTIVE_SYNC_STATUSES.has(ds.latest_sync_run.status),
).length
```

The endpoint is not registered in the Management API. The only existing data-source
list endpoint is `GET /management/knowledge-graphs/{kg_id}/data-sources` which requires
a specific KG ID and is not suitable for the sidebar's tenant-wide active sync count.

**Consequence:** The `apiFetch` call throws (404 → network error), the `catch` block
sets `activeSyncCount.value = 0`, and the badge is never shown. The "(with sync status)"
clause of the Navigation Structure spec is never satisfied.

### `DataSourceResponse` does not include `latest_sync_run`

**File:** `src/api/management/presentation/data_sources/models.py`

```python
class DataSourceResponse(BaseModel):
    id: str
    knowledge_graph_id: str
    tenant_id: str
    name: str
    adapter_type: str
    schedule_type: str
    last_sync_at: datetime | None   # ← only a timestamp, not the full run object
    created_at: datetime
    updated_at: datetime
```

The sidebar expects `latest_sync_run: { status: string }` — an embedded sync run
object. The current `DataSourceResponse` only has `last_sync_at` (a timestamp with no
status). Even if the flat list endpoint existed, the response shape would be wrong.

## Scope

### TDD — write tests first

**Unit test (add to data source service test file):**

```python
class TestListAllForUser:
    """Unit tests for DataSourceService.list_all_for_user."""

    async def test_returns_all_data_sources_across_kgs(
        self, service, mock_kg_service, mock_ds_repo, mock_sync_run_repo
    ):
        # Arrange: user has 2 KGs each with 1 data source
        kg1, kg2 = make_kg("kg-1"), make_kg("kg-2")
        ds1 = make_ds("ds-1", kg_id="kg-1")
        ds2 = make_ds("ds-2", kg_id="kg-2")
        run1 = make_run("run-1", ds_id="ds-1", status="completed")
        mock_kg_service.list_all.return_value = [kg1, kg2]
        mock_ds_repo.list_for_kg.side_effect = lambda kg_id: (
            [ds1] if kg_id == "kg-1" else [ds2]
        )
        mock_sync_run_repo.get_latest_for_data_source.side_effect = lambda ds_id: (
            run1 if ds_id == "ds-1" else None
        )

        result = await service.list_all_for_user(user_id="user-1")

        assert len(result) == 2
        # ds1 has a latest_sync_run
        ds1_result = next(r for r in result if r.data_source.id.value == "ds-1")
        assert ds1_result.latest_sync_run is not None
        assert ds1_result.latest_sync_run.status == "completed"
        # ds2 has no latest sync run
        ds2_result = next(r for r in result if r.data_source.id.value == "ds-2")
        assert ds2_result.latest_sync_run is None
```

**Integration test (add to data sources route test file):**

```python
async def test_list_all_data_sources_returns_flat_list(
    authenticated_client, created_data_source, created_sync_run
):
    """GET /management/data-sources returns all data sources with latest_sync_run."""
    resp = await authenticated_client.get("/management/data-sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "data_sources" in data
    assert "count" in data
    assert data["count"] == 1
    ds = data["data_sources"][0]
    assert ds["id"] == created_data_source.id
    assert ds["latest_sync_run"] is not None
    assert ds["latest_sync_run"]["status"] == created_sync_run.status
```

### Implementation

#### 1. New service method `list_all_for_user`

Add to `src/api/management/application/services/data_source_service.py`:

```python
async def list_all_for_user(
    self, user_id: str
) -> list[DataSourceWithLatestRun]:
    """Return all data sources accessible to the user across the tenant.

    Discovers accessible knowledge graphs (VIEW permission) then
    aggregates their data sources, fetching the latest sync run per source.

    Args:
        user_id: Authenticated user requesting the list.

    Returns:
        List of (DataSource, optional latest SyncRun) pairs.
    """
    kgs = await self._kg_service.list_all(
        user_id=user_id, permission=Permission.VIEW
    )
    result: list[DataSourceWithLatestRun] = []
    for kg in kgs:
        data_sources = await self._ds_repo.list_for_knowledge_graph(
            knowledge_graph_id=kg.id.value
        )
        for ds in data_sources:
            latest_run = await self._sync_run_repo.get_latest_for_data_source(
                data_source_id=ds.id.value
            )
            result.append(DataSourceWithLatestRun(
                data_source=ds, latest_sync_run=latest_run
            ))
    return result
```

#### 2. New response model `DataSourceWithSyncResponse`

Add to `src/api/management/presentation/data_sources/models.py`:

```python
class DataSourceWithSyncResponse(BaseModel):
    """Data source response with embedded latest sync run."""

    id: str
    knowledge_graph_id: str
    tenant_id: str
    name: str
    adapter_type: str
    schedule_type: str
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime
    latest_sync_run: SyncRunResponse | None = None

    @classmethod
    def from_domain(
        cls,
        ds: DataSource,
        latest_run: DataSourceSyncRun | None = None,
    ) -> DataSourceWithSyncResponse:
        return cls(
            id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
            name=ds.name,
            adapter_type=ds.adapter_type.value,
            schedule_type=ds.schedule.schedule_type.value,
            last_sync_at=ds.last_sync_at,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
            latest_sync_run=SyncRunResponse.from_domain(latest_run) if latest_run else None,
        )


class DataSourceListResponse(BaseModel):
    """Response for flat data source list."""
    data_sources: list[DataSourceWithSyncResponse]
    count: int
```

#### 3. New route `GET /management/data-sources`

Add to `src/api/management/presentation/data_sources/routes.py`:

```python
@router.get(
    "/data-sources",
    status_code=status.HTTP_200_OK,
    summary="List all data sources across the tenant",
    description="""
List all data sources accessible to the current user across all their knowledge graphs.

Includes the latest sync run per data source embedded in the response, enabling
the sidebar navigation to show a live count of active syncs without additional
API calls.
""",
)
async def list_all_data_sources(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
) -> DataSourceListResponse:
    """List all data sources in the tenant with latest sync run status."""
    try:
        pairs = await service.list_all_for_user(user_id=current_user.user_id.value)
        responses = [
            DataSourceWithSyncResponse.from_domain(pair.data_source, pair.latest_sync_run)
            for pair in pairs
        ]
        return DataSourceListResponse(data_sources=responses, count=len(responses))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list data sources",
        )
```

## Acceptance Criteria

- `GET /management/data-sources` returns HTTP 200 with `{ data_sources: [...], count: N }`.
- Each item in `data_sources` includes `latest_sync_run: { id, status, started_at, ... } | null`.
- Only data sources belonging to KGs the user has VIEW permission on are returned.
- The sidebar badge correctly shows the count of active syncs when any data source has
  status in `{pending, ingesting, ai_extracting, applying}`.
- When no syncs are active, `activeSyncCount` is 0 and no badge is rendered.
- New unit tests and integration tests pass (`make test-unit && make test-integration`).
- No regressions on existing data source routes.

## TDD Cycle

1. Write unit tests for `list_all_for_user` (RED).
2. Implement `list_all_for_user` and `DataSourceWithLatestRun` dataclass (GREEN).
3. Write integration test for `GET /management/data-sources` (RED).
4. Add `DataSourceWithSyncResponse`, `DataSourceListResponse`, and the route (GREEN).
5. Run `make test-unit && make test-integration` — all pass.
6. Manually verify sidebar badge in dev UI with an active sync.
