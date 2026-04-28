---
task_id: audit-specs/shared-kernel/jwt-authentication.spec.md@224a54b5ab2f7bca552b3845891a363215b7110b
round: 0
role: auditor
verdict: fail
---
## Alignment Audit — JWT Authentication

### Summary

Three of four requirements are fully implemented and tested. One requirement
(Authentication Priority) is correctly implemented on the REST API path but is
violated by the MCP middleware, which applies the opposite priority order.

---

## Gaps

### GAP-1 — Authentication Priority inverted in MCP middleware [FAIL]

**Spec requirement:** "The system SHALL prioritize JWT Bearer tokens over API
keys."

**Scenario violated (Both credentials provided):**
> GIVEN a request with both an `Authorization: Bearer` header and an
> `X-API-Key` header
> WHEN the request is authenticated
> THEN the Bearer token is used AND the API key is ignored

**Scenario violated (Invalid Bearer token with API key present):**
> GIVEN a request with an invalid Bearer token and a valid API key
> WHEN the request is authenticated
> THEN authentication fails immediately (Bearer is not silently skipped)

**File:** `src/api/shared_kernel/middleware/mcp_api_key_auth.py`
**Lines:** 126–159

The MCP middleware tries the API key first (lines 126–139) and returns
immediately on success, only falling back to Bearer token if no API key is
present (lines 141–159). This is the exact inverse of the specified priority.

When both credentials are present, the API key wins rather than Bearer.
When an invalid Bearer token accompanies a valid API key, the invalid Bearer
is silently skipped instead of causing an immediate failure.

The accompanying unit test at
`src/api/tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py`
lines 491–525 (test name `api_key_takes_precedence_over_bearer`) asserts and
documents this inverted behaviour as intentional, confirming the violation is
baked into the design of the MCP path.

---

## Aligned Requirements

### Token Validation — PASS

All five scenarios implemented in
`src/api/shared_kernel/auth/jwt_validator.py` lines 74–153:
- Valid token accepted (RS256, valid sig/aud/iss/exp)
- Expired token → InvalidTokenError (line 116–118)
- Wrong audience → fails (lines 119–126)
- Wrong issuer → fails (lines 119–126)
- Invalid signature → fails (lines 129–135)

Test coverage: `src/api/tests/unit/shared_kernel/auth/test_jwt_validator.py`
lines 178–258.

### User Identity Extraction — PASS

Implemented in `jwt_validator.py` lines 137–153:
- `sub` used as user ID (line 138)
- `preferred_username` used as username (line 146)
- Falls back to `sub` when `preferred_username` absent (line 152)
- Raises InvalidTokenError when `sub` is absent (lines 139–143)

Test coverage: `test_jwt_validator.py` lines 387–516.

### JWKS Caching — PASS

Implemented in `jwt_validator.py`:
- Default TTL 24 hours (line 49)
- Cache state: `_jwks`, `_jwks_fetched_at`, `_jwks_lock` (lines 69–72)
- Cache validity check: `_is_cache_valid()` (lines 179–185)
- Double-check locking pattern prevents duplicate fetches during concurrent
  refresh: `_get_jwks()` (lines 155–177) using `asyncio.Lock` (line 72)

Test coverage: `test_jwt_validator.py` lines 311–385, 546–599 (includes
`asyncio.gather` concurrency tests).

### Authentication Priority (REST API path) — PASS

`src/api/iam/dependencies/user.py` lines 68–152 correctly:
- Tries Bearer first (lines 100–121)
- Fails immediately on invalid Bearer without falling back to API key
  (line 115 raises before reaching API key logic at line 124)

Test coverage: `src/api/tests/unit/iam/dependencies/test_authenticate_dependency.py`
lines 207–262.