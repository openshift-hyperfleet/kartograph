---
id: task-135
title: Query execution — cross-tenant isolation integration test
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: implement
deps: []
round: 0
branch: hyperloop/task-135
pr: null
pr_title: 'test(query): add cross-tenant isolation integration test for query execution'
pr_description: "## What and Why\n\nThe Query Execution spec requires that queries\
  \ are strictly isolated to the\ncaller's tenant and can never observe data from\
  \ another tenant — regardless\nof what the Cypher query contains:\n\n> **Requirement:\
  \ Per-Tenant Graph Routing — Scenario: Query routed to\n> tenant graph**\n> GIVEN\
  \ an authenticated query request\n> WHEN the query is executed\n> THEN it executes\
  \ against the AGE graph named `tenant_{tenant_id}` for the\n> resolved tenant\n\
  > AND queries never cross tenant boundaries regardless of query content\n\nThe existing\
  \ integration test `test_query_mcp.py` exercises the repository\nagainst a **single**\
  \ AGE graph.  It never provisions two separate tenant\ngraphs and confirms that\
  \ tenant A's data is invisible to a repository\nconfigured for tenant B.  Without\
  \ this test a bug that accidentally routes\nall queries to a shared graph (or uses\
  \ the wrong `SET GRAPH` command) would\nnot be caught.\n\n## Spec Requirements Satisfied\n\
  \n`specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`\n\
  \n- **Requirement: Per-Tenant Graph Routing — Scenario: Query routed to\n  tenant\
  \ graph**: enforces `tenant_{tenant_id}` naming and no cross-tenant\n  data leakage.\n\
  - **Requirement: Per-Tenant Graph Routing — Scenario: Tenant graph not\n  found**:\
  \ verifies the pre-flight guard raises `QueryExecutionError` before\n  a Cypher\
  \ round-trip.\n\n## What This Change Does\n\nAdds a new integration test file\n\
  `src/api/tests/integration/test_cross_tenant_isolation.py`.\n\n### `TestCrossTenantIsolation`\n\
  \n**`test_tenant_a_data_invisible_to_tenant_b_repository`**\n\n1. Provision two\
  \ AGE graphs: `tenant_aaa` and `tenant_bbb` (using helpers\n   from `conftest.py`\
  \ or the `AgeGraphClient`).\n2. Insert a `Person {name: \"Alice\"}` node into `tenant_aaa`.\n\
  3. Construct a `QueryGraphRepository` pointing at `tenant_bbb`.\n4. Execute `MATCH\
  \ (p:Person) RETURN p` via the repository.\n5. Assert the result set is **empty**\
  \ — Alice is not visible from\n   tenant_bbb's repository.\n6. Tear down both graphs\
  \ in fixture cleanup.\n\n**`test_tenant_b_data_invisible_to_tenant_a_repository`**\n\
  \nSymmetric: insert Bob into `tenant_bbb`, query from `tenant_aaa`, assert\nempty\
  \ result.\n\n**`test_query_routed_to_correct_tenant_graph`**\n\n1. Insert Alice\
  \ into `tenant_aaa` and Bob into `tenant_bbb`.\n2. Query `tenant_aaa` — assert one\
  \ row (Alice), not Bob.\n3. Query `tenant_bbb` — assert one row (Bob), not Alice.\n\
  \n**`test_tenant_graph_not_found_raises_before_cypher_execution`**\n\nConstruct\
  \ a repository pointing at `tenant_nonexistent` (graph never\nprovisioned).  Call\
  \ `execute_cypher` with any query and assert\n`QueryExecutionError` is raised with\
  \ a message identifying the missing\ngraph.  Confirm no Cypher round-trip reaches\
  \ the database (the pre-flight\n`_validate_graph_exists` check is the blocker).\n\
  \n## Files / Areas Affected\n\n- `src/api/tests/integration/test_cross_tenant_isolation.py`\
  \ — new file\n- `src/api/tests/integration/conftest.py` — may need a helper fixture\
  \ to\n  provision a named AGE graph and tear it down after each test\n\n## How to\
  \ Verify\n\n```bash\nmake instance-up\nsource .instances/$(basename $(pwd))/.env.instance\n\
  cd src/api && uv run pytest tests/integration/test_cross_tenant_isolation.py \\\n\
  \    -v -m integration\n```\n\nAll four tests must pass. Production code must not\
  \ require changes — the\ncross-tenant routing is already implemented via `AgeGraphClient`'s\
  \ graph\nname configuration.\n\n## Implementation Notes\n\n- Use `AgeGraphClient`\
  \ with different `graph_name` values (`tenant_aaa`,\n  `tenant_bbb`) to create two\
  \ distinct `QueryGraphRepository` instances.\n- If `conftest.py` has a `clean_graph`\
  \ fixture that creates and tears down\n  a graph, extend or reuse it for a second\
  \ graph. Use unique names to avoid\n  collision with the shared `test_graph`.\n\
  - The `MATCH (n) RETURN n` query without a LIMIT will have one appended\n  automatically\
  \ by `_ensure_limit`, which is fine for these tests.\n- Write tests FIRST (TDD).\
  \ The production implementation should require\n  zero changes if routing is already\
  \ correct.\n\n## Caveats\n\n- Requires a running PostgreSQL+AGE instance (`make\
  \ instance-up`).\n- Graph provisioning may need `CREATE GRAPH tenant_bbb` via raw\
  \ SQL before\n  the `AgeGraphClient` can execute Cypher against it — check how\n\
  \  `conftest.py`'s existing graph fixtures provision the test graph.\n- Clean up\
  \ both graphs in fixture teardown to avoid orphaned graphs leaking\n  between test\
  \ runs."
---
