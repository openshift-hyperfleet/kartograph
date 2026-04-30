---
task_id: task-035
round: 0
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — Knowledge Graphs (task-035)

### Requirement Status Summary

| Requirement | Status | Notes |
|---|---|---|
| 1. Knowledge Graph Creation | COVERED | |
| 2. Knowledge Graph Name Validation | COVERED | |
| 3. Knowledge Graph Retrieval | COVERED | |
| 4. Knowledge Graph Listing | COVERED | |
| 5. Knowledge Graph Update | COVERED | |
| 6. Knowledge Graph Deletion | PARTIAL | Rollback scenario missing test |
| 7. Permission Inheritance | COVERED | |

---

## Detailed Findings

### Requirement 1 — Knowledge Graph Creation: COVERED

**Spec**: Users with `edit` permission on a workspace can create KGs with a ULID identifier,
workspace+tenant association, and authorization relationships established.

**Implementation**:
- `management/domain/aggregates/knowledge_graph.py` — `KnowledgeGraph.create()` generates ULID via
  `KnowledgeGraphId.generate()` (line 128), sets tenant_id and workspace_id.
- `management/application/services/knowledge_graph_service.py` — `create()` checks EDIT permission
  on workspace (lines 122–137), raises `DuplicateKnowledgeGraphNameError` on `IntegrityError` (lines 159–167).
- `management/infrastructure/outbox/translator.py` — `_translate_knowledge_graph_created()` (lines 119–147)
  writes two `WriteRelationship` ops: `workspace` link and `tenant` link to SpiceDB.

**Tests** (all in unit suite):
- `test_create_checks_edit_permission_on_workspace` — verifies EDIT permission guard
- `test_create_raises_unauthorized_when_permission_denied` — 403 path
- `test_create_saves_aggregate_via_repo` — repo save called
- `test_create_raises_duplicate_on_integrity_error` — duplicate name rejection
- `TestKnowledgeGraphCreated::test_create_sets_all_fields`, `test_create_generates_unique_id`
- `tests/unit/management/infrastructure/outbox/test_translator.py`:
  `test_translates_to_workspace_and_tenant_relationships`,
  `test_first_operation_is_workspace_relationship`,
  `test_second_operation_is_tenant_relationship` — auth relationships verified
- Integration: `test_duplicate_name_in_same_tenant_raises_error`

---

### Requirement 2 — Knowledge Graph Name Validation: COVERED

**Spec**: Names 1–100 characters accepted; empty or >100 characters rejected.

**Implementation**:
- `management/domain/aggregates/knowledge_graph.py` — `_validate_name()` (lines 66–78) raises
  `InvalidKnowledgeGraphNameError` if `not (1 <= len(name) <= 100)`.
- Called from `__post_init__()` (line 62) and `update()` (line 176).

**Tests**:
- `test_create_rejects_empty_name`, `test_create_rejects_name_over_100_chars`,
  `test_create_accepts_name_exactly_100_chars`, `test_create_accepts_single_char_name`
- `test_update_rejects_empty_name`, `test_update_rejects_name_over_100_chars`
- `test_post_init_rejects_empty_name`, `test_post_init_rejects_name_over_100_chars`

---

### Requirement 3 — Knowledge Graph Retrieval: COVERED

**Spec**: Only `view`-permitted users receive details; unauthorized and non-existent return
the same result (no existence leakage).

**Implementation**:
- `knowledge_graph_service.py` — `get()` (lines 169–202): checks VIEW permission; returns `None`
  for both missing record and permission denied.
- `presentation/knowledge_graphs/routes.py` — maps `None` → 404 regardless of cause.

**Tests**:
- `test_get_returns_none_when_not_found`, `test_get_checks_view_permission`,
  `test_get_returns_none_for_different_tenant`, `test_get_returns_none_when_permission_denied`,
  `test_get_returns_aggregate_on_success`
- `test_get_knowledge_graph_returns_200`, `test_get_knowledge_graph_returns_404_when_not_found`

---

### Requirement 4 — Knowledge Graph Listing: COVERED

**Spec**: List KGs for a workspace, filtered to only those the user can `view`.

**Implementation**:
- `knowledge_graph_service.py` — `list_for_workspace()` (lines 204–269): checks VIEW on workspace,
  reads SpiceDB relationships to discover KG IDs, filters by tenant.

**Tests**:
- `test_list_checks_view_permission_on_workspace`, `test_list_raises_unauthorized_when_permission_denied`,
  `test_list_uses_read_relationships_to_discover_kgs`, `test_list_filters_by_tenant`
- `test_list_workspace_kgs_returns_200`, `test_list_workspace_kgs_calls_service_with_correct_args`,
  `test_list_workspace_kgs_returns_403_when_unauthorized`

---

### Requirement 5 — Knowledge Graph Update: COVERED

**Spec**: Users with `edit` permission can update name and description.

**Implementation**:
- `knowledge_graph_service.py` — `update()` (lines 302–361): checks EDIT permission on KG,
  calls `kg.update()`, catches `IntegrityError` for duplicate names.
- `KnowledgeGraph.update()` (lines 156–195): validates name, records `KnowledgeGraphUpdated` event.

