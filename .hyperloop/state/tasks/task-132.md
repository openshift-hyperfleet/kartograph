---
id: task-132
title: "MCP query_graph — HTTP integration test for timeout error response format"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add HTTP integration test for query_graph timeout error response"
pr_description: |
  ## What and Why

  The MCP server spec requires that a query exceeding the timeout is terminated
  and returned with `error_type: "timeout"`. The query-execution spec further
  requires a `correlation_id` in the timeout error for debugging.

  ### Existing coverage

  The unit test pyramid covers this scenario at each layer in isolation:

  - `test_query_repository.py::TestExecuteCypher::test_timeout_raises_query_timeout_error`
    — repository raises `QueryTimeoutError` when PostgreSQL cancels the statement.
  - `test_query_repository.py::TestExecuteCypher::test_timeout_error_has_correlation_id`
    — `QueryTimeoutError` carries a `correlation_id`.
  - `test_application_services.py::test_execute_cypher_query_timeout_error`
    — `MCPQueryService` converts `QueryTimeoutError` → `QueryError(error_type="timeout")`.
  - `test_mcp_query_tool.py::TestBuildErrorResponseTimeoutErrors`
    — `_build_error_response` serialises `correlation_id` when present.
  - `test_query_mcp.py::test_timeout_enforcement`
    — end-to-end integration against a real AGE database (uses `pg_sleep`).

  ### The gap

  There is no **HTTP-level integration test** that exercises the full MCP
  JSON-over-HTTP transport layer for the timeout path. This is the same gap
  `test_query_mcp_http.py` was created to fill for the forbidden query path — a
  regression in `mcp.py`'s `_build_error_response` (e.g., dropping `correlation_id`
  from the timeout branch) or a FastMCP serialisation change would be invisible to
  the existing tests.

  `test_query_mcp_http.py` already covers the forbidden path at HTTP level. The
  timeout scenario deserves the same treatment.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **Requirement: Graph Query Tool — Scenario: Query timeout**:
    "GIVEN a query that exceeds the timeout (default 30 seconds, max 60 seconds)
    WHEN the query is executed
    THEN it is terminated and returned with error type 'timeout'"

  `specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`:

  - **Requirement: Timeout Enforcement — Scenario: Query exceeds timeout**:
    "THEN a timeout error is returned with a correlation ID for debugging"
  - **Requirement: Error Categorization — Scenario: Timeout error**:
    "GIVEN a query that exceeds the timeout
    THEN the error type is 'timeout'"

  ## What This Change Does

  Adds two new tests to `src/api/tests/integration/test_query_mcp_http.py`
  (extending the existing class and fixture pattern in that file):

  ### `TestMCPTimeoutQueryHTTPResponse`

  **`test_timeout_query_error_type_is_timeout`**

  1. Provision a tenant AGE graph (using the `provisioned_tenant_graph` fixture).
  2. Create an API key for authentication.
  3. Send a `query_graph` call via the MCP HTTP transport with `timeout_seconds=1`
     and a query that reliably takes longer than 1 second (e.g., a Cartesian product
     with enough pre-loaded nodes: `MATCH (a), (b), (c) RETURN a, b, c`).
  4. Assert `result["success"] is False`.
  5. Assert `result["error_type"] == "timeout"`.

  **`test_timeout_query_response_includes_correlation_id`**

  1. Same setup as above.
  2. Assert `"correlation_id" in result` and the value is a non-empty string.

  Both tests follow the fixture pattern established in `test_query_mcp_http.py`
  (ASGI lifespan, `fastmcp.Client` over `StreamableHttpTransport`,
  `AGEGraphProvisioner` for test graph setup).

  ## Files / Areas Affected

  - `src/api/tests/integration/test_query_mcp_http.py` — two new test methods
    in a new `TestMCPTimeoutQueryHTTPResponse` class

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_query_mcp_http.py -v -m integration
  ```

  All tests (existing forbidden tests + new timeout tests) must pass.

  ## Implementation Notes for the Agent

  - Pass `timeout_seconds=1` to force the shortest timeout that the
    `_clamp_query_params` helper will accept.
  - A Cartesian product query (`MATCH (a), (b), (c) RETURN a, b, c`) is a reliable
    way to cause a timeout when the graph has ≥ 50–100 nodes. Pre-load enough nodes
    in the test fixture to ensure the query consistently exceeds 1 second.
  - Alternatively, use `SET LOCAL statement_timeout = 1` at the SQL level via a
    fixture that patches the timeout — but a real execution is preferred.
  - Write the tests FIRST (TDD). If they fail because the query completes within
    1 second, increase the node count in the fixture until the timeout is reliable.
  - Do not modify `test_query_mcp.py::test_timeout_enforcement` — keep the new
    HTTP-level tests in `test_query_mcp_http.py` for consistency.

  ## Caveats

  - Timeout tests are inherently sensitive to test environment speed.
    Use a small explicit `statement_timeout` SQL override if the Cartesian
    product approach is flaky on fast machines.
  - Do not decrease `timeout_seconds` below 1 — the tool clamps it at 1 s
    minimum (the `_clamp_query_params` lower bound is caller-controlled and
    currently unclamped, but the test should not rely on sub-second values).
---
