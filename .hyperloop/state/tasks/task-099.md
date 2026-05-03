---
id: task-099
title: Fix truncation detection to use fetch-limit+1 and repair integration test
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(query): implement fetch-limit+1 truncation detection and correct integration test"
pr_description: |
  ## What & Why

  The **Result Truncation Flag** scenario in `specs/query/mcp-server.spec.md` requires:

  > "the server SHOULD fetch `limit + 1` rows and set `truncated` to true only if
  > more than `limit` rows were available; AND the response returns at most `limit` rows."

  Two bugs exist:

  ### Bug 1 — Service layer: false-positive truncation
  `src/api/query/application/services.py` line 79:
  ```python
  truncated = len(rows) >= limit   # WRONG: true when exactly limit rows exist
  ```
  Correct approach: request `limit + 1` rows, set `truncated = len(raw) > limit`,
  slice to `raw[:limit]` before returning.

  ### Bug 2 — Integration test: asserts wrong behavior
  `src/api/tests/integration/test_query_mcp.py` line 205,
  `TestMCPQueryService.test_execute_cypher_query_marks_truncation`:
  ```python
  assert result.row_count == 3
  assert result.truncated is True   # WRONG: 3 rows at limit=3 → truncated MUST be False
  ```
  When Bug 1 is fixed, this assertion will break because exactly-at-limit results are
  no longer considered truncated. This integration test must be updated to reflect the
  spec-correct behavior.

  > **Note:** Tasks task-086, task-089, task-097, task-098 also describe the service
  > fix but do not mention this integration test. This task is the definitive
  > implementation spec and explicitly includes the integration test repair.

  ## Spec Requirement Satisfied

  `specs/query/mcp-server.spec.md` — **Requirement: Graph Query Tool**,
  Scenario: *Result truncation flag*

  ## Files Affected

  ### Implementation
  - `src/api/query/application/services.py`
    - `execute_cypher_query`: request `limit + 1` from repository, set
      `truncated = len(raw_rows) > limit`, return `raw_rows[:limit]`

  ### Unit Tests (update/add)
  - `src/api/tests/unit/query/test_application_services.py`
    - Update `test_tracks_truncation_when_at_limit` — supply `limit + 1` rows to
      repository fake; assert `truncated=True` AND `len(result.rows) == limit`
    - Add `test_not_truncated_when_exactly_at_limit` — supply exactly `limit` rows;
      assert `truncated=False`
    - Add `test_truncated_result_trimmed_to_limit` — supply `limit + 1` rows; assert
      `len(result.rows) == limit` (not `limit + 1`)

  ### Integration Test (repair)
  - `src/api/tests/integration/test_query_mcp.py`
    - Rename `test_execute_cypher_query_marks_truncation` →
      `test_execute_cypher_query_not_truncated_when_exactly_at_limit`
    - Assert `result.truncated is False` (was incorrectly `True`)
    - Add `test_execute_cypher_query_truncated_when_more_exist`:
      create 4 nodes in the test graph, query with `max_rows=3`, assert `truncated=True`
      and `result.row_count == 3`

  ## TDD Cycle

  1. Update `test_not_truncated_when_exactly_at_limit` → RED (new test, fails)
  2. Repair integration test (change assertion) → will be RED after service fix
  3. Fix `execute_cypher_query` in `services.py` → GREEN for unit tests
  4. Run integration tests to confirm repair: `make test-integration`
  5. Commit atomically

  ## How to Verify

  ```bash
  cd src/api

  # Unit tests — all three boundary cases
  uv run pytest tests/unit/query/test_application_services.py -k "truncat" -v

  # Integration tests — confirm repair
  uv run pytest tests/integration/test_query_mcp.py::TestMCPQueryService -v

  # Full unit suite — no regressions
  uv run pytest tests/unit -v
  ```

  Expected:
  - `test_not_truncated_when_exactly_at_limit`: `truncated=False` ✓
  - `test_execute_cypher_query_not_truncated_when_exactly_at_limit`: `truncated=False` ✓
  - `test_execute_cypher_query_truncated_when_more_exist`: `truncated=True`, 3 rows ✓

  ## Caveats

  The spec uses SHOULD (not SHALL), so this is a best-practice improvement.
  The fix closes the false-positive that causes AI agents to issue unnecessary
  follow-up queries. It increases rows fetched from the DB by 1 per query —
  negligible in practice. No API contract changes.
---
