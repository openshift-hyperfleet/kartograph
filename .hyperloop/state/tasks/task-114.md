---
id: task-114
title: "Query execution — integration test for primary database-level read-only enforcement"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration test for primary database-level read-only enforcement"
pr_description: |
  ## What & Why

  `specs/query/query-execution.spec.md` — **Requirement: Read-Only Enforcement**
  defines two distinct defenses:

  > "**Scenario: Database-level enforcement (primary)**
  > GIVEN a query session used for graph queries
  > WHEN any query is executed
  > THEN the database session MUST be configured as read-only
  > AND write attempts are rejected by the database regardless of query content"

  > "**Scenario: Keyword blacklist (secondary)**
  > GIVEN a query containing any of: CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD
  > WHEN the query is submitted (case-insensitive check)
  > THEN it is rejected with a forbidden error before reaching the database"

  The keyword blacklist (secondary) is thoroughly unit- and integration-tested
  (`test_query_repository.py`, `test_query_mcp.py`). The **primary** database-level
  enforcement — `SET TRANSACTION READ ONLY` issued before every query — has **no
  independent test**. If this line were accidentally removed, no existing test would
  catch the regression; only the secondary blacklist would remain.

  This gap is critical: the spec explicitly calls out "defense-in-depth" and the
  database-level control as the **primary** safeguard. A test must verify that even
  when the keyword blacklist is bypassed, the database itself rejects write attempts.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md`:
  - **Requirement: Read-Only Enforcement** — Scenario: *Database-level enforcement (primary)*
    "THEN the database session MUST be configured as read-only"
    "AND write attempts are rejected by the database regardless of query content"

  ## What This Change Does

  Add an integration test in `src/api/tests/integration/test_query_mcp.py` (or a
  new file `test_query_readonly.py`) that explicitly bypasses the keyword blacklist
  and verifies the database session's `READ ONLY` setting rejects writes.

  ### Approach

  The `QueryGraphRepository._validate_read_only()` method is the keyword blacklist
  guard. The test patches it away to simulate a scenario where only the primary
  defense remains.

  ### Test: `test_database_rejects_write_even_when_keyword_blacklist_bypassed`

  Setup:
  1. Obtain a real `QueryGraphRepository` connected to the test AGE graph.
  2. Patch `QueryGraphRepository._validate_read_only` to be a no-op (simulates
     a hypothetical future bug where the blacklist is bypassed or absent).

  Execution:
  - Execute a Cypher mutation query (e.g., `CREATE (n:Test)` or a raw SQL
    `INSERT`/`UPDATE` if AGE surfaces database errors) through the patched repository.

  Assertions:
  - The call raises an exception at the **database level** (PostgreSQL rejects the
    write because the transaction is `READ ONLY`).
  - The exception message mentions "read-only" (PostgreSQL: "cannot execute … in a
    read-only transaction").
  - The secondary blacklist is confirmed to be bypassed (assert `_validate_read_only`
    was indeed skipped).

  ### Implementation Note on AGE / Cypher Writes

  Apache AGE translates Cypher `CREATE` into underlying PostgreSQL table inserts.
  With `SET TRANSACTION READ ONLY`, PostgreSQL will raise:
  `ERROR: cannot execute INSERT in a read-only transaction`

  The test should catch this as either a `QueryExecutionError` (if the repository
  maps it correctly) or a raw `psycopg2.errors.ReadOnlySqlTransaction`. Both
  indicate the primary defense is active.

  ## Files / Areas Affected

  - `src/api/tests/integration/test_query_mcp.py` or new
    `src/api/tests/integration/test_query_readonly.py` — the integration test
  - No production code changes expected

  ## Tests

  The integration test IS the deliverable. Mark with `@pytest.mark.integration`.

  Infrastructure requirements (`make instance-up`):
  - PostgreSQL with AGE extension (for real `SET TRANSACTION READ ONLY` enforcement)

  ## How to Verify

  1. `make instance-up`
  2. `source .instances/$(basename $(pwd))/.env.instance`
  3. `cd src/api && uv run pytest tests/integration/ -v -m integration -k "readonly"`
  4. Confirm test passes green
  5. Temporarily remove `tx.execute_sql("SET TRANSACTION READ ONLY")` from
     `QueryGraphRepository.execute_cypher` and confirm the test fails — validates
     the test is not a false positive

  ## Caveats

  - AGE-level Cypher `CREATE` may not always directly produce a
    `ReadOnlySqlTransaction` error; test with both a Cypher `CREATE` mutation AND
    a raw SQL `INSERT` to confirm which surface the READ ONLY error.
  - The patch must be applied to the **instance method** of the specific
    `QueryGraphRepository` object, not the class, to avoid affecting other tests
    running concurrently.
  - The keyword blacklist (secondary) tests in `TestQueryGraphRepository` should
    remain unmodified; only the new test bypasses it.
---
