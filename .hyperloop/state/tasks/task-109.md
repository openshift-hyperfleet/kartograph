---
id: task-109
title: Per-Tenant Graph Routing — integration tests for tenant-scoped AGE graph queries
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: implement
deps: []
round: 9
branch: hyperloop/task-109
pr: https://github.com/openshift-hyperfleet/kartograph/pull/576
pr_title: 'test(query): add integration tests for per-tenant AGE graph routing'
pr_description: "## What & Why\n\nThe **Per-Tenant Graph Routing** requirement added\
  \ to `specs/query/query-execution.spec.md`\ndefines two scenarios:\n\n> \"GIVEN\
  \ a valid MCP API key associated with tenant A WHEN the query_graph tool is\n> invoked\
  \ THEN the query executes against the AGE graph named `tenant_{tenant_A_id}`\n>\
  \ AND data from tenant B's graph is not accessible\"\n\n> \"GIVEN a tenant whose\
  \ AGE graph does not yet exist WHEN the query_graph tool is\n> invoked THEN the\
  \ server returns a structured error indicating the knowledge graph\n> context is\
  \ unavailable (NOT a raw database error)\"\n\nThe routing implementation is complete\
  \ — `TenantAwareQueryGraphRepository` wraps\n`QueryGraphRepository`, resolves `tenant_{tenant_id}`\
  \ as the graph name, checks\nexistence via `AGEGraphExistenceChecker`, and rejects\
  \ queries before execution if\nthe graph is absent. Unit tests in `tests/unit/query/test_query_repository.py`\n\
  (`TestTenantGraphRouting`) confirm the logic at the repository level.\n\nWhat is\
  \ missing is end-to-end integration coverage exercising the full call chain:\nAPI\
  \ key auth middleware → `get_mcp_query_service()` dependency → `TenantAwareQueryGraphRepository`\n\
  → real PostgreSQL/AGE. Without this, a regression anywhere in the wiring (e.g.,\n\
  `tenant_id` not propagated from auth context, graph name format change) would\n\
  only be caught by production traffic.\n\n## Spec Requirements Satisfied\n\n`specs/query/query-execution.spec.md`:\n\
  - **Requirement: Per-Tenant Graph Routing** — Scenario: *Query executes in tenant\
  \ graph*\n- **Requirement: Per-Tenant Graph Routing** — Scenario: *Tenant graph\
  \ not found*\n\n## What This Change Does\n\nAdd integration tests in `src/api/tests/integration/query/`\
  \ (or extend\n`test_query_mcp.py`) that exercise per-tenant routing against a real\n\
  PostgreSQL+AGE instance:\n\n### Test: `test_query_executes_in_tenant_graph`\n\n\
  Setup:\n1. Create two AGE graphs in the test database: `tenant_alpha` and `tenant_beta`.\n\
  2. Insert a distinguishing node into `tenant_alpha` (e.g., `(:Marker {name: 'alpha'})`).\n\
  3. Insert a different node into `tenant_beta` (e.g., `(:Marker {name: 'beta'})`).\n\
  4. Obtain an API key scoped to `tenant_id = \"alpha\"`.\n\nExecution:\n- POST to\
  \ the MCP `query_graph` tool with `query: \"MATCH (n:Marker) RETURN n\"`.\n\nAssertions:\n\
  - Response is 200.\n- Result rows contain the `alpha` marker node.\n- Result rows\
  \ do NOT contain the `beta` marker node.\n\n### Test: `test_tenant_graph_not_found_returns_structured_error`\n\
  \nSetup:\n1. Ensure no AGE graph named `tenant_missing` exists.\n2. Obtain an API\
  \ key scoped to `tenant_id = \"missing\"`.\n\nExecution:\n- POST to the MCP `query_graph`\
  \ tool with any valid Cypher.\n\nAssertions:\n- Response is 200 (MCP protocol: errors\
  \ are returned in the response body, not HTTP 4xx).\n- Response body is an MCP error\
  \ structure (not a raw PostgreSQL exception).\n- Error message references the knowledge\
  \ graph context being unavailable (not a raw\n  `psycopg2.ProgrammingError` or similar).\n\
  \n## Files / Areas Affected\n\n- `src/api/tests/integration/query/test_tenant_routing.py`\
  \ (new) — the two integration\n  test cases described above\n- `src/api/tests/integration/conftest.py`\
  \ or a new fixtures module — fixtures for\n  creating/dropping AGE graphs and issuing\
  \ test API keys scoped to specific tenant IDs\n- No production code changes are\
  \ expected; if a test reveals a real bug, fix it\n  and note it in the PR description\n\
  \n## Tests\n\nThe two integration tests ARE the deliverable. Mark them with `@pytest.mark.integration`\n\
  and ensure they run with `make test-integration` against the isolated dev instance.\n\
  \nInfrastructure requirements (provided by `make instance-up`):\n- PostgreSQL with\
  \ Apache AGE extension loaded\n- Kartograph API running (for MCP HTTP endpoint)\n\
  - A way to create/drop AGE graphs in the test database (direct psycopg2 connection\n\
  \  or a test fixture that calls `CREATE EXTENSION IF NOT EXISTS age` + `SELECT create_graph(...)`)\n\
  \n## How to Verify\n\n1. `make instance-up` — start isolated test instance\n2. `source\
  \ .instances/$(basename $(pwd))/.env.instance`\n3. `cd src/api && uv run pytest\
  \ tests/integration/query/test_tenant_routing.py -v -m integration`\n4. Confirm\
  \ both tests pass green\n\n## Caveats\n\n- AGE graph creation requires superuser\
  \ or `CREATE` privilege; the test database user\n  must have this privilege, or\
  \ the fixture must use a superuser connection.\n- Tear down created graphs after\
  \ each test to avoid cross-test pollution.\n- The `TenantAwareQueryGraphRepository`\
  \ uses `ag_catalog.ag_graph` to check existence;\n  the integration test implicitly\
  \ validates this query works against the real AGE\n  catalog, not just a mock.\n\
  - If `tenant_id` is a UUID in production but a short string in tests, ensure the\n\
  \  graph name format (`tenant_{tenant_id}`) is consistent with what `get_mcp_query_service()`\n\
  \  actually constructs."
---
