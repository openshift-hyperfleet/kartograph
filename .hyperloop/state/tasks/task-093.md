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
pr_title: "test(query): verify MCP Authentication scenarios against mcp-server spec"
pr_description: |
  ## What & Why

  The **Requirement: MCP Authentication** in `specs/query/mcp-server.spec.md` has
  never had a hyperloop task created for it. All four scenarios are currently
  implemented in `shared_kernel/middleware/mcp_api_key_auth.py`
  (`MCPApiKeyAuthMiddleware`) and tested in
  `tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py` (17 tests).
  Task-038 covers this requirement from the *shared-kernel tenant context spec*
  perspective; this task provides traceability to the *MCP server spec*.

  The primary goal is to verify line-by-line that every spec scenario is correctly
  implemented **and** adequately tested. If any test is missing or tests the wrong
  thing, add it before closing this task.

  ## Spec Scenarios

  ### Scenario: API key authentication
  > GIVEN a valid `X-API-Key` header
  > WHEN the MCP request is processed
  > THEN the request is authenticated using the API key's creator identity
  > AND the tenant is resolved from the API key's tenant scope

  **Implementation:** `MCPApiKeyAuthMiddleware._authenticate_api_key()` calls
  `validate_api_key(secret)`. On success it builds an `MCPAuthContext` with
  `user_id=str(key.created_by_user_id)` and `tenant_id=str(key.tenant_id)`.
  The context is set on the `_mcp_auth_context_var` ContextVar for downstream tools.

  **Tests to verify:**
  - `test_sets_auth_context_on_valid_key` — auth context set with correct fields
  - `test_auth_context_has_correct_fields` — user_id comes from `created_by_user_id`
  - `test_api_key_takes_precedence_over_bearer` — API key checked before Bearer token

  ### Scenario: Bearer token authentication
  > GIVEN a valid `Authorization: Bearer` header (and no API key)
  > WHEN the MCP request is processed
  > THEN the JWT is validated
  > AND the tenant is resolved from the `X-Tenant-ID` header

  **Implementation:** `MCPApiKeyAuthMiddleware._authenticate_bearer()` reads
  the `X-Tenant-ID` header from scope and calls `validate_bearer_token(token, tenant_id)`.
  On success it builds an `MCPAuthContext` with `api_key_id="bearer"`.

  **Tests to verify:**
  - `test_falls_back_to_bearer_when_api_key_missing` — Bearer used when no API key
  - `test_bearer_returns_401_when_token_invalid` — invalid Bearer → 401

  **Gap to check:** Is there a test confirming the `X-Tenant-ID` header value is
  passed to the validator? If not, add it.

  ### Scenario: No credentials
  > GIVEN a request with no authentication headers
  > WHEN the MCP request is processed
  > THEN a 401 response is returned

  **Implementation:** If neither `X-API-Key` nor `Authorization: Bearer` is present,
  `MCPApiKeyAuthMiddleware.__call__()` calls `_send_json_error(send, 401, ...)`.
  The response includes `WWW-Authenticate: ApiKey realm="kartograph"`.

  **Tests to verify:**
  - `test_returns_401_when_header_missing` — missing both headers → 401
  - `test_no_bearer_validator_returns_401_as_before` — backward compat when
    `validate_bearer_token=None`

  ### Scenario: Authentication service unavailable
  > GIVEN a request when the authentication backend is unreachable
  > WHEN the MCP request is processed
  > THEN a 503 response is returned

  **Implementation:** `_authenticate_api_key()` wraps `validate_api_key()` in a
  `try/except Exception`. Any exception (network error, DB down) triggers
  `_send_json_error(send, 503, "Authentication service temporarily unavailable")`.
  Same wrapping in `_authenticate_bearer()`.

  **Tests to verify:**
  - `test_returns_503_when_validator_raises` — validator raises → 503

  **Gap to check:** Is there a corresponding 503 test for the Bearer token path when
  `validate_bearer_token` raises? If not, add `test_returns_503_when_bearer_validator_raises`.

  ## Files Affected

  No implementation changes expected. Potential test additions only:

  - `src/api/tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py`
    — add missing scenario tests if the gap check above reveals any

  ## How to Verify

  1. Run: `cd src/api && uv run pytest tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py -v`
  2. All 17 (or more) tests pass.
  3. Manually trace each spec scenario line to the corresponding test assertion.
  4. If the `X-Tenant-ID` passthrough test is missing, add it and confirm it passes.
  5. If the Bearer 503 test is missing, add it and confirm it passes.

  ## Design Context

  - `MCPApiKeyAuthMiddleware` is framework-agnostic ASGI middleware — it does not
    import FastAPI. This keeps the shared kernel decoupled from the presentation layer.
  - The middleware injects `MCPAuthContext` into a `ContextVar`, which MCP tools
    retrieve via `get_mcp_auth_context()`.
  - The `api_key_id="bearer"` sentinel in the Bearer auth path distinguishes API-key
    sessions from Bearer-token sessions for observability without a type field.
  - The `WWW-Authenticate` header on 401 responses follows RFC 9110 §11.6.1.

  ## Gap Analysis

  Task-038 was the original task for MCP authentication, but it references
  `specs/shared-kernel/tenant-context.spec.md`, not `specs/query/mcp-server.spec.md`.
  All previous mcp-server.spec.md tasks (task-011, task-085, task-086, task-089,
  task-091, task-092) covered other requirements. This task provides spec traceability
  for the MCP Authentication requirement and prompts the agent to check for any
  missing test coverage in the Bearer token error paths.
---
