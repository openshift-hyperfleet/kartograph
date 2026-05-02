---
id: task-077
title: Management API — add workspace_id filter to GET /management/knowledge-graphs
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(management): add optional workspace_id filter to knowledge-graphs list endpoint"
pr_description: |
  ## What & Why

  The Mutations Console UI (task-074) must satisfy this spec clause:

  > AND the selector lists all knowledge graphs the user has `edit` permission on
  > **within the current workspace**

  The UI already calls:

  ```
  GET /management/knowledge-graphs?workspace_id={id}&permission=edit
  ```

  (`src/dev-ui/app/pages/graph/mutations.vue`, line ~149, includes a `TODO` comment
  acknowledging this backend dependency.)

  However, the `GET /management/knowledge-graphs` route currently only accepts
  `?permission=view|edit`. The `workspace_id` query parameter is silently ignored by
  FastAPI (not a declared parameter), so the endpoint returns **all editable KGs in the
  tenant** regardless of the workspace filter. The spec clause — "within the current
  workspace" — is therefore not satisfied end-to-end.

  This PR adds optional `workspace_id` query parameter support to
  `GET /management/knowledge-graphs`. When provided, the response is filtered to
  knowledge graphs belonging to that workspace that the user also has the requested
  permission on.

  ## Spec Requirements Satisfied

  **Requirement: Mutations Console — Scenario: Knowledge graph selection**
  from `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  > AND the selector lists all knowledge graphs the user has `edit` permission on
  > within the current workspace

  The "within the current workspace" clause requires the backend to support
  workspace-scoped + permission-filtered KG listing simultaneously.

  **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**

  The UI passes `workspace_id` to this endpoint. Without backend support, the
  "corresponding backend API call succeeds" clause fails to return the correct
  workspace-scoped results even when the HTTP status is 200.

  ## Key Design Decisions

  - **New service method `list_for_workspace_with_permission`**: Rather than modifying
    the existing `list_for_workspace` (which is called from the workspace-scoped route
    and has different semantics — it checks workspace VIEW permission first, then returns
    all KGs in the workspace), a new method combines workspace membership discovery with
    per-KG permission filtering. This preserves the SRP of each existing method.

  - **Route change is additive (no breaking change)**: The `workspace_id` parameter is
    optional (`Optional[str] = None`). When absent, existing behaviour is unchanged
    (`list_all` is called). When present, the new `list_for_workspace_with_permission`
    method is called.

  - **Workspace membership check**: The new method reuses the same SpiceDB
    `read_relationships` pattern from `list_for_workspace` to discover KG IDs linked to
    the workspace, then applies per-KG permission filtering (same loop as `list_all`).
    No new SpiceDB calls are added beyond what already exists.

  - **Authorization model**: The caller does NOT need VIEW permission on the workspace
    (unlike `list_for_workspace`). SpiceDB per-KG permission checks are sufficient
    — a user with `edit` on a KG in workspace W can see that KG in the mutations
    console KG selector regardless of their workspace-level role.

  - **Probe instrumentation**: The existing `knowledge_graphs_listed` probe is called
    with `workspace_id` so DOO tracing captures the workspace scope.

  ## Files Affected

  - `src/api/management/application/services/knowledge_graph_service.py` — add
    `list_for_workspace_with_permission(user_id, workspace_id, permission)` method.
  - `src/api/management/presentation/knowledge_graphs/routes.py` — add
    `workspace_id: Optional[str] = None` query parameter to
    `list_knowledge_graphs`; route to new service method when workspace_id is provided.
  - `src/api/tests/unit/management/test_knowledge_graph_service.py` (or equivalent
    unit test file) — new tests for `list_for_workspace_with_permission`.
  - `src/api/tests/integration/management/test_knowledge_graphs_routes.py` (or
    equivalent integration test file) — new integration tests for the `?workspace_id=`
    filter on the list endpoint.

  ## How to Verify

  1. Run `make test-unit` — new unit tests for `list_for_workspace_with_permission`
     pass green.
  2. Start the dev instance (`make dev` or `make instance-up`) and run
     `make test-integration` — new route tests pass.
  3. Call `GET /management/knowledge-graphs?workspace_id=<a_real_ws_id>&permission=edit`
     — verify only KGs in that workspace with edit permission are returned.
  4. Call `GET /management/knowledge-graphs?permission=edit` (no workspace_id) — verify
     all tenant-wide editable KGs are returned (unchanged behaviour).
  5. Navigate to the Mutations Console in the dev UI, select a workspace — verify the
     KG dropdown is populated only with KGs from that workspace.
  6. Remove the `TODO` comment from `mutations.vue` line ~147.

  ## TDD Cycle

  1. Write unit tests for `list_for_workspace_with_permission` (RED).
  2. Implement `list_for_workspace_with_permission` in the service (GREEN).
  3. Write integration test for the route with `?workspace_id=` (RED).
  4. Update the route to accept `workspace_id` and call the new service method (GREEN).
  5. Run full test suite: `make test-unit && make test-integration`.
  6. Commit atomically.

  ## Caveats

  - If the `workspace_id` provided does not exist or the user has no KGs with the
    requested permission in that workspace, return an empty list (not 403 or 404).
    This matches the filtering semantics of `list_all`: missing or inaccessible items
    are silently excluded, not rejected.
  - The existing `GET /management/workspaces/{workspace_id}/knowledge-graphs` route
    is unchanged. It continues to check VIEW permission on the workspace and return
    all visible KGs — suitable for the Workspace Management page. This PR targets
    the tenant-level listing route only.
  - This task unblocks task-074 (Mutations Console workspace-scoped KG selector).
    task-074's TODO comment in `mutations.vue` can be removed once this PR lands.
---

## Spec Coverage

**Requirement: Mutations Console — Scenario: Knowledge graph selection** from
`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

