---
id: task-115
title: MCP query_graph tool — tests for parameter bounds enforcement (timeout max
  60 s, rows max 10 000)
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: verify
deps: []
round: 1
branch: hyperloop/task-115
pr: https://github.com/openshift-hyperfleet/kartograph/pull/585
pr_title: 'test(query): add tests for query_graph tool parameter bounds enforcement'
pr_description: "## What & Why\n\n`specs/query/mcp-server.spec.md` specifies explicit\
  \ upper bounds for the\n`query_graph` MCP tool parameters:\n\n> \"**Scenario: Query\
  \ timeout**\n> GIVEN a query that exceeds the timeout (default 30 seconds, **max\
  \ 60 seconds**)\n> WHEN the query is executed\n> THEN it is terminated and returned\
  \ with error type \"timeout\"\"\n\n> \"**Scenario: Result limiting**\n> GIVEN a\
  \ query without a LIMIT clause\n> WHEN the query is executed\n> THEN a LIMIT is\
  \ automatically applied (default 1000, **max 10000**)\"\n\nThe `query_graph` tool\
  \ in `query/presentation/mcp.py` correctly enforces these\nbounds with:\n\n```python\n\
  timeout_seconds = min(timeout_seconds, 60)\nmax_rows = min(max_rows, 10000)\n```\n\
  \nHowever, **no test verifies these `min()` operations at the tool layer**. The\n\
  repository's `_ensure_limit` (which caps explicit LIMIT clauses at `MAX_LIMIT =\n\
  10000`) is tested in `test_query_repository.py`, but that is a different code path.\n\
  The tool-layer cap on the `timeout_seconds` and `max_rows` *request parameters*\n\
  themselves is untested.\n\nIf the two `min()` lines were accidentally deleted, no\
  \ existing test would catch\nthe regression. An MCP client sending `max_rows=99999`\
  \ or `timeout_seconds=3600`\nwould bypass the intended limit.\n\n## Spec Requirements\
  \ Satisfied\n\n`specs/query/mcp-server.spec.md`:\n- **Requirement: Graph Query Tool**\
  \ — Scenario: *Query timeout* (\"max 60 seconds\")\n- **Requirement: Graph Query\
  \ Tool** — Scenario: *Result limiting* (\"max 10000\")\n\n## What This Change Does\n\
  \nAdd unit tests that verify the tool's parameter bounds enforcement. Because\n\
  `query_graph` is wrapped by `@mcp.tool` (making direct invocation in unit tests\n\
  impractical), the bounds logic should be **extracted into a testable pure function**\n\
  and the tool should delegate to it.\n\n### Refactor: Extract `_clamp_query_params`\n\
  \nIn `query/presentation/mcp.py`, extract a small pure helper:\n\n```python\ndef\
  \ _clamp_query_params(\n    timeout_seconds: int,\n    max_rows: int,\n    max_timeout:\
  \ int = 60,\n    max_limit: int = 10_000,\n) -> tuple[int, int]:\n    \"\"\"Clamp\
  \ query parameters to their spec-defined maximums.\n\n    Spec: mcp-server.spec.md\
  \ — Scenario: Query timeout (max 60 s)\n          mcp-server.spec.md — Scenario:\
  \ Result limiting (max 10 000)\n    \"\"\"\n    return min(timeout_seconds, max_timeout),\
  \ min(max_rows, max_limit)\n```\n\nReplace the inline `min()` calls in `query_graph`\
  \ with `_clamp_query_params`.\n\n### Tests: `test_mcp_query_params.py`\n\nAdd a\
  \ new test file `src/api/tests/unit/query/test_mcp_query_params.py`:\n\n**`TestClampQueryParams`\
  \ — timeout_seconds cap at 60:**\n- `test_timeout_seconds_within_bounds_is_unchanged`:\
  \ 30 → 30\n- `test_timeout_seconds_at_max_is_unchanged`: 60 → 60\n- `test_timeout_seconds_above_max_is_clamped`:\
  \ 61 → 60, 3600 → 60, 999 → 60\n- `test_default_timeout_below_max`: default (30)\
  \ passes through unchanged\n\n**`TestClampQueryParams` — max_rows cap at 10 000:**\n\
  - `test_max_rows_within_bounds_is_unchanged`: 1000 → 1000\n- `test_max_rows_at_max_is_unchanged`:\
  \ 10000 → 10000\n- `test_max_rows_above_max_is_clamped`: 10001 → 10000, 99999 →\
  \ 10000\n- `test_default_max_rows_below_max`: default (1000) passes through unchanged\n\
  \n**`TestClampQueryParams` — combined:**\n- `test_both_params_independently_clamped`:\
  \ 120 s / 50000 rows → 60 s / 10000 rows\n- `test_both_params_within_bounds_unchanged`:\
  \ 15 s / 500 rows → 15 s / 500 rows\n\n## Files / Areas Affected\n\n- `src/api/query/presentation/mcp.py`\
  \ — extract `_clamp_query_params` helper;\n  replace inline `min()` calls in `query_graph`\n\
  - `src/api/tests/unit/query/test_mcp_query_params.py` (new) — the test cases\n \
  \ above; import and test `_clamp_query_params` directly\n\n## Tests\n\nThe extracted\
  \ helper tests are pure unit tests (no infrastructure needed):\n\n```bash\ncd src/api\
  \ && uv run pytest tests/unit/query/test_mcp_query_params.py -v\n```\n\n## How to\
  \ Verify\n\n1. `cd src/api && uv run pytest tests/unit/query/test_mcp_query_params.py\
  \ -v`\n2. Confirm all tests pass green\n3. Temporarily change `max_timeout=60` to\
  \ `max_timeout=9999` in `_clamp_query_params`\n   and confirm `test_timeout_seconds_above_max_is_clamped`\
  \ fails — validates the\n   tests are not false positives\n\n## Caveats\n\n- The\
  \ refactor is a behaviour-preserving rename only: the `min()` calls inside\n  `query_graph`\
  \ become a `_clamp_query_params` call. No logic changes.\n- The existing `MCPQueryService`\
  \ and repository-level LIMIT tests are unaffected\n  (they test different layers).\n\
  - If a mypy or ruff hook complains about the new `_clamp_query_params` public\n\
  \  exposure, prefix with underscore (it already starts with `_`) and add a\n  `__all__`\
  \ exclusion if needed."
---
