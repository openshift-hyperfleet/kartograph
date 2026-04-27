---
task_id: audit-specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Spec Alignment Review — specs/management/knowledge-graphs.spec.md

Reviewer: spec-alignment-reviewer (Gate 7)
Date: 2026-04-27

---

### Summary

The implementation partially satisfies the spec. Domain aggregate, service layer,
authorization schema (SpiceDB), and tests are largely correct. However, three
concrete gaps exist where committed code deviates from or omits spec-required behavior.

---

### FAIL: Missing HTTP routes for Update and Delete

**Spec requirements:**
- "The system SHALL allow users with `edit` permission to update knowledge graph metadata."
- "The system SHALL allow users with `manage` permission to delete a knowledge graph, cascading to data sources."

**Implementation:**
`src/api/management/presentation/knowledge_graphs/routes.py` exposes only three routes:
- `GET /management/knowledge-graphs` (line 28)
- `GET /management/knowledge-graphs/{kg_id}` (line 62)
- `POST /management/workspaces/{workspace_id}/knowledge-graphs` (line 111)

No `PUT`/`PATCH` (update) or `DELETE` (delete) HTTP endpoints exist for knowledge graphs.
The service layer (`KnowledgeGraphService.update` and `KnowledgeGraphService.delete`) is
implemented and tested at the unit level, but there is no HTTP surface for callers.

**Files:**
- `src/api/management/presentation/knowledge_graphs/routes.py` — missing update and delete routes
- `src/api/tests/unit/management/presentation/test_knowledge_graphs_routes.py` — no update or delete route tests

---

### FAIL: Missing HTTP route for workspace-scoped listing

**Spec requirement:**
"The system SHALL list knowledge graphs within a workspace, filtered by authorization."
- Scenario: List for workspace — user lists knowledge graphs for a specific workspace

**Implementation:**
`GET /management/knowledge-graphs` (routes.py line 28) uses `service.list_all()`, which lists
all KGs in the tenant filtered by the user's VIEW permission. This is NOT a workspace-scoped list.

`KnowledgeGraphService.list_for_workspace()` (knowledge_graph_service.py line 199) exists and is
unit-tested but is **not reachable via any HTTP route**. There is no
`GET /management/workspaces/{workspace_id}/knowledge-graphs` endpoint.

**Files:**
- `src/api/management/presentation/knowledge_graphs/routes.py` — missing workspace-scoped listing route
- `src/api/tests/unit/management/presentation/test_knowledge_graphs_routes.py` — no workspace listing route tests

---

### FAIL: Cascade delete does not delete encrypted credentials

**Spec requirement:**
"THEN the following cascade executes atomically within a single transaction:
- All data sources within it are deleted (including their encrypted credentials)"

**Implementation:**
`KnowledgeGraphService.delete()` (knowledge_graph_service.py lines 399-408) iterates data sources
and calls `self._ds_repo.delete(ds)` for each, but does NOT delete their encrypted credentials.

The `FernetSecretStore` (fernet_secret_store.py) has a `delete(path, tenant_id)` method.
`DataSourceService.delete()` (data_source_service.py lines 384-392) correctly calls it.
But `KnowledgeGraphService` has no `secret_store` dependency
(confirmed in `knowledge_graph.py` dependencies at dependencies/knowledge_graph.py lines 43-52)
and no call to any credential deletion.

A data source with `credentials_path` set will have its DB record deleted but its encrypted
credential row in `encrypted_credentials` will remain orphaned after a KG cascade delete.

**Files:**
- `src/api/management/application/services/knowledge_graph_service.py` (lines 399-408) — missing credential deletion
- `src/api/management/dependencies/knowledge_graph.py` (lines 43-52) — no secret store provided
- `src/api/tests/unit/management/application/test_knowledge_graph_service.py` — no test asserts credential deletion on cascade delete

---

### PASS Items (for reference)

- ULID generation: `KnowledgeGraphId.generate()` via `str(ULID())` — correct
- Workspace/tenant association: set in `KnowledgeGraph.create()` and persisted — correct
- Auth relationships on creation: `KnowledgeGraphCreated` event triggers workspace+tenant writes in translator — correct
- Duplicate name check: DB unique constraint `uq_knowledge_graphs_tenant_name` + `IntegrityError` handling — correct
- Name validation (1-100 chars): enforced in `KnowledgeGraph._validate_name()` and Pydantic `CreateKnowledgeGraphRequest` — correct
- Retrieval with VIEW permission and no unauthorized/missing distinction: returns `None` in both cases — correct
- Update requires EDIT on knowledge_graph resource — correct
- Delete requires MANAGE on knowledge_graph resource — correct
- Mutation-after-deletion guard: `AggregateDeletedError` raised in `KnowledgeGraph.update()` when `_deleted=True` — correct
- Auth cleanup on deletion: translator removes workspace, tenant, admin, editor, viewer tuples — correct
- Atomic transaction: all deletes inside a single `async with self._session.begin()` block — correct (excluding missing credential deletion)
- Permission inheritance schema: SpiceDB schema.zed correctly models workspace->view/edit/manage chain and direct admin/editor/viewer grants — correct
- Integration tests for SpiceDB permission inheritance: test_knowledge_graph_authorization.py covers all key scenarios — correct
- All 322 unit tests pass