---
id: task-130
title: "MCP Authentication — HTTP integration tests for Bearer token auth and auth-service-unavailable 503"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add HTTP integration tests for MCP Bearer token auth and auth-service-unavailable 503"
pr_description: |
  ## What & Why

  `specs/query/mcp-server.spec.md` defines four scenarios under the **MCP Authentication**
  requirement. Two are not yet covered by HTTP-level integration tests:

  > **Scenario: Bearer token authentication**
  > - GIVEN a valid `Authorization: Bearer` header (and no API key)
  > - WHEN the MCP request is processed
  > - THEN the JWT is validated
  > - AND the tenant is resolved from the `X-Tenant-ID` header

  > **Scenario: Authentication service unavailable**
  > - GIVEN a request when the authentication backend is unreachable
  > - WHEN the MCP request is processed
  > - THEN a 503 response is returned

  ### Current coverage

  `src/api/tests/integration/query/test_api_key_auth.py` (or equivalent) covers the
  **API key** and **no-credentials** scenarios at the HTTP level. However:

  - **Bearer token** — there is no integration test that POSTs to the MCP endpoint
    with an `Authorization: Bearer <jwt>` header, verifies JWT signature validation,
    and confirms the tenant is resolved from the `X-Tenant-ID` header. The middleware
    code path exists in `shared_kernel/middleware/mcp_api_key_auth.py`, but the
    full round-trip from HTTP request through JWT validation to tenant resolution is
    untested.

  - **Auth-service unavailable** — the middleware returns 503 when the IAM/SpiceDB
    backend is unreachable, but no test simulates a backend connection failure and
    asserts that the response status is exactly 503 (not 500 or a propagated exception).

  If someone accidentally broke JWT validation or removed the 503 guard clause,
  no existing test would catch it.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **MCP Authentication — Scenario: Bearer token authentication**: JWT is validated;
    tenant is resolved from the `X-Tenant-ID` header; request proceeds on success.
  - **MCP Authentication — Scenario: Authentication service unavailable**: HTTP 503
    is returned when the authentication backend is unreachable.

  ## What This Change Does

  Add a new integration test file
  `src/api/tests/integration/query/test_mcp_auth_http.py` that exercises
  `MCPApiKeyAuthMiddleware` via the full HTTP stack.

  ### Bearer token tests

  Use the project's fake OIDC provider (`src/api/tests/fakes/oidc_provider.py`) to
  issue real RS256-signed JWTs and submit them to the MCP endpoint. This exercises
  the same code path that production JWTs from Keycloak would follow.

  **`TestMCPBearerTokenAuthentication`**

  - `test_valid_bearer_token_with_tenant_id_is_accepted`
    - Obtain a JWT from the fake OIDC provider for pre-configured user `alice`.
    - POST to the MCP endpoint with `Authorization: Bearer <jwt>` and a valid
      `X-Tenant-ID` header.
    - Assert the response is not 401/403 (request passes authentication and
      reaches the MCP handler).

  - `test_bearer_token_with_invalid_signature_returns_401`
    - Construct a JWT by base64-editing the signature to produce an invalid token.
    - POST with `Authorization: Bearer <tampered_jwt>` and a valid `X-Tenant-ID`.
    - Assert HTTP 401.

  - `test_bearer_token_without_tenant_id_header_returns_401`
    - Obtain a valid JWT from the fake OIDC provider.
    - POST with `Authorization: Bearer <jwt>` but **omit** `X-Tenant-ID`.
    - Assert HTTP 401 (cannot resolve tenant without the header; spec requires tenant
      to be resolved from `X-Tenant-ID`).

  - `test_expired_bearer_token_returns_401`
    - Issue a JWT with `exp` set to a timestamp in the past.
    - POST with `Authorization: Bearer <expired_jwt>` and a valid `X-Tenant-ID`.
    - Assert HTTP 401.

  ### Auth-service-unavailable tests

  Patch the authentication callable inside `MCPApiKeyAuthMiddleware` to raise a
  connection error, simulating the IAM backend being unreachable.

  **`TestMCPAuthServiceUnavailable`**

  - `test_auth_backend_connection_error_returns_503`
    - Patch `validate_mcp_bearer_token` (or `validate_mcp_api_key`) to raise
      `ConnectionError`.
    - POST any request to the MCP endpoint.
    - Assert HTTP 503 (not 500; the spec is explicit that this condition returns 503).

  - `test_auth_backend_timeout_returns_503`
    - Patch the auth validation callable to raise `TimeoutError` (or `asyncio.TimeoutError`).
    - POST any request to the MCP endpoint.
    - Assert HTTP 503.

  ## Files / Areas Affected

  - `src/api/tests/integration/query/test_mcp_auth_http.py` (new) — all tests above
  - `src/api/shared_kernel/middleware/mcp_api_key_auth.py` — read to identify the
    exact exception types and callable names to patch; no production code changes
    are expected if the 503 path already exists
  - `src/api/tests/fakes/oidc_provider.py` — referenced for JWT issuance; no changes

  ## How to Verify

  These are integration tests that require a running dev instance. Use the isolated
  instance manager so they don't interfere with other work:

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/query/test_mcp_auth_http.py -v -m integration
  ```

  Regression validation:

  1. Temporarily comment out the JWT signature verification in `MCPApiKeyAuthMiddleware`
     and confirm `test_bearer_token_with_invalid_signature_returns_401` fails — proves
     the test is not a false positive.
  2. Temporarily change the 503 status code in the middleware's exception handler to 500
     and confirm `test_auth_backend_connection_error_returns_503` fails.
  3. Remove the `X-Tenant-ID` check from the Bearer token path and confirm
     `test_bearer_token_without_tenant_id_header_returns_401` fails.

  ## Caveats

  - The fake OIDC provider issues real RS256-signed JWTs and serves JWKS, so the
    middleware's JWT validation code path (signature check, expiry, claims) is
    exercised end-to-end — no mocking of cryptographic verification.
  - The `X-Tenant-ID` value used in tests must correspond to a tenant that exists
    in the test database; align with fixtures used by the existing integration test
    suite (e.g., `test_api_key_auth.py`).
  - Read `mcp_api_key_auth.py` to confirm which exception types trigger the 503
    response before writing the patches. If the middleware catches a custom exception
    (e.g., `AuthServiceUnavailableError`), patch the callable to raise that type
    rather than the stdlib `ConnectionError`.
  - These tests complement task-115 (parameter bounds) and task-116 (query_graph
    wiring). They do not overlap with either of those tasks.
---
