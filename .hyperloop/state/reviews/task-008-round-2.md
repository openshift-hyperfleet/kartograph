---
task_id: task-008
round: 2
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — Knowledge Graphs (task-008)

One SHALL requirement is implemented but incompletely — encrypted credential
deletion is absent from the KG cascade delete path.

## Requirement Coverage

### 1. Knowledge Graph Creation — COVERED
- `management/application/services/knowledge_graph_service.py` lines 95–162
- ULID ID: `management/domain/value_objects.py` KnowledgeGraphId.generate()
- Authorization relationships (workspace + tenant) via outbox:
  `management/infrastructure/outbox/translator.py` lines 119–147
- Tests: TestKnowledgeGraphServiceCreate, TestCreateKnowledgeGraph,
  TestManagementEventTranslatorKnowledgeGraphCreated

### 2. Duplicate Name Within Tenant — COVERED
- IntegrityError caught → DuplicateKnowledgeGraphNameError (service lines 154–162)
- Test: test_create_raises_duplicate_on_integrity_error
- Integration: TestKnowledgeGraphUniqueness::test_duplicate_name_in_same_tenant_raises_error

### 3. Knowledge Graph Name Validation — COVERED
- 1–100 chars enforced in domain aggregate lines 66–78
- 422 responses for empty/oversized name in create and update routes

### 4. Knowledge Graph Retrieval — COVERED
- Returns None for both unauthorized and not-found (no existence leakage)
- `management/application/services/knowledge_graph_service.py` lines 164–197
- Tests: TestKnowledgeGraphServiceGet (5 scenarios), TestGetKnowledgeGraph

### 5. Knowledge Graph Listing — COVERED
- Workspace-scoped, authz-filtered via read_relationships
- `management/application/services/knowledge_graph_service.py` lines 199–264
- Tests: TestKnowledgeGraphServiceListForWorkspace, TestListKnowledgeGraphs

### 6. Knowledge Graph Update — COVERED
- EDIT permission on KG required; name/desc updated and saved
- `management/application/services/knowledge_graph_service.py` lines 266–325
- Tests: TestKnowledgeGraphServiceUpdate, TestUpdateKnowledgeGraph

### 7. Knowledge Graph Deletion — PARTIAL

FAIL: The spec SHALL states cascade deletes "All data sources within it are
deleted (including their encrypted credentials)."

`KnowledgeGraphService.delete()` (lines 368–377) calls `ds_repo.delete(ds)`
but never calls `secret_store.delete()`. Contrast with `DataSourceService.delete()`
(lines 384–392) which explicitly deletes Vault credentials when
`ds.credentials_path` is set. The KG service has no `ISecretStoreRepository`
dependency at all.

No test verifies that encrypted credentials are removed during KG cascade
delete. `test_delete_cascades_data_sources` asserts only that `ds_repo.delete`
is called, not that credentials are cleaned up.

What IS covered:
- MANAGE permission check
- Cascade data source DB record deletion
- Atomic transaction / rollback-on-failure (`test_delete_rolls_back_on_ds_deletion_failure`)
- Outbox events
- AggregateDeletedError on mutation after deletion (`test_update_raises_after_deletion`)

Required fix: `KnowledgeGraphService.__init__` must accept an
`ISecretStoreRepository` and `delete()` must call
`secret_store.delete(path=ds.credentials_path, tenant_id=...)` for each DS
with a credentials_path before calling `ds_repo.delete(ds)`. A test must
assert this behavior.

### 8. Permission Inheritance — COVERED (schema-level)
- SpiceDB schema: `shared_kernel/authorization/spicedb/schema.zed` lines 107–131
  - view = admin + editor + viewer + workspace->view
  - edit = admin + editor + workspace->edit
  - manage = admin + workspace->manage
- Schema design tests: TestKnowledgeGraphSchemaDesign (7 tests)

## NFR Compliance
- Domain probes: PASS — no direct logger calls in service/domain layers
- DDD boundaries: PASS — all 326 unit tests pass including architecture tests
- Mocks: project-wide pattern (consistent with IAM tests); not a task-008 deviation