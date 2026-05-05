---
id: task-152
title: "Add integration tests for Bearer token MCP authentication"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration tests for Bearer token MCP authentication"
pr_description: |
  ## What and Why

  The MCP Server spec's "MCP Authentication" requirement defines four scenarios.
  Three of them already have test coverage:

  - **No credentials → 401**: covered by `tests/integration/query/test_mcp_auth_http.py`
  - **Invalid API key → 401**: covered by `tests/integration/query/test_mcp_auth_http.py`
  - **Authentication service unavailable → 503**: covered by
    `tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py`

  The **fourth scenario — Bearer token authentication — has no integration-level
  test**:

  > **Requirement: MCP Authentication**
  > **Scenario: Bearer token authentication**
  > "GIVEN a valid `Authorization: Bearer` header (and no API key)
  >  WHEN the MCP request is processed
  >  THEN the JWT is validated
  >  AND the tenant is resolved from the `X-Tenant-ID` header"

  The `validate_mcp_bearer_token` function in `infrastructure/mcp_dependencies.py`
  is fully implemented — it validates the JWT against the OIDC discovery endpoint,
  resolves the tenant from `X-Tenant-ID` (or single-tenant auto-select), and
  verifies membership via SpiceDB. However, no integration test exercises this
  code path through the actual MCP HTTP endpoint.

  The unit tests in `test_mcp_auth_middleware.py` use a fake bearer validator
  callable and cannot cover:
  1. Real JWT signature verification against the OIDC provider's JWKS
  2. Correct `X-Tenant-ID` header parsing and tenant resolution
  3. SpiceDB membership check for the resolved user+tenant
  4. Successful request processing after Bearer auth (not a 401 or 503)

  This is an identical pattern to tasks 149/150/151 which added integration tests
  for scenarios that had unit coverage but no integration-level verification.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`

  - **Requirement: MCP Authentication — Scenario: Bearer token authentication**
    Verify that a valid JWT Bearer token (issued by the fake OIDC provider) is
    accepted by the MCP endpoint, the tenant is resolved from `X-Tenant-ID`, and
    the request succeeds (tool call returns a valid response, not 401/503).

  Also provides a regression guard for the **Scenario: API key takes precedence**
  wiring — when both X-API-Key and Authorization headers are present, the API key
  path is used (unit-tested, but not at HTTP integration level).

  ## Key Design Decisions

  **Integration tests run against `make instance-up`** (fake OIDC provider,
  PostgreSQL, SpiceDB). Mark tests with `@pytest.mark.integration`.

  **Use the fake OIDC provider** (`tests/fakes/oidc_provider.py`) to issue real
  RS256-signed JWTs for `alice` / `bob`. The fake OIDC provider is already part
  of `make instance-up` and issues tokens the JWT validator accepts.

  **Test via the MCP HTTP endpoint** (not the service layer directly), to exercise
  the full stack: Bearer header → `MCPApiKeyAuthMiddleware._authenticate_bearer` →
  `validate_mcp_bearer_token` → JWT validation → SpiceDB membership check →
  `MCPAuthContext` set → tool/resource accessible.

  **Two test classes:**

  1. **`TestBearerTokenAuthentication`**: Obtain a JWT from the fake OIDC
     `/token` endpoint for `alice`. Send an MCP `initialize` request with
     `Authorization: Bearer <jwt>` and `X-Tenant-ID: <tenant_id>`. Assert HTTP
     200 (not 401/503). Then call a simple tool (e.g., `list_tools` or
     `resources/list`) and assert the response is valid MCP JSON-RPC.

  2. **`TestBearerTokenTenantResolution`**: Verify that the tenant is resolved
     correctly — a user who is a member of tenant A cannot use tenant B's
     `X-Tenant-ID` (assert 401 is returned when the SpiceDB membership check
     fails for a non-member tenant). This verifies the membership gate in
     `validate_mcp_bearer_token`.

  Follow the patterns in `test_mcp_auth_http.py` for ASGI test client setup
  and `test_secure_enclave_mcp.py` for tenant provisioning.

  ## What Files Are Affected

  - **New file**:
    `src/api/tests/integration/query/test_mcp_bearer_auth.py`
    — Two test classes covering the Bearer token authentication scenario and
    tenant resolution gate. Marks: `@pytest.mark.integration`.

  - No implementation files change — `validate_mcp_bearer_token` in
    `infrastructure/mcp_dependencies.py` is already correctly implemented;
    only integration-level test coverage is missing.

  ## How to Verify

  ```bash
  # Start isolated dev instance (includes fake OIDC provider)
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance

  # Run the new integration tests
  cd src/api && uv run pytest tests/integration/query/test_mcp_bearer_auth.py \
      -v -m integration

  # Full integration suite — confirm no regressions
  make test-integration
  ```

  ## Caveats

  - The fake OIDC provider must be running (it is part of `make instance-up`,
    which replaces Keycloak for isolated instances).
  - The test must create a real tenant in the database and write SpiceDB
    relationships for the test user (alice) before calling the MCP endpoint,
    so the membership check in `validate_mcp_bearer_token` can succeed.
  - Clean up tenant and SpiceDB relationships in fixture teardown.
  - The MCP HTTP endpoint path is `/mcp` (mounted in `main.py`). Use
    `ASGITransport` + `httpx.AsyncClient` as done in `test_mcp_auth_http.py`.
  - Do NOT apply `@pytest.mark.keycloak` — this test uses the fake OIDC provider
    that is always available in `make instance-up`.
  - The Bearer token path requires `X-Tenant-ID` in multi-tenant mode; ensure
    the test sends this header correctly.
---
