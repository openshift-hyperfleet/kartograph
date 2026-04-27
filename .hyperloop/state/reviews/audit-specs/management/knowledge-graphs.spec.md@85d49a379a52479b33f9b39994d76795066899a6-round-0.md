---
task_id: audit-specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Worker Result — Alignment Audit: specs/management/knowledge-graphs.spec.md

Auditor: spec-alignment
Spec commit: 85d49a379a52479b33f9b39994d76795066899a6
Date: 2026-04-27

---

### Verdict: FAIL

Two gaps found between the spec and the implementation.

---

### Gap 1: Missing Workspace-Scoped List HTTP Endpoint

**Spec requirement (Requirement: Knowledge Graph Listing)**:
> GIVEN a user with `view` permission on a workspace containing knowledge graphs
> WHEN the user lists knowledge graphs for that workspace
> THEN only knowledge graphs the user can view are returned

**What the code does**:
- The service layer has `list_for_workspace(user_id, workspace_id)` in
  `src/api/management/application/services/knowledge_graph_service.py` (line 199)
  which correctly checks VIEW on the workspace and returns only KGs in that workspace.
- However, no HTTP route exposes this method. The routes file
  (`src/api/management/presentation/knowledge_graphs/routes.py`) defines only:
  - `GET /knowledge-graphs` — list all KGs in the tenant (calls `list_all()`)
  - `GET /knowledge-graphs/{kg_id}` — get by ID
  - `POST /workspaces/{workspace_id}/knowledge-graphs` — create

There is no `GET /workspaces/{workspace_id}/knowledge-graphs` endpoint.
`list_for_workspace()` is unreachable via HTTP.

---

### Gap 2: Cascade Delete Does Not Clean Up Encrypted Credentials

**Spec requirement (Requirement: Knowledge Graph Deletion, Scenario: Successful deletion)**:
> All data sources within it are deleted (including their encrypted credentials)

**What the code does**:
`KnowledgeGraphService.delete()` (lines 399–408,
`src/api/management/application/services/knowledge_graph_service.py`) cascades
to data sources like this:

```python
async with self._session.begin():
    if self._ds_repo is not None:
        data_sources = await self._ds_repo.find_by_knowledge_graph(kg_id)
        for ds in data_sources:
            ds.mark_for_deletion(deleted_by=user_id)
            await self._ds_repo.delete(ds)          # DB record deleted

    kg.mark_for_deletion(deleted_by=user_id)
    await self._kg_repo.delete(kg)
```

This deletes data source **database records** but never calls
`ISecretStoreRepository.delete()` on each data source's credentials.
`KnowledgeGraphService` has no `ISecretStoreRepository` dependency at all
(see constructor, lines 43–67, and dependency factory in
`src/api/management/dependencies/knowledge_graph.py`).

By contrast, the standalone `DataSourceService.delete()` (lines 384–392 of
`src/api/management/application/services/data_source_service.py`) correctly
deletes credentials before removing the record:

```python
async with self._session.begin():
    if ds.credentials_path:
        await self._secret_store.delete(
            path=ds.credentials_path,
            tenant_id=self._scope_to_tenant,
        )
    ds.mark_for_deletion(deleted_by=user_id)
    await self._ds_repo.delete(ds)
```

The cascade path through `KnowledgeGraphService` bypasses credential cleanup,
leaving orphaned encrypted credential rows in the `encrypted_credentials` table
after a knowledge graph deletion.

---

### Passing Requirements (for completeness)

The following spec requirements ARE correctly implemented:

- **KG Creation**: ULID generation, workspace/tenant association, EDIT permission
  check on workspace, duplicate name rejected (409).
- **Authorization relationships on creation**: `KnowledgeGraphCreated` event →
  outbox → `ManagementEventTranslator._translate_knowledge_graph_created()` writes
  `workspace` and `tenant` relationships in SpiceDB.
- **Name validation**: 1–100 chars enforced both at domain (`InvalidKnowledgeGraphNameError`)
  and Pydantic model layer; applied on create and update.
- **Retrieval**: VIEW permission checked; unauthorized and missing both return None → 404
  with no distinction (existence leakage prevention).
- **Update**: EDIT permission checked on the KG; duplicate name enforced on update.
- **Deletion — atomicity of DB changes**: All DB deletes (data sources + KG) are wrapped
  in a single `async with self._session.begin()` transaction; rollback on failure.
- **Deletion — SpiceDB cleanup**: `KnowledgeGraphDeleted` event → outbox →
  translator deletes workspace relation, tenant relation, and all direct admin/editor/viewer
  grants (via `DeleteRelationshipsByFilter`).
- **Mutation after deletion**: Once deleted from DB, `get_by_id()` returns None and
  subsequent mutations receive a 404/not-found rejection. The domain aggregate also guards
  with `AggregateDeletedError` on in-memory re-use.
- **Permission inheritance**: SpiceDB schema (`schema.zed`) correctly defines
  `view = admin + editor + viewer + workspace->view`,
  `edit = admin + editor + workspace->edit`,
  `manage = admin + workspace->manage`.
- **Direct admin grant**: `admin` relation grants all three permissions regardless of
  workspace role.