> AND the selector lists all knowledge graphs the user has `edit` permission on
> within the current workspace

## Gap

### `GET /management/knowledge-graphs` ignores `workspace_id` query parameter

**Route:** `src/api/management/presentation/knowledge_graphs/routes.py`

```python
@router.get("/knowledge-graphs", ...)
async def list_knowledge_graphs(
    current_user: ...,
    service: ...,
    permission: Literal["view", "edit"] = "view",   # ← only declared param
) -> KnowledgeGraphListResponse:
    perm = Permission.EDIT if permission == "edit" else Permission.VIEW
    kgs = await service.list_all(user_id=..., permission=perm)
    ...
```

The parameter `workspace_id` is **not declared**. FastAPI silently ignores it.

**UI call (already implemented in `mutations.vue`):**

```typescript
await apiFetch(
  '/management/knowledge-graphs',
  { query: { permission: 'edit', workspace_id: selectedWorkspaceId.value } },
  // TODO: backend must support ?workspace_id= filter on GET /management/knowledge-graphs
)
```

The `workspace_id` is passed but discarded by the backend. The response contains
ALL editable KGs in the tenant — not workspace-scoped. This directly violates
the "within the current workspace" clause of the Mutations Console KG selection scenario.

### `list_for_workspace` does not accept a `permission` parameter

`KnowledgeGraphService.list_for_workspace(user_id, workspace_id)` (line 204) returns
all KGs in the workspace visible to the user (VIEW permission on workspace). It does not
filter individual KGs by EDIT permission. Using it for the mutations console KG selector
would show KGs the user can only read, not mutate.

`KnowledgeGraphService.list_all(user_id, permission)` (line 271) filters by permission
across the entire tenant — no workspace scoping.

Neither existing method provides workspace-scoped + permission-filtered listing.

## Scope

### TDD — write tests first

**Unit tests** (add to the existing KG service test file):

