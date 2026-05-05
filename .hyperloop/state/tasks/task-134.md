---
id: task-134
title: MCP auth service unavailable → 503 — unit and integration tests
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: implement
deps: []
round: 17
branch: hyperloop/task-134
pr: https://github.com/openshift-hyperfleet/kartograph/pull/603
pr_title: 'test(query): add tests for MCP 503 response when auth backend is unavailable'
pr_description: "## What and Why\n\nThe MCP Server spec requires the system to return\
  \ HTTP 503 when the\nauthentication backend (SpiceDB / the API key validation service)\
  \ is\nunreachable:\n\n> **Scenario: Authentication service unavailable**\n> GIVEN\
  \ a request when the authentication backend is unreachable\n> WHEN the MCP request\
  \ is processed\n> THEN a 503 response is returned\n\nThis behaviour is implemented\
  \ in `MCPApiKeyAuthMiddleware` and the bearer\ntoken validation path, but there\
  \ is no test that drives a request into the\nMCP transport while simulating a downed\
  \ auth backend and asserts the 503\nstatus code comes back.\n\nWithout this test,\
  \ a refactor or dependency upgrade that silently swallows\nbackend errors and returns\
  \ 401/500 instead of 503 would not be caught.\n\n## Spec Requirements Satisfied\n\
  \n`specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`\n\n\
  - **Requirement: MCP Authentication — Scenario: Authentication service\n  unavailable**:\
  \ \"GIVEN a request when the authentication backend is\n  unreachable WHEN the MCP\
  \ request is processed THEN a 503 response is\n  returned\"\n\n## What This Change\
  \ Does\n\nAdds tests that verify `MCPApiKeyAuthMiddleware` (and the bearer-token\n\
  path) returns HTTP 503 — not 401, 500, or a raw exception — when\n`validate_api_key`\
  \ / `validate_bearer_token` raise a connectivity error.\n\n### New unit tests (`tests/unit/query/test_mcp_auth_unavailable.py`)\n\
  \n**`test_api_key_validation_backend_error_returns_503`**\n\n- Construct `MCPApiKeyAuthMiddleware`\
  \ with a `validate_api_key` callable\n  that raises a generic connection error (e.g.,\
  \ `httpx.ConnectError` or a\n  plain `Exception(\"backend unavailable\")`).\n- Send\
  \ a fake ASGI request with a valid-looking `X-API-Key` header.\n- Assert the ASGI\
  \ response has `status = 503`.\n\n**`test_bearer_token_backend_error_returns_503`**\n\
  \n- Construct the middleware with a `validate_bearer_token` callable that\n  raises\
  \ a connection error.\n- Send a request with `Authorization: Bearer <token>` and\
  \ no `X-API-Key`.\n- Assert response status is 503.\n\n**`test_transient_backend_error_does_not_expose_internal_details`**\n\
  \n- When the backend raises, the 503 response body must not include raw\n  Python\
  \ exception text or internal stack-trace information.\n\n### Integration test (`tests/integration/test_mcp_auth_503.py`,\
  \ optional)\n\nIf the fake OIDC provider supports forced failures, add a smoke test\
  \ that\nhits the real MCP HTTP endpoint with auth headers while the OIDC/SpiceDB\n\
  connection is broken (or via a stub that raises). This is a stretch goal —\nthe\
  \ unit tests are sufficient to satisfy the spec.\n\n## Files / Areas Affected\n\n\
  - `src/api/tests/unit/query/test_mcp_auth_unavailable.py` — new test file\n- `src/api/shared_kernel/middleware/mcp_api_key_auth.py`\
  \ — may need minor\n  fix if 503 is not currently returned on backend errors (only\
  \ if tests\n  fail; do NOT change if tests pass)\n- `src/api/shared_kernel/middleware/mcp_auth.py`\
  \ — same caveat\n\n## How to Verify\n\n```bash\ncd src/api && uv run pytest tests/unit/query/test_mcp_auth_unavailable.py\
  \ -v\n```\n\nAll tests must pass. If `MCPApiKeyAuthMiddleware` already returns 503,\
  \ the\ntests are green with no production code changes needed — that is the\nexpected\
  \ outcome (tests first, then verify the implementation matches).\n\n## Caveats\n\
  \n- Write tests FIRST (TDD). If the middleware already handles backend errors\n\
  \  correctly, tests pass immediately with no code changes.\n- The middleware wraps\
  \ a Starlette `ASGIApp`; use `httpx.AsyncClient` with\n  `transport=httpx.ASGITransport(app=middleware)`\
  \ for black-box testing\n  without starting a real server.\n- Do not alter the existing\
  \ `test_mcp_auth_wiring.py` tests — they test\n  different contracts (correct credentials\
  \ → correct identity extraction)."
---
