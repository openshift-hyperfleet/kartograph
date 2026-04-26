---
task_id: task-035
round: 6
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — specs/management/knowledge-graphs.spec.md

Reviewer: spec-alignment-reviewer (task-035, re-run after multiple worker crashes)

**NOTE:** The previous worker-result.yaml recorded `verdict: pass` and cited
several tests (`test_delete_rolls_back_on_ds_deletion_failure`,
`test_delete_cascades_encrypted_credentials`, `test_list_all_returns_all_visible_kgs`,
`test_list_all_filters_unauthorized_kgs`, plus PATCH/DELETE routes) that **do not
exist** in the codebase. This review corrects those findings.

---

### Requirement: Knowledge Graph Creation — COVERED

**Code:** `management/application/services/knowledge_graph_service.py::create()`
**Route:** `POST /management/workspaces/{workspace_id}/knowledge-graphs` (162-line routes.py)

**Scenario: Successful creation** — COVERED
- `test_create_checks_edit_permission_on_workspace` verifies EDIT permission on workspace
- `test_create_saves_aggregate_via_repo` verifies workspace/tenant association via aggregate
- Authorization relationships: covered via outbox translator
  (`test_translates_to_workspace_and_tenant_relationships` in
  `tests/unit/management/infrastructure/outbox/test_translator.py`)
- Route: `test_create_knowledge_graph_returns_201` (201 response verified)

**Scenario: Duplicate name** — COVERED
- `test_create_raises_duplicate_on_integrity_error` (service)
- `test_create_knowledge_graph_returns_409_on_duplicate_name` (route → 409)

---

### Requirement: Knowledge Graph Name Validation — COVERED

**Code:** `management/domain/aggregates/knowledge_graph.py::_validate_name()`
**Pydantic model:** `CreateKnowledgeGraphRequest` with `min_length=1, max_length=100`

**Scenario: Valid name** — COVERED
- `test_create_accepts_name_exactly_100_chars`
- `test_create_accepts_single_char_name`

**Scenario: Empty or oversized name** — COVERED
- `test_create_rejects_empty_name`
- `test_create_rejects_name_over_100_chars`
- `test_create_knowledge_graph_requires_name` (route → 422)

---

### Requirement: Knowledge Graph Retrieval — COVERED

**Code:** `management/application/services/knowledge_graph_service.py::get()`
**Route:** `GET /management/knowledge-graphs/{kg_id}`

**Scenario: Authorized retrieval** — COVERED
- `test_get_returns_aggregate_on_success`
- `test_get_knowledge_graph_returns_200`

**Scenario: Unauthorized or non-existent** — COVERED (no existence leakage)
- `test_get_returns_none_when_not_found` → 404
- `test_get_returns_none_when_permission_denied` → 404
- `test_get_returns_none_for_different_tenant` → 404
- `test_get_knowledge_graph_returns_404_when_not_found`

---

### Requirement: Knowledge Graph Listing — COVERED

**Code:** `management/application/services/knowledge_graph_service.py::list_all()` and
`list_for_workspace()`
**Route:** `GET /management/knowledge-graphs` (calls `list_all`)

**Scenario: List for workspace** — COVERED
- `test_list_uses_read_relationships_to_discover_kgs`
- `test_list_filters_by_tenant`
- `test_list_knowledge_graphs_returns_200` (route)

---

### Requirement: Knowledge Graph Update — PARTIAL ← FAIL

**Code:** `management/application/services/knowledge_graph_service.py::update()` exists
and is fully tested at the service layer.

**MISSING: HTTP PATCH route.** The file
`management/presentation/knowledge_graphs/routes.py` contains only **3 endpoints**
(GET list, GET by ID, POST create). There is no `@router.patch` or `@router.put`
endpoint for updating a knowledge graph. There is also no `UpdateKnowledgeGraphRequest`
Pydantic model.

**MISSING: Route-level tests.** `tests/unit/management/presentation/test_knowledge_graphs_routes.py`
contains only `TestListKnowledgeGraphsRoute`, `TestGetKnowledgeGraphRoute`, and
`TestCreateKnowledgeGraphRoute`. There is no `TestUpdateKnowledgeGraphRoute`.

