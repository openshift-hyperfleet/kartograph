---
task_id: audit-specs/management/data-sources.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Worker Result — Spec Alignment Audit: specs/management/data-sources.spec.md

Auditor: spec-alignment-reviewer
Date: 2026-04-27
Spec commit: 85d49a379a52479b33f9b39994d76795066899a6

---

### Overall Verdict: FAIL

The domain layer, application service layer, and infrastructure layer faithfully implement
the spec's business logic. However, the **presentation layer (HTTP API) is materially
incomplete**: three required endpoints are missing, schedule configuration is not exposed
through the API, and the duplicate-name error is not translated to the correct HTTP
response. These are not cosmetic gaps — users cannot exercise the spec's requirements
through the public API.

---

### Gap 1 — CRITICAL: Missing GET /data-sources/{ds_id} endpoint

**Spec requirement:** "Data Source Retrieval — The system SHALL return data source details
only to users with `view` permission."

**Status:** The service method `DataSourceService.get()` exists and correctly implements
the logic (checks VIEW permission, returns None for unauthorized/missing without leaking
existence). However, **no HTTP route exists** to call it.

- File with gap: `src/api/management/presentation/data_sources/routes.py`
  (no `GET /{data_source_id}` route is registered)
- Service method present: `src/api/management/application/services/data_source_service.py`
  (`DataSourceService.get()`)
- Route tests absent: `src/api/tests/unit/management/presentation/test_data_sources_routes.py`

Users cannot retrieve a single data source by ID.

---

### Gap 2 — CRITICAL: Missing PUT/PATCH /data-sources/{ds_id} endpoint

**Spec requirement:** "Data Source Update — The system SHALL allow users with `edit`
permission to update data source connection configuration."

**Status:** The service method `DataSourceService.update()` exists and correctly handles
name/config/credentials updates, permission enforcement, credential re-encryption, and
immutability-after-deletion. However, **no HTTP route exists** to call it.

- File with gap: `src/api/management/presentation/data_sources/routes.py`
  (no `PUT /{data_source_id}` or `PATCH /{data_source_id}` route is registered)
- Service method present: `src/api/management/application/services/data_source_service.py`
  (`DataSourceService.update()`)
- Route tests absent: `src/api/tests/unit/management/presentation/test_data_sources_routes.py`

Users cannot update a data source via the API.

---

### Gap 3 — CRITICAL: Missing DELETE /data-sources/{ds_id} endpoint

**Spec requirement:** "Data Source Deletion — The system SHALL allow users with `manage`
permission to delete a data source."

**Status:** The service method `DataSourceService.delete()` exists and correctly enforces
MANAGE permission, deletes credentials first, marks the aggregate for deletion, and
triggers auth-relationship cleanup. However, **no HTTP route exists** to call it.

- File with gap: `src/api/management/presentation/data_sources/routes.py`
  (no `DELETE /{data_source_id}` route is registered)
- Service method present: `src/api/management/application/services/data_source_service.py`
  (`DataSourceService.delete()`)
- Route tests absent: `src/api/tests/unit/management/presentation/test_data_sources_routes.py`

Users cannot delete a data source via the API.

---

### Gap 4 — CRITICAL: Schedule configuration not exposed through the API

**Spec requirement:** "Schedule Configuration — The system SHALL support three schedule
types: MANUAL, CRON (with cron expression), and INTERVAL (with ISO 8601 duration)."

**Status:** The domain value object `Schedule` / `ScheduleType` fully implements all
three types, including validation that CRON and INTERVAL require a non-empty value. The
service `create()` method accepts a schedule argument. However, **the API request model
has no schedule field**, so callers can never specify CRON or INTERVAL schedules.

- File with gap: `src/api/management/presentation/data_sources/models.py`
  — `CreateDataSourceRequest` lacks a `schedule` field
- File with gap: `src/api/management/presentation/data_sources/routes.py`
  — `create_data_source()` does not forward schedule configuration to the service
- Domain implementation present: `src/api/management/domain/value_objects.py`
  (`ScheduleType.CRON`, `ScheduleType.INTERVAL`, `Schedule._validate()`)
