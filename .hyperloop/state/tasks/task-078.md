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
pr_title: "feat(management): add GET /management/data-sources with latest_sync_run for nav badge"
pr_description: |
  ## What & Why

  The Kartograph sidebar nav item for **Data Sources** is specified to show a live sync-status
  badge — the primary navigation scenario in the UI spec reads:

  > **Data** — Knowledge Graphs, Data Sources (with sync status)

  The UI layout (`src/dev-ui/app/layouts/default.vue`) already implements the badge by
  calling:

  ```typescript
  const result = await apiFetch<{
    data_sources: Array<{ latest_sync_run?: { status: string } }>
  }>('/management/data-sources')
  activeSyncCount.value = result.data_sources.filter(
    ds => ds.latest_sync_run && ACTIVE_SYNC_STATUSES.has(ds.latest_sync_run.status)
  ).length
  ```

  This call currently returns a **404** because no `GET /management/data-sources`
  endpoint exists. The layout's `catch` block degrades gracefully (badge stays at 0),
  so the UI does not crash — but the spec-required "sync status" on the nav item is
  never visible.

  This PR adds the missing backend route and the service method it needs.

  ## Spec Requirements Satisfied

  **Requirement: Navigation Structure — Scenario: Primary navigation** from
  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > THEN the sidebar presents navigation grouped as:
  > - **Data** — Knowledge Graphs, Data Sources (with sync status)

  The "(with sync status)" qualifier requires the backend to supply a tenant-wide
  data-sources list with embedded `latest_sync_run` status so the badge can reflect
  active syncs without mounting the full data-sources page.

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**

  > THEN the corresponding backend API call succeeds (2xx response)
  > AND the UI reflects the updated state without requiring a manual refresh

  The current `GET /management/data-sources` call never returns 2xx, so the badge
  never reflects real sync state.

  ## Key Design Decisions

  - **New route is additive**: no existing routes are changed.
  - **Service method `list_all_visible(user_id)`**: iterates over all knowledge graphs
    the user can VIEW, then collects data sources per KG. This reuses the existing
    `list_for_knowledge_graph` service method, keeping domain logic in one place. An
    N+1 is acceptable here because this is a lightweight badge-fetch called on tenant
    load — not a high-frequency or paginated endpoint.
  - **`latest_sync_run` embed**: the `DataSourceResponse` is extended with an optional
    `latest_sync_run` field that returns the most recent sync run's status, `started_at`,
    and `completed_at`. The sync-run repository's `find_by_data_source` is already
    efficient (returns ordered by `created_at DESC`); only the first result is needed.
  - **Response envelope**: `{ data_sources: [...], count: N }` to match the layout's
    TypeScript type and to be consistent with other list responses (e.g.,
    `KnowledgeGraphListResponse`).
  - **Authorization**: the user must have VIEW permission on each KG to see its data
    sources (same check already done in `list_for_knowledge_graph`). No new permission
    types are introduced.

  ## Files Affected

  - `src/api/management/application/services/data_source_service.py` — add
    `list_all_visible(user_id)` method that aggregates data sources across all accessible KGs.
  - `src/api/management/presentation/data_sources/models.py` — extend
    `DataSourceResponse` with an optional `latest_sync_run: SyncRunSummary | None` field;
    add `SyncRunSummary` dataclass.
  - `src/api/management/presentation/data_sources/routes.py` — add new route
    `GET /data-sources` returning `DataSourceListResponse`.
  - `src/api/tests/unit/management/services/test_data_source_service.py` — new tests
    for `list_all_visible`.
  - `src/api/tests/unit/management/presentation/test_data_sources_routes.py` — new
    tests for `GET /management/data-sources`.

  ## How to Verify

  1. Run `make test-unit` — new tests pass green.
  2. Start dev instance (`make dev` or `make instance-up`) and run `make test-integration`.
  3. Call `GET /management/data-sources` (authenticated) — verify the response is
     `{ data_sources: [...], count: N }` with `latest_sync_run` embedded.
  4. Trigger a sync (`POST /management/data-sources/{id}/sync`), then re-call the flat
     list — verify `latest_sync_run.status` reflects the new run's status.
  5. Open the dev UI — verify the Data Sources sidebar nav item shows a numeric badge
     when a sync is running.

  ## TDD Cycle

  1. Write unit tests for `list_all_visible` (RED).
  2. Implement `list_all_visible` in the service (GREEN).
  3. Write unit/integration tests for the new route (RED).
  4. Add the route and response model changes (GREEN).
  5. Run `make test-unit && make test-integration`.
  6. Commit atomically.

  ## Caveats

  - `latest_sync_run` is the single most-recent run by `created_at DESC`. If a data
    source has never been synced, `latest_sync_run` is `null`.
  - This endpoint is intentionally simple (no pagination, no filters). The full
    per-data-source detail (including full sync history) remains on the KG-scoped
    routes.
  - Once this PR lands, remove the graceful-degradation comment from the layout
    (`// Best-effort — badge is an optional indicator, not critical UI`) and update
    the corresponding test in `default.layout.test.ts` to assert the badge IS shown
    rather than just not crashing on 404.