**Tests**:
- `test_update_checks_edit_permission_on_kg`, `test_update_raises_unauthorized_when_permission_denied`,
  `test_update_calls_aggregate_update_and_saves`, `test_update_raises_duplicate_on_integrity_error`
- `test_update_changes_name_and_description`, `test_update_emits_knowledge_graph_updated_event`
- Integration: `test_updates_knowledge_graph`, `test_update_records_outbox_event`
- Routes: `test_update_knowledge_graph_returns_200`, `test_update_knowledge_graph_returns_403_when_unauthorized`,
  `test_update_knowledge_graph_returns_409_on_duplicate_name`

---

### Requirement 6 — Knowledge Graph Deletion: PARTIAL ← FAIL TRIGGER

**Spec scenario A (Successful deletion)**: Atomic cascade: delete DS credentials, delete DS records,
delete KG record, clean up all auth relationships in a single transaction. Rollback if any step fails.

**Spec scenario B (Mutation after deletion)**: Any mutation on a deleted KG is rejected.

**Implementation**:
- `knowledge_graph_service.py` — `delete()` (lines 363–424): wraps entire cascade in
  `async with self._session.begin():` (line 404). Deletes DS credentials → DS records → KG record.
  `mark_for_deletion()` writes SpiceDB cleanup via outbox within the same transaction.
- `KnowledgeGraph.update()` (line 174): raises `AggregateDeletedError` when `self._deleted` is True.
- `KnowledgeGraphDeleted` event (translator lines 160–221): removes workspace+tenant links plus
  filter-deletes admin/editor/viewer grants.

**Tests — Scenario B (Mutation after deletion): COVERED**
- `tests/unit/management/test_knowledge_graph.py::TestKnowledgeGraphUpdate::test_update_raises_after_deletion`
  (line 214): verifies `AggregateDeletedError` raised after `mark_for_deletion()`.

**Tests — Scenario A (Atomicity / Rollback): MISSING**

There is **no test** verifying that a failure mid-cascade causes the entire transaction to roll back
with no partial state. The implementation relies on SQLAlchemy's implicit rollback within
`async with session.begin():`, but the spec explicitly states:

> AND if any step fails, the entire deletion rolls back with no partial state

The IAM context has an equivalent test (`test_rollback_removes_both_group_and_outbox_entry` in
`tests/integration/iam/test_outbox_consistency.py`) that explicitly verifies rollback semantics
using `raise Exception("Forced rollback for test")`. No such test exists for KG deletion in the
management context.

**What is needed to pass**:
Add an integration test (e.g., in `tests/integration/management/test_knowledge_graph_repository.py`
or a new `test_knowledge_graph_deletion_atomicity.py`) that:
1. Creates a KG with at least one data source.
2. Injects a failure mid-cascade (e.g., after DS deletion, before KG deletion).
3. Asserts that neither the KG nor the DS records were deleted (full rollback).

Example pattern (mirrors IAM rollback test):
```python
async def test_deletion_rollback_on_failure(async_session, ...):
    # arrange: create KG with DS
    try:
        async with async_session.begin():
            ds.mark_for_deletion()
            await ds_repo.delete(ds)
            raise Exception("simulated failure before KG delete")
    except Exception:
        pass
    # assert: KG and DS both still exist
    assert await kg_repo.get_by_id(kg.id) is not None
    remaining_ds = await ds_repo.find_by_knowledge_graph(kg.id.value)
    assert len(remaining_ds) == 1
```

---

### Requirement 7 — Permission Inheritance: COVERED

**Spec**: KG permissions inherit from parent workspace; direct grants (admin) override.

**Implementation**:
- SpiceDB schema defines `workspace` and `tenant` relation on `knowledge_graph` resource type.
- Translator writes these relationships on `KnowledgeGraphCreated`.
- All permission checks use `AuthorizationProvider.check_permission()`.

**Tests** (`tests/integration/management/test_knowledge_graph_authorization.py`):
- `TestWorkspaceInheritedKnowledgeGraphAccess`:
  - `test_workspace_editor_can_view_knowledge_graph`
  - `test_workspace_editor_can_edit_knowledge_graph`
  - `test_workspace_editor_cannot_manage_knowledge_graph`
  - `test_workspace_admin_can_manage_knowledge_graph`
  - `test_workspace_member_can_view_knowledge_graph`
  - `test_workspace_member_cannot_edit_knowledge_graph`
  - `test_user_without_workspace_role_cannot_access_knowledge_graph`
- `TestDirectGrantKnowledgeGraphAccess`:
  - `test_direct_kg_admin_has_manage_permission`
  - `test_direct_kg_admin_has_edit_permission`
  - `test_direct_kg_admin_has_view_permission`
  - `test_direct_kg_editor_has_edit_and_view_but_not_manage`
  - `test_direct_kg_viewer_has_view_only`

---

## Verdict: FAIL

**Single failing gap**: Requirement 6 (Knowledge Graph Deletion) — the spec's "Successful deletion"
scenario explicitly mandates that failure in any step rolls back the entire operation with no partial
state. The implementation is correctly structured (SQLAlchemy `async with session.begin()` provides
automatic rollback), but there is **no test** exercising this rollback property.

All other 6 SHALL requirements are fully implemented and have corresponding test coverage.
Once the rollback test is added, this task should pass a re-review.