---
task_id: task-035
round: 2
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review: specs/management/knowledge-graphs.spec.md

### Requirement: Knowledge Graph Creation

**Scenario: Successful creation** — COVERED
- Aggregate: `management/domain/aggregates/knowledge_graph.py` — `KnowledgeGraph.create()` generates ULID (`KnowledgeGraphId.generate()`), records workspace/tenant IDs, emits `KnowledgeGraphCreated`.
- Authorization relationships: `management/infrastructure/outbox/translator.py` `_translate_knowledge_graph_created()` writes workspace and tenant relationships to SpiceDB.
- Service: `knowledge_graph_service.py` `create()` checks EDIT on workspace before persisting.
- Tests: `test_knowledge_graph.py::TestKnowledgeGraphCreate::test_create_sets_all_fields`, `test_create_emits_knowledge_graph_created_event`; `test_knowledge_graph_service.py::TestKnowledgeGraphServiceCreate::test_create_saves_aggregate_via_repo`.

**Scenario: Duplicate name within tenant** — COVERED
- Implementation: DB unique constraint on `(tenant_id, name)`; `IntegrityError` caught and re-raised as `DuplicateKnowledgeGraphNameError`.
- Tests: `test_knowledge_graph_service.py::test_create_raises_duplicate_on_integrity_error`; integration `test_knowledge_graph_repository.py::TestKnowledgeGraphUniqueness::test_duplicate_name_in_same_tenant_raises_error`.

---

### Requirement: Knowledge Graph Name Validation

**Scenario: Valid name (1-100 chars)** — COVERED
- Implementation: `_validate_name()` in aggregate enforces `1 <= len(name) <= 100`; Pydantic `CreateKnowledgeGraphRequest` and `UpdateKnowledgeGraphRequest` both set `min_length=1, max_length=100`.
- Tests: `test_knowledge_graph.py::TestKnowledgeGraphCreate::test_create_accepts_name_exactly_100_chars`, `test_create_accepts_single_char_name`.

**Scenario: Empty or oversized name** — COVERED
- Implementation: `InvalidKnowledgeGraphNameError` raised in aggregate; 422 returned at API layer via Pydantic.
- Tests: `test_knowledge_graph.py::test_create_rejects_empty_name`, `test_create_rejects_name_over_100_chars`, `test_update_rejects_empty_name`, `test_update_rejects_name_over_100_chars`; route test `test_create_knowledge_graph_requires_name` returns 422.

---

### Requirement: Knowledge Graph Retrieval

**Scenario: Authorized retrieval** — COVERED
- Implementation: `knowledge_graph_service.py::get()` fetches by ID, checks VIEW permission, returns aggregate.
- Tests: `test_knowledge_graph_service.py::TestKnowledgeGraphServiceGet::test_get_returns_aggregate_on_success`; route test `TestGetKnowledgeGraphRoute::test_get_knowledge_graph_returns_200`.

**Scenario: Unauthorized or non-existent** — COVERED
- Implementation: `get()` returns `None` for missing KG, different-tenant KG, or permission-denied; route returns 404 in all cases with no distinction.
- Tests: `test_get_returns_none_when_not_found`, `test_get_returns_none_for_different_tenant`, `test_get_returns_none_when_permission_denied`; route test `test_get_knowledge_graph_returns_404_when_not_found`.

---

### Requirement: Knowledge Graph Listing

**Scenario: List for workspace** — COVERED
- Implementation: `list_for_workspace()` checks VIEW on workspace, reads SpiceDB relationships to discover KG IDs, filters by tenant.
- Tests: `TestKnowledgeGraphServiceListForWorkspace::test_list_uses_read_relationships_to_discover_kgs`, `test_list_filters_by_tenant`; route test `TestListWorkspaceKnowledgeGraphsRoute::test_list_workspace_kgs_returns_200`.

---

### Requirement: Knowledge Graph Update

**Scenario: Update name and description** — COVERED
- Implementation: `update()` service method checks EDIT on the KG, calls `kg.update()`, saves via repo.
- Tests: `TestKnowledgeGraphServiceUpdate::test_update_calls_aggregate_update_and_saves`; route test `TestUpdateKnowledgeGraphRoute::test_update_knowledge_graph_returns_200`.

---

### Requirement: Knowledge Graph Deletion

