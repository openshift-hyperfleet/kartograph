---
id: task-112
title: 'MCP HTTP-level integration test: correlation_id in forbidden query response
  body'
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: not_started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: 'test(query): add MCP HTTP integration test for correlation_id in forbidden
  query response'
pr_description: "## What & Why\n\nThe `specs/query/query-execution.spec.md` **Keyword\
  \ Blacklist** scenario requires:\n\n> AND the error response includes a correlation\
  \ ID for log lookup\n\nThe implementation satisfies this: `_build_error_response`\
  \ in `query/presentation/mcp.py`\nincludes `correlation_id` in the response dict\
  \ when the `QueryError` carries one, and\n`MCPQueryService` preserves the `correlation_id`\
  \ from `QueryForbiddenError` into the\nreturned `QueryError`.\n\nThe *unit* tests\
  \ verify each layer independently:\n- `test_application_services.py::test_forbidden_error_includes_correlation_id_in_response`\
  \ ✓\n- `test_application_services.py::test_forbidden_error_correlation_id_included_in_probe_call`\
  \ ✓\n- `test_mcp_query_tool.py::TestBuildErrorResponseForbiddenErrors` ✓\n\n**What\
  \ is missing**: an *integration* test at the **MCP HTTP protocol level** — using\n\
  the actual MCP HTTP client against a running API instance — that submits a forbidden\n\
  query and asserts the JSON response body includes `\"correlation_id\"`.\n\nThe existing\
  \ `tests/integration/test_query_mcp.py` works at the `MCPQueryService`\nPython object\
  \ level (it calls `service.execute_cypher_query(...)` directly). It does\nNOT exercise\
  \ the MCP JSON-over-HTTP transport layer. A regression in `mcp.py`'s\n`_build_error_response`\
  \ (e.g., accidentally removing `correlation_id` from the dict)\nor a serialisation\
  \ change in FastMCP would be invisible to the current test suite.\n\n## Spec Requirements\
  \ Satisfied\n\n`specs/query/query-execution.spec.md`:\n- **Requirement: Read-Only\
  \ Enforcement** — Scenario: *Keyword blacklist (secondary)*\n  - \"AND the error\
  \ response includes a correlation ID for log lookup\"\n\n`specs/query/mcp-server.spec.md`\
  \ (same test also covers):\n- **Requirement: Graph Query Tool** — Scenario: *Write\
  \ operation rejected*\n  - \"THEN it is rejected with error type 'forbidden'\"\n\
  \n## What This Change Does\n\nAdd `tests/integration/test_query_mcp_http.py` (or\
  \ extend `test_query_mcp.py`)\nwith an end-to-end HTTP test that:\n\n### Setup\n\
  \n1. Use the isolated dev instance (`make instance-up` / `source .env.instance`).\n\
  2. Obtain an API key for a test user via the IAM API (or use a fixture that already\n\
  \   creates one).\n3. Identify a provisioned tenant AGE graph to route the query\
  \ to (the test user's\n   tenant must have an AGE graph; use the same tenant created\
  \ by the instance).\n\n### Execution\n\nSubmit a forbidden Cypher query to the MCP\
  \ HTTP endpoint using the MCP\nclient protocol:\n\n```\nPOST /mcp\nX-API-Key: <test-api-key>\n\
  Content-Type: application/json\n\n{ \"jsonrpc\": \"2.0\", \"id\": 1, \"method\"\
  : \"tools/call\",\n  \"params\": { \"name\": \"query_graph\",\n              \"\
  arguments\": { \"cypher\": \"CREATE (n:Test)\" } } }\n```\n\nAlternatively, use\
  \ the `fastmcp.Client` Python client to call `query_graph` with a\nforbidden Cypher\
  \ string and inspect the tool result dict.\n\n### Assertions\n\n1. The response\
  \ `success` field is `False`.\n2. The response `error_type` field is `\"forbidden\"\
  `.\n3. The response body contains a `\"correlation_id\"` key.\n4. The `\"correlation_id\"\
  ` value is a non-empty string (UUID format).\n5. The raw query text (`\"CREATE (n:Test)\"\
  `) does NOT appear in the response body.\n\n### Test Location\n\n```\nsrc/api/tests/integration/test_query_mcp_http.py\n\
  ```\n\nMark with `@pytest.mark.integration`. Reuse existing integration fixtures\n\
  (API key creation, tenant graph existence check).\n\n## Files / Areas Affected\n\
  \n- `src/api/tests/integration/test_query_mcp_http.py` (new) — HTTP-level integration\n\
  \  test for forbidden query MCP response\n- No production code changes; this is\
  \ a test-only addition\n- Reuses existing integration infrastructure (`make instance-up`)\n\
  \n## How to Verify\n\n1. `make instance-up` — start isolated test instance\n2. `source\
  \ .instances/$(basename $(pwd))/.env.instance`\n3. `cd src/api && uv run pytest\
  \ tests/integration/test_query_mcp_http.py -v -m integration`\n4. Confirm: `test_forbidden_query_response_includes_correlation_id`\
  \ passes green\n\n## Caveats\n\n- The MCP HTTP endpoint is at `/mcp` (the path configured\
  \ in `mcp.py`). Confirm the\n  path matches the dev instance's routing.\n- Use `fastmcp.Client`\
  \ in HTTP mode to avoid raw JSON-RPC construction; see FastMCP\n  docs for the `stateless_http=True`\
  \ transport.\n- The test must ensure the tenant's AGE graph exists (if not, the\
  \ response will be\n  `error_type=\"execution_error\"` from the graph-not-found\
  \ check, not `\"forbidden\"`).\n  Use the same fixture pattern as `test_query_mcp.py`'s\
  \ `repository_with_data`.\n- The correlation_id UUID is generated at runtime; assert\
  \ the key is present and\n  non-empty, not a specific value."
---
