---
task_id: audit-specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Worker Result — Spec Alignment Audit
## Spec: specs/management/knowledge-graphs.spec.md

Auditor: alignment-auditor
Date: 2026-04-27

---

### Verdict: FAIL

Three critical gaps exist between the spec and the current implementation. The domain model
and service layer are largely well-implemented, but the API surface is incomplete.

---

### Gap 1 — MISSING: Knowledge Graph Update HTTP Endpoint (CRITICAL)

**Spec requirement:** "The system SHALL allow users with `edit` permission to update knowledge
graph metadata (name and description)."

**Finding:** No HTTP route exists for updating a knowledge graph.

- `src/api/management/presentation/knowledge_graphs/routes.py` — only defines `GET /knowledge-graphs`,
  `GET /knowledge-graphs/{kg_id}`, and `POST /workspaces/{workspace_id}/knowledge-graphs`.
  There is no `PATCH` or `PUT` endpoint.
- `src/api/management/presentation/knowledge_graphs/models.py` — no `UpdateKnowledgeGraphRequest`
  model exists.
- The **service layer implementation is complete**: `KnowledgeGraphService.update()` exists and
  correctly checks EDIT permission, validates name, rejects duplicates, and emits
  `KnowledgeGraphUpdated`. The gap is purely in the presentation layer.

---

### Gap 2 — MISSING: Knowledge Graph Delete HTTP Endpoint (CRITICAL)

**Spec requirement:** "The system SHALL allow users with `manage` permission to delete a
knowledge graph, cascading to data sources."

**Finding:** No HTTP route exists for deleting a knowledge graph.

- `src/api/management/presentation/knowledge_graphs/routes.py` — no `DELETE` endpoint defined.
- The **service layer implementation exists**: `KnowledgeGraphService.delete()` checks MANAGE
  permission, cascades to data sources within a transaction, marks the aggregate for deletion
  (protecting against post-deletion mutations), and emits `KnowledgeGraphDeleted` for SpiceDB
  cleanup. The gap is purely in the presentation layer.

---

### Gap 3 — INCORRECT: List Endpoint Does Not Filter By Workspace (CRITICAL)

**Spec requirement:** "The system SHALL list knowledge graphs **within a workspace**, filtered
by authorization."

**Finding:** The `GET /management/knowledge-graphs` endpoint lists ALL knowledge graphs within
the tenant, not filtered to a specific workspace.

- `src/api/management/presentation/knowledge_graphs/routes.py` lines 28–59: calls
  `service.list_all()` which returns all tenant-scoped KGs filtered by VIEW permission.
- The spec explicitly requires workspace-scoped listing. The service has a `list_for_workspace()`
  method that correctly takes a `workspace_id`, verifies VIEW on the workspace, and returns only
  KGs linked to that workspace via SpiceDB — but this method is **not wired to any HTTP route**.
- The correct endpoint shape (matching the creation route) would be
  `GET /management/workspaces/{workspace_id}/knowledge-graphs` calling `list_for_workspace()`.

---

### Gap 4 — CONCERN: Cascading Credential Deletion Not Verified (MINOR)

**Spec requirement:** "All data sources within it are deleted **(including their encrypted
credentials)**."

**Finding:** The KG deletion cascade (`KnowledgeGraphService.delete()`) calls
`DataSourceRepository.delete()` for each child data source, but it is not verifiable from
the service code alone that this method also deletes the Vault-stored encrypted credentials.
If `DataSourceRepository.delete()` only removes the database row and does not call the
credential backend, the spec requirement for credential cleanup is silently violated.

This should be verified at the repository and integration-test level.

---

### Items That ARE Correctly Implemented

- **Creation**: ULID generation, workspace/tenant association, SpiceDB relationship creation,
  duplicate-name rejection via `(tenant_id, name)` unique constraint — all correct.
- **Name validation**: 1–100 character constraint enforced at both domain layer
  (`KnowledgeGraph._validate_name()`) and Pydantic layer (`CreateKnowledgeGraphRequest`).
- **Retrieval**: `get()` returns `None` for unauthorized AND missing KGs with no distinction,
  correctly mapping to HTTP 404 at the API layer.
- **Mutation-after-deletion guard**: Aggregate raises `AggregateDeletedError` on update/delete
  when `self._deleted` is True.
- **Permission inheritance in SpiceDB schema**: `schema.zed` correctly defines
  `view = admin + editor + viewer + workspace->view`,
  `edit = admin + editor + workspace->edit`,
  `manage = admin + workspace->manage` — matching both spec scenarios.
- **SpiceDB cleanup on deletion**: `ManagementEventTranslator._translate_knowledge_graph_deleted()`
  removes workspace relationship, tenant relationship, and all direct grants (admin, editor,
  viewer) via filter operations.
- **Atomic transaction on deletion**: DB operations are wrapped in `async with self._session.begin()`.