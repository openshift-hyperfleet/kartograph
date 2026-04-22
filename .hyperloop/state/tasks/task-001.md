---
id: task-001
title: "Management — Knowledge Graph REST routes"
spec_ref: specs/management/knowledge-graphs.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Summary

The Management context's domain aggregates (`KnowledgeGraph`), application services (`KnowledgeGraphService`), and infrastructure repositories (`KnowledgeGraphRepository`) are fully implemented. The `management/dependencies/knowledge_graph.py` FastAPI dependency file also exists. What is missing is the **presentation layer** — FastAPI routes exposed under `/management/knowledge-graphs`.

## Scope

Implement `src/api/management/presentation/` with:

- `src/api/management/presentation/__init__.py`
- `src/api/management/presentation/knowledge_graphs/`
  - `__init__.py`
  - `models.py` — Pydantic request/response models
  - `routes.py` — FastAPI router

### Endpoints to implement (per `specs/nfr/api-conventions.spec.md`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/management/workspaces/{workspace_id}/knowledge-graphs` | Create (scoped to parent workspace) |
| `GET` | `/management/workspaces/{workspace_id}/knowledge-graphs` | List within workspace |
| `GET` | `/management/knowledge-graphs/{id}` | Get by ID |
| `PATCH` | `/management/knowledge-graphs/{id}` | Update name/description |
| `DELETE` | `/management/knowledge-graphs/{id}` | Delete (cascade data sources + credentials + SpiceDB) |

### Authorization checks (per spec)

- Create: `edit` permission on the parent workspace
- List: filter by `view` permission via SpiceDB bulk lookup
- Get: `view` permission on the KG (return 404 if denied — no distinction)
- Update: `edit` permission on the KG
- Delete: `manage` permission on the KG

### Business rules

- Name: 1–100 characters; unique within tenant (reject duplicate with `409 Conflict`)
- Delete cascades atomically: all data sources → their credentials → KG record → SpiceDB relationships
- Reject mutations on a KG marked for deletion with a `409 Conflict`

### Wiring

Mount the router in `src/api/main.py` under the `/management` prefix.

## TDD Notes

Write integration tests first under `tests/integration/management/test_knowledge_graph_routes.py`. Tests require a running Postgres + SpiceDB instance.

Write unit tests for Pydantic model validation under `tests/unit/management/test_knowledge_graph_models.py`.
