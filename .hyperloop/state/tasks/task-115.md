---
id: task-115
title: "MCP query_graph tool — tests for parameter bounds enforcement (timeout max 60 s, rows max 10 000)"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add tests for query_graph tool parameter bounds enforcement"
pr_description: |
  ## What & Why

  `specs/query/mcp-server.spec.md` specifies explicit upper bounds for the
  `query_graph` MCP tool parameters:

  > "**Scenario: Query timeout**
  > GIVEN a query that exceeds the timeout (default 30 seconds, **max 60 seconds**)
  > WHEN the query is executed
  > THEN it is terminated and returned with error type "timeout""

  > "**Scenario: Result limiting**
  > GIVEN a query without a LIMIT clause
  > WHEN the query is executed
  > THEN a LIMIT is automatically applied (default 1000, **max 10000**)"

  The `query_graph` tool in `query/presentation/mcp.py` correctly enforces these
  bounds with:

  ```python
  timeout_seconds = min(timeout_seconds, 60)
  max_rows = min(max_rows, 10000)
  ```

  However, **no test verifies these `min()` operations at the tool layer**. The
  repository's `_ensure_limit` (which caps explicit LIMIT clauses at `MAX_LIMIT =
  10000`) is tested in `test_query_repository.py`, but that is a different code path.
  The tool-layer cap on the `timeout_seconds` and `max_rows` *request parameters*
  themselves is untested.

  If the two `min()` lines were accidentally deleted, no existing test would catch
  the regression. An MCP client sending `max_rows=99999` or `timeout_seconds=3600`
  would bypass the intended limit.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md`:
  - **Requirement: Graph Query Tool** — Scenario: *Query timeout* ("max 60 seconds")
  - **Requirement: Graph Query Tool** — Scenario: *Result limiting* ("max 10000")

  ## What This Change Does

  Add unit tests that verify the tool's parameter bounds enforcement. Because
  `query_graph` is wrapped by `@mcp.tool` (making direct invocation in unit tests
  impractical), the bounds logic should be **extracted into a testable pure function**
  and the tool should delegate to it.

  ### Refactor: Extract `_clamp_query_params`

  In `query/presentation/mcp.py`, extract a small pure helper:

  ```python
  def _clamp_query_params(
      timeout_seconds: int,
      max_rows: int,
      max_timeout: int = 60,
      max_limit: int = 10_000,
  ) -> tuple[int, int]:
      """Clamp query parameters to their spec-defined maximums.

      Spec: mcp-server.spec.md — Scenario: Query timeout (max 60 s)
            mcp-server.spec.md — Scenario: Result limiting (max 10 000)
      """
      return min(timeout_seconds, max_timeout), min(max_rows, max_limit)
  ```

  Replace the inline `min()` calls in `query_graph` with `_clamp_query_params`.

  ### Tests: `test_mcp_query_params.py`

  Add a new test file `src/api/tests/unit/query/test_mcp_query_params.py`:

  **`TestClampQueryParams` — timeout_seconds cap at 60:**
  - `test_timeout_seconds_within_bounds_is_unchanged`: 30 → 30
  - `test_timeout_seconds_at_max_is_unchanged`: 60 → 60
  - `test_timeout_seconds_above_max_is_clamped`: 61 → 60, 3600 → 60, 999 → 60
  - `test_default_timeout_below_max`: default (30) passes through unchanged

  **`TestClampQueryParams` — max_rows cap at 10 000:**
  - `test_max_rows_within_bounds_is_unchanged`: 1000 → 1000
  - `test_max_rows_at_max_is_unchanged`: 10000 → 10000
  - `test_max_rows_above_max_is_clamped`: 10001 → 10000, 99999 → 10000
  - `test_default_max_rows_below_max`: default (1000) passes through unchanged

  **`TestClampQueryParams` — combined:**
  - `test_both_params_independently_clamped`: 120 s / 50000 rows → 60 s / 10000 rows
  - `test_both_params_within_bounds_unchanged`: 15 s / 500 rows → 15 s / 500 rows

  ## Files / Areas Affected

  - `src/api/query/presentation/mcp.py` — extract `_clamp_query_params` helper;
    replace inline `min()` calls in `query_graph`
  - `src/api/tests/unit/query/test_mcp_query_params.py` (new) — the test cases
    above; import and test `_clamp_query_params` directly

  ## Tests

  The extracted helper tests are pure unit tests (no infrastructure needed):

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_mcp_query_params.py -v
  ```

  ## How to Verify

  1. `cd src/api && uv run pytest tests/unit/query/test_mcp_query_params.py -v`
  2. Confirm all tests pass green
  3. Temporarily change `max_timeout=60` to `max_timeout=9999` in `_clamp_query_params`
     and confirm `test_timeout_seconds_above_max_is_clamped` fails — validates the
     tests are not false positives

  ## Caveats

  - The refactor is a behaviour-preserving rename only: the `min()` calls inside
    `query_graph` become a `_clamp_query_params` call. No logic changes.
  - The existing `MCPQueryService` and repository-level LIMIT tests are unaffected
    (they test different layers).
  - If a mypy or ruff hook complains about the new `_clamp_query_params` public
    exposure, prefix with underscore (it already starts with `_`) and add a
    `__all__` exclusion if needed.
---
