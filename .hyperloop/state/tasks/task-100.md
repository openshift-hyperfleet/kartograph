---
id: task-100
title: Add cross-tenant boundary enforcement integration test for MCP queries
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add cross-tenant isolation integration test for MCP query execution"
pr_description: |
  ## What & Why

  The **Per-Tenant Graph Routing** requirement in `specs/query/query-execution.spec.md`
  states:

  > "THEN it executes against the AGE graph named `tenant_{tenant_id}` for the
  > resolved tenant AND queries never cross tenant boundaries regardless of query
  > content."

  The existing integration test suite (`test_query_mcp.py`) uses a shared test graph
  (`test_graph`, see `conftest.py` line 71) rather than a `tenant_{tenant_id}`-named
  graph. As a result, the cross-tenant isolation guarantee is **never verified at the
  integration level**.

  The unit tests in `tests/unit/query/test_query_repository.py`
  (`TestTenantGraphRouting`) verify the behavior through mocks, but mock-based tests
  cannot catch the real database behavior where:
  - `tenant_a` could accidentally read `tenant_b`'s data if the graph name resolution
    is broken
  - The AGE `SET GRAPH PATH` or equivalent routing mechanism has a bug in production

  This task adds an integration test that provisions two real AGE graphs with
  `tenant_` prefix names, writes distinct data to each, and verifies that queries
  routed to `tenant_a` cannot see `tenant_b`'s data.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md` — **Requirement: Per-Tenant Graph Routing**:
  - Scenario: *Query routed to tenant graph* — `tenant_{tenant_id}`
  - Scenario: *Tenant graph not found* — rejected before reaching DB

  ## Files Affected

  - `src/api/tests/integration/test_query_mcp.py`
    — new test class `TestCrossTenantIsolation` with:
      - `test_tenant_a_cannot_see_tenant_b_data`: provision two AGE graphs
        (`tenant_test_a`, `tenant_test_b`), insert a unique node in each,
        query via `QueryGraphRepository` scoped to `tenant_test_a`, assert
        only `tenant_a`'s node is returned
      - `test_tenant_graph_not_found_raises_before_db`: configure client with
        `graph_name="tenant_nonexistent_xyz"` (graph that doesn't exist),
        call `execute_cypher`, assert `QueryExecutionError` is raised and
        `transaction()` is never opened

  ## Test Setup

  The tests need a helper to create/drop AGE graphs:
  ```python
  def _create_age_graph(conn, name: str) -> None:
      conn.execute(text(f"SELECT ag_catalog.create_graph('{name}')"))

  def _drop_age_graph(conn, name: str) -> None:
      conn.execute(text(f"SELECT ag_catalog.drop_graph('{name}', true)"))
  ```

  Both graphs must be cleaned up in test teardown to avoid polluting other tests.

  ## TDD Cycle

  1. Write `TestCrossTenantIsolation` with the two test methods → RED (test infra
     needs the helper functions)
  2. Implement helper functions → GREEN
  3. Run: `cd src/api && uv run pytest tests/integration/test_query_mcp.py::TestCrossTenantIsolation -v`
  4. Commit atomically

  ## How to Verify

  ```bash
  cd src/api
  uv run pytest tests/integration/test_query_mcp.py::TestCrossTenantIsolation -v -m integration
  ```

  Expected:
  - `test_tenant_a_cannot_see_tenant_b_data`: only tenant_a's node returned ✓
  - `test_tenant_graph_not_found_raises_before_db`: `QueryExecutionError` raised,
    no DB transaction opened ✓

  ## Caveats

  - AGE graph creation/deletion requires superuser or `ag_catalog` privileges — the
    test user must have `CREATE GRAPH` permission. Verify in the test DB setup.
  - Tests must clean up their graphs in `finally` blocks to prevent leftover state.
  - These tests are in the `integration` mark and require a running DB instance.
---
