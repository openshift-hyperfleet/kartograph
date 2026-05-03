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

  The **Per-Tenant Graph Routing** requirement in `specs/query/query-execution.spec.md`
  defines two scenarios:

  > "GIVEN an authenticated query request WHEN the query is executed THEN it executes
  > against the AGE graph named `tenant_{tenant_id}` for the resolved tenant AND queries
  > never cross tenant boundaries regardless of query content"

  > "GIVEN a tenant whose AGE graph has not been provisioned WHEN a query is submitted
  > THEN the request is rejected with an execution error before reaching the database"

  The routing implementation is complete — `TenantAwareQueryGraphRepository` wraps
  `QueryGraphRepository`, resolves `tenant_{tenant_id}` as the graph name, checks
  existence via `AGEGraphExistenceChecker`, and rejects queries before execution if
  the graph is absent. Unit tests in `tests/unit/query/test_tenant_routing.py` and
  `tests/unit/query/test_dependencies.py` confirm the logic at the repository and
  dependency-injection levels.

  What is missing is end-to-end integration coverage exercising the full call chain:
  API key auth middleware → `get_mcp_query_service()` dependency →
  `TenantAwareQueryGraphRepository` → real PostgreSQL/AGE. Without this, a regression
  anywhere in the wiring (e.g., `tenant_id` not propagated from auth context, graph
  name format change) would only be caught by production traffic.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md`:
  - **Requirement: Per-Tenant Graph Routing** — Scenario: *Query routed to tenant graph*
  - **Requirement: Per-Tenant Graph Routing** — Scenario: *Tenant graph not found*

  ## What This Change Does

  Add integration tests in `src/api/tests/integration/` (or extend
  `tests/integration/test_query_mcp.py`) that exercise per-tenant routing against a
  real PostgreSQL+AGE instance:

  ### Test: `test_query_executes_in_tenant_graph`

  Setup:
  1. Create two AGE graphs in the test database: `tenant_alpha` and `tenant_beta`.
  2. Insert a distinguishing node into `tenant_alpha` (e.g., `(:Marker {name: 'alpha'})`).
  3. Insert a different node into `tenant_beta` (e.g., `(:Marker {name: 'beta'})`).
  4. Obtain an API key scoped to `tenant_id = "alpha"`.

  Execution:
  - Call the MCP `query_graph` tool with `cypher: "MATCH (n:Marker) RETURN n"`.

  Assertions:
  - Result rows contain the `alpha` marker node.
  - Result rows do NOT contain the `beta` marker node.
  - Cross-tenant data isolation is enforced at the AGE graph level.

  ### Test: `test_tenant_graph_not_found_returns_structured_error`

  Setup:
  1. Ensure no AGE graph named `tenant_missing` exists.
  2. Obtain an API key scoped to `tenant_id = "missing"`.

  Execution:
  - Call the MCP `query_graph` tool with any valid Cypher.

  Assertions:
  - Response body has `success: False` and `error_type: "execution_error"`.
  - Error message references graph not being provisioned (not a raw
    `psycopg2.ProgrammingError` or similar database exception).

  ## Files / Areas Affected

  - `src/api/tests/integration/test_query_mcp.py` — extend with per-tenant routing
    test cases, OR create `src/api/tests/integration/query/test_tenant_routing.py`
  - `src/api/tests/integration/conftest.py` or a shared fixtures module — fixtures
    for creating/dropping AGE graphs and issuing test API keys scoped to specific
    tenant IDs
  - No production code changes are expected; if a test reveals a real bug, fix it
    and note it in the PR description

  ## Tests

  The integration tests ARE the deliverable. Mark them with `@pytest.mark.integration`
  and ensure they run with `make test-integration` against the isolated dev instance.

  Infrastructure requirements (provided by `make instance-up`):
  - PostgreSQL with Apache AGE extension loaded
  - Kartograph API running (for MCP HTTP endpoint)
  - Ability to create/drop AGE graphs in the test database (direct psycopg2 or
    a test fixture calling `SELECT create_graph(...)`)

  ## How to Verify

  1. `make instance-up` — start isolated test instance
  2. `source .instances/$(basename $(pwd))/.env.instance`
  3. `cd src/api && uv run pytest tests/integration/ -v -m integration -k "tenant_routing"`
  4. Confirm both tests pass green

  ## Caveats

  - AGE graph creation requires `CREATE` privilege in PostgreSQL; ensure the test
    database user has this, or use a superuser fixture connection.
  - Tear down created graphs after each test to avoid cross-test pollution.
  - The `TenantAwareQueryGraphRepository` uses `ag_catalog.ag_graph` to check graph
    existence; the integration test implicitly validates this catalog query against
    real AGE infrastructure.
  - If `tenant_id` is a ULID/UUID in production but a short string in tests, ensure
    the graph name format (`tenant_{tenant_id}`) is consistent with what
    `get_mcp_query_service()` constructs from the auth context.
---
