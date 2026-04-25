---
id: task-035
title: Add workspace-scoped listing, update, and delete routes for Knowledge Graphs
spec_ref: specs/management/knowledge-graphs.spec.md
status: not-started
phase: null
deps:
- task-008
round: 0
branch: null
pr: null
---

## Spec Gap

The `KnowledgeGraphService` already has `update()`, `delete()`, and
`list_for_workspace()` methods, but the presentation layer is missing
three HTTP routes:

- `GET /workspaces/{workspace_id}/knowledge-graphs` — list KGs scoped to a workspace
- `PATCH /knowledge-graphs/{kg_id}` — update name and/or description
- `DELETE /knowledge-graphs/{kg_id}` — delete with cascade (data sources + credentials + SpiceDB cleanup)

### Spec requirements covered

**Knowledge Graph Listing (workspace-scoped)**
- GIVEN a user with `view` permission on a workspace containing knowledge graphs
- WHEN the user lists knowledge graphs for that workspace
- THEN only knowledge graphs the user can view are returned
- (Requires `GET /workspaces/{workspace_id}/knowledge-graphs` route)

**Knowledge Graph Update**
- GIVEN a user with `edit` permission on a knowledge graph
- WHEN the user updates the name and description
- THEN the metadata is updated
- (Requires `PATCH /knowledge-graphs/{kg_id}` route)

**Knowledge Graph Deletion**
- GIVEN a user with `manage` permission on a knowledge graph
- WHEN the user deletes the knowledge graph
- THEN all data sources within it are deleted (including encrypted credentials), the
  knowledge graph record is deleted, and all authorization relationships are cleaned up —
  atomically within a single transaction
- AND if any step fails, the entire deletion rolls back with no partial state
- (Requires `DELETE /knowledge-graphs/{kg_id}` route; task-019 separately covers the
  credential cleanup cascade)

**Mutation after deletion**
- GIVEN a knowledge graph that has been marked for deletion
- WHEN any mutation is attempted
- THEN the operation is rejected
- (Requires `is_deleted` guard in the service, wired through the route)

## Implementation notes

- `list_for_workspace` in the service already handles authorization filtering via
  SpiceDB bulk permission check. The route must forward `workspace_id` and the
  current user's ID.
- The update route should return 409 on duplicate name, 403 on insufficient permission,
  and 404 when the KG cannot be viewed (information hiding).
- The delete route should emit domain events via the outbox so SpiceDB relationships
  are cleaned up asynchronously. The service's existing `delete()` method already
  marks the aggregate for deletion and persists via repository.
- task-019 specifically handles the credential cleanup cascade (encrypted credentials
  for data sources must be deleted). That task depends on task-009. The delete route
  here should still call `service.delete()` and let task-019 complete the cascade.
