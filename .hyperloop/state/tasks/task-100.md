---
id: task-100
title: Add cross-tenant boundary enforcement integration test for MCP queries
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: verify
deps: []
round: 8
branch: hyperloop/task-100
pr: https://github.com/openshift-hyperfleet/kartograph/pull/566
pr_title: 'test(query): add cross-tenant isolation integration test for MCP query
  execution'
pr_description: "## What & Why\n\nThe **Per-Tenant Graph Routing** requirement in\
  \ `specs/query/query-execution.spec.md`\nstates:\n\n> \"THEN it executes against\
  \ the AGE graph named `tenant_{tenant_id}` for the\n> resolved tenant AND queries\
  \ never cross tenant boundaries regardless of query\n> content.\"\n\nThe existing\
  \ integration test suite (`test_query_mcp.py`) uses a shared test graph\n(`test_graph`,\
  \ see `conftest.py` line 71) rather than a `tenant_{tenant_id}`-named\ngraph. As\
  \ a result, the cross-tenant isolation guarantee is **never verified at the\nintegration\
  \ level**.\n\nThe unit tests in `tests/unit/query/test_query_repository.py`\n(`TestTenantGraphRouting`)\
  \ verify the behavior through mocks, but mock-based tests\ncannot catch the real\
  \ database behavior where:\n- `tenant_a` could accidentally read `tenant_b`'s data\
  \ if the graph name resolution\n  is broken\n- The AGE `SET GRAPH PATH` or equivalent\
  \ routing mechanism has a bug in production\n\nThis task adds an integration test\
  \ that provisions two real AGE graphs with\n`tenant_` prefix names, writes distinct\
  \ data to each, and verifies that queries\nrouted to `tenant_a` cannot see `tenant_b`'s\
  \ data.\n\n## Spec Requirements Satisfied\n\n`specs/query/query-execution.spec.md`\
  \ — **Requirement: Per-Tenant Graph Routing**:\n- Scenario: *Query routed to tenant\
  \ graph* — `tenant_{tenant_id}`\n- Scenario: *Tenant graph not found* — rejected\
  \ before reaching DB\n\n## Files Affected\n\n- `src/api/tests/integration/test_query_mcp.py`\n\
  \  — new test class `TestCrossTenantIsolation` with:\n    - `test_tenant_a_cannot_see_tenant_b_data`:\
  \ provision two AGE graphs\n      (`tenant_test_a`, `tenant_test_b`), insert a unique\
  \ node in each,\n      query via `QueryGraphRepository` scoped to `tenant_test_a`,\
  \ assert\n      only `tenant_a`'s node is returned\n    - `test_tenant_graph_not_found_raises_before_db`:\
  \ configure client with\n      `graph_name=\"tenant_nonexistent_xyz\"` (graph that\
  \ doesn't exist),\n      call `execute_cypher`, assert `QueryExecutionError` is\
  \ raised and\n      `transaction()` is never opened\n\n## Test Setup\n\nThe tests\
  \ need a helper to create/drop AGE graphs:\n```python\ndef _create_age_graph(conn,\
  \ name: str) -> None:\n    conn.execute(text(f\"SELECT ag_catalog.create_graph('{name}')\"\
  ))\n\ndef _drop_age_graph(conn, name: str) -> None:\n    conn.execute(text(f\"SELECT\
  \ ag_catalog.drop_graph('{name}', true)\"))\n```\n\nBoth graphs must be cleaned\
  \ up in test teardown to avoid polluting other tests.\n\n## TDD Cycle\n\n1. Write\
  \ `TestCrossTenantIsolation` with the two test methods → RED (test infra\n   needs\
  \ the helper functions)\n2. Implement helper functions → GREEN\n3. Run: `cd src/api\
  \ && uv run pytest tests/integration/test_query_mcp.py::TestCrossTenantIsolation\
  \ -v`\n4. Commit atomically\n\n## How to Verify\n\n```bash\ncd src/api\nuv run pytest\
  \ tests/integration/test_query_mcp.py::TestCrossTenantIsolation -v -m integration\n\
  ```\n\nExpected:\n- `test_tenant_a_cannot_see_tenant_b_data`: only tenant_a's node\
  \ returned ✓\n- `test_tenant_graph_not_found_raises_before_db`: `QueryExecutionError`\
  \ raised,\n  no DB transaction opened ✓\n\n## Caveats\n\n- AGE graph creation/deletion\
  \ requires superuser or `ag_catalog` privileges — the\n  test user must have `CREATE\
  \ GRAPH` permission. Verify in the test DB setup.\n- Tests must clean up their graphs\
  \ in `finally` blocks to prevent leftover state.\n- These tests are in the `integration`\
  \ mark and require a running DB instance."
---
