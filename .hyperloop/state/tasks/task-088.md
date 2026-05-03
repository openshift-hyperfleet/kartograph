---
id: task-088
title: Expose correlation_id in query_graph MCP error responses
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(query): expose correlation_id in query_graph MCP forbidden and timeout error responses"
pr_description: |
  ## What & Why

  Two scenarios in `query-execution.spec.md` require the error response to include a
  correlation ID so MCP consumers (AI agents, integrations) can cross-reference
  server-side log entries without the server needing to expose the raw query text:

  **Scenario: Keyword blacklist (secondary)**
  > AND the error response includes a correlation ID for log lookup

  **Scenario: Query exceeds timeout**
  > THEN a timeout error is returned with a correlation ID for debugging

  The domain and service layers already generate and carry `correlation_id`:
  - `QueryGraphRepository._validate_read_only()` creates a UUID correlation_id and sets
    it on `QueryForbiddenError`.
  - The PostgreSQL timeout path creates a correlation_id and sets it on `QueryTimeoutError`.
  - `MCPQueryService.execute_cypher_query()` propagates the correlation_id into the
    returned `QueryError` value object.

  However, the **MCP presentation layer** (`query/presentation/mcp.py`) builds the error
  dict without the `correlation_id` field:

  ```python
  # current — correlation_id is silently dropped
  if isinstance(result, QueryError):
      return {
          "success": False,
          "error_type": result.error_type,
          "message": result.message,
      }
  ```

  This means MCP clients receive a `forbidden` or `timeout` error with no way to locate
  the corresponding redacted server log entry. The correlation_id generated in the
  inner layers is wasted.

  ## What This PR Does

  ### 1. Fix `mcp.py` — include `correlation_id` in error response

  ```python
  if isinstance(result, QueryError):
      error_response: dict[str, Any] = {
          "success": False,
          "error_type": result.error_type,
          "message": result.message,
      }
      if result.correlation_id is not None:
          error_response["correlation_id"] = result.correlation_id
      return error_response
  ```

  Only include the key when `correlation_id` is not None (execution errors and unknown
  errors don't generate a correlation_id and should not emit a spurious null).

  ### 2. Add unit tests for `query_graph` error response format

  Create `src/api/tests/unit/query/test_mcp_query_tool.py`:

  1. **Forbidden error response includes correlation_id:**
     Mock `MCPQueryService.execute_cypher_query()` to return a `QueryError` with
     `error_type="forbidden"` and a known `correlation_id`. Call `query_graph()` and
     assert the returned dict contains
     `{"success": False, "error_type": "forbidden", "correlation_id": "<expected-id>"}`.

  2. **Timeout error response includes correlation_id:**
     Same as above with `error_type="timeout"`.

  3. **Execution error response omits correlation_id key:**
     Return a `QueryError(error_type="execution_error", correlation_id=None)` and assert
     `"correlation_id"` is NOT a key in the response dict (avoids misleading null).

  4. **Unknown error response omits correlation_id key:**
     Same pattern for `error_type="unknown_error"`.

  5. **Successful response is unchanged:**
     Verify that a successful `CypherQueryResult` return still produces the expected
     `{"success": True, "rows": [...], "row_count": ..., "truncated": ..., "execution_time_ms": ...}`
     with no `correlation_id` key.

  ### 3. Test file location

  Place tests in `src/api/tests/unit/query/test_mcp_query_tool.py`.

  The existing `test_mcp_tools.py` tests private helpers (`_filter_by_knowledge_graph`,
  `_filter_internal_properties`). The new file tests the public `query_graph` function's
  output contract — keeping them separate keeps responsibility clear.

  ## Files Affected

  - `src/api/query/presentation/mcp.py` — add `correlation_id` to error response dict
  - `src/api/tests/unit/query/test_mcp_query_tool.py` — new test file for `query_graph`
    error response format

  ## How to Verify

  1. Run `cd src/api && uv run pytest tests/unit/query/test_mcp_query_tool.py -v`.
     All 5 new tests must pass.
  2. Run `cd src/api && uv run pytest tests/unit/query/ -v` — no regressions.
  3. Manually: submit a CREATE query to the MCP endpoint and confirm the JSON response
     body contains a `correlation_id` field alongside `error_type: "forbidden"`.

  ## Spec Mapping

  | Spec scenario | Requirement satisfied |
  |---|---|
  | Keyword blacklist — "error response includes a correlation ID" | `forbidden` response now carries `correlation_id` |
  | Query exceeds timeout — "timeout error returned with correlation ID" | `timeout` response now carries `correlation_id` |

  ## Design Decisions

  - **Conditional inclusion**: `correlation_id` is only included when non-None. This
    avoids clients having to handle `null` and keeps the response compact for the
    common `execution_error` case (syntax errors etc.) that don't generate correlation IDs.
  - **No breaking change**: Adding a new optional key to the error response dict is
    backwards-compatible. Existing MCP clients that don't inspect `correlation_id` are
    unaffected.
  - **No service-layer change needed**: The service and repository layers already
    generate and carry correlation IDs correctly. This is purely a presentation-layer fix.

  ## Caveats

  `query_graph` is an async FastMCP tool function decorated with `@mcp.tool`, which
  makes calling it directly in unit tests require care (the `Depends()` injection for
  `MCPQueryService` must be bypassed). Use `create_autospec` or a plain mock to
  substitute `MCPQueryService` and call the underlying function logic directly.
  Alternatively, extract the error-dict construction into a small helper function
  (`_build_error_response(result: QueryError) -> dict`) and test that helper directly.
---

## Spec Coverage

**Requirement: Read-Only Enforcement — Scenario: Keyword blacklist (secondary)** from
`specs/query/query-execution.spec.md`:

> AND a redacted reference is logged (not the raw query text)
> AND the error response includes a correlation ID for log lookup

**Requirement: Timeout Enforcement — Scenario: Query exceeds timeout** from
`specs/query/query-execution.spec.md`:

> THEN a timeout error is returned with a correlation ID for debugging

## Gap Analysis

The gap is purely in the **presentation layer** (`query/presentation/mcp.py`). The inner
layers already satisfy the spec:

| Layer | Status |
|---|---|
| `QueryGraphRepository._validate_read_only()` | ✅ sets `correlation_id` on `QueryForbiddenError` |
| `QueryGraphRepository.execute_cypher()` timeout path | ✅ sets `correlation_id` on `QueryTimeoutError` |
| `MCPQueryService.execute_cypher_query()` | ✅ propagates `correlation_id` into `QueryError` |
| `DefaultQueryServiceProbe.cypher_query_rejected()` | ✅ logs `correlation_id`, never the raw query |
| `mcp.py query_graph()` error dict | ❌ drops `correlation_id` — **this is the gap** |

## Verification Commands

```bash
# Run new tests
cd src/api && uv run pytest tests/unit/query/test_mcp_query_tool.py -v

# Confirm no regressions
cd src/api && uv run pytest tests/unit/query/ -v
```
