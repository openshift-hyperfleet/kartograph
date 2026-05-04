---
id: task-099
title: Fix MCP query result truncation to use limit+1 detection
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: mark-ready
deps: []
round: 10
branch: hyperloop/task-099
pr: https://github.com/openshift-hyperfleet/kartograph/pull/565
pr_title: 'fix: implement limit+1 truncation detection for MCP query results'
pr_description: "## What and Why\n\nThe `query_graph` MCP tool includes a `truncated`\
  \ flag in its response, signalling\nto the caller whether more rows exist beyond\
  \ the returned set. The spec (Result\ntruncation flag scenario) states:\n\n> the\
  \ server SHOULD fetch `limit + 1` rows and set `truncated` to true **only if\n>\
  \ more than `limit` rows were available**, AND the response returns at most `limit`\
  \ rows.\n\nThe current implementation has a correctness bug: `QueryGraphRepository._ensure_limit`\n\
  appends `LIMIT max_rows` to the query, and `MCPQueryService` sets\n`truncated =\
  \ len(rows) >= limit`. When the database contains **exactly** `max_rows`\nrows the\
  \ service returns all of them and incorrectly sets `truncated = True` — a\nfalse\
  \ positive that misleads AI agents into thinking more data exists when it does not.\n\
  \n## Spec Requirements Satisfied\n\n- **mcp-server.spec.md** → Requirement: Graph\
  \ Query Tool → Scenario: Result truncation flag\n\n## Design Decisions\n\nThe fix\
  \ applies the canonical \"fetch N+1\" approach at the repository layer:\n\n1. **`QueryGraphRepository._ensure_limit`**\
  \ — when no `LIMIT` clause is present,\n   append `LIMIT max_rows + 1` instead of\
  \ `LIMIT max_rows`; when an explicit\n   `LIMIT` exceeds `MAX_LIMIT`, cap to `MAX_LIMIT\
  \ + 1` so over-limit queries also\n   benefit from accurate truncation detection.\n\
  \n2. **`MCPQueryService.execute_cypher_query`** — change the truncation check from\n\
  \   `len(rows) >= limit` to `len(rows) > limit`, then slice `rows[:limit]` before\n\
  \   building the `CypherQueryResult`. This ensures the response always contains\
  \ at\n   most `limit` rows and `truncated` is True only when more than `limit` rows\n\
  \   were returned by the DB.\n\n## Files Affected\n\n- `src/api/query/infrastructure/query_repository.py`\
  \ — `_ensure_limit` method\n- `src/api/query/application/services.py` — truncation\
  \ check and slice\n- `src/api/tests/unit/query/test_query_repository.py` — `TestEnsureLimit`\
  \ tests\n  that assert specific `LIMIT N` values (must be updated to `N+1` for the\n\
  \  no-limit and cap cases)\n- `src/api/tests/unit/query/test_application_services.py`\
  \ — `test_tracks_truncation_when_at_limit`\n  currently passes 1000 rows and expects\
  \ `truncated=True`; under the fix 1000 rows\n  returned when the limit is 1000 means\
  \ `truncated=False` — test must be updated\n  and a new test added that returns\
  \ 1001 rows to verify `truncated=True` with slicing\n\n## How to Verify\n\n1. Run\
  \ unit tests: `cd src/api && uv run pytest tests/unit/query/ -v`\n2. Confirm `test_tracks_truncation_when_at_limit`\
  \ is updated to reflect the new\n   semantics (1001 rows returned → truncated, 1000\
  \ rows returned → not truncated)\n3. Confirm `TestEnsureLimit` tests expect `LIMIT\
  \ 1001` when `max_rows=1000` and\n   no LIMIT clause is present\n4. Integration\
  \ smoke: call `query_graph` against a table with exactly N rows where N\n   equals\
  \ `max_rows`; the response should have `truncated: false`\n\n## Caveats\n\n- Queries\
  \ with an **explicit** `LIMIT` clause at or below `MAX_LIMIT` are left\n  unchanged\
  \ — the user chose their own limit, so no `+1` is appended.  The\n  `truncated`\
  \ flag for these queries will still use `len(rows) > effective_limit`\n  which is\
  \ always False since the DB cannot return more rows than the stated `LIMIT`.\n-\
  \ The `SHOULD` wording in the spec makes this a recommendation, not a hard\n  requirement,\
  \ but the false-positive behaviour actively misleads MCP clients and\n  is therefore\
  \ worth correcting."
---
