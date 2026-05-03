---
id: task-097
title: 'MCP query_graph: implement spec-compliant truncation via fetch-limit+1'
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: implement
deps: []
round: 0
branch: hyperloop/task-097
pr: null
pr_title: 'fix(query): implement fetch-limit+1 truncation detection in MCPQueryService'
pr_description: "## What & Why\n\nThe **Result Truncation Flag** scenario in `specs/query/mcp-server.spec.md`\
  \ specifies:\n\n> THEN the server SHOULD fetch `limit + 1` rows and set `truncated`\
  \ to true only\n> if more than `limit` rows were available\n> AND the response returns\
  \ at most `limit` rows\n\nThe current implementation uses an approximation:\n\n\
  ```python\ntruncated = len(rows) >= limit\n```\n\nThis causes a false positive:\
  \ when the database returns *exactly* `limit` rows,\n`truncated` is set to `True`\
  \ even though there may be no additional rows. The spec\nexplicitly calls for fetching\
  \ `limit + 1` rows to distinguish \"hit the cap\" from\n\"exactly that many rows\
  \ exist.\"\n\nAdditionally, the existing unit test `test_tracks_truncation_when_at_limit`\
  \ in\n`test_application_services.py` encodes the wrong behavior — it asserts\n`truncated=True`\
  \ when exactly `limit` rows are returned, which should be\n`truncated=False` under\
  \ the spec's approach. This test must be updated as part\nof this fix.\n\n## Spec\
  \ Requirements Satisfied\n\n- **Requirement: Graph Query Tool / Scenario: Result\
  \ truncation flag**\n  (specs/query/mcp-server.spec.md, lines 46–49)\n\n## What\
  \ This Change Does\n\n### Application Layer (`query/application/services.py`)\n\n\
  `MCPQueryService.execute_cypher_query` is changed to:\n1. Request `limit + 1` rows\
  \ from the repository (`max_rows = limit + 1`).\n2. Set `truncated = len(rows) >\
  \ limit`.\n3. Trim the result to `rows[:limit]` when truncated.\n\nThis ensures\
  \ `truncated` is `True` *only* when a 1001st row (for limit=1000)\nactually existed,\
  \ not just when exactly 1000 rows were returned.\n\n### Tests Updated (`tests/unit/query/test_application_services.py`)\n\
  \nThe following changes align tests with the corrected behavior:\n\n**Modified test**\
  \ — `test_tracks_truncation_when_at_limit`:\n- Old: returns exactly `limit` rows\
  \ → expects `truncated=True` (wrong)\n- New: returns `limit + 1` rows → expects\
  \ `truncated=True` AND only `limit` rows in result\n\n**New test** — `test_not_truncated_when_exactly_at_limit`:\n\
  - Returns exactly `limit` rows → expects `truncated=False` (was the false-positive\
  \ case)\n\n**New test** — `test_truncated_result_trimmed_to_limit`:\n- Returns `limit\
  \ + 1` rows → result contains exactly `limit` rows\n\n## Files Affected\n\n- `src/api/query/application/services.py`\n\
  \  — `execute_cypher_query`: request `limit+1`, trim to `limit`, set `truncated`\
  \ correctly\n- `src/api/tests/unit/query/test_application_services.py`\n  — update\
  \ `test_tracks_truncation_when_at_limit`\n  — add `test_not_truncated_when_exactly_at_limit`\n\
  \  — add `test_truncated_result_trimmed_to_limit`\n\n## TDD Cycle\n\n1. Add/modify\
  \ the three tests above — RED for the wrong cases\n2. Run: `cd src/api && uv run\
  \ pytest tests/unit/query/test_application_services.py -v`\n3. Fix `execute_cypher_query`\
  \ in services.py — GREEN\n4. Run full unit suite to confirm no regressions:\n  \
  \ `cd src/api && uv run pytest tests/unit -v`\n5. Commit atomically\n\n## How to\
  \ Verify\n\n```bash\ncd src/api\n# Run targeted tests\nuv run pytest tests/unit/query/test_application_services.py\
  \ -k \"truncat\" -v\n# Run all query unit tests\nuv run pytest tests/unit/query/\
  \ -v\n```\n\nExpected outcomes:\n- `test_tracks_truncation_when_at_limit`: repository\
  \ returns 1001 rows →\n  `result.truncated is True` AND `len(result.rows) == 1000`\n\
  - `test_not_truncated_when_exactly_at_limit`: repository returns 1000 rows →\n \
  \ `result.truncated is False`\n- `test_truncated_result_trimmed_to_limit`: confirms\
  \ `len(result.rows) == 1000`\n  not 1001\n\n## Caveats\n\nThe spec uses SHOULD (not\
  \ SHALL), so this is a best-practice improvement.\nThe fix closes the false-positive\
  \ truncation report case and matches the spec's\nintended semantics. No changes\
  \ to the infrastructure (repository) layer are\nrequired — only the service layer\
  \ and its tests.\n\nNo integration test changes are required; integration tests\
  \ validate the\nend-to-end stack and the truncation flag is a service-layer concern."
---