**Scenario: Successful deletion** — PARTIAL
- Cascade (DS deletion + KG deletion) in single SQLAlchemy transaction: COVERED in `knowledge_graph_service.py::delete()` at lines 404-420; integration rollback test at `test_knowledge_graph_repository.py::TestCascadeDeleteRollback::test_knowledge_graph_deletion_rollback_on_failure` verifies atomicity.
- Credential cleanup: COVERED (`test_delete_calls_secret_store_delete_for_credential_bearing_ds`).
- Authorization cleanup via outbox translator: COVERED (workspace, tenant, admin/editor/viewer filter deletes in `_translate_knowledge_graph_deleted()`).
- **GAP — rollback integration test uses only the repository layer, not the full service.** The spec says "if any step fails, the entire deletion rolls back with no partial state." The integration rollback test (`TestCascadeDeleteRollback`) injects a failure in the _repository layer directly_, bypassing `KnowledgeGraphService`. There is no integration test exercising the service's `delete()` path end-to-end with a real DB session and a mid-transaction failure through the service. The `test_knowledge_graph_service.py` tests use `AsyncMock` sessions, which cannot verify real SQLAlchemy rollback semantics (as noted in the test comment). This is acknowledged in test comments but no separate end-to-end service integration test covers the scenario.
- **Verdict for this scenario: PARTIAL** — the atomicity proof lives in the repository-layer test, not the service layer. The spec references the deletion as a whole operation. The service test uses a mock session that cannot verify real rollback.

**Scenario: Mutation after deletion** — COVERED
- Implementation: `_deleted` flag set in `mark_for_deletion()`; `update()` checks it and raises `AggregateDeletedError`.
- Tests: `test_knowledge_graph.py::TestKnowledgeGraphUpdate::test_update_raises_after_deletion`.
- Note: only `update()` has this guard; `mark_for_deletion()` is idempotent (tested). No other "mutations" exist on the aggregate, so coverage is complete.

---

### Requirement: Permission Inheritance

**Scenario: Workspace-inherited access** — COVERED
- Implementation: SpiceDB schema `schema.zed` lines 107-131 define `knowledge_graph.edit = admin + editor + workspace->edit`; `knowledge_graph.view = admin + editor + viewer + workspace->view`; `knowledge_graph.manage = admin + workspace->manage`.
- Tests: `test_knowledge_graph_authorization.py::TestWorkspaceInheritedKnowledgeGraphAccess` (7 integration tests against real SpiceDB: editor can view, editor can edit, editor cannot manage, admin can manage, member can view, member cannot edit, no-role user denied).

**Scenario: Direct grant** — COVERED
- Implementation: `admin`, `editor`, `viewer` relations on `knowledge_graph` in schema.zed.
- Tests: `test_knowledge_graph_authorization.py::TestDirectGrantKnowledgeGraphAccess` (5 integration tests: admin has manage/edit/view; editor has edit+view but not manage; viewer has view only).

---

## NFR Violations

### NFR: testing.spec.md — No Mocking Libraries for Domain or Application Logic

**FAIL — `test_knowledge_graph_service.py` uses `AsyncMock` and `MagicMock` for infrastructure ports and probe protocols.**

The spec says: "Mocking is NOT acceptable for: domain services, repositories, event handlers, or probe protocols."

Specifically:
- `mock_kg_repo = AsyncMock()` (line 53) — mocks `IKnowledgeGraphRepository`, a repository port. The spec explicitly lists repositories as not acceptable mock targets.
- `mock_ds_repo = AsyncMock()` (line 58) — mocks `IDataSourceRepository`, same issue.
- `mock_secret_store = AsyncMock()` (line 63) — mocks `ISecretStoreRepository`.
- `mock_authz = AsyncMock()` (line 68) — mocks `AuthorizationProvider`; an `InMemoryAuthorizationProvider` fake exists at `tests/fakes/authorization.py` but is not used here.
- `mock_probe = MagicMock()` (line 74) — mocks `KnowledgeGraphServiceProbe`, a probe protocol. The spec explicitly says probe protocols must NOT be mocked with `MagicMock`.

