---
id: task-021
title: Add tests for API key cascade deletion on tenant deletion
spec_ref: specs/iam/api-keys.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Context

`specs/iam/api-keys.spec.md` defines:

> **Requirement: API Key Cascade Deletion**
> The system SHALL delete all API keys in a tenant when the tenant is deleted.
>
> **Scenario: Tenant deletion**
> - GIVEN a tenant with active API keys
> - WHEN the tenant is deleted
> - THEN all API keys in the tenant are deleted
> - AND authorization relationships are cleaned up

The implementation in `TenantService.delete_tenant` already handles this correctly:
it lists all API keys for the tenant, calls `api_key.mark_for_deletion()` (raising
`APIKeyDeleted` events), and calls `api_key_repository.delete(api_key)` for each.
The outbox translator maps `APIKeyDeleted` to SpiceDB relationship deletions.

However, **no test exercises this scenario**:

- `tests/unit/iam/application/test_tenant_service.py` — all `delete_tenant` tests
  set `mock_api_key_repo.list = AsyncMock(return_value=[])` (empty list), so the
  deletion loop is never exercised.
- `tests/integration/iam/test_tenant_api.py` — `TestDeleteTenant` creates no API
  keys before deletion; it only verifies the tenant record is removed.

## Work Required

1. **Unit test** — In `tests/unit/iam/application/test_tenant_service.py`, add a
   test class or test method (e.g. `test_delete_tenant_deletes_active_api_keys`)
   that:
   - Mocks `api_key_repo.list` to return one or more `APIKey` objects.
   - Calls `tenant_service.delete_tenant(...)`.
   - Asserts `api_key_repo.delete` was called once per key.
   - Asserts probe event `tenant_cascade_deletion_started` reports the correct
     `api_keys_count`.

2. **Integration test** — In `tests/integration/iam/test_tenant_api.py` (or a
   new file), add a test that:
   - Creates a tenant and creates at least one API key in that tenant.
   - Deletes the tenant via `DELETE /iam/tenants/{id}`.
   - Asserts the tenant is gone (404 on subsequent GET).
   - Asserts the API key is gone (no longer returned by `GET /iam/api-keys`
     with appropriate auth headers, or 404 if a GET-by-ID endpoint exists).
   - Optionally: processes the outbox and confirms SpiceDB relationships are
     cleaned up (API key owner/tenant relationships deleted).
