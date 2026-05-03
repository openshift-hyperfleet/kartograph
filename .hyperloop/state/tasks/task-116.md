---
id: task-116
title: "query_graph MCP tool — unit tests for success-path response format and secure-enclave wiring"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add unit tests for query_graph tool success path and secure enclave wiring"
pr_description: |
  ## What & Why

  `specs/query/mcp-server.spec.md` defines three scenarios under the
  **Graph Query Tool** requirement that are only partially covered at the
  tool layer today:

  > **Scenario: Successful query**
  > GIVEN an authenticated MCP client
  > WHEN the client calls `query_graph` with a valid Cypher query
  > THEN the query executes against the caller's tenant graph
  > AND the results are returned with rows, row count, truncation flag,
  > and execution time

  > **Scenario: Secure enclave redaction**
  > GIVEN query results containing entities the caller is not authorized to view
  > WHEN the results are returned
  > THEN unauthorized nodes are redacted to ID-only (all other properties stripped)
  > AND unauthorized edges are redacted to their ID, start_id, and end_id only
  > AND the graph topology is preserved

  > **Scenario: Internal property filtering**
  > GIVEN query results containing internal properties (e.g., `all_content_lower`)
  > WHEN the results are returned to the client
  > THEN internal properties are stripped from the response

  ### What is tested today

  Each _component_ in the `query_graph` execution chain has thorough tests:
  - `MCPQueryService.execute_cypher_query()` → `test_mcp_query_service.py`
  - `_filter_by_knowledge_graph()` → `test_mcp_tools.py`
  - `MCPQuerySecureEnclave.apply_redaction()` → `test_mcp_secure_enclave.py`
  - `_filter_internal_properties()` → `test_mcp_query_tool.py`
  - `_build_error_response()` (error path) → `test_mcp_query_tool.py`

  ### What is NOT tested

  The **wiring** of the success path inside `query_graph` itself is untested:

  1. **Response format** — no test asserts the success dict contains
     `success=True`, `rows`, `row_count`, `truncated`, and `execution_time_ms`.
     If someone accidentally dropped `execution_time_ms` or renamed `row_count`,
     no test would catch it.

  2. **Secure enclave call** — no test verifies that `query_graph` actually calls
     `secure_enclave.apply_redaction(rows)` on the service result. If that line
     were removed, every `MCPQuerySecureEnclave` unit test would still pass —
     the data would just be silently unredacted. This is a spec-breaking regression
     with no safety net.

  3. **Internal-property filter call** — no test verifies that
     `_filter_internal_properties` is applied to the rows _after_ redaction.
     The ordering (redact → strip) is correct but untested at the integration level.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:
  - **Graph Query Tool — Scenario: Successful query**: response carries rows,
    row_count, truncated, execution_time_ms with `success=True`.
  - **Graph Query Tool — Scenario: Secure enclave redaction**: `query_graph` calls
    `apply_redaction` and returns the redacted output to callers.
  - **Graph Query Tool — Scenario: Internal property filtering**: `query_graph` calls
    `_filter_internal_properties` and strips internal keys before returning results.

  ## What This Change Does

  Add a new test file `src/api/tests/unit/query/test_mcp_query_tool_wiring.py` (or
  extend `test_mcp_query_tool.py`) with tests that exercise the **full success branch**
  of `query_graph` by patching its dependencies.

  Because `query_graph` is wrapped by `@mcp.tool`, its underlying callable is exposed
  via `.fn`. Tests call `await query_graph.fn(...)` directly, injecting fakes/mocks
  for the FastMCP `Depends` arguments and patching the module-level callables.

  ### Approach

  ```python
  import query.presentation.mcp as mcp_module

  async def test_success_response_format():
      fake_service = FakeMCPQueryService(result=CypherQueryResult(
          rows=[{"value": 42}],
          row_count=1,
          truncated=False,
          execution_time_ms=12.5,
      ))
      fake_enclave = FakePassthroughEnclave()

      with (
          patch.object(mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave),
      ):
          result = await query_graph.fn(
              cypher="MATCH (n) RETURN count(n)",
              service=fake_service,
          )

      assert result["success"] is True
      assert result["row_count"] == 1
      assert result["truncated"] is False
      assert result["execution_time_ms"] == 12.5
      assert result["rows"] == [{"value": 42}]
  ```

  ### Tests to add

  **`TestQueryGraphToolSuccessPath`**
  - `test_success_response_contains_all_required_fields` — the dict has
    `success`, `rows`, `row_count`, `truncated`, `execution_time_ms`.
  - `test_success_flag_is_true` — `result["success"] is True`.
  - `test_row_count_matches_rows_length` — `row_count == len(rows)`.
  - `test_truncated_forwarded_from_service_result` — `truncated` is taken from
    `CypherQueryResult.truncated`, not computed.
  - `test_execution_time_ms_forwarded_from_service_result` — same for `execution_time_ms`.

  **`TestQueryGraphToolSecureEnclaveWiring`**
  - `test_apply_redaction_called_on_service_result_rows` — patch `get_mcp_secure_enclave`
    to return a recording enclave; assert `apply_redaction` was called with the rows
    returned by the service.
  - `test_apply_redaction_called_before_internal_property_filter` — the rows passed to
    `_filter_internal_properties` are the POST-redaction rows, not the raw rows.
  - `test_redacted_rows_returned_not_raw_rows` — when the enclave redacts a node, the
    returned dict contains the redacted version.

  **`TestQueryGraphToolInternalPropertyFilterWiring`**
  - `test_internal_properties_stripped_from_success_response` — patch the service to
    return a row with `all_content_lower`; assert the key is absent from the tool
    response.
  - `test_filter_applied_after_kg_filter` — rows filtered by KG ID are then passed
    through `_filter_internal_properties`.

  ## Files / Areas Affected

  - `src/api/tests/unit/query/test_mcp_query_tool_wiring.py` (new) — all tests above
  - No production code changes expected

  ## Tests

  Pure unit tests — no infrastructure required:

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_mcp_query_tool_wiring.py -v
  ```

  ## How to Verify

  1. Run the new tests and confirm they pass.
  2. Temporarily remove the `rows = await secure_enclave.apply_redaction(rows)` line
     in `query/presentation/mcp.py` and confirm
     `test_apply_redaction_called_on_service_result_rows` fails — proves the test is
     not a false positive.
  3. Temporarily change `"row_count": len(filtered_rows)` to `"row_count": 0` and
     confirm `test_row_count_matches_rows_length` fails.

  ## Caveats

  - `query_graph` is an `async def` function decorated with `@mcp.tool`.  FastMCP
    exposes the underlying callable via the `.fn` attribute (a `FunctionTool` or
    similar descriptor). Tests should call `await query_graph.fn(...)` and inject
    the `service` argument directly to bypass the `Depends` resolution.
  - `get_mcp_secure_enclave()` is called _inside_ the tool function, not injected via
    FastMCP's `Depends`. Patch it at the module level:
    `patch.object(mcp_module, "get_mcp_secure_enclave", ...)`.
  - The `get_mcp_auth_context()` call in `get_accessible_knowledge_graphs()` is not
    relevant for `query_graph` — no auth-context patching is needed for these tests.
  - Keep fakes consistent with the project's "fakes over mocks" testing philosophy:
    `FakeMCPQueryService` should implement `IQueryGraphRepository`-aware fake patterns
    rather than using `MagicMock`.
---
