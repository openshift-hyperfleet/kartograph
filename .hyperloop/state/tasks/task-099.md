---
id: task-099
title: Fix MCP query result truncation to use limit+1 detection
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix: implement limit+1 truncation detection for MCP query results"
pr_description: |
  ## What and Why

  The `query_graph` MCP tool includes a `truncated` flag in its response, signalling
  to the caller whether more rows exist beyond the returned set. The spec (Result
  truncation flag scenario) states:

  > the server SHOULD fetch `limit + 1` rows and set `truncated` to true **only if
  > more than `limit` rows were available**, AND the response returns at most `limit` rows.

  The current implementation has a correctness bug: `QueryGraphRepository._ensure_limit`
  appends `LIMIT max_rows` to the query, and `MCPQueryService` sets
  `truncated = len(rows) >= limit`. When the database contains **exactly** `max_rows`
  rows the service returns all of them and incorrectly sets `truncated = True` — a
  false positive that misleads AI agents into thinking more data exists when it does not.

  ## Spec Requirements Satisfied

  - **mcp-server.spec.md** → Requirement: Graph Query Tool → Scenario: Result truncation flag

  ## Design Decisions

  The fix applies the canonical "fetch N+1" approach at the repository layer:

  1. **`QueryGraphRepository._ensure_limit`** — when no `LIMIT` clause is present,
     append `LIMIT max_rows + 1` instead of `LIMIT max_rows`; when an explicit
     `LIMIT` exceeds `MAX_LIMIT`, cap to `MAX_LIMIT + 1` so over-limit queries also
     benefit from accurate truncation detection.

  2. **`MCPQueryService.execute_cypher_query`** — change the truncation check from
     `len(rows) >= limit` to `len(rows) > limit`, then slice `rows[:limit]` before
     building the `CypherQueryResult`. This ensures the response always contains at
     most `limit` rows and `truncated` is True only when more than `limit` rows
     were returned by the DB.

  ## Files Affected

  - `src/api/query/infrastructure/query_repository.py` — `_ensure_limit` method
  - `src/api/query/application/services.py` — truncation check and slice
  - `src/api/tests/unit/query/test_query_repository.py` — `TestEnsureLimit` tests
    that assert specific `LIMIT N` values (must be updated to `N+1` for the
    no-limit and cap cases)
  - `src/api/tests/unit/query/test_application_services.py` — `test_tracks_truncation_when_at_limit`
    currently passes 1000 rows and expects `truncated=True`; under the fix 1000 rows
    returned when the limit is 1000 means `truncated=False` — test must be updated
    and a new test added that returns 1001 rows to verify `truncated=True` with slicing

  ## How to Verify

  1. Run unit tests: `cd src/api && uv run pytest tests/unit/query/ -v`
  2. Confirm `test_tracks_truncation_when_at_limit` is updated to reflect the new
     semantics (1001 rows returned → truncated, 1000 rows returned → not truncated)
  3. Confirm `TestEnsureLimit` tests expect `LIMIT 1001` when `max_rows=1000` and
     no LIMIT clause is present
  4. Integration smoke: call `query_graph` against a table with exactly N rows where N
     equals `max_rows`; the response should have `truncated: false`

  ## Caveats

  - Queries with an **explicit** `LIMIT` clause at or below `MAX_LIMIT` are left
    unchanged — the user chose their own limit, so no `+1` is appended.  The
    `truncated` flag for these queries will still use `len(rows) > effective_limit`
    which is always False since the DB cannot return more rows than the stated `LIMIT`.
  - The `SHOULD` wording in the spec makes this a recommendation, not a hard
    requirement, but the false-positive behaviour actively misleads MCP clients and
    is therefore worth correcting.
---