The spec states: "The system SHALL allow users with `edit` permission to **update**
knowledge graph metadata." Without an HTTP endpoint, this operation is unreachable
by API consumers. Service-level coverage is insufficient to satisfy the SHALL.

**What is needed:**
1. Add `PATCH /management/knowledge-graphs/{kg_id}` route in `routes.py`
2. Add `UpdateKnowledgeGraphRequest` Pydantic model (name, description fields)
3. Add `TestUpdateKnowledgeGraphRoute` tests: 200 success, 403 unauthorized,
   409 duplicate, 422 validation error, 404 not found

---

### Requirement: Knowledge Graph Deletion — PARTIAL ← FAIL

**Code:** `management/application/services/knowledge_graph_service.py::delete()` exists
and is tested at the service layer. The outbox translator
`_translate_knowledge_graph_deleted()` correctly cleans up workspace, tenant, admin,
editor, and viewer SpiceDB relationships (verified by 5 translator tests).

**MISSING: HTTP DELETE route.** `management/presentation/knowledge_graphs/routes.py`
has no `@router.delete` endpoint. Users cannot invoke deletion through the API.

**MISSING: Route-level tests.** No `TestDeleteKnowledgeGraphRoute` class exists in
the route test file.

**MISSING: Atomicity test.** The spec requires: "if any step fails, the entire
deletion rolls back with no partial state." The service wraps deletion in
`async with self._session.begin()` (correct implementation), but there is NO test
that exercises the rollback path — e.g., a test where DS deletion raises an exception
and asserts the KG was NOT deleted. The previous worker result incorrectly claimed
`test_delete_rolls_back_on_ds_deletion_failure` exists; it does not appear anywhere
in the test suite (`grep` confirms zero matches).

**Scenario: Successful deletion** — PARTIAL
- `test_delete_cascades_data_sources` ✓ (service; verifies DS marked and deleted)
- Route: MISSING
- Atomicity: NOT TESTED

**Scenario: Mutation after deletion** — COVERED
- `test_update_raises_after_deletion` verifies `AggregateDeletedError` on `kg.update()`
  after `mark_for_deletion()` (aggregate level, which is correct)

**What is needed:**
1. Add `DELETE /management/knowledge-graphs/{kg_id}` route in `routes.py`
2. Add `TestDeleteKnowledgeGraphRoute` tests: 204 success, 403 unauthorized, 404 not found
3. Add atomicity test (integration or unit with real transaction semantics):
   - Given: DS repository raises exception during `delete()`
   - When: `service.delete()` is called
   - Then: The KG is NOT deleted (full rollback)

---

### Requirement: Permission Inheritance — COVERED

**Code:** SpiceDB schema (`shared_kernel/authorization/spicedb/schema.zed`) defines
`knowledge_graph` with `workspace->view`, `workspace->edit`, `workspace->manage`
computed permissions. ✓

**Scenario: Workspace-inherited access** — COVERED
- `test_workspace_editor_can_view_knowledge_graph` ✓
- `test_workspace_editor_can_edit_knowledge_graph` ✓
- `test_workspace_admin_can_manage_knowledge_graph` ✓
(All in `tests/integration/management/test_knowledge_graph_authorization.py`)

**Scenario: Direct grant** — COVERED
- `test_direct_kg_admin_has_manage_permission` ✓
- `test_direct_kg_admin_has_edit_permission` ✓
- `test_direct_kg_admin_has_view_permission` ✓

---

### Summary

| Requirement                        | Status  | Blocker                                          |
|------------------------------------|---------|--------------------------------------------------|
| Knowledge Graph Creation           | COVERED | —                                                |
| Knowledge Graph Name Validation    | COVERED | —                                                |
| Knowledge Graph Retrieval          | COVERED | —                                                |
| Knowledge Graph Listing            | COVERED | —                                                |
| Knowledge Graph Update             | PARTIAL | No PATCH HTTP route; no route tests              |
| Knowledge Graph Deletion           | PARTIAL | No DELETE HTTP route; no route tests; no atomicity test |
| Permission Inheritance             | COVERED | —                                                |

**Verdict: FAIL** — Two SHALL requirements lack HTTP endpoint implementation and
corresponding tests. The service layer is correct but unreachable via the API.