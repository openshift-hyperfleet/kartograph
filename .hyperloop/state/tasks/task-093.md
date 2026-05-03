---
id: task-093
title: MCP server — MCP Authentication requirement spec alignment
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): verify MCP Authentication requirement against spec — all four scenarios"
pr_description: |
  ## What & Why

  The **Requirement: MCP Authentication** in `specs/query/mcp-server.spec.md`
  has never had a hyperloop task created for it. All four scenarios in this
  requirement are currently implemented in:

  - `src/api/shared_kernel/middleware/mcp_api_key_auth.py` — `MCPApiKeyAuthMiddleware`
    (the ASGI middleware wrapping the MCP HTTP app)
  - `src/api/query/presentation/mcp.py` — `query_mcp_app` (the middleware-wrapped app)
  - `src/api/tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py` — full
    middleware test suite covering API key auth, Bearer fallback, 401/503 responses,
    context cleanup, and non-HTTP passthrough
  - `src/api/tests/unit/query/test_mcp_auth_wiring.py` — confirms the MCP app is
    wrapped with `MCPApiKeyAuthMiddleware`

  This task creates traceability between the spec requirement and the existing
  implementation, and confirms every scenario is covered line-by-line.

  ## Spec Scenarios

  ### Scenario: API key authentication
  > GIVEN a valid `X-API-Key` header
  > WHEN the MCP request is processed
  > THEN the request is authenticated using the API key's creator identity
  > AND the tenant is resolved from the API key's tenant scope

  Implementation: `MCPApiKeyAuthMiddleware` reads `x-api-key` from ASGI headers,
  calls `validate_api_key(secret)`, and on success sets `MCPAuthContext(user_id,
  tenant_id, api_key_id)` in a `ContextVar` for the downstream request.

  Tests:
  - `TestMCPApiKeyAuthMiddlewareSuccess.test_sets_auth_context_on_valid_key` — verifies
    `user_id`, `tenant_id`, and `api_key_id` are correctly set from the API key record
  - `test_auth_context_has_correct_fields` — asserts the exact field values in `MCPAuthContext`
  - `TestMCPAppHasAuthMiddleware.test_query_mcp_app_is_wrapped_with_auth_middleware`

  ### Scenario: Bearer token authentication
  > GIVEN a valid `Authorization: Bearer` header (and no API key)
  > WHEN the MCP request is processed
  > THEN the JWT is validated
  > AND the tenant is resolved from the `X-Tenant-ID` header

  Implementation: `MCPApiKeyAuthMiddleware` falls back to Bearer token when no
  `x-api-key` header is present. It calls `validate_bearer_token(token, tenant_id)`
  where `tenant_id` is read from the `x-tenant-id` header. On success, sets
  `MCPAuthContext(user_id=resolved_user_id, tenant_id=tenant_id)`.

  Tests:
  - `TestMCPApiKeyAuthMiddlewareBearerFallback.test_falls_back_to_bearer_when_api_key_missing`
  - `test_bearer_returns_401_when_token_invalid`
  - `test_api_key_takes_precedence_over_bearer` — API key wins when both present
  - `test_returns_401_for_invalid_utf8_in_authorization_header`
  - `test_returns_401_for_invalid_utf8_in_tenant_id_header`

  ### Scenario: No credentials
  > GIVEN a request with no authentication headers
  > WHEN the MCP request is processed
  > THEN a 401 response is returned

  Implementation: `MCPApiKeyAuthMiddleware` returns `{"error": "X-API-Key header
  is required"}` with HTTP 401 and `WWW-Authenticate: ApiKey realm="kartograph"`.

  Tests:
  - `TestMCPApiKeyAuthMiddleware401WhenMissing.test_returns_401_when_header_missing`
  - `test_calls_probe_on_missing_header`
  - `TestMCPApiKeyAuthMiddlewareContextCleanup.test_context_var_cleared_after_request`
    (verifies context does not leak from a prior authenticated request)

  ### Scenario: Authentication service unavailable
  > GIVEN a request when the authentication backend is unreachable
  > WHEN the MCP request is processed
  > THEN a 503 response is returned

  Implementation: `MCPApiKeyAuthMiddleware` catches any exception raised by
  `validate_api_key()` and returns `{"error": "Authentication service temporarily
  unavailable"}` with HTTP 503.

  Tests:
  - `TestMCPApiKeyAuthMiddlewareValidationError.test_returns_503_when_validator_raises`
  - `probe.mcp_auth_validation_error` is called on the domain probe

  ## Files Affected

  No new implementation expected — this task verifies existing code:

  - `src/api/shared_kernel/middleware/mcp_api_key_auth.py` — `MCPApiKeyAuthMiddleware`
  - `src/api/shared_kernel/middleware/mcp_auth.py` — `MCPAuthContext`, `_mcp_auth_context_var`
  - `src/api/query/presentation/mcp.py` — `query_mcp_app` (middleware-wrapped MCP app)
  - `src/api/tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py`
  - `src/api/tests/unit/query/test_mcp_auth_wiring.py`

  ## How to Verify

  1. Run `cd src/api && uv run pytest tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py -v`
  2. Run `cd src/api && uv run pytest tests/unit/query/test_mcp_auth_wiring.py -v`
  3. Confirm all four spec scenarios have at least one test. If any scenario is
     NOT covered by an existing test, add a focused test (TDD: write first, then
     verify the existing implementation passes).
  4. Run `cd src/api && uv run pytest tests/unit/ -v` to confirm no regressions.

  ## Gap Analysis

  All four scenarios have implementation and test coverage. This task provides
  spec traceability — the `MCPApiKeyAuthMiddleware` was implemented as part of
  the shared-kernel tenant context work (task-038, referencing
  `tenant-context.spec.md`) rather than as a direct hyperloop task for
  `mcp-server.spec.md`. This task closes the traceability gap.

  One potential gap to verify: the spec says the Bearer token path resolves
  "the tenant from the `X-Tenant-ID` header." Confirm the test
  `test_falls_back_to_bearer_when_api_key_missing` checks that the tenant_id
  in the resulting `MCPAuthContext` matches the value from the `x-tenant-id`
  header (not a hardcoded value).

  ## Design Context

  - `MCPApiKeyAuthMiddleware` is an ASGI middleware, not a FastAPI dependency, so
    it operates before any FastMCP tool dispatch. Authentication failures return
    raw JSON without entering the MCP server at all.
  - The `_mcp_auth_context_var` `ContextVar` propagates the resolved identity
    into MCP tool functions via `get_mcp_auth_context()`. Each ASGI request gets
    an isolated context token; the middleware resets the var after the request
    completes to prevent identity bleed.
  - `validate_api_key` and `validate_bearer_token` are callables injected at
    construction time, enabling the unit tests to use lightweight fakes without
    touching the database or OIDC provider.
---
