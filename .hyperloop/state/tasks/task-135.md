---
id: task-135
title: "Query execution — cross-tenant isolation integration test"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add cross-tenant isolation integration test for query execution"
pr_description: |
  ## What and Why

  The Query Execution spec requires that queries are strictly isolated to the
  caller's tenant and can never observe data from another tenant — regardless
  of what the Cypher query contains:

  > **Requirement: Per-Tenant Graph Routing — Scenario: Query routed to
  > tenant graph**
  > GIVEN an authenticated query request
  > WHEN the query is executed
  > THEN it executes against the AGE graph named `tenant_{tenant_id}` for the
  > resolved tenant
  > AND queries never cross tenant boundaries regardless of query content

  The existing integration test `test_query_mcp.py` exercises the repository
  against a **single** AGE graph.  It never provisions two separate tenant
  graphs and confirms that tenant A's data is invisible to a repository
  configured for tenant B.  Without this test a bug that accidentally routes
  all queries to a shared graph (or uses the wrong `SET GRAPH` command) would
  not be caught.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`

  - **Requirement: Per-Tenant Graph Routing — Scenario: Query routed to
    tenant graph**: enforces `tenant_{tenant_id}` naming and no cross-tenant
    data leakage.
  - **Requirement: Per-Tenant Graph Routing — Scenario: Tenant graph not
    found**: verifies the pre-flight guard raises `QueryExecutionError` before
    a Cypher round-trip.

  ## What This Change Does

  Adds a new integration test file
  `src/api/tests/integration/test_cross_tenant_isolation.py`.

  ### `TestCrossTenantIsolation`

  **`test_tenant_a_data_invisible_to_tenant_b_repository`**

  1. Provision two AGE graphs: `tenant_aaa` and `tenant_bbb` (using helpers
     from `conftest.py` or the `AgeGraphClient`).
  2. Insert a `Person {name: "Alice"}` node into `tenant_aaa`.
  3. Construct a `QueryGraphRepository` pointing at `tenant_bbb`.
  4. Execute `MATCH (p:Person) RETURN p` via the repository.
  5. Assert the result set is **empty** — Alice is not visible from
     tenant_bbb's repository.
  6. Tear down both graphs in fixture cleanup.

  **`test_tenant_b_data_invisible_to_tenant_a_repository`**

  Symmetric: insert Bob into `tenant_bbb`, query from `tenant_aaa`, assert
  empty result.

  **`test_query_routed_to_correct_tenant_graph`**

  1. Insert Alice into `tenant_aaa` and Bob into `tenant_bbb`.
  2. Query `tenant_aaa` — assert one row (Alice), not Bob.
  3. Query `tenant_bbb` — assert one row (Bob), not Alice.

  **`test_tenant_graph_not_found_raises_before_cypher_execution`**

  Construct a repository pointing at `tenant_nonexistent` (graph never
  provisioned).  Call `execute_cypher` with any query and assert
  `QueryExecutionError` is raised with a message identifying the missing
  graph.  Confirm no Cypher round-trip reaches the database (the pre-flight
  `_validate_graph_exists` check is the blocker).

  ## Files / Areas Affected

  - `src/api/tests/integration/test_cross_tenant_isolation.py` — new file
  - `src/api/tests/integration/conftest.py` — may need a helper fixture to
    provision a named AGE graph and tear it down after each test

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_cross_tenant_isolation.py \
      -v -m integration
  ```

  All four tests must pass. Production code must not require changes — the
  cross-tenant routing is already implemented via `AgeGraphClient`'s graph
  name configuration.

  ## Implementation Notes

  - Use `AgeGraphClient` with different `graph_name` values (`tenant_aaa`,
    `tenant_bbb`) to create two distinct `QueryGraphRepository` instances.
  - If `conftest.py` has a `clean_graph` fixture that creates and tears down
    a graph, extend or reuse it for a second graph. Use unique names to avoid
    collision with the shared `test_graph`.
  - The `MATCH (n) RETURN n` query without a LIMIT will have one appended
    automatically by `_ensure_limit`, which is fine for these tests.
  - Write tests FIRST (TDD). The production implementation should require
    zero changes if routing is already correct.

  ## Caveats

  - Requires a running PostgreSQL+AGE instance (`make instance-up`).
  - Graph provisioning may need `CREATE GRAPH tenant_bbb` via raw SQL before
    the `AgeGraphClient` can execute Cypher against it — check how
    `conftest.py`'s existing graph fixtures provision the test graph.
  - Clean up both graphs in fixture teardown to avoid orphaned graphs leaking
    between test runs.
---
