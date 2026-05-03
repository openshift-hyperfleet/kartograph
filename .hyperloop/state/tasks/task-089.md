---
id: task-089
title: Fix result truncation to use limit+1 sentinel row
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(query): use limit+1 sentinel to determine result truncation accurately"
pr_description: |
  ## What & Why

  The MCP server spec requires an accurate truncation signal:

  > **Scenario: Result truncation flag**
  > THEN the server SHOULD fetch `limit + 1` rows and set `truncated` to true only if
  > more than `limit` rows were available
  > AND the response returns at most `limit` rows

  The current implementation in `MCPQueryService.execute_cypher_query()` is:

  ```python
  rows = self._repository.execute_cypher(query=query, timeout_seconds=timeout, max_rows=limit)
  truncated = len(rows) >= limit
  ```

  This produces **false positives**: when exactly `limit` rows exist in the graph,
  `truncated` is set to `True` even though there are no additional rows. The client
  cannot distinguish "exactly N rows" from "more than N rows exist". The spec fixes
  this by fetching one extra row as a sentinel.

  ## What This PR Does

  ### 1. Fix `QueryGraphRepository._ensure_limit()` and `execute_cypher()`

  Modify `execute_cypher()` to request `max_rows + 1` rows from the database. After
  receiving results, return only the first `max_rows` rows and set `truncated = True`
  only when the raw row count exceeds `max_rows`.

  Key changes in `src/api/query/infrastructure/query_repository.py`:

  ```python
  def execute_cypher(self, query: str, timeout_seconds: int = 30, max_rows: int = 1000):
      # ... validation ...
      # Request one extra row to detect truncation without false positives
      query = self._ensure_limit(query, max_rows + 1)
      # ... execute ...
      raw_rows = [self._row_to_dict(row) for row in result.rows]
      truncated = len(raw_rows) > max_rows
      return raw_rows[:max_rows]  # return at most max_rows rows
  ```

  The `_ensure_limit()` helper already handles the case where an explicit LIMIT is
  present. When the query has no LIMIT, appending `LIMIT max_rows + 1` is safe.
  When the query has an explicit LIMIT ≤ max_rows, the existing LIMIT is respected
  as-is (spec: "Explicit LIMIT within bounds is respected") — no sentinel needed
  because the caller specified exactly how many rows they want.

  **Explicit LIMIT handling**: When a caller provides `LIMIT 50` and `max_rows=1000`,
  the LIMIT 50 stays unchanged. The `+1` sentinel only applies when the LIMIT is
  appended automatically (no LIMIT clause) or when it is capped by MAX_LIMIT.

  ### 2. Update `MCPQueryService.execute_cypher_query()`

  The service layer currently computes `truncated = len(rows) >= limit` after receiving
  the list from the repository. With the fix, the repository returns only up to
  `max_rows` rows and the service should use the `CypherQueryResult` fields correctly:

  ```python
  rows = self._repository.execute_cypher(query=query, timeout_seconds=timeout, max_rows=limit)
  elapsed_ms = ...
  truncated = len(rows) > limit  # changed: > not >=, but repository enforces max_rows
  ```

  Actually, the cleaner approach is to have the repository return a namedtuple/dataclass
  with `(rows, truncated)` so the service doesn't need to recompute. However, to
  minimize interface changes, the simplest fix is: the repository returns at most
  `max_rows` rows, and the service knows truncation occurred if the repository returned
  exactly `max_rows` rows AND requested `max_rows + 1` from the database.

  A clean implementation: add a private `_execute_with_truncation_check()` method
  on the repository that returns `(list[QueryResultRow], bool)`, or change the
  repository interface to return the sentinel. The PR author should choose the
  minimal-change approach that makes tests pass.

  ### 3. Write tests first (TDD)

  Add tests to `src/api/tests/unit/query/test_query_repository.py`:

  **Test: No false positive when exactly max_rows exist**
  ```python
  def test_truncated_false_when_exactly_limit_rows_exist(repository, mock_client, mock_transaction):
      """Should NOT set truncated when exactly limit rows exist (no more available)."""
      # Repository requests limit+1; DB returns exactly limit rows → not truncated
      mock_transaction.execute_cypher.return_value = CypherResult(
          rows=tuple([(AgeVertex(...),)] * 1000),  # exactly limit rows
          row_count=1000,
      )
      result = repository.execute_cypher("MATCH (n) RETURN n", max_rows=1000)
      # Result has 1000 rows, NOT truncated
      assert len(result) == 1000
      # ... verify truncated signal is correct
  ```

  **Test: Truncated true when more than max_rows exist**
  ```python
  def test_truncated_true_when_more_than_limit_rows_exist(repository, ...):
      """Truncated flag is True only when the DB returns limit+1 rows (more exist)."""
      mock_transaction.execute_cypher.return_value = CypherResult(
          rows=tuple([...] * 1001),  # limit+1 sentinel returned
          row_count=1001,
      )
      result = repository.execute_cypher("MATCH (n) RETURN n", max_rows=1000)
      assert len(result) == 1000  # at most max_rows returned
      # test truncated signal propagates correctly
  ```

  Also add/update integration tests in `test_query_mcp.py`:

  **Existing failing test**: `test_execute_cypher_query_marks_truncation` currently
  expects `truncated=True` when `row_count == max_rows`. With the fix, this is a
  false positive. The test must be updated: it should set `max_rows = 2` (with 3
  rows in the DB) to confirm truncated=True when MORE rows exist, and add a new test
  with `max_rows = 3` (exactly 3 rows) to confirm truncated=False.

  ## Files Affected

  - `src/api/query/infrastructure/query_repository.py` — sentinel row logic in
    `execute_cypher()` and `_ensure_limit()`
  - `src/api/query/application/services.py` — update truncation computation if needed
  - `src/api/tests/unit/query/test_query_repository.py` — new/updated tests
  - `src/api/tests/integration/test_query_mcp.py` — update `test_execute_cypher_query_marks_truncation`

  ## How to Verify

  1. `cd src/api && uv run pytest tests/unit/query/test_query_repository.py -v` — all tests pass
  2. `cd src/api && uv run pytest tests/unit/query/ -v` — no regressions
  3. `cd src/api && uv run pytest tests/integration/test_query_mcp.py -v -m integration` — passes with running DB

  ## Design Decisions

  - **Sentinel only for auto-appended LIMIT**: When the user provides an explicit
    LIMIT (e.g., `LIMIT 50`), we respect it. The sentinel (+1) is injected only when
    the limit is appended or capped by the system.
  - **Minimal interface change**: The repository returns `list[QueryResultRow]` as
    before; truncation detection happens internally via the sentinel. The service layer
    gets the correct row count and does not need to recompute truncation.
  - **No regression on explicit LIMIT within bounds**: A query with `LIMIT 50` and
    `max_rows=1000` returns exactly 50 rows, `truncated=False`. This is correct
    because the caller asked for 50 and got 50.

  ## Spec Reference

  `specs/query/mcp-server.spec.md` — Requirement: Graph Query Tool — Scenario: Result truncation flag
