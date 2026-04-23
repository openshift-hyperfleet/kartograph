---
task_id: task-021
round: 0
role: spec-reviewer
verdict: fail
---
# API Keys Full Spec Alignment Review — Task-021

## Scope
This is a full spec alignment review covering all six requirements in
`specs/iam/api-keys.spec.md`. The review examines implementation in the
`hyperloop/task-021` branch and checks that every SHALL/MUST requirement
and every Scenario is covered by at least one test (unit or integration).

---

## Requirement Coverage Summary

### REQ-1: API Key Creation — PARTIAL
**Code:** `iam/application/services/api_key_service.py`, `iam/presentation/api_keys/routes.py`,
`iam/presentation/api_keys/models.py`

#### Scenario: Successful creation — COVERED
- `karto_` prefix → `TestAPIKeyServiceCreate.test_secret_has_karto_prefix`
- Plaintext returned once → `test_returns_plaintext_secret_only_at_creation` + route `test_returns_secret_in_response`
- Bcrypt hash stored → `test_creates_api_key_with_hashed_secret`
- 12-character prefix stored → `test_stores_prefix_from_secret` (asserts `api_key.prefix == plaintext_secret[:12]`)
- Permission check → `TestAPIKeyServiceCreateAuthorization.test_create_checks_tenant_permission`

#### Scenario: Duplicate name per user — COVERED
- Service raises `DuplicateAPIKeyNameError` → `test_raises_on_duplicate_name`
- Route returns 409 → `test_returns_409_on_duplicate_name`

#### Scenario: Expiration bounds — PARTIAL
- Range 1–3650 validated → `test_validates_expires_in_days_minimum` (0 → 422) + `test_validates_expires_in_days_maximum` (3651 → 422)
- Key created with specified expiration → `test_creates_with_expiration`
- **MISSING: "default expiration is 30 days if unspecified"** — The Pydantic model
  has `expires_in_days: int = Field(30, ...)`, which implements the default. However
  no test omits `expires_in_days` from a request AND then asserts the service is
  called with `expires_in_days=30`. `test_creates_api_key_returns_201` omits the
  field but only asserts the response status and body, not `create_api_key.call_args`.
  **Fix:** Add an assertion to `test_creates_api_key_returns_201` (or a new test) that
  calls `mock_api_key_service.create_api_key.assert_called_once_with(..., expires_in_days=30)`
  when the request body contains only `{"name": "..."}`.

---

### REQ-2: API Key Authentication — PARTIAL
**Code:** `iam/dependencies/user.py` (`_authenticate`), `iam/application/services/api_key_service.py`
(`validate_and_get_key`), `shared_kernel/middleware/mcp_api_key_auth.py`

#### Scenario: Valid key — COVERED
- Authenticated as creator + `last_used_at` updated →
  `TestAPIKeyAuthentication.test_authenticates_with_valid_api_key` (integration) +
  `test_updates_last_used_at_on_success` (integration) +
  `TestAPIKeyServiceValidate.test_updates_last_used_at` (unit service)

#### Scenario: Expired key — PARTIAL
- Service returns None for expired key → `TestAPIKeyServiceValidate.test_returns_none_for_expired_key`
- `_authenticate` in `user.py` raises 401 when `validate_and_get_key` returns None
  (visible at lines 124–131; no dedicated test for this exact path through the REST API)
- Middleware returns 401 when validation callable returns None →
  `TestMCPApiKeyAuthMiddleware401WhenInvalid.test_returns_401_when_key_invalid`
- **MISSING: end-to-end test** — There is no test that sends a request to a
  protected REST endpoint with an expired API key and asserts 401. Creating an
  expired key through the public API is impossible (min 1 day), but the key can be
  inserted directly into the DB via a fixture, or a conftest helper can create a key
  via `APIKeyService` with a past `expires_at` bypassing the route validation.
  Without this, the GIVEN/WHEN/THEN chain is only covered by split unit tests.
  **Fix:** Add an integration test fixture that inserts an expired API key directly
  into the DB and asserts that authenticating with it returns 401.

#### Scenario: Revoked key — COVERED
- `test_returns_401_for_revoked_api_key` (integration): creates key, revokes via API,
  then authenticates — gets 401.

#### Scenario: JWT takes precedence — COVERED
- `test_prefers_jwt_when_both_provided` + `test_invalid_jwt_with_valid_api_key_uses_api_key`
  (integration). The second test proves JWT blocks API-key fallback when JWT is invalid.
- Implementation confirmed in `_authenticate` (user.py): JWT is tried first;
  if invalid JWT is present, raises 401 immediately without trying the API key.

#### Scenario: Prefix collision — COVERED
- `TestAPIKeyRepositoryGetVerifiedKey.test_logs_error_on_prefix_collision` verifies
  `probe.api_key_prefix_collision` is called with the correct prefix and collision count.
- `DefaultAPIKeyRepositoryProbe.api_key_prefix_collision` calls `self._logger.error(...)`,
  satisfying "error-level event is logged".
