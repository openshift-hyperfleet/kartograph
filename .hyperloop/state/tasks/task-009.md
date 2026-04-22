---
id: task-009
title: Implement Management REST API for Data Sources
spec_ref: specs/management/data-sources.spec.md
status: not-started
phase: null
deps: [task-008]
round: 0
branch: null
pr: null
---

## What

Add the presentation layer (FastAPI routes + Pydantic models) for the Data Sources resource. The application service (`DataSourceService`), domain, ports, infrastructure, and credential store are complete — only the HTTP interface is missing.

## Spec gaps (all HTTP scenarios unimplemented — no routes registered)

- `POST /knowledge-graphs/{kg_id}/data-sources` — create data source, encrypt credentials, default schedule MANUAL, check `edit` permission on KG, 201
- `GET /data-sources/{ds_id}` — retrieve, check `view` permission, 404 on unauthorized, no raw credentials returned
- `PATCH /data-sources/{ds_id}` — update name/connection config/credentials, check `edit` permission
- `DELETE /data-sources/{ds_id}` — delete credentials first, then data source, clean auth relationships, check `manage` permission
- `POST /data-sources/{ds_id}/sync` — trigger manual sync, create sync run record (status=pending), emit `SyncRequested` event, check `manage` permission

**Schedule configuration:**
- MANUAL: no value required
- CRON: cron expression value required
- INTERVAL: ISO 8601 duration value required
- Reject CRON/INTERVAL without value (422)

**Name validation:** reject empty or >100 character names (422)

**Immutability after deletion:** reject updates/sync on soft-deleted data sources (409)

**Sync run tracking:**
- `GET /data-sources/{ds_id}/sync-runs` — list sync runs (status, started_at, completed_at, error)

## Location

`management/presentation/data_sources/routes.py` and `models.py` — new presentation layer.

Register the router in `main.py`.

## Notes

- Credentials are never returned in GET responses — only metadata (name, prefix, created_at).
- Credential path format: `datasource/{id}/credentials` — managed by service, not settable by client.
- The `DataSourceService` handles all business logic including credential encryption.