The `InMemoryAuthorizationProvider` exists (`tests/fakes/authorization.py`) and should be used in place of `AsyncMock()` for `authz`. No in-memory fake repositories exist for `IKnowledgeGraphRepository`, `IDataSourceRepository`, or `ISecretStoreRepository` — they need to be created per the testing NFR.

The probe (`mock_probe = MagicMock()`) is used as if it is a no-op recording test double, but the testing spec requires a concrete class implementation, not a `MagicMock`.

This is a spec violation in the application-layer test for `KnowledgeGraphService`.

### NFR: observability.spec.md — PASS
- Domain probes: `KnowledgeGraphProbe` Protocol + `DefaultKnowledgeGraphProbe` class in `management/domain/observability/knowledge_graph_probe.py`.
- Application probes: `KnowledgeGraphServiceProbe` Protocol + `DefaultKnowledgeGraphServiceProbe` in `management/application/observability/knowledge_graph_service_probe.py`.
- All domain code depends on the Protocol, not directly on structlog (structlog only in Default implementations).
- Tests: `test_probes.py` verifies protocol compliance and structlog calls.

### NFR: architecture.spec.md — PASS
- `test_architecture.py` enforces all DDD layer boundaries and bounded context isolation via `pytest-archon`.
- Management does not import from IAM/Graph/Ingestion/Extraction/Querying (with documented exceptions for DI wiring in `management.dependencies` and `management.presentation`).

### NFR: api-conventions.spec.md — PASS
- URL patterns follow spec: `POST /management/workspaces/{workspace_id}/knowledge-graphs`, `GET /management/knowledge-graphs`, `GET /management/knowledge-graphs/{kg_id}`, `PATCH /management/knowledge-graphs/{kg_id}`, `DELETE /management/knowledge-graphs/{kg_id}`.
- Status codes: 201 create, 200 get/list/update, 204 delete, 403 unauthorized, 404 not found, 409 conflict, 422 validation.
- Error format: `{"detail": "..."}` throughout.
- Field naming: snake_case in all Pydantic models.
- Authentication: `get_current_user` dependency used on all routes.

---

## Summary

| Requirement | Status |
|---|---|
| KG Creation — Successful | COVERED |
| KG Creation — Duplicate name | COVERED |
| KG Name Validation — Valid | COVERED |
| KG Name Validation — Empty/oversized | COVERED |
| KG Retrieval — Authorized | COVERED |
| KG Retrieval — Unauthorized/missing | COVERED |
| KG Listing — Workspace filter | COVERED |
| KG Update — name and description | COVERED |
| KG Deletion — Atomic cascade | PARTIAL — no service-layer integration test verifying real rollback through `KnowledgeGraphService.delete()` |
| KG Deletion — Mutation after deletion | COVERED |
| Permission Inheritance — Workspace | COVERED |
| Permission Inheritance — Direct grant | COVERED |
| NFR: Testing — fakes over mocks | FAIL — `test_knowledge_graph_service.py` mocks repository ports and probe protocol with `AsyncMock`/`MagicMock` |
| NFR: Observability — domain probes | PASS |
| NFR: Architecture — DDD boundaries | PASS |
| NFR: API conventions | PASS |

## Required Fixes

1. **[FAIL — NFR Testing]** In `src/api/tests/unit/management/application/test_knowledge_graph_service.py`:
   - Replace `mock_kg_repo = AsyncMock()` with an in-memory fake implementing `IKnowledgeGraphRepository`.
   - Replace `mock_ds_repo = AsyncMock()` with an in-memory fake implementing `IDataSourceRepository`.
   - Replace `mock_secret_store = AsyncMock()` with an in-memory fake or concrete no-op implementing `ISecretStoreRepository`.
   - Replace `mock_authz = AsyncMock()` with `InMemoryAuthorizationProvider` from `tests/fakes/authorization.py`.
   - Replace `mock_probe = MagicMock()` with a concrete recording no-op class (not `MagicMock(spec=...)`) implementing `KnowledgeGraphServiceProbe`.

2. **[PARTIAL — Cascade Atomicity]** Add an integration test that exercises `KnowledgeGraphService.delete()` with a real `AsyncSession` and injects a failure mid-cascade to verify the service-level transaction rolls back fully. The existing repository-layer rollback test (`TestCascadeDeleteRollback`) is necessary but not sufficient since the service wraps `async with self._session.begin()` which is the real rollback boundary.