---

## Spec Coverage

**Requirement: Navigation Structure — Scenario: Primary navigation** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> THEN the sidebar presents navigation grouped as:
> - **Data** — Knowledge Graphs, Data Sources **(with sync status)**

## Gap

### Missing route: `GET /management/data-sources`

The layout (`src/dev-ui/app/layouts/default.vue`) calls this endpoint to power the
sync-status badge on the Data Sources sidebar nav item:

```typescript
const result = await apiFetch<{
  data_sources: Array<{ latest_sync_run?: { status: string } }>
}>('/management/data-sources')
```

The current backend (`src/api/management/presentation/data_sources/routes.py`) only
defines these routes:

| Method | Path |
|--------|------|
| GET    | `/knowledge-graphs/{kg_id}/data-sources` |
| POST   | `/knowledge-graphs/{kg_id}/data-sources` |
| POST   | `/data-sources/{ds_id}/sync` |
| GET    | `/data-sources/{ds_id}/sync-runs` |
| GET    | `/data-sources/{ds_id}/sync-runs/{run_id}/logs` |

`GET /data-sources` (flat, tenant-wide) **does not exist**. FastAPI returns a 404
for every call from the layout. The `catch` block in `fetchActiveSyncCount` absorbs
the error and sets `activeSyncCount` to 0, so the badge is permanently invisible even
when data sources are actively syncing.

### The UI badge is fully implemented — only the backend endpoint is missing

`src/dev-ui/app/layouts/default.vue` (lines ~219–237):
```typescript
const ACTIVE_SYNC_STATUSES = new Set(['pending', 'ingesting', 'ai_extracting', 'applying'])
const activeSyncCount = ref(0)

async function fetchActiveSyncCount() {
  if (!hasTenant.value) return
  try {
    const result = await apiFetch<{ data_sources: Array<{ latest_sync_run?: { status: string } }> }>(
      '/management/data-sources',
    )
    activeSyncCount.value = (result.data_sources ?? []).filter(
      (ds) => ds.latest_sync_run && ACTIVE_SYNC_STATUSES.has(ds.latest_sync_run.status),
    ).length
  } catch {
    activeSyncCount.value = 0
  }
}
```

The badge logic, nav item wiring, and test coverage in
`src/dev-ui/app/tests/default.layout.test.ts` are complete. The backend is the
only missing piece.

## Scope

### TDD — write tests first

**Unit tests** (add to `src/api/tests/unit/management/services/test_data_source_service.py`):

```python
class TestListAllVisible:
    """Tests for DataSourceService.list_all_visible."""

    async def test_returns_data_sources_across_all_accessible_kgs(
        self, service, mock_authz, mock_kg_repo, mock_ds_repo
    ):
        # Arrange: two accessible KGs, one DS each
        kg1_id, kg2_id = "kg-1", "kg-2"
        mock_authz.check_permission.return_value = True  # user can VIEW both KGs
        mock_kg_repo.list_all.return_value = [KG(id=kg1_id), KG(id=kg2_id)]
        mock_ds_repo.find_by_knowledge_graph.side_effect = lambda kg_id: (
            [DS(id="ds-1", kg_id=kg_id)] if kg_id == kg1_id else [DS(id="ds-2", kg_id=kg_id)]
        )

        result = await service.list_all_visible(user_id="user-1")

        assert len(result) == 2
        assert {ds.id for ds in result} == {"ds-1", "ds-2"}

    async def test_excludes_data_sources_from_inaccessible_kgs(
        self, service, mock_authz, mock_kg_repo, mock_ds_repo
    ):
        mock_authz.check_permission.return_value = False  # user cannot VIEW any KG
        mock_kg_repo.list_all.return_value = [KG(id="kg-private")]

        result = await service.list_all_visible(user_id="user-1")
        assert result == []

    async def test_returns_empty_when_no_kgs_exist(
        self, service, mock_authz, mock_kg_repo
    ):
        mock_kg_repo.list_all.return_value = []
        result = await service.list_all_visible(user_id="user-1")
        assert result == []
```

**Route unit tests** (add to `src/api/tests/unit/management/presentation/test_data_sources_routes.py`):

```python
class TestListAllDataSources:
    """Tests for GET /management/data-sources."""

    def test_returns_200_with_data_source_list_envelope(
        self, test_client, mock_service, sample_data_source
    ):
        mock_service.list_all_visible.return_value = [sample_data_source]
        response = test_client.get("/management/data-sources")

        assert response.status_code == 200
        data = response.json()
        assert "data_sources" in data
        assert "count" in data
        assert data["count"] == 1

    def test_includes_latest_sync_run_when_present(
        self, test_client, mock_service, mock_sync_run_repo,
        sample_data_source, sample_sync_run
    ):
        mock_service.list_all_visible.return_value = [sample_data_source]
        mock_sync_run_repo.find_by_data_source.return_value = [sample_sync_run]
        response = test_client.get("/management/data-sources")

        assert response.status_code == 200
        ds = response.json()["data_sources"][0]
        assert ds["latest_sync_run"] is not None
        assert ds["latest_sync_run"]["status"] == sample_sync_run.status.value

    def test_latest_sync_run_is_null_when_no_runs(
        self, test_client, mock_service, mock_sync_run_repo, sample_data_source
    ):
        mock_service.list_all_visible.return_value = [sample_data_source]
        mock_sync_run_repo.find_by_data_source.return_value = []
        response = test_client.get("/management/data-sources")

        assert response.status_code == 200
        ds = response.json()["data_sources"][0]
        assert ds["latest_sync_run"] is None

    def test_returns_403_when_not_authenticated(self, unauthenticated_client):
        response = unauthenticated_client.get("/management/data-sources")
        assert response.status_code in (401, 403)
```

