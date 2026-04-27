---
task_id: audit-specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — specs/management/knowledge-graphs.spec.md

Auditor: spec-alignment-reviewer
Date: 2026-04-27

---

### Summary

**Verdict: FAIL**

Three requirements from the spec are not reachable via the HTTP API. The service
layer implements all operations correctly, but the presentation layer
(`src/api/management/presentation/knowledge_graphs/routes.py`) only exposes three
endpoints — `GET /knowledge-graphs`, `GET /knowledge-graphs/{kg_id}`, and
`POST /workspaces/{workspace_id}/knowledge-graphs` — leaving update, delete, and
workspace-scoped listing with no HTTP surface.

---

### Gap 1 — Knowledge Graph Update (Requirement: Knowledge Graph Update)

**Spec:** "The system SHALL allow users with `edit` permission to update knowledge
graph metadata."

**Status: NOT EXPOSED via HTTP.**

`routes.py` (lines 1–163) contains no `PATCH` or `PUT` endpoint.
`KnowledgeGraphService.update()` (`knowledge_graph_service.py` lines 297–356) is
fully implemented and correct — it checks `EDIT` permission, validates the aggregate,
persists the change atomically inside `session.begin()`, and raises
`DuplicateKnowledgeGraphNameError` on name collision — but there is no route that
calls it. End users have no way to update a knowledge graph through the API.

---

### Gap 2 — Knowledge Graph Deletion (Requirement: Knowledge Graph Deletion)

**Spec:** "The system SHALL allow users with `manage` permission to delete a knowledge
graph, cascading to data sources."

**Status: NOT EXPOSED via HTTP.**

`routes.py` contains no `DELETE` endpoint.
`KnowledgeGraphService.delete()` (`knowledge_graph_service.py` lines 358–412) is
fully implemented — `MANAGE` permission check, cascade data-source deletion inside
one `session.begin()` transaction, outbox events for SpiceDB cleanup of workspace,
tenant, admin, editor, and viewer relations (see `translator.py` lines 160–211) —
but there is no route that calls it.

---

### Gap 3 — Knowledge Graph Listing scoped to a Workspace (Requirement: Knowledge Graph Listing)

**Spec:** "The system SHALL list knowledge graphs within a workspace, filtered by
authorization."
**Scenario:** "WHEN the user lists knowledge graphs for that workspace, THEN only
knowledge graphs the user can view are returned."

**Status: NOT EXPOSED via HTTP.**

The only list route is `GET /knowledge-graphs` (`routes.py` lines 28–59), which
calls `service.list_all()` — returning every KG in the tenant that the user can
VIEW, without workspace scoping. `KnowledgeGraphService.list_for_workspace()`
(`knowledge_graph_service.py` lines 199–264) exists and implements the correct
behaviour (VIEW check on workspace, SpiceDB relationship traversal to discover KG
IDs, tenant filter), but no HTTP route calls it. There is no
`GET /workspaces/{workspace_id}/knowledge-graphs` endpoint.

---

### Requirements verified as PASSING

| Requirement | Status | Key evidence |
|---|---|---|
| Creation with ULID, workspace/tenant association | PASS | `KnowledgeGraph.create()` domain aggregate; `KnowledgeGraphCreated` event written to outbox |
| Auth relationships established on creation | PASS | Outbox translator `_translate_knowledge_graph_created()` writes workspace + tenant relations to SpiceDB |
| Duplicate name within tenant rejected (409) | PASS | `uq_knowledge_graphs_tenant_name` DB constraint; `DuplicateKnowledgeGraphNameError` mapped to HTTP 409 |
| Name length validation (1–100 chars) | PASS | Domain `_validate_name()` + Pydantic `min_length=1, max_length=100` |
| Retrieval with VIEW permission, no existence leakage | PASS | Service returns `None` for not-found, tenant mismatch, and unauthorized; route always returns 404 |
| Permission inheritance via SpiceDB schema | PASS | `schema.zed`: `edit = admin + editor + workspace->edit`; `manage = admin + workspace->manage` |
| Direct admin grant gives manage/edit/view | PASS | Same schema; admin appears in all three permission expressions |
| Mutation-after-deletion guard | PASS | `AggregateDeletedError` raised in domain `update()` when `_deleted` is True |
| Cascade delete correctness (when called) | PASS | Data sources deleted + KG deleted in one transaction; SpiceDB cleanup of all relation types via outbox translator |