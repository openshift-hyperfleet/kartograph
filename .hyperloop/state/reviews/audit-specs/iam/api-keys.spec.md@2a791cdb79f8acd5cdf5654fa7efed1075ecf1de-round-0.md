---
task_id: audit-specs/iam/api-keys.spec.md@2a791cdb79f8acd5cdf5654fa7efed1075ecf1de
round: 0
role: auditor
verdict: fail
---
## Worker Result — API Keys Spec Alignment Audit

---

### Verdict: FAIL

One gap found. All other requirements are correctly implemented.

---

### Gap Detail

#### GAP-1 — Authentication priority is inverted (HIGH)

**Requirement:** API Key Authentication, Scenario: "JWT takes precedence"

**Spec says:**
> GIVEN a request with both a Bearer token and an `X-API-Key` header
> WHEN the request is authenticated
> THEN the Bearer token is used
> AND the API key is ignored

**Implementation does the opposite.**

File: `src/api/shared_kernel/middleware/mcp_api_key_auth.py`

The `MCPApiKeyAuthMiddleware.__call__` method (lines 126–160) tries
`X-API-Key` **first** and returns immediately on success, so the
Bearer token is never consulted when both headers are present.
Bearer token authentication only runs as a **fallback** when the
`X-API-Key` header is absent.

```python
# lines 126-139 — X-API-Key is primary, not fallback
if api_key_secret is not None:
    auth_context = await self._authenticate_api_key(api_key_secret, send)
    ...
    return   # Bearer token branch is never reached

# lines 141-160 — Bearer is fallback, not primary
if self._validate_bearer_token is not None:
    ...
```

**Fix required:** Swap the order — check `Authorization: Bearer`
first; fall through to `X-API-Key` only when no Bearer token is
present. The docstring already describes the correct intended order
("X-API-Key (primary)… Bearer token (fallback)"), so the docstring
must be updated to match whichever behavior is actually adopted.

---

### Passing Checks

All other requirements in the spec are correctly implemented:

- karto_ prefix on generated secrets (`iam/application/security.py: generate_api_key_secret`)
- bcrypt hashing with work factor 12 (`security.py: hash_api_key_secret`)
- 12-character prefix stored for fast lookup (`security.py: extract_prefix`)
- plaintext secret returned exactly once, never persisted (`api_key_service.py`)
- duplicate name per user/tenant rejected with 409 (`api_key_repository.py: _get_by_name`)
- expiration bounds 1–3650 days enforced at route layer (`presentation/api_keys/routes.py`)
- default expiration of 30 days (`presentation/api_keys/models.py: CreateAPIKeyRequest`)
- expired key rejected at authentication time (`domain/aggregates/api_key.py: is_valid`)
- revoked key rejected at authentication time (`domain/aggregates/api_key.py: is_valid`)
- last_used_at updated on successful authentication (`api_key_service.py: validate_and_get_key`)
- prefix collision: all candidates checked via bcrypt (`api_key_repository.py: get_verified_key`)
- prefix collision: ERROR-level log emitted (`infrastructure/observability/api_key_repository_probe.py` line 137: `self._logger.error`)
- list response excludes plaintext secrets (`presentation/api_keys/models.py: APIKeyResponse`)
- filter by creator user_id supported (`api_key_service.py: list_api_keys`, `routes.py`)
- owner revocation via SpiceDB REVOKE permission on API_KEY resource (`api_key_service.py`)
- tenant admin revocation via SpiceDB relationship hierarchy (`api_key_service.py`)
- already-revoked key returns 409 Conflict (`domain/aggregates/api_key.py: revoke` + `routes.py`)
- revoked key remains visible in listings with is_revoked=true (no physical delete in revoke path)
- unauthorized revocation returns 403 Forbidden (`routes.py`)
- cascade deletion via RESTRICT FK + application-layer APIKeyDeleted domain events
- SpiceDB relationships cleaned up via transactional outbox + event handler
- name length 1–255 enforced by Pydantic (`presentation/api_keys/models.py: min_length=1, max_length=255`)
- empty name rejected with validation error (`min_length=1` constraint)