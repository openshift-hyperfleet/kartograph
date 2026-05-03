---
id: task-086
title: Fix result truncation detection — fetch limit+1 rows
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(query): use limit+1 fetch strategy for accurate truncation detection"
pr_description: |
  ## What & Why

  The `mcp-server.spec.md` **Scenario: Result truncation flag** requires:

  > THEN the server SHOULD fetch `limit + 1` rows and set `truncated` to true
  > only if more than `limit` rows were available
  > AND the response returns at most `limit` rows

  The current implementation fetches exactly `limit` rows and sets:

  ```python
  truncated = len(rows) >= limit
  ```

  This produces **false positives**: when the database contains exactly `limit`
  rows, the query returns `limit` rows, `truncated` is set to `True` — but there
  are no further rows available. The client is told "there is more data" when
  there is not.

  The spec-compliant approach:
  1. Fetch `limit + 1` rows from the database.
  2. If more than `limit` rows are returned, `truncated = True`; trim the result
     to `limit` rows before returning.
  3. If `limit` or fewer rows are returned, `truncated = False`.

  This makes `truncated` a reliable signal to consumers (and MCP agents) that
  a second query with a higher limit or pagination is needed.

  ## Root Cause

  Two locations contribute to the bug:

  ### 1. `query/infrastructure/query_repository.py` — `_ensure_limit()`

  ```python
  # Current (incorrect)
  return f"{query}\nLIMIT {max_rows}"

  # Fixed
  return f"{query}\nLIMIT {max_rows + 1}"
  ```

  The repository appends `LIMIT max_rows` when no LIMIT clause is present, and
  caps explicit LIMITs at `MAX_LIMIT`. Both cases must fetch one extra row so the
  service layer can detect over-limit results.

  **Explicit LIMIT cap also needs updating:**

  ```python
  # When an explicit LIMIT > MAX_LIMIT is found, cap to MAX_LIMIT + 1
  # so the service can still detect truncation correctly
  ```

  Wait — actually the cap case is simpler: when an explicit LIMIT is provided by
  the caller (e.g., `LIMIT 500`), the DB returns at most 500 rows and we never
  add +1 for that path. The +1 is only needed in the no-LIMIT and
  use-default-limit cases. See below for the precise logic.

  ### Revised `_ensure_limit()` semantics

  The spec says: "fetch `limit + 1` rows". `limit` here is `max_rows` (the
  effective limit the service requested). Three cases:

  | Case | Current query | New query |
  |------|--------------|-----------|
  | No LIMIT in query | append `LIMIT max_rows` | append `LIMIT max_rows + 1` |
  | LIMIT ≤ MAX_LIMIT | keep as-is | keep as-is (caller's explicit limit, no +1) |
  | LIMIT > MAX_LIMIT | replace with `LIMIT MAX_LIMIT` | replace with `LIMIT MAX_LIMIT + 1` |

  For **explicit LIMITs** the caller controls the limit, so the `+1` does not
  apply (the service does not know what the caller's "intended" limit was). Only
  when the service imposes a limit (no-LIMIT case or over-MAX_LIMIT cap) should
  it fetch +1.

  The simplest safe approach: always add +1 to the appended/capped LIMIT, and
  let the service trim the result. This means:

  - No LIMIT → `LIMIT max_rows + 1`
  - LIMIT > MAX_LIMIT → `LIMIT MAX_LIMIT + 1`
  - Explicit LIMIT ≤ MAX_LIMIT → unchanged (the caller owns this limit)

  ### 2. `query/application/services.py` — `execute_cypher_query()`

  ```python
  # Current (incorrect)
  rows = self._repository.execute_cypher(query=query, ...)
  truncated = len(rows) >= limit

  # Fixed
  raw_rows = self._repository.execute_cypher(query=query, ...)
  truncated = len(raw_rows) > limit
  rows = raw_rows[:limit]   # trim the extra row if present
  ```

  The service trims the result to `limit` rows and sets `truncated` accurately.

  ## Files Affected

  - `src/api/query/infrastructure/query_repository.py`
    - `_ensure_limit()`: append `LIMIT max_rows + 1` (no-LIMIT case)
    - `_ensure_limit()`: cap over-limit queries to `MAX_LIMIT + 1`
  - `src/api/query/application/services.py`
    - `execute_cypher_query()`: trim `rows = raw_rows[:limit]`, set
      `truncated = len(raw_rows) > limit`
  - `src/api/tests/unit/query/test_query_repository.py`
    - Update `TestEnsureLimit.test_adds_limit_when_missing` to expect
      `LIMIT max_rows + 1`
    - Update `TestEnsureLimit.test_caps_limit_above_absolute_maximum` to expect
      `LIMIT MAX_LIMIT + 1` (i.e., `LIMIT 10001`)
    - Update `TestEnsureLimit.test_respects_limit_at_absolute_maximum` — stays
      unchanged (explicit LIMIT at MAX_LIMIT is not modified)
    - Add new test: `test_respects_explicit_limit_below_maximum_unchanged`
  - `src/api/tests/integration/test_query_mcp.py`
    - Fix `test_execute_cypher_query_marks_truncation`: current setup has 3 data
      points with `max_rows=3` — this should now return `truncated=False`
      (exactly 3 rows available, limit is 3 so 4 are fetched, only 3 returned).
      Change to `max_rows=2` to correctly demonstrate truncation with 3 data points.

  ## How to Verify

  1. Unit tests: `make test-unit` — all pass.
  2. Integration test: with 3 nodes in the test graph:
     - `max_rows=2` → `row_count=2`, `truncated=True` (3 exist, fetched 3 via
       LIMIT 3, trimmed to 2)
     - `max_rows=3` → `row_count=3`, `truncated=False` (3 exist, fetched 4 via
       LIMIT 4, got 3)
     - `max_rows=4` → `row_count=3`, `truncated=False` (3 exist, fetched 5 via
       LIMIT 5, got 3)
  3. MCP tool: `query_graph("MATCH (n) RETURN n", max_rows=2)` on a graph with
     3 nodes returns `{"truncated": true, "row_count": 2}`.

  ## TDD Cycle

  1. Write failing unit tests for `_ensure_limit()` reflecting the +1 append/cap
     behavior — RED.
  2. Update `_ensure_limit()` — GREEN.
  3. Write failing integration test showing `truncated=False` when row count ==
     max_rows — RED.
  4. Update `execute_cypher_query()` — GREEN.
  5. Confirm `make test-unit` and `make test-integration` both pass.
  6. Atomic commit.

  ## Caveats

  - The explicit-LIMIT case (caller includes `LIMIT 50` and 50 ≤ MAX_LIMIT)
    is NOT affected. The service does not know the "natural" row count in that
    case and cannot add +1 without risking different semantics. Spec language
    ("the server SHOULD fetch limit+1") applies to the server-imposed limits,
    not caller-explicit limits.
  - The KG filter in `mcp.py` runs *after* the service trims to `limit` rows.
    `truncated` is set before KG filtering, so filtering may reduce `row_count`
    below `limit` while `truncated` remains `True`. This is a pre-existing design
    decision (spec does not address post-filter truncation) and is out of scope.
---
