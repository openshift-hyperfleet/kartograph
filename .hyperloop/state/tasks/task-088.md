---
id: task-088
title: Expose correlation_id in query_graph MCP error responses
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: merge
deps: []
round: 0
branch: hyperloop/task-088
pr: https://github.com/openshift-hyperfleet/kartograph/pull/555
pr_title: 'fix(query): expose correlation_id in query_graph MCP forbidden and timeout
  error responses'
pr_description: "## What & Why\n\nTwo scenarios in `query-execution.spec.md` require\
  \ the error response to include a\ncorrelation ID so MCP consumers (AI agents, integrations)\
  \ can cross-reference\nserver-side log entries without the server needing to expose\
  \ the raw query text:\n\n**Scenario: Keyword blacklist (secondary)**\n> AND the\
  \ error response includes a correlation ID for log lookup\n\n**Scenario: Query exceeds\
  \ timeout**\n> THEN a timeout error is returned with a correlation ID for debugging\n\
  \nThe domain and service layers already generate and carry `correlation_id`:\n-\
  \ `QueryGraphRepository._validate_read_only()` creates a UUID correlation_id and\
  \ sets\n  it on `QueryForbiddenError`.\n- The PostgreSQL timeout path creates a\
  \ correlation_id and sets it on `QueryTimeoutError`.\n- `MCPQueryService.execute_cypher_query()`\
  \ propagates the correlation_id into the\n  returned `QueryError` value object (verified\
  \ by `test_application_services.py`).\n\nHowever, the **MCP presentation layer**\
  \ (`query/presentation/mcp.py`) builds the error\ndict without the `correlation_id`\
  \ field:\n\n```python\n# current — correlation_id is silently dropped\nif isinstance(result,\
  \ QueryError):\n    return {\n        \"success\": False,\n        \"error_type\"\
  : result.error_type,\n        \"message\": result.message,\n    }\n```\n\nThis means\
  \ MCP clients receive a `forbidden` or `timeout` error with no way to locate\nthe\
  \ corresponding redacted server log entry. The correlation_id generated in the\n\
  inner layers is wasted.\n\n## What This PR Does\n\n### 1. Fix `mcp.py` — include\
  \ `correlation_id` in error response\n\n```python\nif isinstance(result, QueryError):\n\
  \    error_response: dict[str, Any] = {\n        \"success\": False,\n        \"\
  error_type\": result.error_type,\n        \"message\": result.message,\n    }\n\
  \    if result.correlation_id is not None:\n        error_response[\"correlation_id\"\
  ] = result.correlation_id\n    return error_response\n```\n\nOnly include the key\
  \ when `correlation_id` is not None (execution errors and unknown\nerrors don't\
  \ generate a correlation_id and should not emit a spurious null).\n\n### 2. Add\
  \ unit tests for `query_graph` error response format\n\nCreate or extend `src/api/tests/unit/query/test_mcp_query_tool.py`:\n\
  \n1. **Forbidden error response includes correlation_id:**\n   Mock `MCPQueryService.execute_cypher_query()`\
  \ to return a `QueryError` with\n   `error_type=\"forbidden\"` and a known `correlation_id`.\
  \ Call `query_graph()` (via\n   direct function call, bypassing FastMCP) and assert\
  \ the returned dict contains\n   `{\"success\": False, \"error_type\": \"forbidden\"\
  , \"correlation_id\": \"<expected-id>\"}`.\n\n2. **Timeout error response includes\
  \ correlation_id:**\n   Same as above with `error_type=\"timeout\"`.\n\n3. **Execution\
  \ error response omits correlation_id key:**\n   Return a `QueryError(error_type=\"\
  execution_error\", correlation_id=None)` and assert\n   `\"correlation_id\"` is\
  \ NOT a key in the response dict (avoids misleading null).\n\n4. **Unknown error\
  \ response omits correlation_id key:**\n   Same pattern for `error_type=\"unknown_error\"\
  `.\n\n5. **Successful response is unchanged:**\n   Verify that a successful `CypherQueryResult`\
  \ return still produces the expected\n   `{\"success\": True, \"rows\": [...], \"\
  row_count\": ..., \"truncated\": ..., \"execution_time_ms\": ...}`\n   with no `correlation_id`\
  \ key.\n\n### 3. Test file location\n\nPlace tests in `src/api/tests/unit/query/test_mcp_query_tool.py`.\n\
  \nThe existing `test_mcp_tools.py` tests private helpers (`_filter_by_knowledge_graph`,\n\
  `_filter_internal_properties`). The new file tests the public `query_graph` function's\n\
  output contract — keeping them separate keeps responsibility clear.\n\n## Files\
  \ Affected\n\n- `src/api/query/presentation/mcp.py` — add `correlation_id` to error\
  \ response dict\n- `src/api/tests/unit/query/test_mcp_query_tool.py` — new test\
  \ file for `query_graph`\n  error response format\n\n## How to Verify\n\n1. Run\
  \ `cd src/api && uv run pytest tests/unit/query/test_mcp_query_tool.py -v`.\n  \
  \ All 5 new tests must pass.\n2. Run `cd src/api && uv run pytest tests/unit/query/\
  \ -v` — no regressions.\n3. Manually: submit a CREATE query to the MCP endpoint\
  \ and confirm the JSON response\n   body contains a `correlation_id` field.\n\n\
  ## Spec Mapping\n\n| Spec scenario | Requirement satisfied |\n|---|---|\n| Keyword\
  \ blacklist — \"error response includes a correlation ID\" | `forbidden` response\
  \ now carries `correlation_id` |\n| Query exceeds timeout — \"timeout error returned\
  \ with correlation ID\" | `timeout` response now carries `correlation_id` |\n\n\
  ## Design Decisions\n\n- **Conditional inclusion**: `correlation_id` is only included\
  \ when non-None. This\n  avoids clients having to handle `null` and keeps the response\
  \ compact for the\n  common `execution_error` case (syntax errors etc.) that don't\
  \ generate correlation IDs.\n- **No breaking change**: Adding a new optional key\
  \ to the error response dict is\n  backwards-compatible. Existing MCP clients that\
  \ don't inspect `correlation_id` are\n  unaffected.\n- **No service-layer change\
  \ needed**: The service and repository layers already\n  generate and carry correlation\
  \ IDs correctly. This is purely a presentation-layer fix.\n\n## Caveats\n\n`query_graph`\
  \ is an async FastMCP tool function decorated with `@mcp.tool`, which\nmakes calling\
  \ it directly in unit tests require care (the `Depends()` injection for\n`MCPQueryService`\
  \ must be bypassed). Use `create_autospec` or a plain mock to\nsubstitute `MCPQueryService`\
  \ and call the underlying function logic directly.\nAlternatively, extract the error-dict\
  \ construction into a small helper function\n(`_build_error_response(result: QueryError)\
  \ -> dict`) and test that helper directly."
---
