---
id: task-093
title: MCP server — MCP Authentication requirement spec alignment
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: spec-review
deps: []
round: 0
branch: hyperloop/task-093
pr: https://github.com/openshift-hyperfleet/kartograph/pull/559
pr_title: 'test(query): verify MCP Authentication scenarios against mcp-server spec'
pr_description: "## What & Why\n\nThe **Requirement: MCP Authentication** in `specs/query/mcp-server.spec.md`\
  \ has\nnever had a hyperloop task created for it. All four scenarios are currently\n\
  implemented in `shared_kernel/middleware/mcp_api_key_auth.py`\n(`MCPApiKeyAuthMiddleware`)\
  \ and tested in\n`tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py`\
  \ (17 tests).\nTask-038 covers this requirement from the *shared-kernel tenant context\
  \ spec*\nperspective; this task provides traceability to the *MCP server spec*.\n\
  \nThe primary goal is to verify line-by-line that every spec scenario is correctly\n\
  implemented **and** adequately tested. If any test is missing or tests the wrong\n\
  thing, add it before closing this task.\n\n## Spec Scenarios\n\n### Scenario: API\
  \ key authentication\n> GIVEN a valid `X-API-Key` header\n> WHEN the MCP request\
  \ is processed\n> THEN the request is authenticated using the API key's creator\
  \ identity\n> AND the tenant is resolved from the API key's tenant scope\n\n**Implementation:**\
  \ `MCPApiKeyAuthMiddleware._authenticate_api_key()` calls\n`validate_api_key(secret)`.\
  \ On success it builds an `MCPAuthContext` with\n`user_id=str(key.created_by_user_id)`\
  \ and `tenant_id=str(key.tenant_id)`.\nThe context is set on the `_mcp_auth_context_var`\
  \ ContextVar for downstream tools.\n\n**Tests to verify:**\n- `test_sets_auth_context_on_valid_key`\
  \ — auth context set with correct fields\n- `test_auth_context_has_correct_fields`\
  \ — user_id comes from `created_by_user_id`\n- `test_api_key_takes_precedence_over_bearer`\
  \ — API key checked before Bearer token\n\n### Scenario: Bearer token authentication\n\
  > GIVEN a valid `Authorization: Bearer` header (and no API key)\n> WHEN the MCP\
  \ request is processed\n> THEN the JWT is validated\n> AND the tenant is resolved\
  \ from the `X-Tenant-ID` header\n\n**Implementation:** `MCPApiKeyAuthMiddleware._authenticate_bearer()`\
  \ reads\nthe `X-Tenant-ID` header from scope and calls `validate_bearer_token(token,\
  \ tenant_id)`.\nOn success it builds an `MCPAuthContext` with `api_key_id=\"bearer\"\
  `.\n\n**Tests to verify:**\n- `test_falls_back_to_bearer_when_api_key_missing` —\
  \ Bearer used when no API key\n- `test_bearer_returns_401_when_token_invalid` —\
  \ invalid Bearer → 401\n\n**Gap to check:** Is there a test confirming the `X-Tenant-ID`\
  \ header value is\npassed to the validator? If not, add it.\n\n### Scenario: No\
  \ credentials\n> GIVEN a request with no authentication headers\n> WHEN the MCP\
  \ request is processed\n> THEN a 401 response is returned\n\n**Implementation:**\
  \ If neither `X-API-Key` nor `Authorization: Bearer` is present,\n`MCPApiKeyAuthMiddleware.__call__()`\
  \ calls `_send_json_error(send, 401, ...)`.\nThe response includes `WWW-Authenticate:\
  \ ApiKey realm=\"kartograph\"`.\n\n**Tests to verify:**\n- `test_returns_401_when_header_missing`\
  \ — missing both headers → 401\n- `test_no_bearer_validator_returns_401_as_before`\
  \ — backward compat when\n  `validate_bearer_token=None`\n\n### Scenario: Authentication\
  \ service unavailable\n> GIVEN a request when the authentication backend is unreachable\n\
  > WHEN the MCP request is processed\n> THEN a 503 response is returned\n\n**Implementation:**\
  \ `_authenticate_api_key()` wraps `validate_api_key()` in a\n`try/except Exception`.\
  \ Any exception (network error, DB down) triggers\n`_send_json_error(send, 503,\
  \ \"Authentication service temporarily unavailable\")`.\nSame wrapping in `_authenticate_bearer()`.\n\
  \n**Tests to verify:**\n- `test_returns_503_when_validator_raises` — validator raises\
  \ → 503\n\n**Gap to check:** Is there a corresponding 503 test for the Bearer token\
  \ path when\n`validate_bearer_token` raises? If not, add `test_returns_503_when_bearer_validator_raises`.\n\
  \n## Files Affected\n\nNo implementation changes expected. Potential test additions\
  \ only:\n\n- `src/api/tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py`\n\
  \  — add missing scenario tests if the gap check above reveals any\n\n## How to\
  \ Verify\n\n1. Run: `cd src/api && uv run pytest tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py\
  \ -v`\n2. All 17 (or more) tests pass.\n3. Manually trace each spec scenario line\
  \ to the corresponding test assertion.\n4. If the `X-Tenant-ID` passthrough test\
  \ is missing, add it and confirm it passes.\n5. If the Bearer 503 test is missing,\
  \ add it and confirm it passes.\n\n## Design Context\n\n- `MCPApiKeyAuthMiddleware`\
  \ is framework-agnostic ASGI middleware — it does not\n  import FastAPI. This keeps\
  \ the shared kernel decoupled from the presentation layer.\n- The middleware injects\
  \ `MCPAuthContext` into a `ContextVar`, which MCP tools\n  retrieve via `get_mcp_auth_context()`.\n\
  - The `api_key_id=\"bearer\"` sentinel in the Bearer auth path distinguishes API-key\n\
  \  sessions from Bearer-token sessions for observability without a type field.\n\
  - The `WWW-Authenticate` header on 401 responses follows RFC 9110 §11.6.1.\n\n##\
  \ Gap Analysis\n\nTask-038 was the original task for MCP authentication, but it\
  \ references\n`specs/shared-kernel/tenant-context.spec.md`, not `specs/query/mcp-server.spec.md`.\n\
  All previous mcp-server.spec.md tasks (task-011, task-085, task-086, task-089,\n\
  task-091, task-092) covered other requirements. This task provides spec traceability\n\
  for the MCP Authentication requirement and prompts the agent to check for any\n\
  missing test coverage in the Bearer token error paths."
---
