---
id: task-114
title: Query execution — integration test for primary database-level read-only enforcement
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: merge
deps: []
round: 0
branch: hyperloop/task-114
pr: https://github.com/openshift-hyperfleet/kartograph/pull/584
pr_title: 'test(query): add integration test for primary database-level read-only
  enforcement'
pr_description: "## What & Why\n\n`specs/query/query-execution.spec.md` — **Requirement:\
  \ Read-Only Enforcement**\ndefines two distinct defenses:\n\n> \"**Scenario: Database-level\
  \ enforcement (primary)**\n> GIVEN a query session used for graph queries\n> WHEN\
  \ any query is executed\n> THEN the database session MUST be configured as read-only\n\
  > AND write attempts are rejected by the database regardless of query content\"\n\
  \n> \"**Scenario: Keyword blacklist (secondary)**\n> GIVEN a query containing any\
  \ of: CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD\n> WHEN the query is submitted\
  \ (case-insensitive check)\n> THEN it is rejected with a forbidden error before\
  \ reaching the database\"\n\nThe keyword blacklist (secondary) is thoroughly unit-\
  \ and integration-tested\n(`test_query_repository.py`, `test_query_mcp.py`). The\
  \ **primary** database-level\nenforcement — `SET TRANSACTION READ ONLY` issued before\
  \ every query — has **no\nindependent test**. If this line were accidentally removed,\
  \ no existing test would\ncatch the regression; only the secondary blacklist would\
  \ remain.\n\nThis gap is critical: the spec explicitly calls out \"defense-in-depth\"\
  \ and the\ndatabase-level control as the **primary** safeguard. A test must verify\
  \ that even\nwhen the keyword blacklist is bypassed, the database itself rejects\
  \ write attempts.\n\n## Spec Requirements Satisfied\n\n`specs/query/query-execution.spec.md`:\n\
  - **Requirement: Read-Only Enforcement** — Scenario: *Database-level enforcement\
  \ (primary)*\n  \"THEN the database session MUST be configured as read-only\"\n\
  \  \"AND write attempts are rejected by the database regardless of query content\"\
  \n\n## What This Change Does\n\nAdd an integration test in `src/api/tests/integration/test_query_mcp.py`\
  \ (or a\nnew file `test_query_readonly.py`) that explicitly bypasses the keyword\
  \ blacklist\nand verifies the database session's `READ ONLY` setting rejects writes.\n\
  \n### Approach\n\nThe `QueryGraphRepository._validate_read_only()` method is the\
  \ keyword blacklist\nguard. The test patches it away to simulate a scenario where\
  \ only the primary\ndefense remains.\n\n### Test: `test_database_rejects_write_even_when_keyword_blacklist_bypassed`\n\
  \nSetup:\n1. Obtain a real `QueryGraphRepository` connected to the test AGE graph.\n\
  2. Patch `QueryGraphRepository._validate_read_only` to be a no-op (simulates\n \
  \  a hypothetical future bug where the blacklist is bypassed or absent).\n\nExecution:\n\
  - Execute a Cypher mutation query (e.g., `CREATE (n:Test)` or a raw SQL\n  `INSERT`/`UPDATE`\
  \ if AGE surfaces database errors) through the patched repository.\n\nAssertions:\n\
  - The call raises an exception at the **database level** (PostgreSQL rejects the\n\
  \  write because the transaction is `READ ONLY`).\n- The exception message mentions\
  \ \"read-only\" (PostgreSQL: \"cannot execute … in a\n  read-only transaction\"\
  ).\n- The secondary blacklist is confirmed to be bypassed (assert `_validate_read_only`\n\
  \  was indeed skipped).\n\n### Implementation Note on AGE / Cypher Writes\n\nApache\
  \ AGE translates Cypher `CREATE` into underlying PostgreSQL table inserts.\nWith\
  \ `SET TRANSACTION READ ONLY`, PostgreSQL will raise:\n`ERROR: cannot execute INSERT\
  \ in a read-only transaction`\n\nThe test should catch this as either a `QueryExecutionError`\
  \ (if the repository\nmaps it correctly) or a raw `psycopg2.errors.ReadOnlySqlTransaction`.\
  \ Both\nindicate the primary defense is active.\n\n## Files / Areas Affected\n\n\
  - `src/api/tests/integration/test_query_mcp.py` or new\n  `src/api/tests/integration/test_query_readonly.py`\
  \ — the integration test\n- No production code changes expected\n\n## Tests\n\n\
  The integration test IS the deliverable. Mark with `@pytest.mark.integration`.\n\
  \nInfrastructure requirements (`make instance-up`):\n- PostgreSQL with AGE extension\
  \ (for real `SET TRANSACTION READ ONLY` enforcement)\n\n## How to Verify\n\n1. `make\
  \ instance-up`\n2. `source .instances/$(basename $(pwd))/.env.instance`\n3. `cd\
  \ src/api && uv run pytest tests/integration/ -v -m integration -k \"readonly\"\
  `\n4. Confirm test passes green\n5. Temporarily remove `tx.execute_sql(\"SET TRANSACTION\
  \ READ ONLY\")` from\n   `QueryGraphRepository.execute_cypher` and confirm the test\
  \ fails — validates\n   the test is not a false positive\n\n## Caveats\n\n- AGE-level\
  \ Cypher `CREATE` may not always directly produce a\n  `ReadOnlySqlTransaction`\
  \ error; test with both a Cypher `CREATE` mutation AND\n  a raw SQL `INSERT` to\
  \ confirm which surface the READ ONLY error.\n- The patch must be applied to the\
  \ **instance method** of the specific\n  `QueryGraphRepository` object, not the\
  \ class, to avoid affecting other tests\n  running concurrently.\n- The keyword\
  \ blacklist (secondary) tests in `TestQueryGraphRepository` should\n  remain unmodified;\
  \ only the new test bypasses it."
---
