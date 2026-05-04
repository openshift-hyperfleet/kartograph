---
id: task-142
title: "MCP query_graph — HTTP integration test for internal property filtering"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add HTTP integration test for query_graph internal property filtering"
pr_description: |
  ## What and Why

  `specs/query/mcp-server.spec.md` specifies the following for the **Graph Query
  Tool — Scenario: Internal property filtering**:

  > GIVEN query results containing internal properties (e.g., `all_content_lower`)
  > WHEN the results are returned to the client
  > THEN internal properties are stripped from the response

  This scenario is currently tested at two levels:

  - **Unit level** (`test_mcp_query_tool.py`): `_filter_internal_properties()` is
    called directly and asserted to strip `all_content_lower` from flat and nested
    dicts.
  - **Tool wiring level** (`test_mcp_query_tool_wiring.py`): `query_graph.fn()` is
    called directly with a fake `MCPQueryService` that returns rows containing
    `all_content_lower`, and the response is asserted to be clean.

  **What is missing:** no integration test verifies this behaviour end-to-end at the
  **MCP HTTP transport layer**. Specifically, no test:

  1. Inserts a node into the real AGE graph with an `all_content_lower` property.
  2. Queries it via the MCP `query_graph` tool over the full HTTP/ASGI stack.
  3. Asserts that `all_content_lower` is absent from the returned node properties
     in the HTTP response body.

  Without this test, a regression that removes or bypasses the
  `_filter_internal_properties()` call in the HTTP request path (e.g., an accidental
  code restructure that leaves the call inside a branch never exercised by HTTP
  requests) would go undetected. The wiring tests call `query_graph.fn()` with a
  fake service — they do not exercise the ASGI middleware, MCP protocol framing, or
  the real `MCPQueryService` + `QueryGraphRepository` path.

  This is the same class of gap that task-141 closed for the "Successful query
  response shape" scenario.

  ## Spec Requirement Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **Requirement: Graph Query Tool — Scenario: Internal property filtering**
    "GIVEN query results containing internal properties (e.g., `all_content_lower`)
     WHEN the results are returned to the client
     THEN internal properties are stripped from the response"

  ## Key Design Decisions

  This task adds a new test class `TestInternalPropertyFilteringHTTP` to the
  existing `src/api/tests/integration/test_query_mcp_http.py` file (or, if setup
  coupling is significant, a new file
  `tests/integration/query/test_internal_property_filtering_mcp.py`).

  The preferred placement is alongside the existing HTTP tests in
  `test_query_mcp_http.py` because it reuses the same AGE provisioning and API key
  fixture infrastructure.

  ### Test: `test_internal_property_stripped_from_node_in_http_response`

  1. Use the existing fixture infrastructure in `test_query_mcp_http.py`
     (AGEGraphProvisioner, API key creation, `fastmcp.Client` via HTTP).
  2. Insert a node into the tenant AGE graph that includes `all_content_lower`:
     ```cypher
     CREATE (:Person {
       name: 'Alice',
       all_content_lower: 'alice engineer platform team'
     })
     ```
  3. Call the `query_graph` tool with `MATCH (n:Person) RETURN n LIMIT 1` via the
     MCP HTTP client.
  4. Assert `result.is_error is False`.
  5. Assert `tool_result["success"] is True`.
  6. Assert exactly one row is returned.
  7. Extract the node properties from the row (via the `node` key).
  8. Assert `"all_content_lower" not in node_properties`.
  9. Assert `"name" in node_properties` and `node_properties["name"] == "Alice"` —
     confirms non-internal properties are preserved.

  ### Test: `test_internal_property_stripped_from_nested_map_in_http_response`

  1. Same setup.
  2. Call `query_graph` with a map-return query:
     ```cypher
     MATCH (n:Person) RETURN {name: n.name, all_content_lower: n.all_content_lower} AS info
     ```
  3. Assert `"all_content_lower" not in tool_result["rows"][0]["info"]`.
  4. Assert `tool_result["rows"][0]["info"]["name"] == "Alice"`.

  These are **raw HTTP MCP protocol tests** using the existing `fastmcp.Client`
  pattern from `test_query_mcp_http.py`. They verify the full path:
  HTTP request → ASGI middleware (auth) → MCP protocol framing → `query_graph` tool
  → `_filter_internal_properties` → `MCPQueryService` → real AGE graph →
  JSON serialisation → HTTP response.

  ## What Files Are Affected

  **Preferred** (collocated with existing HTTP MCP tests):
  - `src/api/tests/integration/test_query_mcp_http.py` — add
    `TestInternalPropertyFilteringHTTP` class

  **Alternative** (if setup coupling is too heavy):
  - `src/api/tests/integration/query/test_internal_property_filtering_http.py` (new)
  - `src/api/tests/integration/query/__init__.py` (already exists)

  No production code changes are expected. The implementation already strips
  `all_content_lower` correctly.

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_query_mcp_http.py \
      -v -m integration -k "TestInternalPropertyFilteringHTTP"
  ```

  Regression validation:
  1. In `query/presentation/mcp.py`, remove the `_filter_internal_properties(rows)`
     call from the `query_graph` success branch.
  2. `test_internal_property_stripped_from_node_in_http_response` MUST fail
     (`all_content_lower` will be present in the response).
  3. Restore the call — all tests pass.

  ## Implementation Notes

  - Mark tests with `@pytest.mark.asyncio` and `@pytest.mark.integration`.
  - Do NOT mark with `@pytest.mark.keycloak` — API key auth is sufficient.
  - Follow the pattern from `TestQueryGraphSuccessResponse` (task-141) for fixture
    reuse: `AGEGraphProvisioner` to insert nodes, `fastmcp.Client` for HTTP calls.
  - Insert nodes with `all_content_lower` via `AGEGraphProvisioner` or a direct
    AGE `CREATE` executed through the test database connection.
  - The `all_content_lower` property is a real property stored in the AGE graph for
    full-text search optimisation. Nodes inserted by tests may or may not have it;
    this test must explicitly include it to verify stripping.
  - After asserting `all_content_lower` is absent, also assert that `name` and other
    non-internal properties ARE present — this rules out the case where ALL properties
    are accidentally stripped.
  - `execution_time_ms` and response shape assertions from task-141 are NOT required
    here; focus solely on property filtering.

  ## Caveats

  - The test requires a running dev instance (PostgreSQL + SpiceDB + AGE provisioned).
  - Follow the colocation pattern from `TestQueryGraphSuccessResponse` (task-141)
    in `test_query_mcp_http.py` to keep setup consistent across HTTP-level MCP tests.
  - This task does NOT test `_filter_internal_properties` for edge properties or
    map-of-nodes returns — those are covered by unit tests in `test_mcp_query_tool.py`.
    Focus the HTTP integration test on the common case (single node return with
    `all_content_lower`).
  - If `all_content_lower` is not stored on real nodes during tests (because test
    data does not include it), the regression gate is still valid: the test will only
    fail if the property is present in the response, which can only happen if the node
    had it AND filtering was skipped.
---
