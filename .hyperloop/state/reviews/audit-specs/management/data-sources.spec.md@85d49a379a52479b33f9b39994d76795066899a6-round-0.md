---
task_id: audit-specs/management/data-sources.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — specs/management/data-sources.spec.md

Four gaps were found. The application/domain layer is complete and correct,
but the HTTP presentation layer is missing three required endpoints and has
one error-handling deficiency.

---

## GAP 1 — Missing HTTP endpoint: Data Source Retrieval

**Spec:** "The system SHALL return data source details only to users with
`view` permission." (Scenarios: Authorized retrieval / Unauthorized or
non-existent — no distinction between unauthorized and missing)

**Finding:** `DataSourceService.get()` is fully and correctly implemented in
`src/api/management/application/services/data_source_service.py` lines 183–216,
including VIEW permission enforcement and existence-leakage prevention.
However, no HTTP route exposes this to callers.
`src/api/management/presentation/data_sources/routes.py` defines only:

  - GET  /knowledge-graphs/{kg_id}/data-sources  (list)
  - POST /knowledge-graphs/{kg_id}/data-sources  (create)
  - POST /data-sources/{ds_id}/sync              (trigger sync)
  - GET  /data-sources/{ds_id}/sync-runs         (list sync runs)

There is no `GET /data-sources/{ds_id}` route. Users have no API endpoint to
retrieve a single data source by ID.

---

## GAP 2 — Missing HTTP endpoint: Data Source Update

**Spec:** "The system SHALL allow users with `edit` permission to update data
source connection configuration." (Scenario: Update connection config — name,
connection_config, raw credentials; credentials path not client-settable)

**Finding:** `DataSourceService.update()` is fully and correctly implemented in
`src/api/management/application/services/data_source_service.py` lines 266–341,
with EDIT permission check, credential re-encryption at
`datasource/{id}/credentials`, and system-managed `credentials_path`.
However, there is no `PATCH` or `PUT /data-sources/{ds_id}` HTTP route in
`src/api/management/presentation/data_sources/routes.py`. The update capability
is entirely inaccessible via the API.

---

## GAP 3 — Missing HTTP endpoint: Data Source Deletion

**Spec:** "The system SHALL allow users with `manage` permission to delete a
data source." (Scenario: credentials deleted first, then DS, then authorization
relationships cleaned up)

**Finding:** `DataSourceService.delete()` is fully and correctly implemented in
`src/api/management/application/services/data_source_service.py` lines 343–396:
credentials deleted first (lines 385–389), data source deleted (line 392), and
`DataSourceDeleted` event published via outbox (repository lines 151–163) which
triggers downstream authorization cleanup. However, there is no
`DELETE /data-sources/{ds_id}` HTTP route in
`src/api/management/presentation/data_sources/routes.py`. Deletion is entirely
inaccessible via the API.

---

## GAP 4 — Duplicate name error not surfaced correctly in HTTP response

**Spec:** "WHEN a user attempts to create another [data source] with the same
name, THEN the request is rejected with a duplicate name error."

**Finding:** The domain layer correctly raises `DuplicateDataSourceNameError`
(via `IntegrityError` on the `uq_data_sources_kg_name` constraint) in
`src/api/management/infrastructure/repositories/data_source_repository.py`
lines 107–115. However, the `create_data_source` HTTP route in
`src/api/management/presentation/data_sources/routes.py` lines 119–132 handles
only `UnauthorizedError` (→ 403), `ValueError` (→ 404), and catch-all
`Exception` (→ 500). `DuplicateDataSourceNameError` falls through to the 500
handler. The spec requires a meaningful duplicate-name error response, not a
generic internal server error.

---

## Requirements that ARE correctly implemented

| Requirement | Status |
|---|---|
| ULID generation, KG/tenant association, MANUAL schedule default | PASS |
| Credential encryption at datasource/{id}/credentials | PASS |
| Name validation 1–100 chars (domain + Pydantic layer) | PASS |
| Schedule types MANUAL/CRON/INTERVAL; missing value validation | PASS |
| Immutability after deletion (AggregateDeletedError in aggregate) | PASS |
| Sync triggering: pending sync run created + event emitted | PASS |
| Sync run lifecycle tracking (status/started_at/completed_at/error) | PASS |
| Sync run cascade deletion via DB foreign key ON DELETE CASCADE | PASS |
| Permission inheritance via SpiceDB schema (inherited from KG) | PASS |
| Not-found / unauthorized conflation in service.get() | PASS |