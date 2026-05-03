---
id: task-098
title: Fix MCP query result truncation to use limit+1 fetch pattern
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix: enforce limit+1 row fetch for precise MCP query result truncation detection"
pr_description: |
  ## What This Change Does

  Fixes a subtle semantic bug in the MCP `query_graph` result truncation detection.
  The `truncated` flag in the response tells MCP clients (AI agents) whether they
  received a complete result set or whether more rows exist beyond the limit.

  **Current behaviour (buggy):** `services.py` sets `truncated = len(rows) >= limit`.
  This produces a **false positive** whenever the result set contains exactly `limit`
  rows with no additional rows — the flag says "there may be more" when the result
  is actually complete.

  **Correct behaviour (spec):** The server SHOULD fetch `limit + 1` rows from the
  repository, set `truncated = (len(raw_rows) > limit)`, and slice the response to
  `raw_rows[:limit]` before returning. This definitively answers whether overflow
  exists without guessing.

  ## Spec Requirement Satisfied

  `specs/query/mcp-server.spec.md` — **Requirement: Graph Query Tool**, Scenario:
  *Result truncation flag*:

  > "the server SHOULD fetch `limit + 1` rows and set `truncated` to true only if
  > more than `limit` rows were available; AND the response returns at most `limit`
  > rows."

  ## Root Cause

  `src/api/query/application/services.py` line 79:

  ```python
  # BEFORE (heuristic — false positive at boundary)
  truncated = len(rows) >= limit

  # AFTER (definitive — fetches one extra probe row)
  raw_rows = await self._repository.execute_cypher(query, params, limit=limit + 1)
  truncated = len(raw_rows) > limit
  rows = raw_rows[:limit]
  ```

  The repository layer must be updated to accept and return up to `limit + 1` rows.

  ## Files / Areas Affected

  - `src/api/query/application/services.py` — change truncation logic
  - `src/api/query/infrastructure/query_graph_repository.py` — ensure `_ensure_limit()`
    honours `limit + 1` when passed from the service layer, or accept an explicit
    `fetch_limit` parameter distinct from the enforced result limit
  - `src/api/tests/unit/query/test_application_services.py` — add/update tests for
    the three boundary cases below
  - `src/api/tests/unit/query/test_query_repository.py` — verify `limit + 1` passed
    through correctly

  ## How to Verify

  Run `make test-unit` — all three new boundary scenarios must pass:

  1. **Exactly limit rows returned** → `truncated = False` (was wrongly `True` before)
  2. **Limit + 1 rows returned (more exist)** → `truncated = True`, response has
     exactly `limit` rows
  3. **Fewer than limit rows returned** → `truncated = False`

  ## Caveats / Follow-up

  - The fix increases the maximum rows fetched from the DB by 1 per query; this is
    negligible in practice but correct to note.
  - The spec says SHOULD (not MUST), so the existing behaviour is not wrong in
    principle, but the false-positive case causes AI agents to issue unnecessary
    follow-up queries. Fixing it improves agent efficiency.
  - No API contract changes — `truncated` remains a boolean field in the existing
    response schema.
---
