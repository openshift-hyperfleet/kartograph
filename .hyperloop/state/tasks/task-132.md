---
id: task-132
title: MCP query_graph — HTTP integration test for timeout error response format
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: merge
deps: []
round: 0
branch: hyperloop/task-132
pr: https://github.com/openshift-hyperfleet/kartograph/pull/599
pr_title: 'test(query): add HTTP integration test for query_graph timeout error response'
pr_description: "## What and Why\n\nThe MCP server spec requires that a query exceeding\
  \ the timeout is terminated\nand returned with `error_type: \"timeout\"`. The spec\
  \ also requires (via\n`query-execution.spec.md`) that the timeout error includes\
  \ a `correlation_id`\nfor debugging cross-reference.\n\n### Existing coverage\n\n\
  The unit test pyramid covers this scenario at each layer in isolation:\n\n- `test_query_repository.py::TestExecuteCypher::test_timeout_raises_query_timeout_error`\n\
  \  — repository raises `QueryTimeoutError` when PostgreSQL cancels the statement.\n\
  - `test_query_repository.py::TestExecuteCypher::test_timeout_error_has_correlation_id`\n\
  \  — `QueryTimeoutError` carries a `correlation_id`.\n- `test_application_services.py::test_execute_cypher_query_timeout_error`\n\
  \  — `MCPQueryService` converts `QueryTimeoutError` → `QueryError(error_type=\"\
  timeout\")`.\n- `test_mcp_query_tool.py::TestBuildErrorResponse*`\n  — `_build_error_response`\
  \ serialises `correlation_id` when present.\n- `test_query_mcp.py::test_timeout_enforcement`\n\
  \  — end-to-end integration against a real AGE database (uses `pg_sleep`).\n\n###\
  \ The gap\n\nThere is no **HTTP-level integration test** that exercises the full\
  \ MCP\nJSON-over-HTTP transport layer for the timeout path. This is the same\ngap\
  \ that `test_query_mcp_http.py` was created to fill for the forbidden\nquery path\
  \ — a regression in `mcp.py`'s `_build_error_response` (e.g.,\ndropping `correlation_id`\
  \ from the timeout branch) or a FastMCP\nserialisation change would be invisible\
  \ to the existing tests.\n\n`test_query_mcp_http.py` explicitly notes this rationale\
  \ (see its module\ndocstring) and adds `test_forbidden_query_response_includes_correlation_id`\n\
  and `test_forbidden_query_error_type_is_forbidden`. The timeout scenario\ndeserves\
  \ the same treatment.\n\n## Spec Requirements Satisfied\n\n`specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:\n\
  \n- **Requirement: Graph Query Tool — Scenario: Query timeout**:\n  \"GIVEN a query\
  \ that exceeds the timeout (default 30 seconds, max 60 seconds)\n  WHEN the query\
  \ is executed\n  THEN it is terminated and returned with error type 'timeout'\"\n\
  \n`specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`:\n\
  \n- **Requirement: Timeout Enforcement — Scenario: Query exceeds timeout**:\n  \"\
  THEN a timeout error is returned with a correlation ID for debugging\"\n\n- **Requirement:\
  \ Error Categorization — Scenario: Timeout error**:\n  \"GIVEN a query that exceeds\
  \ the timeout\n  THEN the error type is 'timeout'\"\n\n## What This Change Does\n\
  \nAdds two new tests to `src/api/tests/integration/test_query_mcp_http.py`\n(extending\
  \ the existing class/fixture pattern in that file):\n\n### `test_timeout_query_error_type_is_timeout`\n\
  \n1. Send a Cypher query via the MCP HTTP transport that is guaranteed to\n   exceed\
  \ the timeout. The simplest approach is to use `CALL pg_sleep(n)`\n   within AGE\
  \ and set the `timeout_seconds` parameter to 1 (minimum):\n   ```\n   MATCH (n)\
  \ WHERE 1 = pg_sleep(5) RETURN n\n   ```\n   (or the equivalent mechanism for AGE\
  \ to call `pg_sleep`).\n   Alternatively, patch the database-level timeout to a\
  \ very low value\n   (e.g., 10 ms) and run any query that requires table access.\n\
  2. Inspect the MCP tool result JSON.\n3. Assert `result[\"error_type\"] == \"timeout\"\
  `.\n\n### `test_timeout_query_response_includes_correlation_id`\n\n1. Trigger the\
  \ same timeout scenario.\n2. Assert `\"correlation_id\" in result` and that the\
  \ value is a non-empty\n   UUID string (matches `[0-9a-f-]{36}`).\n\nBoth tests\
  \ follow the fixture pattern established in\n`test_query_mcp_http.py` (ASGI lifespan,\
  \ `fastmcp.Client` over\n`StreamableHttpTransport`, `AGEGraphProvisioner` for test\
  \ graph setup).\n\n## Files / Areas Affected\n\n- `src/api/tests/integration/test_query_mcp_http.py`\
  \ — two new test methods added\n\n## How to Verify\n\n```bash\nmake instance-up\n\
  source .instances/$(basename $(pwd))/.env.instance\ncd src/api && uv run pytest\
  \ tests/integration/test_query_mcp_http.py -v -m integration\n```\n\nAll tests (existing\
  \ forbidden tests + new timeout tests) must pass.\n\n## Implementation Notes for\
  \ the Agent\n\n- The `timeout_seconds` parameter accepted by the `query_graph` tool\
  \ is\n  clamped to `min(requested, 60)`. Pass `timeout_seconds=1` to force the\n\
  \  shortest allowed timeout.\n- Apache AGE does not expose `pg_sleep` natively in\
  \ Cypher. Use a\n  PostgreSQL-level approach: set `SET LOCAL statement_timeout =\
  \ 1` via\n  SQL before executing the Cypher query, or use the fact that the\n  repository\
  \ already sets `SET LOCAL statement_timeout = {timeout_seconds * 1000}`.\n  With\
  \ `timeout_seconds=1` (1000 ms) this gives a 1-second window.\n- For a query that\
  \ reliably times out in 1 second, consider a Cartesian\n  product query against\
  \ a reasonably-sized graph: `MATCH (a), (b), (c) RETURN a, b, c`.\n  Pre-load enough\
  \ nodes (≥ 100) so the cross-product exceeds 1 second.\n- Alternatively, bypass\
  \ AGE entirely and patch the repository's\n  `_client.transaction()` to simulate\
  \ a timeout exception — but a real\n  integration test is preferable per the project's\
  \ integration test philosophy.\n- Write tests FIRST (TDD), then adjust the test\
  \ graph population if the\n  query does not reliably time out.\n\n## Caveats\n\n\
  - Timeout tests are inherently sensitive to test environment speed.\n  Use a timeout\
  \ of 10 ms (not 1 s) if the environment is fast enough\n  to run any non-trivial\
  \ query within 1 s. Adjust the pre-populated node\n  count to ensure the query reliably\
  \ exceeds the timeout.\n- Do not modify `test_query_mcp.py`'s `test_timeout_enforcement`\
  \ — keep\n  the new HTTP-level tests in `test_query_mcp_http.py` for consistency\n\
  \  with the existing separation of concerns."
---
