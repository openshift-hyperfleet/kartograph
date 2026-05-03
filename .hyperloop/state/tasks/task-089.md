---
id: task-089
title: Route MCP queries to per-tenant AGE graph
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): route MCP queries to tenant-specific AGE graph"
pr_description: |
  ## What and Why

  The query-execution spec (Requirement: Per-Tenant Graph Routing) mandates that
  every Cypher query executes against the AGE graph named `tenant_{tenant_id}`
  for the authenticated caller's tenant, never the default graph.

  Currently `get_mcp_query_service()` in `src/api/query/dependencies.py` creates
  an `AgeGraphClient` without a tenant-specific `graph_name` argument, meaning
  all MCP queries run against `settings.graph_name` (the default single-tenant
  graph). This violates the per-tenant isolation requirement and will silently
  return wrong data as soon as more than one tenant's data is present.

  The `MCPAuthContext` (set by the auth middleware for every MCP request) already
  carries `tenant_id`, so the routing information is available — it just isn't
  being used.

  ## Spec Requirements Satisfied

  - **Scenario: Query routed to tenant graph** — queries execute against
    `tenant_{tenant_id}` and never cross tenant boundaries.
  - **Scenario: Tenant graph not found** — if the AGE graph for the tenant has
    not been provisioned, the request is rejected with an execution error before
    reaching the database.

  ## Key Design Decisions

  ### Tenant graph routing
  `get_mcp_query_service()` (or its inner `mcp_graph_client_context()`) must:
  1. Call `get_mcp_auth_context()` to obtain `tenant_id`.
  2. Construct `graph_name = f"tenant_{tenant_id}"`.
  3. Pass `graph_name` to `AgeGraphClient.__init__` (the constructor already
     accepts this parameter for per-tenant isolation).

  `mcp_graph_client_context` should be refactored to accept an optional
  `graph_name` parameter so the test surface remains clean.

  ### Tenant graph existence check
  `AgeGraphClient.connect()` currently auto-creates the graph if it does not
  exist — correct for provisioning contexts, wrong for the Query context. Two
  options:
  a) Add an `existence_only=True` mode to `AgeGraphClient` that raises
     `QueryExecutionError` instead of auto-creating.
  b) **Preferred**: Add a lightweight existence check inside
     `QueryGraphRepository.execute_cypher` (or a new `ensure_graph_exists`
     helper) that queries `ag_catalog.ag_graph` before running the user query
     and raises `QueryExecutionError("Tenant graph not provisioned")` when the
     graph is absent.

  Option (b) keeps the Graph infrastructure unchanged and is simpler to test in
  isolation.

  ### Error propagation
  The `QueryExecutionError` raised for "graph not found" surfaces to the caller
  as `error_type = "execution_error"` through the existing error categorisation in
  `MCPQueryService`, which is the spec's expected behaviour.

  ## Files / Areas Affected

  - `src/api/query/dependencies.py` — `mcp_graph_client_context()` and
    `get_mcp_query_service()`: read `MCPAuthContext.tenant_id`, derive
    `graph_name`, pass to `AgeGraphClient`
  - `src/api/query/infrastructure/query_repository.py` — add a pre-execution
    check that the `tenant_{tenant_id}` AGE graph exists; raise
    `QueryExecutionError` if not
  - `src/api/tests/unit/query/test_query_repository.py` — add tests for
    "tenant graph not found" scenario (mock `ag_catalog.ag_graph` returning
    no rows)
  - `src/api/tests/unit/query/test_mcp_auth_wiring.py` or new
    `test_mcp_tenant_routing.py` — unit tests verifying the correct graph name
    is passed to `AgeGraphClient` based on `MCPAuthContext.tenant_id`
  - `src/api/tests/integration/test_query_mcp.py` — ensure existing integration
    tests still pass with the tenant-scoped graph name (`tenant_{tenant_id}`)

  ## How to Verify

  1. `make test-unit` — new unit tests must pass.
  2. `make instance-up` — the instance manager provisions a tenant graph during
     setup; the `test-integration` suite should pass unchanged.
  3. Manually create a second tenant (no AGE graph provisioned) and attempt an
     MCP query with that tenant's API key — expect `error_type: "execution_error"`
     in the response.
  4. Confirm that queries from tenant A never return nodes/edges belonging to
     tenant B by checking the `knowledge_graph_id` properties in results.

  ## Caveats

  - The integration test suite uses a single test tenant whose graph is
    provisioned by the instance setup script. All existing tests should continue
    to pass without modification; only the graph-name parameter changes.
  - If `MCPAuthContext` is not set when `get_mcp_query_service()` is called
    (e.g., in a test that bypasses the auth middleware), the call to
    `get_mcp_auth_context()` will raise `LookupError`. Unit tests for the
    dependency function must mock the context var.
  - The "tenant graph not found" check adds one extra SQL query per MCP query
    execution. This is acceptable for correctness; it can be cached per-request
    if profiling shows it is a bottleneck.
---