### Implementation

#### 1. Extend `DataSourceResponse` model

In `src/api/management/presentation/data_sources/models.py`, add:

```python
class SyncRunSummary(BaseModel):
    """Lightweight sync run summary for embedding in data source responses."""
    id: str
    status: str
    started_at: str
    completed_at: str | None = None

class DataSourceResponse(BaseModel):
    # ... existing fields ...
    latest_sync_run: SyncRunSummary | None = None

    @classmethod
    def from_domain(cls, ds: DataSource) -> "DataSourceResponse":
        # ... unchanged base fields ...
        # latest_sync_run is populated by the route handler, not the domain object

class DataSourceListResponse(BaseModel):
    """Envelope for the flat data-sources list."""
    data_sources: list[DataSourceResponse]
    count: int
```

#### 2. New service method `list_all_visible`

In `src/api/management/application/services/data_source_service.py`:

```python
async def list_all_visible(self, user_id: str) -> list[DataSource]:
    """List all data sources visible to the user across all accessible KGs.

    Iterates over all knowledge graphs in the tenant. For each KG where the
    user has VIEW permission, collects the data sources. Used by the nav-badge
    endpoint which needs a tenant-wide flat list.

    Args:
        user_id: The user requesting the list

    Returns:
        All data sources in the tenant that the user can see, in KG order.
    """
    all_kgs = await self._kg_repo.list_all()
    result: list[DataSource] = []
    for kg in all_kgs:
        has_view = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg.id.value,
            permission=Permission.VIEW,
        )
        if has_view:
            sources = await self._ds_repo.find_by_knowledge_graph(kg.id.value)
            result.extend(sources)
    self._probe.data_sources_listed(count=len(result))
    return result
```

#### 3. New route `GET /data-sources`

In `src/api/management/presentation/data_sources/routes.py`:

```python
@router.get(
    "/data-sources",
    status_code=status.HTTP_200_OK,
)
async def list_all_data_sources(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_data_source_service)],
    sync_run_repo: Annotated[IDataSourceSyncRunRepository, Depends(get_sync_run_repository)],
) -> DataSourceListResponse:
    """List all data sources visible to the current user across all knowledge graphs.

    Used by the UI navigation badge to show the number of active syncs.
    Each data source includes its most recent sync run (latest_sync_run) so
    the client can determine sync status without additional requests.

    Returns:
        DataSourceListResponse with embedded latest_sync_run per data source.
    """
    try:
        data_sources = await service.list_all_visible(
            user_id=current_user.user_id.value,
        )

        ds_responses: list[DataSourceResponse] = []
        for ds in data_sources:
            runs = await sync_run_repo.find_by_data_source(ds.id.value)
            latest = runs[0] if runs else None
            response = DataSourceResponse.from_domain(ds)
            if latest is not None:
                response.latest_sync_run = SyncRunSummary(
                    id=latest.id,
                    status=latest.status.value,
                    started_at=latest.started_at.isoformat(),
                    completed_at=latest.completed_at.isoformat() if latest.completed_at else None,
                )
            ds_responses.append(response)

        return DataSourceListResponse(
            data_sources=ds_responses,
            count=len(ds_responses),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list data sources",
        )
```

## Acceptance Criteria

- `GET /management/data-sources` (authenticated) returns HTTP 200 with:
  - `{ data_sources: [...], count: N }` envelope
  - Each entry includes `latest_sync_run: { id, status, started_at, completed_at }` or `null`
  - `latest_sync_run.status` is one of: `pending | ingesting | ai_extracting | applying | completed | failed`
- Unauthenticated requests return 401 or 403.
- The Data Sources sidebar nav item in the UI shows a numeric badge when
  `latest_sync_run.status ∈ { pending, ingesting, ai_extracting, applying }`.
- Badge updates when the user switches tenants.
- Existing routes are unaffected (no regression).
- All new tests pass before committing (`make test-unit`).

## TDD Cycle

1. Write unit tests for `list_all_visible` service method (RED).
2. Implement `list_all_visible` (GREEN).
3. Write route unit tests for `GET /management/data-sources` (RED).
4. Add `DataSourceListResponse`, `SyncRunSummary`, and the route (GREEN).
5. Run `make test-unit`.
6. Commit atomically.
