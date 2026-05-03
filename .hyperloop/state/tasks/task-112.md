---
id: task-112
title: "Read-Only Enforcement — integration test for database-level primary defense"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration test for SET TRANSACTION READ ONLY primary defense"
pr_description: |
  ## What & Why

  The **Read-Only Enforcement** requirement in `specs/query/query-execution.spec.md`
  defines a two-layer defense:

  > "GIVEN a Cypher query containing a mutation keyword WHEN the query is submitted
  > THEN the request is rejected before reaching the database AND the response includes
  > `success: False` and `error_type: 'forbidden'` AND a redacted reference is logged"

  > "GIVEN a Cypher query that reaches the database WHEN the database receives the
  > query THEN the transaction is opened with `SET TRANSACTION READ ONLY` AND any
  > write that bypasses keyword detection is rejected at the database level"

  The secondary (keyword blacklist) defense is tested in `tests/integration/test_query_mcp.py`
  via `test_enforces_read_only`, which submits `CREATE (n:Test)` — but CREATE is caught
  by `MUTATION_KEYWORDS` in `_validate_read_only()` before the query ever reaches
  PostgreSQL. That test never exercises the `SET TRANSACTION READ ONLY` statement.

  The primary defense — `SET TRANSACTION READ ONLY` issued at the start of every
  transaction in `QueryGraphRepository._execute_query()` — is untested at the
  integration level. If the `SET TRANSACTION READ ONLY` line were accidentally
  removed or placed after the query execution, writes that bypass keyword detection
  would silently succeed in production.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md`:
  - **Requirement: Read-Only Enforcement** — Scenario: *Database-level read-only
    enforcement (primary defense)*

  ## What This Change Does

  Add an integration test that verifies `SET TRANSACTION READ ONLY` independently
  from the keyword blacklist by submitting a write query directly to
  `QueryGraphRepository` (bypassing `_validate_read_only()`) and asserting that
  PostgreSQL itself rejects the write.

  ### Test: `test_database_level_read_only_rejects_writes_independently_of_keyword_check`

  Setup:
  1. Instantiate `QueryGraphRepository` directly (not via MCP endpoint) against the
     real test PostgreSQL+AGE instance.
  2. Patch or subclass `_validate_read_only()` to be a no-op so the keyword blacklist
     is bypassed — this isolates the primary defense from the secondary defense.

  Execution:
  - Call `repository.execute_cypher(query="CREATE (n:PrimaryDefenseTest)", ...)`.

  Assertions:
  - A `QueryExecutionError` (or `QueryForbiddenError`) is raised.
  - The error message references a PostgreSQL read-only transaction error
    (e.g., contains "read-only transaction" or the psycopg2 error code `25006`).
  - No `(:PrimaryDefenseTest)` node exists in the AGE graph after the call
    (verify with a subsequent SELECT query).

  ### Test: `test_every_query_transaction_is_opened_read_only` (complementary)

  Setup:
  1. Instantiate `QueryGraphRepository` against the real PostgreSQL+AGE instance.
  2. Use a connection-level listener or intercept `cursor.execute` calls to capture
     the SQL statements issued within a single `execute_cypher()` call.

  Execution:
  - Call `repository.execute_cypher(query="MATCH (n) RETURN n LIMIT 1", ...)`.

  Assertions:
  - `SET TRANSACTION READ ONLY` appears in the captured statements before any
    graph query statement.
  - `SET LOCAL statement_timeout = ...` also appears (validates the timeout wiring
    is present).

  ## Files / Areas Affected

  - `src/api/tests/integration/query/test_read_only_primary_defense.py` (new) — the
    two integration test cases described above
  - `src/api/tests/integration/conftest.py` — fixture for a direct
    `QueryGraphRepository` instance pointed at the test PostgreSQL+AGE database
  - No production code changes expected; if the test reveals the primary defense is
    missing or misplaced, fix `query/infrastructure/query_repository.py` and note it
    in the PR description

  ## Tests

  The integration tests ARE the deliverable. Mark them with `@pytest.mark.integration`
  and ensure they run with `make test-integration` against the isolated dev instance.

  Infrastructure requirements (provided by `make instance-up`):
  - PostgreSQL with Apache AGE extension loaded
  - Direct psycopg2 connection available for `QueryGraphRepository` (not via MCP HTTP)

  ## How to Verify

  1. `make instance-up` — start isolated test instance
  2. `source .instances/$(basename $(pwd))/.env.instance`
  3. `cd src/api && uv run pytest tests/integration/ -v -m integration -k "read_only_primary"`
  4. Confirm both tests pass green; specifically confirm that test 1 fails when
     `SET TRANSACTION READ ONLY` is temporarily removed from the repository

  ## Caveats

  - The keyword blacklist bypass in test 1 MUST be done via patching or subclassing
    only — never by modifying production code. Use `unittest.mock.patch` or a test
    subclass of `QueryGraphRepository` that overrides `_validate_read_only()`.
  - Test 2 (statement capture) may be complex depending on psycopg2 connection
    wrapping. An alternative: use a `cursor_factory` that records executed SQL.
    If too complex, a simpler proxy approach is acceptable.
  - Ensure the test AGE graph (`tenant_{test_tenant_id}`) exists before calling
    `execute_cypher()` directly, as `QueryGraphRepository` does not check existence
    (that is `TenantAwareQueryGraphRepository`'s responsibility).
  - Clean up any nodes that might have been created if the primary defense somehow
    fails, using a fixture teardown that deletes `(:PrimaryDefenseTest)` nodes.
---