- bcrypt comparison of each candidate is the implementation behavior (the repository
  iterates all candidates with the same prefix and calls `verify_api_key_secret`).

---

### REQ-3: API Key Listing — COVERED
**Code:** `iam/application/services/api_key_service.py`, `iam/presentation/api_keys/routes.py`

#### Scenario: List keys — COVERED
- Metadata fields (name, prefix, created_at, expires_at, last_used_at, is_revoked)
  all present in `APIKeyResponse` model; `test_lists_api_keys_for_user` (route) exercises
  the full response shape.
- No secrets exposed → `test_never_returns_secret_or_hash` explicitly checks `"secret"`,
  `"key_hash"`, and `"hash"` are absent from list responses.

#### Scenario: Filter by creator — COVERED
- `TestAPIKeyServiceList.test_filters_by_created_by_user_id` asserts that when
  `created_by_user_id` is passed to `list_api_keys`, it is forwarded to
  `repo.list(created_by_user_id=filter_user_id)`.

---

### REQ-4: API Key Revocation — PARTIAL
**Code:** `iam/application/services/api_key_service.py`, `iam/presentation/api_keys/routes.py`

#### Scenario: Owner revokes own key — PARTIAL
- Key marked revoked → `test_revokes_existing_key` (service, asserts `saved_key.is_revoked is True`) +
  `test_revokes_api_key_returns_204` (route) + `test_owner_can_revoke_own_key` (integration).
- **MISSING: "key remains visible in listings with `is_revoked` set to true"** —
  No test chains revocation followed by listing to verify the revoked key is still
  returned with `is_revoked=True`. The implementation is correct (the service's
  `list_api_keys` does not filter revoked keys; `APIKeyResponse.is_revoked` is
  included in the response). But the spec's "AND" clause is not exercised by any
  test.
  **Fix:** Add a test (unit or integration) that: (1) creates a key, (2) revokes it,
  (3) lists keys, (4) asserts the revoked key appears with `is_revoked=True`.

#### Scenario: Tenant admin revokes any key — COVERED
- `test_tenant_admin_can_revoke_other_users_key` (integration): Bob creates key,
  Alice (tenant admin) revokes it → 204.

#### Scenario: Already revoked — COVERED
- `test_raises_when_already_revoked` (service) + `test_returns_409_when_already_revoked` (route).

#### Scenario: Unauthorized revocation — COVERED
- `test_non_admin_cannot_revoke_other_users_key` (integration, Bob cannot revoke
  Alice's key → 403) + `test_revoke_api_key_returns_403_when_unauthorized` (route).

---

### REQ-5: API Key Cascade Deletion — COVERED
**Code:** `iam/application/services/tenant_service.py` (`delete_tenant`)

#### Scenario: Tenant deletion — COVERED
- Six unit tests in `TestDeleteTenant` (commit `7cf228fd`) cover:
  - Single key deleted → `test_deletes_api_keys_on_tenant_deletion`
  - Multiple keys deleted → `test_deletes_multiple_api_keys_on_tenant_deletion`
  - Domain event emitted → `test_api_key_mark_for_deletion_emits_deleted_event`
  - Tenant scoping → `test_api_key_repo_queried_by_tenant_on_deletion`
  - Probe fires with count → `test_cascade_deletion_probe_reports_api_key_count`
  - Keys deleted before tenant → `test_api_keys_deleted_before_tenant_on_cascade`

---

### REQ-6: API Key Name Validation — COVERED
**Code:** `iam/presentation/api_keys/models.py` (`CreateAPIKeyRequest`)

#### Scenario: Valid name — COVERED
- `test_creates_api_key_returns_201` accepts a 9-character name ("my-api-key"); the
  Pydantic model enforces 1–255 character bounds.

#### Scenario: Empty name — COVERED
- `test_validates_name_min_length` sends `{"name": ""}` → 422.

---

## Items Requiring Fixes

### FAIL-1 (REQ-1, Expiration Bounds): Default expiration not tested
The spec states "the default expiration is 30 days if unspecified." The implementation
is correct (`Field(30, ...)` in `CreateAPIKeyRequest`). A test must omit
`expires_in_days` from the request body and assert `create_api_key` was called with
`expires_in_days=30`.

### FAIL-2 (REQ-2, Expired key): No end-to-end test for expired key → 401
The spec states "authentication fails with a 401 response" for expired keys. Unit
tests at the service and middleware layers cover the two halves independently, but
no test exercises the full GIVEN/WHEN/THEN chain through the REST API. An integration
test that directly inserts an expired key (bypassing the 1-day minimum route
validation) is needed.

### FAIL-3 (REQ-4, Owner revocation): Revoked key not verified to remain in listing
The spec states "the key remains visible in listings with `is_revoked` set to true."
The implementation is correct, but no test exercises this: after a key is revoked,
list keys, assert the revoked entry is present with `is_revoked=True`.