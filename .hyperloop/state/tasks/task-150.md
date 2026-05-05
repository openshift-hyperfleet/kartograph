---
id: task-150
title: "Add integration tests for per-tenant graph routing (query execution spec)"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration tests for per-tenant graph routing"
pr_description: |
  ## What and Why

  The Query Execution spec's "Per-Tenant Graph Routing" requirement (newly added
  in commit `6bea4557d`) defines two scenarios:

  > **Requirement: Per-Tenant Graph Routing**
  >
  > **Scenario: Query routed to tenant graph**
  > "GIVEN an authenticated query request
  >  WHEN the query is executed
  >  THEN it executes against the AGE graph named `tenant_{tenant_id}` for the
  >  resolved tenant
  >  AND queries never cross tenant boundaries regardless of query content"
  >
  > **Scenario: Tenant graph not found**
  > "GIVEN a tenant whose AGE graph has not been provisioned
  >  WHEN a query is submitted
  >  THEN the request is rejected with an execution error before reaching the
  >  database"

  Both scenarios are implemented in `TenantAwareQueryGraphRepository` (added as
  a routing decorator over `QueryGraphRepository`) and are verified by
  comprehensive unit tests in `tests/unit/query/test_tenant_routing.py`.

  However, no integration test exercises these scenarios against a real
  PostgreSQL + Apache AGE instance. The per-tenant isolation guarantee is a
  security property — queries must **never** cross tenant boundaries — and that
  property deserves end-to-end verification against the actual database, not
  just unit-level fakes.

  This mirrors the pattern established by task-149 (which added tests for the
  503 auth scenario that was implemented but untested).

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`

  - **Requirement: Per-Tenant Graph Routing — Scenario: Query routed to tenant graph**
    Verify that `TenantAwareQueryGraphRepository.execute_cypher` directs the query
    to the real `tenant_{tenant_id}` AGE graph in PostgreSQL.

  - **Requirement: Per-Tenant Graph Routing — Scenario: Tenant graph not found**
    Verify that when the graph `tenant_{tenant_id}` does not exist in
    `ag_catalog.ag_graph`, the query raises `QueryExecutionError` before any
    Cypher reaches the database.

  ## Key Design Decisions

  **Integration tests run against `make instance-up`** (PostgreSQL + AGE,
  no Keycloak needed). Mark tests with `@pytest.mark.integration`.

  **Test structure** — two test classes:

  1. **`TestQueryRoutedToTenantGraph`**: Provision a test tenant graph
     (`tenant_{uuid}`) in the real AGE instance, execute a simple Cypher query
     through `TenantAwareQueryGraphRepository`, and assert the results come back
     (proving the query hit the correct graph). Clean up the test graph in a
     fixture teardown.

  2. **`TestTenantGraphNotFound`**: Attempt to query against a non-existent
     tenant ID (one for which no `ag_catalog.ag_graph` entry exists) and assert
     that `QueryExecutionError` is raised _without_ any database error from a
     failed graph lookup.

  **No MCP layer required** — these tests exercise `QueryGraphRepository` and
  `TenantAwareQueryGraphRepository` directly, bypassing the MCP presentation
  layer. This keeps the tests focused on the routing requirement and avoids
  the authentication overhead of standing up the full MCP stack.

  **Graph provisioning** — use the same `CREATE EXTENSION IF NOT EXISTS age`
  + `SELECT create_graph('tenant_{test_id}')` pattern used by the IAM/Graph
  bounded context for tenant provisioning. Tear down with
  `SELECT drop_graph('tenant_{test_id}', true)` in an `autouse` fixture.

  ## What Files Are Affected

  - **New file**:
    `src/api/tests/integration/query/test_tenant_routing_integration.py`
    — Two test classes covering the two Per-Tenant Graph Routing scenarios.
    Fixtures: async engine from `DatabaseSettings`, graph create/drop helpers.
    Marks: `@pytest.mark.integration`.

  - No implementation files change — the behavior is already correct;
    only integration-level test coverage is missing.

  ## How to Verify

  ```bash
  # Start isolated dev instance
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance

  # Run the new integration tests
  cd src/api && uv run pytest tests/integration/query/test_tenant_routing_integration.py \
      -v -m integration

  # Full integration suite — confirm no regressions
  make test-integration
  ```

  ## Caveats

  - The test must clean up the provisioned AGE graph even if the test fails
    (use `autouse` fixtures with `try/finally` or `addfinalizer`).
  - Do NOT use a graph name that collides with any production or existing test
    graph; generate a UUID suffix for isolation.
  - The `TenantAwareQueryGraphRepository` wraps `QueryGraphRepository` with a
    `TenantGraphClient` that sets `graph_name = f"tenant_{tenant_id}"`. The
    integration test should build the repository the same way the DI layer does
    (see `query/dependencies.py` and `query/infrastructure/tenant_routing.py`).
  - AGE graphs are PostgreSQL schema-level objects; ensure the test user has
    `CREATE SCHEMA` and `USAGE` on the `ag_catalog` schema.
---
