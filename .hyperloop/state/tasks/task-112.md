---
id: task-112
title: "MCP HTTP-level integration test: correlation_id in forbidden query response body"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add MCP HTTP integration test for correlation_id in forbidden query response"
pr_description: |
  ## What & Why

  The `specs/query/query-execution.spec.md` **Keyword Blacklist** scenario requires:

  > AND the error response includes a correlation ID for log lookup

  The implementation satisfies this: `_build_error_response` in `query/presentation/mcp.py`
  includes `correlation_id` in the response dict when the `QueryError` carries one, and
  `MCPQueryService` preserves the `correlation_id` from `QueryForbiddenError` into the
  returned `QueryError`.

  The *unit* tests verify each layer independently:
  - `test_application_services.py::test_forbidden_error_includes_correlation_id_in_response` ✓
  - `test_application_services.py::test_forbidden_error_correlation_id_included_in_probe_call` ✓
  - `test_mcp_query_tool.py::TestBuildErrorResponseForbiddenErrors` ✓

  **What is missing**: an *integration* test at the **MCP HTTP protocol level** — using
  the actual MCP HTTP client against a running API instance — that submits a forbidden
  query and asserts the JSON response body includes `"correlation_id"`.

  The existing `tests/integration/test_query_mcp.py` works at the `MCPQueryService`
  Python object level (it calls `service.execute_cypher_query(...)` directly). It does
  NOT exercise the MCP JSON-over-HTTP transport layer. A regression in `mcp.py`'s
  `_build_error_response` (e.g., accidentally removing `correlation_id` from the dict)
  or a serialisation change in FastMCP would be invisible to the current test suite.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md`:
  - **Requirement: Read-Only Enforcement** — Scenario: *Keyword blacklist (secondary)*
    - "AND the error response includes a correlation ID for log lookup"

  `specs/query/mcp-server.spec.md` (same test also covers):
  - **Requirement: Graph Query Tool** — Scenario: *Write operation rejected*
    - "THEN it is rejected with error type 'forbidden'"

  ## What This Change Does

  Add `tests/integration/test_query_mcp_http.py` (or extend `test_query_mcp.py`)
  with an end-to-end HTTP test that:

  ### Setup

  1. Use the isolated dev instance (`make instance-up` / `source .env.instance`).
  2. Obtain an API key for a test user via the IAM API (or use a fixture that already
     creates one).
  3. Identify a provisioned tenant AGE graph to route the query to (the test user's
     tenant must have an AGE graph; use the same tenant created by the instance).

  ### Execution

  Submit a forbidden Cypher query to the MCP HTTP endpoint using the MCP
  client protocol:

  ```
  POST /mcp
  X-API-Key: <test-api-key>
  Content-Type: application/json

  { "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": { "name": "query_graph",
                "arguments": { "cypher": "CREATE (n:Test)" } } }
  ```

  Alternatively, use the `fastmcp.Client` Python client to call `query_graph` with a
  forbidden Cypher string and inspect the tool result dict.

  ### Assertions

  1. The response `success` field is `False`.
  2. The response `error_type` field is `"forbidden"`.
  3. The response body contains a `"correlation_id"` key.
  4. The `"correlation_id"` value is a non-empty string (UUID format).
  5. The raw query text (`"CREATE (n:Test)"`) does NOT appear in the response body.

  ### Test Location

  ```
  src/api/tests/integration/test_query_mcp_http.py
  ```

  Mark with `@pytest.mark.integration`. Reuse existing integration fixtures
  (API key creation, tenant graph existence check).

  ## Files / Areas Affected

  - `src/api/tests/integration/test_query_mcp_http.py` (new) — HTTP-level integration
    test for forbidden query MCP response
  - No production code changes; this is a test-only addition
  - Reuses existing integration infrastructure (`make instance-up`)

  ## How to Verify

  1. `make instance-up` — start isolated test instance
  2. `source .instances/$(basename $(pwd))/.env.instance`
  3. `cd src/api && uv run pytest tests/integration/test_query_mcp_http.py -v -m integration`
  4. Confirm: `test_forbidden_query_response_includes_correlation_id` passes green

  ## Caveats

  - The MCP HTTP endpoint is at `/mcp` (the path configured in `mcp.py`). Confirm the
    path matches the dev instance's routing.
  - Use `fastmcp.Client` in HTTP mode to avoid raw JSON-RPC construction; see FastMCP
    docs for the `stateless_http=True` transport.
  - The test must ensure the tenant's AGE graph exists (if not, the response will be
    `error_type="execution_error"` from the graph-not-found check, not `"forbidden"`).
    Use the same fixture pattern as `test_query_mcp.py`'s `repository_with_data`.
  - The correlation_id UUID is generated at runtime; assert the key is present and
    non-empty, not a specific value.
---
