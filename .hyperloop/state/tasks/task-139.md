---
id: task-139
title: "Per-Tenant Graph Routing — cross-tenant isolation HTTP integration test"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration test verifying per-tenant graph routing and cross-tenant data isolation"
pr_description: |
  ## What and Why

  The Per-Tenant Graph Routing requirement specifies two scenarios. The second
  scenario is the primary security guarantee of the platform:

  > **Scenario: Query routed to tenant graph**
  > - GIVEN an authenticated query request
  > - WHEN the query is executed
  > - THEN it executes against the AGE graph named `tenant_{tenant_id}` for the resolved tenant
  > - AND queries never cross tenant boundaries regardless of query content

  ### What Is Already Covered

  **task-134** covers the error path: "Tenant graph not found" — what happens when
  `tenant_{tenant_id}` has not been provisioned.

  Unit tests in `TestTenantGraphRouting` (`test_query_repository.py`) verify the
  routing logic in isolation:
  - `test_proceeds_when_tenant_graph_exists`: routing proceeds when graph exists (mock)
  - `test_checks_client_graph_name_for_existence`: correct graph name is used (mock)

  The dependency injection in `get_mcp_query_service` constructs `tenant_graph_name =
  f"tenant_{tenant_id}"` and passes it to `AgeGraphClient`. This is verifiable by reading
  the code.

  ### The Gap

  No test verifies that, in a real multi-tenant deployment:
  1. MCP queries from tenant A execute against `tenant_A`'s AGE graph and return tenant A's data.
  2. MCP queries from tenant B cannot access tenant A's data — even with a query crafted
     to attempt cross-tenant access.

  The "AND queries never cross tenant boundaries regardless of query content" clause is a
  critical security property. Unit tests verify the architecture; no HTTP-level integration
  test proves it with real data in two real AGE graphs.

  Without this test, a regression in `get_mcp_query_service` (e.g., using a hard-coded
  graph name instead of `f"tenant_{tenant_id}"`, or sharing a single graph client across
  tenants) would go undetected until a production security incident.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`:

  - **Requirement: Per-Tenant Graph Routing — Scenario: Query routed to tenant graph**:
    "THEN it executes against the AGE graph named `tenant_{tenant_id}` for the resolved
    tenant"
    "AND queries never cross tenant boundaries regardless of query content"

  ## What This Change Does

  Creates a new integration test file
  `src/api/tests/integration/query/test_tenant_isolation.py` with class
  `TestCrossTenantIsolation`.

  ### Test Infrastructure

  The tests require two distinct tenants with independently provisioned AGE graphs.
  Use the `AGEGraphProvisioner` (already used in `test_query_mcp_http.py`) to provision
  graphs for both tenants. Create an API key for each tenant via the IAM API.

  ### Tests

  **`test_tenant_sees_own_data_but_not_other_tenants`**

  1. Create tenant A and tenant B (or use the default tenant + create a second one via
     the IAM API).
  2. Provision AGE graph for tenant A (`tenant_{tenant_A_id}`) and create a unique
     marker node: `CREATE (:IsolationMarker {owner: 'tenant_A', marker: '<uuid>'})`.
  3. Provision AGE graph for tenant B (`tenant_{tenant_B_id}`) and create a different
     marker node: `CREATE (:IsolationMarker {owner: 'tenant_B', marker: '<uuid>'})`.
  4. Create API keys for both tenants.
  5. Send `query_graph("MATCH (n:IsolationMarker) RETURN n")` via MCP HTTP transport
     authenticated as tenant A.
  6. Assert the response contains only tenant A's marker — not tenant B's marker.
  7. Repeat as tenant B: verify only tenant B's marker is visible.

  **`test_graph_name_is_tenant_scoped`**

  1. With a provisioned tenant graph, send a valid `query_graph` call via the MCP endpoint
     authenticated as that tenant.
  2. Assert `result["success"] is True`.
  3. Assert the graph in which the query ran is `tenant_{tenant_id}` by querying
     `ag_catalog.ag_graph` via the SQL layer and confirming the name matches.
     (Alternatively, verify this indirectly: create a node in the tenant graph directly,
     then confirm it appears in the MCP query result.)

  **`test_query_content_cannot_bypass_tenant_routing`**

  1. With two provisioned tenant graphs (A and B), each with a marker node.
  2. As tenant A, attempt a query that explicitly references tenant B's graph name
     (e.g., a Cypher comment or a SET search_path attempt).
  3. Assert the result only contains tenant A's data (not tenant B's), regardless of
     query content.

  Note: this test may be redundant if the database-level read-only enforcement already
  prevents SET search_path mutations. Include it as a defense-in-depth verification.

  ## Files / Areas Affected

  - `src/api/tests/integration/query/test_tenant_isolation.py` (new) — all tests above
  - `src/api/tests/integration/query/__init__.py` — ensure the package file exists
    (already present per glob results)

  No production code changes are expected. The implementation in
  `query/dependencies.py::get_mcp_query_service` and
  `query/infrastructure/tenant_routing.py::TenantAwareQueryGraphRepository`
  is already correct.

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/query/test_tenant_isolation.py \
      -v -m integration
  ```

  All tests must pass. Regression validation:
  1. Temporarily replace `f"tenant_{tenant_id}"` with `"tenant_default"` in
     `get_mcp_query_service` — `test_tenant_sees_own_data_but_not_other_tenants`
     must fail for tenant B (it would see tenant A's default-graph data).
  2. This confirms the test is not a false positive.

  ## Implementation Notes for the Agent

  - Creating a second tenant requires the IAM Tenant API (`POST /iam/tenants`). Check
    if a superadmin or similar role is needed and use the appropriate auth headers.
  - Use `AGEGraphProvisioner` to provision the second tenant's graph (same pattern as
    `provisioned_tenant_graph` fixture in `test_query_mcp_http.py`). Tear down both
    graphs in a `yield`-based fixture to prevent cross-test contamination.
  - Insert marker nodes using the graph client directly (not via MCP) so the test
    setup does not depend on write operations being allowed through the MCP endpoint.
  - Use `fastmcp.Client` with `StreamableHttpTransport` (same as `test_query_mcp_http.py`)
    for the actual MCP calls. Pass `X-API-Key` for each tenant's API key separately.
  - Write the tests FIRST (TDD). The existing production code needs no changes if the
    routing is already correct.
  - This is a `@pytest.mark.integration` test (no `@pytest.mark.keycloak` needed if
    using API key auth, not Bearer token auth, for the actual MCP calls).

  ## Caveats

  - Creating a second tenant may require admin-level JWT auth. Adapt the `tenant_auth_headers`
    fixture or create a superuser fixture as needed.
  - The second tenant's AGE graph must be torn down in fixture cleanup to avoid polluting
    the shared instance for other tests.
  - If `test_query_content_cannot_bypass_tenant_routing` is too complex to implement cleanly
    (e.g., requires a graph-crossing Cypher that AGE doesn't support), skip it with a
    `pytest.mark.skip` comment explaining why the architecture prevents it.
---
