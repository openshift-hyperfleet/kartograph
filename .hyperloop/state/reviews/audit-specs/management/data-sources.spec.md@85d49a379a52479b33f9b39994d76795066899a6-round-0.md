---
task_id: audit-specs/management/data-sources.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Audit Result — specs/management/data-sources.spec.md

### Summary

The domain layer, application service layer, authorization model, credential
encryption, and sync run tracking are all correctly and thoroughly implemented.
However, **three HTTP endpoints required by the spec are absent** from the
presentation layer (`src/api/management/presentation/data_sources/routes.py`),
making the corresponding operations inaccessible to API clients.

---

### GAPS

#### GAP 1 — Requirement: Data Source Retrieval — Missing HTTP Endpoint

**Spec:** "The system SHALL return data source details only to users with `view`
permission" when requested by ID. Not-found and unauthorized responses MUST be
indistinguishable.

**Implementation:** `DataSourceService.get()` is fully implemented
(`data_source_service.py` lines 183–216). It checks VIEW permission and returns
`None` for both "not found" and "unauthorized" cases (satisfying the ambiguity
requirement). It is already called internally by the `list_sync_runs` route for
authorization. However, **no `GET /data-sources/{ds_id}` endpoint is wired** in
`routes.py`. The file contains only four routes: list (GET /kg/{id}/data-sources),
create (POST /kg/{id}/data-sources), trigger sync (POST /data-sources/{id}/sync),
list sync runs (GET /data-sources/{id}/sync-runs).

#### GAP 2 — Requirement: Data Source Update — Missing HTTP Endpoint

**Spec:** "The system SHALL allow users with `edit` permission to update data
source connection configuration" (name, connection config, raw credentials). The
credentials path MUST NOT be directly settable by the client.

**Implementation:** `DataSourceService.update()` is fully implemented
(`data_source_service.py` lines 266–341). It enforces EDIT permission, re-encrypts
credentials at `datasource/{id}/credentials`, and the service API accepts only
`raw_credentials` (not `credentials_path`), satisfying the immutability constraint.
However, **no `PUT` or `PATCH /data-sources/{ds_id}` endpoint is wired** in
`routes.py`. Additionally, no `UpdateDataSourceRequest` Pydantic model is defined
in `presentation/data_sources/models.py` (only `CreateDataSourceRequest` and
response models exist).

#### GAP 3 — Requirement: Data Source Deletion — Missing HTTP Endpoint

**Spec:** "The system SHALL allow users with `manage` permission to delete a data
source." The encrypted credentials MUST be deleted first, then the data source, and
authorization relationships MUST be cleaned up.

**Implementation:** `DataSourceService.delete()` is fully implemented
(`data_source_service.py` lines 343–396). It enforces MANAGE permission, calls
`secret_store.delete()` before `repo.delete()` (correct ordering), and emits
`DataSourceDeleted` event for SpiceDB relationship cleanup via the outbox.
`DataSourceSyncRun` rows are cascade-deleted by the FK `ondelete="CASCADE"`
(`infrastructure/models/data_source_sync_run.py` line 41). However, **no
`DELETE /data-sources/{ds_id}` endpoint is wired** in `routes.py`.

---

### VERIFIED CORRECT

The following spec requirements are correctly implemented end-to-end:

- **ULID identifiers** on creation (`DataSourceId.generate()` in `domain/value_objects.py`)
- **Tenant association** (all service operations scoped by `tenant_id`)
- **Default schedule MANUAL** (`data_source.py` line 144, no explicit schedule needed at creation)
- **Credential encryption** at path `datasource/{id}/credentials`
  (`fernet_secret_store.py` + `data_source_service.py` lines 163–170 and 326–332)
- **Client cannot set `credentials_path`** — service accepts only `raw_credentials`; path is server-computed
- **Duplicate name rejection** within knowledge graph (unique index on `(knowledge_graph_id, name)` +
  `DuplicateDataSourceNameError` in `data_source_repository.py` lines 107–115)
- **Name validation 1–100 chars** (domain `_validate_name()` + Pydantic `min_length=1, max_length=100`
  on `CreateDataSourceRequest.name`)
- **Schedule validation**: CRON/INTERVAL require non-empty value; MANUAL requires no value
  (`domain/value_objects.py` `Schedule.__post_init__()` lines 115–127)
- **Permission inheritance**: `data_source.view/edit/manage` fully derived from parent KG in SpiceDB
  schema (`schema.zed`: `permission view = knowledge_graph->view`, etc.)
- **Immutability after deletion**: `update_connection()`, `request_sync()`, `record_sync_completed()`
  all check `self._deleted` and raise `AggregateDeletedError`
- **Sync run created with status "pending"** (`data_source_service.py` lines 443–451)
- **`DataSourceSyncRequested` event emitted** on sync trigger (outbox pattern)
- **Sync run fields**: `status`, `started_at`, `completed_at`, `error`
  (`domain/entities/data_source_sync_run.py` lines 10–26)
- **Cascade deletion of sync runs** via `ondelete="CASCADE"` FK
- **Authorization relationship cleanup** via `DataSourceDeleted` event → outbox → SpiceDB consumer