---
task_id: task-008
round: 0
role: spec-reviewer
verdict: fail
---
Spec alignment review for specs/management/knowledge-graphs.spec.md against
branch hyperloop/task-008.

## Requirement-by-Requirement Findings

### Requirement: Knowledge Graph Creation — COVERED

**Scenario: Successful creation**
- Code: `KnowledgeGraphService.create()` checks `Permission.EDIT` on workspace;
  `KnowledgeGraph.create()` generates a ULID via `KnowledgeGraphId.generate()`;
  aggregate is saved via repository; `KnowledgeGraphCreated` event triggers
  SpiceDB workspace+tenant relationship writes via `ManagementEventTranslator`.
- Tests:
  - `test_create_checks_edit_permission_on_workspace` (service unit)
  - `test_create_saves_aggregate_via_repo` (verifies workspace_id + tenant_id)
  - `test_generate_creates_valid_ulid` (value objects unit)
  - `test_first/second_operation_is_workspace/tenant_relationship` (translator unit)
  - `test_create_knowledge_graph_returns_201` (presentation unit)

**Scenario: Duplicate name within tenant**
- Code: `IntegrityError` from DB unique constraint → `DuplicateKnowledgeGraphNameError`.
- Tests:
  - `test_create_raises_duplicate_on_integrity_error` (service unit)
  - `test_duplicate_name_in_same_tenant_raises_error` (repo integration)
  - `test_create_knowledge_graph_returns_409_for_duplicate_name` (presentation unit)

---

### Requirement: Knowledge Graph Name Validation — COVERED

**Scenario: Valid name**
- Code: `KnowledgeGraph._validate_name()` enforces `1 <= len(name) <= 100`;
  Pydantic models enforce `min_length=1, max_length=100`.
- Tests:
  - `test_create_accepts_name_exactly_100_chars`, `test_create_accepts_single_char_name`

**Scenario: Empty or oversized name → validation error**
- Code: Domain raises `InvalidKnowledgeGraphNameError`; Pydantic returns 422.
- Tests:
  - `test_create_rejects_empty_name`, `test_create_rejects_name_over_100_chars` (domain unit)
  - `test_update_rejects_empty_name`, `test_update_rejects_name_over_100_chars` (domain unit)
  - `test_create_knowledge_graph_returns_422_for_empty/oversized_name` (presentation unit)
  - `test_update_knowledge_graph_returns_422_for_empty/oversized_name` (presentation unit)

---

### Requirement: Knowledge Graph Retrieval — COVERED

**Scenario: Authorized retrieval**
- Code: `KnowledgeGraphService.get()` checks `Permission.VIEW`; returns aggregate.
- Tests:
  - `test_get_checks_view_permission`, `test_get_returns_aggregate_on_success` (service unit)
  - `test_get_knowledge_graph_returns_200` (presentation unit)

**Scenario: Unauthorized or non-existent → 404 (no distinction)**
- Code: `get()` returns `None` for both not-found and unauthorized; route returns 404.
- Tests:
  - `test_get_returns_none_when_not_found`, `test_get_returns_none_when_permission_denied` (service unit)
  - `test_get_knowledge_graph_returns_404_when_not_found/unauthorized` (presentation unit)

---

### Requirement: Knowledge Graph Listing — COVERED

**Scenario: List for workspace (filtered by authorization)**
- Code: Checks `Permission.VIEW` on workspace; uses `read_relationships` to discover
  linked KG IDs; filters by tenant.
- Tests:
  - `test_list_checks_view_permission_on_workspace` (service unit)
  - `test_list_uses_read_relationships_to_discover_kgs` (service unit)
  - `test_list_filters_by_tenant` (service unit)
  - `test_list_knowledge_graphs_returns_200_with_list` (presentation unit)

---

### Requirement: Knowledge Graph Update — COVERED

**Scenario: Update name and description**
- Code: `KnowledgeGraphService.update()` checks `Permission.EDIT` on the KG;
  calls `kg.update(name, description)` and saves.
- Tests:
  - `test_update_calls_aggregate_update_and_saves` (service unit)
  - Multiple domain tests in `TestKnowledgeGraphUpdate`
  - `test_update_knowledge_graph_returns_200` (presentation unit)

---

### Requirement: Knowledge Graph Deletion — PARTIAL ← FAIL TRIGGER

**Scenario: Successful deletion with atomic cascade**

The spec states (SHALL):

> THEN the following cascade executes atomically within a single transaction:
> - All data sources within it are deleted (including their encrypted credentials)
> - The knowledge graph record is deleted
> - All authorization relationships are cleaned up (workspace, tenant, and all direct grants)
> AND if any step fails, the entire deletion rolls back with no partial state

**What is implemented:**
- `KnowledgeGraphService.delete()` wraps DS deletion and KG deletion in
  `async with self._session.begin():` — auto-rollback on exception. ✓