---

## Spec Coverage

**Requirement: Graph Query Tool — Scenario: Result truncation flag** from
`specs/query/mcp-server.spec.md`:

> THEN the server SHOULD fetch `limit + 1` rows and set `truncated` to true only if
> more than `limit` rows were available
> AND the response returns at most `limit` rows

## Gap Analysis

The gap is in `QueryGraphRepository.execute_cypher()` and
`MCPQueryService.execute_cypher_query()`.

| Component | Current behaviour | Required behaviour |
|---|---|---|
| `_ensure_limit(query, max_rows)` | Appends `LIMIT max_rows` | Should append `LIMIT max_rows + 1` when no LIMIT present or LIMIT capped |
| `execute_cypher()` result handling | Returns all rows from DB | Should return first `max_rows` rows, detect `truncated` via sentinel |
| `execute_cypher_query()` in service | `truncated = len(rows) >= limit` | `truncated = len(raw_rows) > limit` (after repository enforces max_rows) |
| Integration test `test_execute_cypher_query_marks_truncation` | Expects `truncated=True` when `row_count == max_rows` | False positive — must test with `row_count > max_rows` |

## Verification Commands

```bash
cd src/api && uv run pytest tests/unit/query/test_query_repository.py -v
cd src/api && uv run pytest tests/unit/query/ -v
```
