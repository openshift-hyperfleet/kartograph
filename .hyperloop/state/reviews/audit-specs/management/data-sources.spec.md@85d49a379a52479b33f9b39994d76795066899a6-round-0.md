---
task_id: audit-specs/management/data-sources.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — specs/management/data-sources.spec.md

Auditor: spec-alignment
Date: 2026-04-27
Spec commit: 85d49a379a52479b33f9b39994d76795066899a6

---

### Summary

**FAIL — 3 critical gaps, 1 minor gap**

The domain and application layers are well-implemented and correctly model all
spec behaviors. However, three spec requirements that require HTTP endpoints have
no corresponding HTTP routes in the presentation layer. The service methods exist
and are tested, but are unreachable by API clients.

---

### Requirement 1: Data Source Creation — PASS

- ULID ID generation via `DataSourceId.generate()` ✓ (`data_source.py:137`)
- KG and tenant association enforced ✓ (`data_source_service.py:154-161`)
- Schedule defaults to MANUAL ✓ (`data_source.py:144`)
- Credentials encrypted and stored at `datasource/{id}/credentials` ✓ (`data_source_service.py:163-170`)
- Only path stored, not raw credentials ✓
- Duplicate name rejected via `uq_data_sources_kg_name` constraint ✓ (`data_source_repository.py:108-115`)
- EDIT permission on KG verified ✓ (`data_source_service.py:129-144`)
- HTTP endpoint: POST `/knowledge-graphs/{kg_id}/data-sources` ✓ (`routes.py:72`)

**Minor gap:** `DuplicateDataSourceNameError` is raised by the repository but is
not caught in the HTTP route handler (`routes.py:129-132`). It falls through to
the generic `except Exception` clause and returns HTTP 500 instead of a meaningful
error (e.g., 409 Conflict). The spec says the request "is rejected with a duplicate
name error" — the current behavior rejects it, but as an opaque server error.

---

### Requirement 2: Data Source Name Validation — PASS

- Domain-level: `_validate_name()` enforces 1–100 chars ✓ (`data_source.py:90-102`)
- Request-level: Pydantic `min_length=1, max_length=100` ✓ (`models.py:16-20`)

---

### Requirement 3: Schedule Configuration — PASS

- Three types (MANUAL, CRON, INTERVAL) defined ✓ (`value_objects.py:85-93`)
- MANUAL: no value required ✓ (`value_objects.py:122-127`)
- CRON/INTERVAL: value required, rejected if missing ✓ (`value_objects.py:117-121`)

---

### Requirement 4: Data Source Retrieval — FAIL (missing HTTP endpoint)

**Gap:** The spec states: "WHEN the user requests it by ID, THEN the data source
details are returned." The service method `DataSourceService.get()` is correctly
implemented with VIEW permission enforcement and no-distinction between unauthorized
and not-found (`data_source_service.py:183-216`). However, **there is no HTTP GET
endpoint for a single data source by ID** (`GET /data-sources/{ds_id}`).

The only retrieval endpoint is the list endpoint
(`GET /knowledge-graphs/{kg_id}/data-sources`) at `routes.py:28`. The `service.get()`
is called internally by the sync-runs list endpoint for authorization, but it is
not exposed as a standalone resource endpoint.

---

### Requirement 5: Data Source Update — FAIL (missing HTTP endpoint)

**Gap:** The service method `DataSourceService.update()` is fully implemented
(`data_source_service.py:266-341`) and correctly:
- Verifies EDIT permission on the data source ✓
- Updates name and connection config ✓
- Encrypts and stores new credentials at the system-managed path ✓
- Does not allow the client to set `credentials_path` directly ✓
- Delegates to `DataSource.update_connection()` which enforces immutability
  (raises `AggregateDeletedError` if `_deleted=True`) ✓

However, **there is no HTTP PUT or PATCH endpoint** for updating a data source.
The entire update capability exists only at the service layer and is unreachable
by API clients. This is a complete spec requirement that is unimplemented at the
presentation layer.

---

### Requirement 6: Immutability After Deletion — PASS

- `DataSource._deleted` flag set by `mark_for_deletion()` ✓ (`data_source.py:256-285`)
- `update_connection()` raises `AggregateDeletedError` if `_deleted=True` ✓ (`data_source.py:190-191`)
- `request_sync()` raises `AggregateDeletedError` if `_deleted=True` ✓ (`data_source.py:226-227`)

Note: The implementation uses hard deletion (physical row removal). After deletion,
the SpiceDB relationships are cleaned up asynchronously via the outbox, so a
subsequent update/sync request will first get 403 (unauthorized) due to missing
authz relationships, or 404 if the race resolves after the DB delete. The in-flight
`_deleted` guard protects against mutations within the same request lifecycle.

---

### Requirement 7: Data Source Deletion — FAIL (missing HTTP endpoint)

**Gap:** The service method `DataSourceService.delete()` is fully implemented
(`data_source_service.py:343-396`) and correctly:
- Verifies MANAGE permission ✓
- Deletes encrypted credentials first ✓ (`data_source_service.py:385-389`)
- Calls `mark_for_deletion()` on the aggregate ✓ (`data_source_service.py:391`)
- Hard-deletes the record from PostgreSQL ✓
- Emits `DataSourceDeleted` event via outbox → translator deletes SpiceDB relationships ✓
  (`translator.py:255-283`)

However, **there is no HTTP DELETE endpoint** for a data source. The delete
capability exists only at the service layer and is unreachable by API clients.

---

### Requirement 8: Sync Triggering — PASS

- MANAGE permission verified ✓ (`data_source_service.py:416-431`)
- Sync run created with status "pending" ✓ (`data_source_service.py:443-451`)
- `DataSourceSyncRequested` event emitted ✓ (`data_source.py:228-236`)
- HTTP endpoint: POST `/data-sources/{ds_id}/sync` ✓ (`routes.py:136`)

---

### Requirement 9: Sync Run Tracking — PASS

- Status field with pending/running/completed/failed ✓ (DB CHECK constraint)
- `started_at`, `completed_at`, `error` fields present ✓
- Cascade deletion via `ondelete="CASCADE"` foreign key ✓

---

### Requirement 10: Permission Inheritance — PASS

SpiceDB schema correctly defines fully inherited permissions:
```
data_source.view   = knowledge_graph->view   (schema.zed:146)
data_source.edit   = knowledge_graph->edit   (schema.zed:149)
data_source.manage = knowledge_graph->manage (schema.zed:152)
```
No direct user/group relations on `data_source` — all access is through the parent KG.
Integration tests verify inheritance chain (`test_data_source_authorization.py`).

---

### Files Examined

- `src/api/management/presentation/data_sources/routes.py` — **4 endpoints only; missing GET by ID, PUT/PATCH, DELETE**
- `src/api/management/application/services/data_source_service.py` — all 5 CRUD + trigger_sync methods implemented
- `src/api/management/domain/aggregates/data_source.py` — aggregate correctly models all business rules
- `src/api/management/domain/value_objects.py` — Schedule validation correct
- `src/api/management/infrastructure/repositories/data_source_repository.py` — hard delete, outbox events
- `src/api/management/infrastructure/outbox/translator.py` — SpiceDB cleanup on delete ✓
- `src/api/shared_kernel/authorization/spicedb/schema.zed` — permission inheritance correct