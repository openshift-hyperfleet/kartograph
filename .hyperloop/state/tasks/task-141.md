---
id: task-141
title: "MCP query_graph — HTTP integration test for successful query response shape"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add HTTP integration test for query_graph successful response shape"
pr_description: |
  ## What and Why

  `specs/query/mcp-server.spec.md` specifies the following for the **Graph Query
  Tool — Scenario: Successful query**:

  > GIVEN an authenticated MCP client
  > WHEN the client calls `query_graph` with a valid Cypher query
  > THEN the query executes against the caller's tenant graph
  > AND the results are returned with **rows, row count, truncation flag, and
  >   execution time**

  The four response fields (`rows`, `row_count`, `truncated`, `execution_time_ms`)
  are tested at the **unit level** in `test_mcp_query_tool_wiring.py`, which
  exercises the `query_graph` function with a `FakeMCPQueryService` and asserts
  that all four keys are present in the returned dict.

  However, no existing test verifies these fields at the **MCP HTTP transport
  layer**. Specifically:

  - `test_query_mcp_http.py` exercises the HTTP path but covers only **error
    responses** (forbidden query, timeout). The success path — where a valid
    Cypher query returns data — is not tested at the HTTP level.
  - `test_query_mcp.py` tests the service and repository layers directly (not
    via the MCP HTTP protocol). It does not exercise the MCP framing layer or
    the `query_graph` tool's JSON serialisation path.

  Without an HTTP-level success test, a regression that breaks the tool's JSON
  serialisation (e.g., renaming a key, omitting `execution_time_ms`, or failing
  to set `success=True`) would not be caught until a real MCP client attempted a
  query.

  ## Spec Requirement Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **Requirement: Graph Query Tool — Scenario: Successful query**
    "THEN the results are returned with rows, row count, truncation flag, and
     execution time"

  ## Key Design Decisions

  This task adds a new test class `TestQueryGraphSuccessResponse` to the existing
  `src/api/tests/integration/test_query_mcp_http.py` file (or a new file
  `tests/integration/query/test_query_mcp_http_success.py`). The simplest
  placement is alongside the existing HTTP tests in `test_query_mcp_http.py`.

  ### Test: `test_successful_query_response_contains_all_required_fields`

  1. Use the existing fixture infrastructure in `test_query_mcp_http.py`
     (AGEGraphProvisioner, API key creation, fastmcp Client via HTTP).
  2. Insert at least one node into the tenant AGE graph.
  3. Call the `query_graph` tool with a valid MATCH query via the MCP client.
  4. Assert `result.is_error is False`.
  5. Assert `tool_result["success"] is True`.
  6. Assert `"rows"` is present and is a list.
  7. Assert `"row_count"` is present and is a non-negative integer.
  8. Assert `"truncated"` is present and is a boolean.
  9. Assert `"execution_time_ms"` is present and is a non-negative number.

  ### Test: `test_successful_empty_query_response_shape`

  1. Same setup but query a graph with no matching nodes (e.g., `MATCH (n:NoSuch) RETURN n`).
  2. Assert `result.is_error is False`.
  3. Assert `tool_result["success"] is True`.
  4. Assert `tool_result["rows"] == []`.
  5. Assert `tool_result["row_count"] == 0`.
  6. Assert `tool_result["truncated"] is False`.
  7. Assert `"execution_time_ms"` is present (non-negative).

  These are **raw HTTP MCP protocol tests** using the existing `fastmcp.Client`
  pattern from `test_query_mcp_http.py`. They verify the full path: HTTP request
  → ASGI middleware (auth) → MCP protocol framing → `query_graph` tool →
  `MCPQueryService` → real AGE graph → JSON serialisation → HTTP response.

  ## What Files Are Affected

  **Preferred** (collocated with existing HTTP MCP tests):
  - `src/api/tests/integration/test_query_mcp_http.py` — add
    `TestQueryGraphSuccessResponse` class

  **Alternative** (if the success path needs its own setup):
  - `src/api/tests/integration/query/test_query_mcp_http_success.py` (new)
  - `src/api/tests/integration/query/__init__.py` (already exists)

  No production code changes are expected. The implementation already produces
  the correct response shape.

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_query_mcp_http.py \
      -v -m integration -k "TestQueryGraphSuccessResponse"
  ```

  Regression validation:
  1. In `query/presentation/mcp.py`, remove `"execution_time_ms"` from the
     success response dict returned by `query_graph`.
  2. `test_successful_query_response_contains_all_required_fields` MUST fail.
  3. Restore the key — all tests pass.

  ## Implementation Notes

  - Mark tests with `@pytest.mark.asyncio` and `@pytest.mark.integration`.
  - Do NOT mark with `@pytest.mark.keycloak` — API key auth is sufficient.
  - The test requires a running dev instance (PostgreSQL + SpiceDB + AGE provisioned
    for the tenant). Follow the pattern from `TestForbiddenQueryResponseFormat` in
    `test_query_mcp_http.py` for fixture reuse.
  - After inserting a node, query it: `MATCH (n) RETURN n LIMIT 1`. The result
    should have exactly 1 row with a `node` key.
  - `row_count` must equal `len(rows)` — assert both values match.
  - `execution_time_ms` should be `>= 0`; do not assert a specific value (CI
    timing is unpredictable).

  ## Caveats

  - The test requires at least one node in the tenant graph. Insert one
    programmatically via `AGEGraphProvisioner` or the IAM/graph API before
    asserting a non-empty result. If inserting is complex, the empty-result
    variant (`test_successful_empty_query_response_shape`) requires no pre-seeded
    data and can run without graph insertion.
  - This task does NOT test the `knowledge_graph_id` filter parameter (covered
    by task-116) or secure enclave redaction (covered by task-133). Focus is
    solely on the response field shape for the happy path.
---
