---
id: task-140
title: "MCP endpoint — HTTP integration test for no-credentials 401 response"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add HTTP integration test for MCP no-credentials 401 response"
pr_description: |
  ## What and Why

  The MCP Authentication requirement in `specs/query/mcp-server.spec.md` specifies
  four authentication scenarios. Three are already tracked by existing tasks:

  - **API key authentication** — implicitly covered by all MCP HTTP tests that use
    `X-API-Key` (e.g., `test_query_mcp_http.py`, `test_secure_enclave_mcp.py`).
  - **Bearer token authentication** — task-130 (not-started).
  - **Authentication service unavailable (503)** — task-130 (not-started).

  The **fourth scenario is completely uncovered at the HTTP transport level**:

  > **Scenario: No credentials**
  > - GIVEN a request with no authentication headers
  > - WHEN the MCP request is processed
  > - THEN a 401 response is returned

  The `MCPApiKeyAuthMiddleware` implements this correctly at line 163:
  `await self._send_json_error(send, 401, "X-API-Key header is required")`.
  The middleware unit test (`test_mcp_auth_wiring.py`) only checks
  `isinstance(query_mcp_app, MCPApiKeyAuthMiddleware)` — it does not verify
  the 401 HTTP response when credentials are absent. No integration test sends
  a raw HTTP request to `/query/mcp` without auth headers and asserts the
  response status code.

  Without this test, a regression in `MCPApiKeyAuthMiddleware.__call__` that
  accidentally calls the inner app before authentication (allowing unauthenticated
  access) would go undetected until a security review or production incident.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **Requirement: MCP Authentication — Scenario: No credentials**
    "GIVEN a request with no authentication headers
     WHEN the MCP request is processed
     THEN a 401 response is returned"

  ## Key Design Decisions

  This task creates a new test class in an existing or new test file within
  `tests/integration/` or `tests/integration/query/`. The simplest placement
  is alongside the existing MCP auth tests, or as a new file
  `tests/integration/query/test_mcp_auth_http.py`.

  ### Test: `test_no_credentials_returns_401`

  1. Start the Kartograph app in-process via `LifespanManager(app)`.
  2. Create an `httpx.AsyncClient` with `ASGITransport(app=app)`.
  3. Send a `POST /query/mcp` (or `GET /query/mcp`) **without** any
     `X-API-Key` or `Authorization` header.
  4. Assert `response.status_code == 401`.
  5. Assert the response body contains a non-empty `error` or `message` field
     (confirms a structured error, not a crash).

  ### Additional test: `test_invalid_api_key_returns_401`

  1. Same setup.
  2. Send a request with `X-API-Key: invalid-garbage-key`.
  3. Assert `response.status_code == 401`.
  4. This verifies the middleware does not leak stack traces for bad keys.

  These are **raw HTTP tests** (not MCP protocol tests via `fastmcp.Client`).
  The goal is to verify the ASGI middleware behavior at the HTTP response layer,
  not the tool-call response format. Use `httpx.AsyncClient` directly.

  ## What Files Are Affected

  **Option A** (preferred — collocated with existing MCP auth tests):
  - `src/api/tests/integration/query/test_mcp_auth_http.py` (new)
  - `src/api/tests/integration/query/__init__.py` (already exists)

  **Option B** (if it fits better with existing patterns):
  - Add a new class to `src/api/tests/integration/test_auth_enforcement.py`

  No production code changes are expected. The middleware already implements
  the correct behavior.

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/query/test_mcp_auth_http.py \
      -v -m integration
  ```

  Regression validation:
  1. In `MCPApiKeyAuthMiddleware.__call__`, remove the final
     `await self._send_json_error(send, 401, "X-API-Key header is required")` line
     (or replace it with a pass to the inner app).
  2. `test_no_credentials_returns_401` MUST fail (response will be 200 or 500,
     not 401).
  3. Restore the line — all tests pass.

  ## Implementation Notes

  - Mark tests with `@pytest.mark.asyncio` and `@pytest.mark.integration`.
  - Do NOT mark with `@pytest.mark.keycloak` — these tests don't need a real
    OIDC provider (they're testing the no-credentials path, not Bearer token).
  - The `async_client` fixture from `conftest.py` wraps the full app via
    `LifespanManager` and `ASGITransport`. Use it if already available in
    the integration conftest, or define a local version.
  - For the "invalid API key → 401" test, the API key validation backend
    (PostgreSQL) must be running. Use the `@pytest.mark.integration` marker
    to gate it on the dev instance.
  - The 401 response body from `MCPApiKeyAuthMiddleware._send_json_error` is
    a JSON object with an `"error"` key. Assert the body is parseable as JSON
    and the error field is non-empty.

  ## Caveats

  - The `/query/mcp` endpoint path may vary depending on how the MCP app is
    mounted in `main.py`. Verify the path (likely `/query/mcp`) before sending
    requests.
  - The MCP HTTP transport expects POST requests with a JSON body. The middleware
    runs before MCP protocol parsing, so any HTTP method will exercise the auth
    check. A simple GET or POST with no body is sufficient to test the 401 path.
---