- SpiceDB cleanup: handled via `KnowledgeGraphDeleted` event through the outbox
  pattern (5 operations: delete workspace, tenant, admin filter, editor filter,
  viewer filter). ✓ Tested in `TestManagementEventTranslatorKnowledgeGraphDeleted`.
- DS cascade: `test_delete_cascades_data_sources` verifies each DS is marked and
  deleted before the KG. ✓

**What is NOT tested (FAIL):**

> "if any step fails, the entire deletion rolls back with no partial state"

There is NO test that exercises the rollback path. The spec explicitly requires
atomicity with rollback on failure. No test simulates, for example, the second
`ds_repo.delete()` raising an exception and verifying that:
1. The first DS deletion is rolled back.
2. The KG record is NOT deleted.
3. No outbox event is emitted.

The implementation uses `async with self._session.begin():` which provides
automatic rollback — but this behavior is never tested.

**To fix:** Add a unit test to `TestKnowledgeGraphServiceDelete` that raises an
exception mid-cascade (e.g., mock `mock_ds_repo.delete` to raise on the second
call) and asserts that `mock_kg_repo.delete` is never called, verifying rollback
semantics at the service layer.

**Scenario: Mutation after deletion**
- Code: `KnowledgeGraph.update()` raises `AggregateDeletedError` when `_deleted=True`.
- Tests: `test_update_raises_after_deletion` (domain unit). ✓
- At service level: deleted KG is absent from repo → `ValueError("not found")`. ✓

---

### Requirement: Permission Inheritance — COVERED

**Scenario: Workspace-inherited access**
- Code: SpiceDB schema defines `permission edit = admin + editor + workspace->edit`;
  `permission manage = admin + workspace->manage`;
  `permission view = admin + editor + viewer + workspace->view`.
- Tests (schema design, `test_schema_design.py::TestKnowledgeGraphSchemaDesign`):
  - `test_knowledge_graph_edit_includes_workspace_edit` ✓
  - `test_knowledge_graph_manage_includes_workspace_manage` ✓
  - `test_knowledge_graph_view_includes_workspace_view` ✓

**Scenario: Direct grant (admin has manage + edit + view)**
- Code: `admin` appears in all three permission expressions in the schema.
- Tests:
  - `test_knowledge_graph_manage_is_admin_based` (admin in manage) ✓
  - `test_knowledge_graph_edit_includes_direct_roles` (admin in edit) ✓
  - `test_knowledge_graph_view_includes_direct_roles` (admin in view) ✓

---

## Verdict: FAIL

**Root cause:** One SHALL requirement has test coverage missing.

**Requirement: Knowledge Graph Deletion — PARTIAL**
The spec requires "if any step fails, the entire deletion rolls back with no
partial state." This behavior is implemented (SQLAlchemy auto-rollback) but is
NOT tested. Per the review protocol, a SHALL requirement without test coverage
is a FAIL.

**Fix needed (exact):**
In `src/api/tests/unit/management/application/test_knowledge_graph_service.py`,
class `TestKnowledgeGraphServiceDelete`, add a test such as:

```python
@pytest.mark.asyncio
async def test_delete_rolls_back_on_ds_deletion_failure(
    self, service, mock_authz, mock_kg_repo, mock_ds_repo, user_id, tenant_id
):
    """delete() rolls back entirely when a DS deletion fails mid-cascade."""
    kg = _make_kg(tenant_id=tenant_id)
    ds1 = MagicMock()
    ds2 = MagicMock()
    mock_authz.check_permission.return_value = True
    mock_kg_repo.get_by_id.return_value = kg
    mock_ds_repo.find_by_knowledge_graph.return_value = [ds1, ds2]
    # First DS deletes fine; second raises
    mock_ds_repo.delete.side_effect = [None, RuntimeError("DB failure")]

    with pytest.raises(RuntimeError):
        await service.delete(user_id=user_id, kg_id=kg.id.value)

    # KG itself must NOT have been deleted (transaction rolled back)
    mock_kg_repo.delete.assert_not_called()
```

No other requirements are missing implementation or test coverage.

## Non-blocking Observations

1. **AsyncMock over fakes:** Presentation tests use `AsyncMock(spec=KnowledgeGraphService)`
   consistent with existing IAM tests rather than a hand-written fake. Acceptable
   given project precedent.

2. **Fragile ValueError dispatch in update route:** String-matching on "not found"
   to discriminate 404 vs 400 is fragile. A typed `KnowledgeGraphNotFoundError`
   port exception would be cleaner. Pre-existing gap from the service-layer task.

3. **SpiceDB cleanup via outbox is eventual, not synchronous:** The spec says
   "authorization relationships are cleaned up" as part of the atomic cascade.
   The implementation uses the outbox pattern (eventual consistency). This is the
   correct production pattern (at-least-once delivery guarantees eventual cleanup)
   and the outbox event IS written atomically with the DB deletion, so the
   guarantees are maintained. Flagged for clarity only — not a failure.