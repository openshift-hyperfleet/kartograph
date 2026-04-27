---
task_id: audit-specs/management/data-sources.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — specs/management/data-sources.spec.md

Auditor: spec-alignment-reviewer
Date: 2026-04-27
Spec commit: 85d49a379a52479b33f9b39994d76795066899a6

---

### Summary

The domain and application layers implement the spec thoroughly. However, the
**presentation layer (HTTP routes) is incomplete**: three operations described
by the spec are unreachable via the API because the corresponding endpoints
were never wired up. These are not minor gaps — they are externally visible
contractual obligations defined by the spec.

---

### GAP 1 — Missing `GET /data-sources/{ds_id}` endpoint (Requirement: Data Source Retrieval)

**Spec says:**
> GIVEN a data source the user has `view` permission on
> WHEN the user requests it by ID
> THEN the data source details are returned (without raw credentials)

**Code:**
- `DataSourceService.get()` exists and enforces VIEW permission and hides existence
  from unauthorized callers (`src/api/management/application/services/data_source_service.py`, lines 183–216).
- `src/api/management/presentation/data_sources/routes.py` exposes only:
  - `POST /knowledge-graphs/{kg_id}/data-sources` (create)
  - `GET  /knowledge-graphs/{kg_id}/data-sources` (list)
  - `POST /knowledge-graphs/{kg_id}/data-sources/{ds_id}/sync` (trigger sync)
  - `GET  /knowledge-graphs/{kg_id}/data-sources/{ds_id}/sync-runs` (list sync runs)
- No `GET /knowledge-graphs/{kg_id}/data-sources/{ds_id}` route exists.

**Impact:** Individual data source retrieval by ID is spec-required but impossible via the API.

---

### GAP 2 — Missing `PATCH /data-sources/{ds_id}` endpoint (Requirement: Data Source Update)

**Spec says:**
> GIVEN a user with `edit` permission on a data source
> WHEN the user updates the name, connection config, or raw credentials
> THEN the data source metadata is updated
> AND if raw credentials are provided, they are encrypted and stored at the system-managed path
> AND the credentials path is not directly settable by the client

**Code:**
- `DataSource.update_connection()` is fully implemented at the domain layer
  (`src/api/management/domain/aggregates/data_source.py`, lines 170–213).
- `DataSourceService.update()` is fully implemented
  (`src/api/management/application/services/data_source_service.py`, lines 266–341):
  validates EDIT permission, updates name/config, re-encrypts credentials, rejects
  client-supplied credentials_path.
- No HTTP PATCH or PUT route is wired up in
  `src/api/management/presentation/data_sources/routes.py`.

**Impact:** Data source update is spec-required but impossible via the API.

---

### GAP 3 — Missing `DELETE /data-sources/{ds_id}` endpoint (Requirement: Data Source Deletion)

**Spec says:**
> GIVEN a user with `manage` permission on a data source
> WHEN the user deletes the data source
> THEN the encrypted credentials are deleted first
> AND the data source is deleted
> AND authorization relationships are cleaned up

**Code:**
- `DataSourceService.delete()` is fully implemented
  (`src/api/management/application/services/data_source_service.py`, lines 343–396):
  checks MANAGE permission, deletes credentials first, calls `mark_for_deletion()`,
  persists deletion, emits `DataSourceDeleted` event for downstream auth cleanup.
- No HTTP DELETE route is wired up in
  `src/api/management/presentation/data_sources/routes.py`.

**Impact:** Data source deletion is spec-required but impossible via the API.

---

### Passing Requirements

The following spec requirements are correctly and fully implemented end-to-end:

| Requirement | Verdict | Notes |
|---|---|---|
| Data Source Creation | PASS | ULID, KB association, tenant scoping, MANUAL default, credential encryption at `datasource/{id}/credentials`, duplicate name rejection |
| Name Validation (1–100 chars) | PASS | Enforced at domain layer and Pydantic model |
| Schedule Configuration (MANUAL/CRON/INTERVAL) | PASS | Missing value for CRON/INTERVAL rejected with `InvalidScheduleError` |
| Immutability After Deletion | PASS | `AggregateDeletedError` raised on update and sync after `mark_for_deletion()` |
| Sync Triggering | PASS | POST route exists, creates pending sync run, emits `DataSourceSyncRequested` event |
| Sync Run Tracking | PASS | All four statuses, `started_at`, `completed_at`, `error_message`; CASCADE delete verified |
| Permission Inheritance | PASS | SpiceDB schema wires `data_source.{view,edit,manage}` ← `knowledge_graph.{view,edit,manage}`; integration tests verify full chain |