---
id: task-134
title: "MCP auth service unavailable → 503 — unit and integration tests"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add tests for MCP 503 response when auth backend is unavailable"
pr_description: |
  ## What and Why

  The MCP Server spec requires the system to return HTTP 503 when the
  authentication backend (SpiceDB / the API key validation service) is
  unreachable:

  > **Scenario: Authentication service unavailable**
  > GIVEN a request when the authentication backend is unreachable
  > WHEN the MCP request is processed
  > THEN a 503 response is returned

  This behaviour is implemented in `MCPApiKeyAuthMiddleware` and the bearer
  token validation path, but there is no test that drives a request into the
  MCP transport while simulating a downed auth backend and asserts the 503
  status code comes back.

  Without this test, a refactor or dependency upgrade that silently swallows
  backend errors and returns 401/500 instead of 503 would not be caught.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`

  - **Requirement: MCP Authentication — Scenario: Authentication service
    unavailable**: "GIVEN a request when the authentication backend is
    unreachable WHEN the MCP request is processed THEN a 503 response is
    returned"

  ## What This Change Does

  Adds tests that verify `MCPApiKeyAuthMiddleware` (and the bearer-token
  path) returns HTTP 503 — not 401, 500, or a raw exception — when
  `validate_api_key` / `validate_bearer_token` raise a connectivity error.

  ### New unit tests (`tests/unit/query/test_mcp_auth_unavailable.py`)

  **`test_api_key_validation_backend_error_returns_503`**

  - Construct `MCPApiKeyAuthMiddleware` with a `validate_api_key` callable
    that raises a generic connection error (e.g., `httpx.ConnectError` or a
    plain `Exception("backend unavailable")`).
  - Send a fake ASGI request with a valid-looking `X-API-Key` header.
  - Assert the ASGI response has `status = 503`.

  **`test_bearer_token_backend_error_returns_503`**

  - Construct the middleware with a `validate_bearer_token` callable that
    raises a connection error.
  - Send a request with `Authorization: Bearer <token>` and no `X-API-Key`.
  - Assert response status is 503.

  **`test_transient_backend_error_does_not_expose_internal_details`**

  - When the backend raises, the 503 response body must not include raw
    Python exception text or internal stack-trace information.

  ### Integration test (`tests/integration/test_mcp_auth_503.py`, optional)

  If the fake OIDC provider supports forced failures, add a smoke test that
  hits the real MCP HTTP endpoint with auth headers while the OIDC/SpiceDB
  connection is broken (or via a stub that raises). This is a stretch goal —
  the unit tests are sufficient to satisfy the spec.

  ## Files / Areas Affected

  - `src/api/tests/unit/query/test_mcp_auth_unavailable.py` — new test file
  - `src/api/shared_kernel/middleware/mcp_api_key_auth.py` — may need minor
    fix if 503 is not currently returned on backend errors (only if tests
    fail; do NOT change if tests pass)
  - `src/api/shared_kernel/middleware/mcp_auth.py` — same caveat

  ## How to Verify

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_mcp_auth_unavailable.py -v
  ```

  All tests must pass. If `MCPApiKeyAuthMiddleware` already returns 503, the
  tests are green with no production code changes needed — that is the
  expected outcome (tests first, then verify the implementation matches).

  ## Caveats

  - Write tests FIRST (TDD). If the middleware already handles backend errors
    correctly, tests pass immediately with no code changes.
  - The middleware wraps a Starlette `ASGIApp`; use `httpx.AsyncClient` with
    `transport=httpx.ASGITransport(app=middleware)` for black-box testing
    without starting a real server.
  - Do not alter the existing `test_mcp_auth_wiring.py` tests — they test
    different contracts (correct credentials → correct identity extraction).
---