- Effect: All data sources are permanently MANUAL regardless of what the client intends.
  The "Missing schedule value" validation scenario (CRON/INTERVAL without value → error)
  is also unreachable via the API.

---

### Gap 5 — MAJOR: DuplicateDataSourceNameError not translated to 409 in routes

**Spec requirement:** "Duplicate name within knowledge graph — the request is rejected
with a duplicate name error."

**Status:** The repository correctly raises `DuplicateDataSourceNameError` when the
uniqueness constraint (`uq_data_sources_kg_name`) is violated. However, the routes layer
does **not** import or catch this exception. It falls through to a generic `except
Exception` handler that returns HTTP 500.

- File with gap: `src/api/management/presentation/data_sources/routes.py`
  — `create_data_source()` imports only `UnauthorizedError`; `DuplicateDataSourceNameError`
  is not caught; the caller receives 500 instead of 409 Conflict.
- Exception defined: `src/api/management/domain/exceptions.py` (`DuplicateDataSourceNameError`)
- Exception raised: `src/api/management/infrastructure/repositories/data_source_repository.py`
  (lines ~107–115)
- Missing test: `src/api/tests/unit/management/presentation/test_data_sources_routes.py`
  has no test case for the duplicate-name HTTP response.

---

### What IS Correctly Implemented

The following areas are fully implemented and align with the spec:

- **Domain aggregate** (`data_source.py`): ULID generation, KG/tenant association,
  MANUAL default, credential-path storage, immutability-after-deletion guard on all
  mutation methods (`update_connection`, `request_sync`, `record_sync_completed`).
- **Credential encryption path**: `datasource/{id}/credentials` — service encrypts
  and stores; only the path reference is persisted in the aggregate.
- **Name validation**: 1–100 characters enforced at both Pydantic (request layer) and
  domain layer.
- **Sync triggering endpoint**: `POST /{data_source_id}/sync` exists, checks MANAGE
  permission, creates sync run with "pending" status, emits sync-requested event.
- **Sync run tracking**: Entity tracks status, started_at, completed_at, error; DB
  `CHECK` constraint enforces valid status values.
- **Cascade deletion of sync runs**: FK `ondelete="CASCADE"` in
  `data_source_sync_run` model.
- **Permission inheritance**: SpiceDB schema wires `data_source.view/edit/manage`
  through to `knowledge_graph->view/edit/manage`; integration auth tests verify the chain.
- **Unauthorized/missing ambiguity**: Service returns `None` for both cases (no
  existence leakage).

---

### Summary Table

| Spec Requirement                        | Domain | Service | Route | Tests (route) |
|-----------------------------------------|--------|---------|-------|---------------|
| Creation (ULID, KG assoc, MANUAL default) | ✓    | ✓       | ✓     | ✓             |
| Creation with credential encryption      | ✓    | ✓       | ✓     | ✓             |
| Duplicate name → error                  | ✓    | ✓       | ✗     | ✗             |
| Name validation (1–100 chars)           | ✓    | ✓       | ✓     | ✓             |
| Schedule: MANUAL default                | ✓    | ✓       | ✓     | ✓             |
| Schedule: CRON (API-exposed)            | ✓    | ✓       | ✗     | ✗             |
| Schedule: INTERVAL (API-exposed)        | ✓    | ✓       | ✗     | ✗             |
| Schedule: missing value → error (API)   | ✓    | ✓       | ✗     | ✗             |
| Retrieval (GET by ID)                   | ✓    | ✓       | ✗     | ✗             |
| Retrieval: unauth/missing → 404         | ✓    | ✓       | ✗     | ✗             |
| Update (PUT/PATCH)                      | ✓    | ✓       | ✗     | ✗             |
| Immutability after deletion             | ✓    | ✓       | N/A   | ✓             |
| Deletion (DELETE)                       | ✓    | ✓       | ✗     | ✗             |
| Sync trigger (POST /sync)               | ✓    | ✓       | ✓     | ✓             |
| Sync run tracking (lifecycle fields)    | ✓    | ✓       | N/A   | ✓             |
| Cascade deletion of sync runs           | ✓    | ✓       | N/A   | ~             |
| Permission inheritance                  | ✓    | ✓       | ✓     | ✓             |