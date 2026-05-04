---
id: task-149
title: "Add tests for MCP auth 503 (authentication service unavailable) scenario"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add 503 coverage for MCP auth service unavailable scenario"
pr_description: |
  ## What and Why

  The MCP server spec requires that when the authentication backend is
  unreachable, the server returns a 503 response:

  > **Requirement: MCP Authentication**
  > **Scenario: Authentication service unavailable**
  > "GIVEN a request when the authentication backend is unreachable
  >  WHEN the MCP request is processed
  >  THEN a 503 response is returned"

  `MCPApiKeyAuthMiddleware` correctly implements this — both the API-key
  path (`_authenticate_api_key`) and the Bearer-token path
  (`_authenticate_bearer`) catch all exceptions from their validation
  callables and return a 503 JSON error:

  ```python
  # src/api/shared_kernel/middleware/mcp_api_key_auth.py
  except Exception as exc:
      self._probe.mcp_auth_validation_error(error=str(exc))
      await self._send_json_error(send, 503, "Authentication service temporarily unavailable")
  ```

  However, no test exercises this path. The existing integration tests in
  `tests/integration/query/test_mcp_auth_http.py` cover 401 (no
  credentials) and 401 (invalid API key), but the 503 case is absent.

  A regression that removes the `try/except` or changes the status code
  would go undetected, and a failing auth backend would silently return
  unexpected responses to MCP clients.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`

  - **Requirement: MCP Authentication — Scenario: Authentication service unavailable**
    "GIVEN a request when the authentication backend is unreachable
     WHEN the MCP request is processed
     THEN a 503 response is returned"

  ## Key Design Decisions

  **Unit tests are preferred over integration tests here.** The 503 path
  is triggered by an exception inside the validation callable — this is
  straightforward to inject in a unit test without needing a live
  PostgreSQL or Keycloak instance.

  Two separate test classes should cover the two middleware paths:

  1. **API key path**: Inject a `validate_api_key` callable that raises an
     exception (e.g., `asyncpg.TooManyConnectionsError`) — assert 503.

  2. **Bearer token path**: Inject a `validate_bearer_token` callable that
     raises an exception — assert 503.

  Each class should verify:
  - HTTP status code is 503
  - Response body is JSON with a non-empty `error` field
  - The error message is not a raw traceback (structured error, not crash)

  The tests should live in a new file:
  `src/api/tests/unit/shared_kernel/middleware/test_mcp_api_key_auth_503.py`

  OR they can be added to an existing middleware test file if one exists
  for `MCPApiKeyAuthMiddleware`.

  Use `pytest.mark.asyncio` and a raw ASGI test harness (construct minimal
  `scope`, `receive`, `send` callables directly — no FastAPI/httpx needed
  for these pure ASGI middleware unit tests).

  ## What Files Are Affected

  - **New file** (or additions to existing):
    `src/api/tests/unit/shared_kernel/middleware/test_mcp_api_key_auth_503.py`
    — unit tests for the 503 path via exception injection

  - No changes to implementation files — the middleware already correctly
    implements 503; only tests are missing.

  ## How to Verify

  ```bash
  cd src/api && uv run pytest tests/unit/shared_kernel/middleware/ -v -k "503"
  ```

  All new tests must pass. Additionally run the full unit suite to confirm
  no regressions:

  ```bash
  make test-unit
  ```

  ## Caveats

  - Do NOT add integration tests for the 503 path — they would require
    mocking PostgreSQL connection failures at the infrastructure level,
    which is fragile and adds no coverage value over the unit approach.
  - The `MCPApiKeyAuthMiddleware` is in `shared_kernel`, but the spec
    lives in the `query` context. The tests should sit under
    `shared_kernel/middleware/` to match the implementation location.
  - If a unit test directory for `shared_kernel/middleware/` does not
    yet exist, create it with the required `__init__.py` files.
---
