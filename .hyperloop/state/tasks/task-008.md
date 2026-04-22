---
id: task-008
title: Implement Management REST API for Knowledge Graphs
spec_ref: specs/management/knowledge-graphs.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

Add the presentation layer (FastAPI routes + Pydantic models) for the Knowledge Graphs bounded context resource. The application service (`KnowledgeGraphService`), domain, ports, and infrastructure layers are complete — only the HTTP interface is missing.

## Spec gaps (all HTTP scenarios unimplemented — no routes registered in main.py)

- `POST /workspaces/{workspace_id}/knowledge-graphs` — create KG, check `edit` permission on workspace, return 201
- `GET /knowledge-graphs/{kg_id}` — retrieve by ID, check `view` permission, 404 on unauthorized (information hiding)
- `GET /workspaces/{workspace_id}/knowledge-graphs` — list KGs in workspace, filter by `view` permission
- `PATCH /knowledge-graphs/{kg_id}` — update name/description, check `edit` permission
- `DELETE /knowledge-graphs/{kg_id}` — cascade delete (data sources + credentials + auth relationships), check `manage` permission, atomic transaction

**Name validation:**
- Reject empty or >100 character names with 422

**Authorization scenarios from authorization.spec.md:**
- Workspace-inherited access: `edit` on workspace → `edit` on all KGs in that workspace
- Direct grant: `admin` on KG → `manage`, `edit`, `view`

## Location

`management/presentation/knowledge_graphs/routes.py` and `models.py` — new presentation layer following the IAM pattern (`iam/presentation/tenants/`).

Register the router in `main.py` alongside `iam_router`.

## Notes

- The `KnowledgeGraphService` already handles all business logic including cascading deletion.
- Use the SpiceDB authorization provider for permission checks (already wired in `infrastructure/authorization_dependencies.py`).
- Authorization must use information-hiding: unauthorized → 404, not 403.
