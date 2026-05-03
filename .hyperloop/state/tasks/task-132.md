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
  and returned with `error_type: "timeout"`. The spec also requires (via
  `query-execution.spec.md`) that the timeout error includes a `correlation_id`
  for debugging cross-reference.

  ### Existing coverage

  The unit test pyramid covers this scenario at each layer in isolation:

  - `test_query_repository.py::TestExecuteCypher::test_timeout_raises_query_timeout_error`
    — repository raises `QueryTimeoutError` when PostgreSQL cancels the statement.
  - `test_query_repository.py::TestExecuteCypher::test_timeout_error_has_correlation_id`
    — `QueryTimeoutError` carries a `correlation_id`.
  - `test_application_services.py::test_execute_cypher_query_timeout_error`
    — `MCPQueryService` converts `QueryTimeoutError` → `QueryError(error_type="timeout")`.
  - `test_mcp_query_tool.py::TestBuildErrorResponse*`
    — `_build_error_response` serialises `correlation_id` when present.
  - `test_query_mcp.py::test_timeout_enforcement`
    — end-to-end integration against a real AGE database (uses `pg_sleep`).

  ### The gap

  There is no **HTTP-level integration test** that exercises the full MCP
  JSON-over-HTTP transport layer for the timeout path. This is the same
  gap that `test_query_mcp_http.py` was created to fill for the forbidden
  query path — a regression in `mcp.py`'s `_build_error_response` (e.g.,
  dropping `correlation_id` from the timeout branch) or a FastMCP
  serialisation change would be invisible to the existing tests.

  `test_query_mcp_http.py` explicitly notes this rationale (see its module
  docstring) and adds `test_forbidden_query_response_includes_correlation_id`
  and `test_forbidden_query_error_type_is_forbidden`. The timeout scenario
  deserves the same treatment.

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
  (extending the existing class/fixture pattern in that file):

  ### `test_timeout_query_error_type_is_timeout`

  1. Send a Cypher query via the MCP HTTP transport that is guaranteed to
     exceed the timeout. The simplest approach is to use `CALL pg_sleep(n)`
     within AGE and set the `timeout_seconds` parameter to 1 (minimum):
     ```
     MATCH (n) WHERE 1 = pg_sleep(5) RETURN n
     ```
     (or the equivalent mechanism for AGE to call `pg_sleep`).
     Alternatively, patch the database-level timeout to a very low value
     (e.g., 10 ms) and run any query that requires table access.
  2. Inspect the MCP tool result JSON.
  3. Assert `result["error_type"] == "timeout"`.

  ### `test_timeout_query_response_includes_correlation_id`

  1. Trigger the same timeout scenario.
  2. Assert `"correlation_id" in result` and that the value is a non-empty
     UUID string (matches `[0-9a-f-]{36}`).

  Both tests follow the fixture pattern established in
  `test_query_mcp_http.py` (ASGI lifespan, `fastmcp.Client` over
  `StreamableHttpTransport`, `AGEGraphProvisioner` for test graph setup).

  ## Files / Areas Affected

  - `src/api/tests/integration/test_query_mcp_http.py` — two new test methods added

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_query_mcp_http.py -v -m integration
  ```

  All tests (existing forbidden tests + new timeout tests) must pass.

  ## Implementation Notes for the Agent

  - The `timeout_seconds` parameter accepted by the `query_graph` tool is
    clamped to `min(requested, 60)`. Pass `timeout_seconds=1` to force the
    shortest allowed timeout.
  - Apache AGE does not expose `pg_sleep` natively in Cypher. Use a
    PostgreSQL-level approach: set `SET LOCAL statement_timeout = 1` via
    SQL before executing the Cypher query, or use the fact that the
    repository already sets `SET LOCAL statement_timeout = {timeout_seconds * 1000}`.
    With `timeout_seconds=1` (1000 ms) this gives a 1-second window.
  - For a query that reliably times out in 1 second, consider a Cartesian
    product query against a reasonably-sized graph: `MATCH (a), (b), (c) RETURN a, b, c`.
    Pre-load enough nodes (≥ 100) so the cross-product exceeds 1 second.
  - Alternatively, bypass AGE entirely and patch the repository's
    `_client.transaction()` to simulate a timeout exception — but a real
    integration test is preferable per the project's integration test philosophy.
  - Write tests FIRST (TDD), then adjust the test graph population if the
    query does not reliably time out.

  ## Caveats

  - Timeout tests are inherently sensitive to test environment speed.
    Use a timeout of 10 ms (not 1 s) if the environment is fast enough
    to run any non-trivial query within 1 s. Adjust the pre-populated node
    count to ensure the query reliably exceeds the timeout.
  - Do not modify `test_query_mcp.py`'s `test_timeout_enforcement` — keep
    the new HTTP-level tests in `test_query_mcp_http.py` for consistency
    with the existing separation of concerns.
---
