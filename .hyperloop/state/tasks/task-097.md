---
id: task-097
title: "MCP query_graph: implement spec-compliant truncation via fetch-limit+1"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(query): implement fetch-limit+1 truncation detection in MCPQueryService"
pr_description: |
  ## What & Why

  The **Result Truncation Flag** scenario in `specs/query/mcp-server.spec.md` specifies:

  > THEN the server SHOULD fetch `limit + 1` rows and set `truncated` to true only
  > if more than `limit` rows were available
  > AND the response returns at most `limit` rows

  The current implementation uses an approximation:

  ```python
  truncated = len(rows) >= limit
  ```

  This causes a false positive: when the database returns *exactly* `limit` rows,
  `truncated` is set to `True` even though there may be no additional rows. The spec
  explicitly calls for fetching `limit + 1` rows to distinguish "hit the cap" from
  "exactly that many rows exist."

  Additionally, the existing unit test `test_tracks_truncation_when_at_limit` in
  `test_application_services.py` encodes the wrong behavior — it asserts
  `truncated=True` when exactly `limit` rows are returned, which should be
  `truncated=False` under the spec's approach. This test must be updated as part
  of this fix.

  ## Spec Requirements Satisfied

  - **Requirement: Graph Query Tool / Scenario: Result truncation flag**
    (specs/query/mcp-server.spec.md, lines 46–49)

  ## What This Change Does

  ### Application Layer (`query/application/services.py`)

  `MCPQueryService.execute_cypher_query` is changed to:
  1. Request `limit + 1` rows from the repository (`max_rows = limit + 1`).
  2. Set `truncated = len(rows) > limit`.
  3. Trim the result to `rows[:limit]` when truncated.

  This ensures `truncated` is `True` *only* when a 1001st row (for limit=1000)
  actually existed, not just when exactly 1000 rows were returned.

  ### Tests Updated (`tests/unit/query/test_application_services.py`)

  The following changes align tests with the corrected behavior:

  **Modified test** — `test_tracks_truncation_when_at_limit`:
  - Old: returns exactly `limit` rows → expects `truncated=True` (wrong)
  - New: returns `limit + 1` rows → expects `truncated=True` AND only `limit` rows in result

  **New test** — `test_not_truncated_when_exactly_at_limit`:
  - Returns exactly `limit` rows → expects `truncated=False` (was the false-positive case)

  **New test** — `test_truncated_result_trimmed_to_limit`:
  - Returns `limit + 1` rows → result contains exactly `limit` rows

  ## Files Affected

  - `src/api/query/application/services.py`
    — `execute_cypher_query`: request `limit+1`, trim to `limit`, set `truncated` correctly
  - `src/api/tests/unit/query/test_application_services.py`
    — update `test_tracks_truncation_when_at_limit`
    — add `test_not_truncated_when_exactly_at_limit`
    — add `test_truncated_result_trimmed_to_limit`

  ## TDD Cycle

  1. Add/modify the three tests above — RED for the wrong cases
  2. Run: `cd src/api && uv run pytest tests/unit/query/test_application_services.py -v`
  3. Fix `execute_cypher_query` in services.py — GREEN
  4. Run full unit suite to confirm no regressions:
     `cd src/api && uv run pytest tests/unit -v`
  5. Commit atomically

  ## How to Verify

  ```bash
  cd src/api
  # Run targeted tests
  uv run pytest tests/unit/query/test_application_services.py -k "truncat" -v
  # Run all query unit tests
  uv run pytest tests/unit/query/ -v
  ```

  Expected outcomes:
  - `test_tracks_truncation_when_at_limit`: repository returns 1001 rows →
    `result.truncated is True` AND `len(result.rows) == 1000`
  - `test_not_truncated_when_exactly_at_limit`: repository returns 1000 rows →
    `result.truncated is False`
  - `test_truncated_result_trimmed_to_limit`: confirms `len(result.rows) == 1000`
    not 1001

  ## Caveats

  The spec uses SHOULD (not SHALL), so this is a best-practice improvement.
  The fix closes the false-positive truncation report case and matches the spec's
  intended semantics. No changes to the infrastructure (repository) layer are
  required — only the service layer and its tests.

  No integration test changes are required; integration tests validate the
  end-to-end stack and the truncation flag is a service-layer concern.
---
