---
id: task-002
title: "Management — Data Source REST routes"
spec_ref: specs/management/data-sources.spec.md
status: not-started
phase: null
deps: [task-001]
round: 0
branch: null
pr: null
---

## Summary

The Management context's domain aggregates (`DataSource`, `DataSourceSyncRun`), application services (`DataSourceService`), infrastructure repositories (`DataSourceRepository`, `DataSourceSyncRunRepository`, `FernetSecretStore`), and FastAPI dependency file (`management/dependencies/data_source.py`) are all implemented. What is missing is the **presentation layer** — FastAPI routes exposed under `/management`.

This task depends on `task-001` because data source creation is nested under knowledge graphs per API conventions (`POST /management/knowledge-graphs/{id}/data-sources`).

## Scope

Add to `src/api/management/presentation/`:

- `data_sources/`
  - `__init__.py`
  - `models.py` — Pydantic request/response models (including schedule config, credential fields)
  - `routes.py` — FastAPI router

### Endpoints to implement

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/management/knowledge-graphs/{kg_id}/data-sources` | Create (scoped to parent KG) |
| `GET` | `/management/knowledge-graphs/{kg_id}/data-sources` | List within KG |
| `GET` | `/management/data-sources/{id}` | Get by ID |
| `PATCH` | `/management/data-sources/{id}` | Update (name, connection config, credentials) |
| `DELETE` | `/management/data-sources/{id}` | Delete (credentials → DS → SpiceDB) |
| `POST` | `/management/data-sources/{id}/sync` | Trigger sync |

### Authorization checks

- Create / List in KG: `edit` permission on the parent knowledge graph
- Get: `view` permission (return 404 if denied)
- Update: `edit` permission on the DS
- Delete: `manage` permission on the DS
- Trigger sync: `manage` permission on the DS

### Business rules

- Name: 1–100 characters; unique within knowledge graph (`409 Conflict` on duplicate)
- Schedule types: `MANUAL` (no value), `CRON` (cron expression), `INTERVAL` (ISO 8601 duration); reject CRON/INTERVAL without a value
- Creation with credentials: encrypt via `FernetSecretStore`, store at `datasource/{id}/credentials`; response NEVER includes raw credentials
- Update with credentials: re-encrypt and overwrite at the system-managed path; client cannot set `credentials_path` directly
- Trigger sync: create sync run record with status `pending`, emit sync-requested outbox event
- Reject mutations on a DS marked for deletion (`409 Conflict`)
- Cascade deletion: encrypted credentials deleted before DS record

### Sync Run sub-resource (read-only, no separate routes needed)

Sync run status is returned as part of the data source response (last sync run metadata: status, started_at, completed_at, error).

## TDD Notes

Write integration tests first under `tests/integration/management/test_data_source_routes.py`. Mock the secret store (or use a real Fernet key in test config).

Write unit tests for schedule validation and credential path logic under `tests/unit/management/`.