```python
class TestListForWorkspaceWithPermission:
    """Tests for KnowledgeGraphService.list_for_workspace_with_permission."""

    async def test_returns_only_kgs_in_workspace_with_edit_permission(
        self, service, mock_authz, mock_kg_repo
    ):
        # Arrange: two KGs in workspace; user has EDIT on one, VIEW on the other
        ws_id = "ws-abc"
        kg1_id, kg2_id = "kg-1", "kg-2"
        # read_relationships returns both KGs as linked to the workspace
        mock_authz.read_relationships.return_value = [
            MockTuple(f"knowledge_graph:{kg1_id}"),
            MockTuple(f"knowledge_graph:{kg2_id}"),
        ]
        # Only kg1 has EDIT permission
        mock_authz.check_permission.side_effect = lambda **kw: (
            kw["resource_id"] == kg1_id and kw["permission"] == Permission.EDIT
        )
        mock_kg_repo.get_by_id.side_effect = lambda id_: (
            KG(id=id_) if id_.value in [kg1_id, kg2_id] else None
        )

        result = await service.list_for_workspace_with_permission(
            user_id="user-1",
            workspace_id=ws_id,
            permission=Permission.EDIT,
        )

        assert len(result) == 1
        assert result[0].id.value == kg1_id

    async def test_returns_empty_list_when_no_kgs_in_workspace(
        self, service, mock_authz, mock_kg_repo
    ):
        mock_authz.read_relationships.return_value = []
        result = await service.list_for_workspace_with_permission(
            user_id="user-1", workspace_id="ws-empty", permission=Permission.EDIT
        )
        assert result == []

    async def test_returns_empty_list_when_user_has_no_edit_permission_on_any_kg(
        self, service, mock_authz, mock_kg_repo
    ):
        mock_authz.read_relationships.return_value = [
            MockTuple("knowledge_graph:kg-readonly")
        ]
        mock_authz.check_permission.return_value = False  # no EDIT on any KG
        result = await service.list_for_workspace_with_permission(
            user_id="user-1", workspace_id="ws-1", permission=Permission.EDIT
        )
        assert result == []
```

**Integration tests** (add to the KG routes integration test file):

```python
async def test_list_knowledge_graphs_filters_by_workspace_id(
    authenticated_client, created_workspace, created_kg_in_workspace, other_kg
):
    """?workspace_id= returns only KGs in that workspace."""
    resp = await authenticated_client.get(
        "/management/knowledge-graphs",
        params={"workspace_id": created_workspace.id, "permission": "edit"},
    )
    assert resp.status_code == 200
    data = resp.json()
    kg_ids = [kg["id"] for kg in data["knowledge_graphs"]]
    assert created_kg_in_workspace.id in kg_ids
    assert other_kg.id not in kg_ids  # belongs to a different workspace

async def test_list_knowledge_graphs_without_workspace_id_returns_all(
    authenticated_client, created_kg_in_workspace, other_kg
):
    """Without workspace_id, the tenant-wide list is returned (unchanged behaviour)."""
    resp = await authenticated_client.get(
        "/management/knowledge-graphs",
        params={"permission": "edit"},
    )
    assert resp.status_code == 200
    data = resp.json()
    kg_ids = [kg["id"] for kg in data["knowledge_graphs"]]
    # Both KGs appear in the tenant-wide list
    assert created_kg_in_workspace.id in kg_ids
    assert other_kg.id in kg_ids
```

### Implementation

#### 1. New service method: `list_for_workspace_with_permission`

Add to `src/api/management/application/services/knowledge_graph_service.py`:

