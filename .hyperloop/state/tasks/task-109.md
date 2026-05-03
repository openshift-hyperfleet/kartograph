---
id: task-109
title: "Per-Tenant Graph Routing — integration tests for tenant-scoped AGE graph queries"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration tests for per-tenant AGE graph routing"
pr_description: |
  ## What & Why

  The **Per-Tenant Graph Routing** requirement added to `specs/query/query-execution.spec.md`
  defines two scenarios:

  > "GIVEN a valid MCP API key associated with tenant A WHEN the query_graph tool is
  > invoked THEN the query executes against the AGE graph named `tenant_{tenant_A_id}`
  > AND data from tenant B's graph is not accessible"

  > "GIVEN a tenant whose AGE graph does not yet exist WHEN the query_graph tool is
  > invoked THEN the server returns a structured error indicating the knowledge graph
  > context is unavailable (NOT a raw database error)"

  The routing implementation is complete — `TenantAwareQueryGraphRepository` wraps
  `QueryGraphRepository`, resolves `tenant_{tenant_id}` as the graph name, checks
  existence via `AGEGraphExistenceChecker`, and rejects queries before execution if
  the graph is absent. Unit tests in `tests/unit/query/test_query_repository.py`
  (`TestTenantGraphRouting`) confirm the logic at the repository level.

  What is missing is end-to-end integration coverage exercising the full call chain:
  API key auth middleware → `get_mcp_query_service()` dependency → `TenantAwareQueryGraphRepository`
  → real PostgreSQL/AGE. Without this, a regression anywhere in the wiring (e.g.,
  `tenant_id` not propagated from auth context, graph name format change) would
  only be caught by production traffic.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md`:
  - **Requirement: Per-Tenant Graph Routing** — Scenario: *Query executes in tenant graph*
  - **Requirement: Per-Tenant Graph Routing** — Scenario: *Tenant graph not found*

  ## What This Change Does

  Add integration tests in `src/api/tests/integration/query/` (or extend
  `test_query_mcp.py`) that exercise per-tenant routing against a real
  PostgreSQL+AGE instance:

  ### Test: `test_query_executes_in_tenant_graph`

  Setup:
  1. Create two AGE graphs in the test database: `tenant_alpha` and `tenant_beta`.
  2. Insert a distinguishing node into `tenant_alpha` (e.g., `(:Marker {name: 'alpha'})`).
  3. Insert a different node into `tenant_beta` (e.g., `(:Marker {name: 'beta'})`).
  4. Obtain an API key scoped to `tenant_id = "alpha"`.

  Execution:
  - POST to the MCP `query_graph` tool with `query: "MATCH (n:Marker) RETURN n"`.

  Assertions:
  - Response is 200.
  - Result rows contain the `alpha` marker node.
  - Result rows do NOT contain the `beta` marker node.

  ### Test: `test_tenant_graph_not_found_returns_structured_error`

  Setup:
  1. Ensure no AGE graph named `tenant_missing` exists.
  2. Obtain an API key scoped to `tenant_id = "missing"`.

  Execution:
  - POST to the MCP `query_graph` tool with any valid Cypher.

  Assertions:
  - Response is 200 (MCP protocol: errors are returned in the response body, not HTTP 4xx).
  - Response body is an MCP error structure (not a raw PostgreSQL exception).
  - Error message references the knowledge graph context being unavailable (not a raw
    `psycopg2.ProgrammingError` or similar).

  ## Files / Areas Affected

  - `src/api/tests/integration/query/test_tenant_routing.py` (new) — the two integration
    test cases described above
  - `src/api/tests/integration/conftest.py` or a new fixtures module — fixtures for
    creating/dropping AGE graphs and issuing test API keys scoped to specific tenant IDs
  - No production code changes are expected; if a test reveals a real bug, fix it
    and note it in the PR description

  ## Tests

  The two integration tests ARE the deliverable. Mark them with `@pytest.mark.integration`
  and ensure they run with `make test-integration` against the isolated dev instance.

  Infrastructure requirements (provided by `make instance-up`):
  - PostgreSQL with Apache AGE extension loaded
  - Kartograph API running (for MCP HTTP endpoint)
  - A way to create/drop AGE graphs in the test database (direct psycopg2 connection
    or a test fixture that calls `CREATE EXTENSION IF NOT EXISTS age` + `SELECT create_graph(...)`)

  ## How to Verify

  1. `make instance-up` — start isolated test instance
  2. `source .instances/$(basename $(pwd))/.env.instance`
  3. `cd src/api && uv run pytest tests/integration/query/test_tenant_routing.py -v -m integration`
  4. Confirm both tests pass green

  ## Caveats

  - AGE graph creation requires superuser or `CREATE` privilege; the test database user
    must have this privilege, or the fixture must use a superuser connection.
  - Tear down created graphs after each test to avoid cross-test pollution.
  - The `TenantAwareQueryGraphRepository` uses `ag_catalog.ag_graph` to check existence;
    the integration test implicitly validates this query works against the real AGE
    catalog, not just a mock.
  - If `tenant_id` is a UUID in production but a short string in tests, ensure the
    graph name format (`tenant_{tenant_id}`) is consistent with what `get_mcp_query_service()`
    actually constructs.
---