```python
async def list_for_workspace_with_permission(
    self,
    user_id: str,
    workspace_id: str,
    permission: Permission = Permission.VIEW,
) -> list[KnowledgeGraph]:
    """List knowledge graphs in a workspace filtered by permission.

    Discovers KGs linked to the workspace via SpiceDB relationships,
    then filters to those the user has the requested permission on.
    Unlike list_for_workspace, does NOT require workspace-level VIEW
    permission — per-KG permission checks are sufficient.

    Args:
        user_id: The user requesting the list
        workspace_id: The workspace to filter by
        permission: Minimum permission to check on each KG (VIEW or EDIT)

    Returns:
        KGs in the workspace that the user has the requested permission on.
    """
    # Discover KG IDs linked to the workspace (same as list_for_workspace)
    tuples = await self._authz.read_relationships(
        resource_type=ResourceType.KNOWLEDGE_GRAPH,
        relation=RelationType.WORKSPACE,
        subject_type=ResourceType.WORKSPACE,
        subject_id=workspace_id,
    )

    kg_ids: list[str] = []
    for rel_tuple in tuples:
        parts = rel_tuple.resource.split(":")
        if len(parts) == 2:
            kg_ids.append(parts[1])

    # Filter by permission (same loop as list_all)
    kgs: list[KnowledgeGraph] = []
    for kg_id in kg_ids:
        has_perm = await self._check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGE_GRAPH,
            resource_id=kg_id,
            permission=permission,
        )
        if has_perm:
            kg = await self._kg_repo.get_by_id(KnowledgeGraphId(value=kg_id))
            if kg is not None and kg.tenant_id == self._scope_to_tenant:
                kgs.append(kg)

    self._probe.knowledge_graphs_listed(
        workspace_id=workspace_id,
        count=len(kgs),
    )
    return kgs
```

#### 2. Update route: add `workspace_id` query parameter

In `src/api/management/presentation/knowledge_graphs/routes.py`:

```python
from typing import Annotated, Literal, Optional

@router.get("/knowledge-graphs", ...)
async def list_knowledge_graphs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
    permission: Annotated[
        Literal["view", "edit"],
        Query(description="Filter by minimum permission level (view or edit)."),
    ] = "view",
    workspace_id: Annotated[
        Optional[str],
        Query(
            description=(
                "Optional workspace ID. When provided, results are filtered to "
                "knowledge graphs in that workspace that the user has the requested "
                "permission on. Used by the Mutations Console KG selector."
            )
        ),
    ] = None,
) -> KnowledgeGraphListResponse:
    """List knowledge graphs accessible to the current user.

    When workspace_id is provided, returns only KGs in that workspace
    that the user has the requested permission on.

    When workspace_id is omitted, returns all accessible KGs in the tenant.
    """
    perm = Permission.EDIT if permission == "edit" else Permission.VIEW
    try:
        if workspace_id:
            kgs = await service.list_for_workspace_with_permission(
                user_id=current_user.user_id.value,
                workspace_id=workspace_id,
                permission=perm,
            )
        else:
            kgs = await service.list_all(
                user_id=current_user.user_id.value,
                permission=perm,
            )
        kg_responses = [KnowledgeGraphResponse.from_domain(kg) for kg in kgs]
        return KnowledgeGraphListResponse(
            knowledge_graphs=kg_responses,
            count=len(kg_responses),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list knowledge graphs",
        )
```

## Acceptance Criteria

- `GET /management/knowledge-graphs?workspace_id=<id>&permission=edit` returns only
  KGs in the specified workspace that the user has EDIT permission on.
- `GET /management/knowledge-graphs?permission=edit` (no workspace_id) returns the
  same results as before (tenant-wide editable KGs). No regression.
- `GET /management/knowledge-graphs?workspace_id=<id>&permission=view` returns KGs
  in the workspace the user can view.
- Empty list (not 404) when workspace has no KGs or user has no permission on any KG
  in the workspace.
- New unit tests for `list_for_workspace_with_permission` pass (TDD-first).
- New integration tests for the workspace-filtered route pass.
- `make test-unit && make test-integration` exits 0 with no regressions.
- The `TODO` comment in `mutations.vue` (`# TODO: backend must support...`) is removed
  in the same commit as this backend change, OR in a follow-up to task-074.

## TDD Cycle

1. Write unit tests for `list_for_workspace_with_permission` (RED).
2. Implement the service method (GREEN).
3. Write integration test for route with `?workspace_id=` param (RED).
4. Update the route handler to accept and use `workspace_id` (GREEN).
5. Run `make test-unit && make test-integration`.
6. Commit atomically.
