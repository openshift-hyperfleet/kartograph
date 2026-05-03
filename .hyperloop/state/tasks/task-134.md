---
id: task-134
title: "Per-Tenant Graph Routing — HTTP integration test for unprovisioned tenant graph"
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add HTTP integration test for unprovisioned-tenant-graph execution error"
pr_description: |
  ## What and Why

  The Per-Tenant Graph Routing requirement specifies two scenarios. One of them is:

  > **Scenario: Tenant graph not found**
  > - GIVEN a tenant whose AGE graph has not been provisioned
  > - WHEN a query is submitted
  > - THEN the request is rejected with an execution error before reaching the database

  ### Current coverage

  Unit tests in `test_tenant_routing.py` and `TestTenantGraphRouting` in
  `test_query_repository.py` verify this scenario in isolation: when
  `graph_exists()` returns False the repository raises `QueryExecutionError`
  without opening a transaction.

  `test_query_mcp_http.py` provides the only HTTP-transport-level integration
  test for the `query_graph` MCP tool. However, all of its tests depend on the
  `provisioned_tenant_graph` fixture — and the fixture comment explicitly
  acknowledges that **without a provisioned graph, the response would be
  `error_type: "execution_error"` (graph not found) rather than `"forbidden"`**.
  No test exercises this path.

  Without an HTTP-level test for the unprovisioned scenario:
  - A regression in the graph-existence check (e.g., swallowing the
    `QueryExecutionError` and forwarding the query to the database anyway) would
    not be caught at the HTTP boundary.
  - The `error_type: "execution_error"` response contract is untested end-to-end.

  ## Spec Requirements Satisfied

  `specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`:

  - **Requirement: Per-Tenant Graph Routing — Scenario: Tenant graph not found**:
    "GIVEN a tenant whose AGE graph has not been provisioned
    WHEN a query is submitted
    THEN the request is rejected with an execution error before reaching the database"

  ## What This Change Does

  Adds a new test class `TestMCPTenantGraphNotFoundHTTPResponse` to
  `src/api/tests/integration/test_query_mcp_http.py` containing:

  **`test_query_without_provisioned_graph_returns_execution_error`**

  1. Create an API key using `tenant_auth_headers` (default tenant exists, but
     do NOT provision its AGE graph — intentionally skip the
     `provisioned_tenant_graph` fixture).
  2. Send a `query_graph` call via the MCP HTTP transport with a valid read-only
     query: `MATCH (n) RETURN n LIMIT 10`.
  3. Assert `result["success"] is False`.
  4. Assert `result["error_type"] == "execution_error"`.
  5. Assert `"message"` in result describes the missing graph (e.g., contains
     "does not exist" or "not provisioned").

  **`test_query_without_provisioned_graph_error_occurs_before_database`**

  1. Same setup as above (no provisioned graph).
  2. Submit a query that would be caught by the keyword blacklist if the graph
     existed (e.g., `CREATE (n:Test) RETURN n`).
  3. Assert `result["error_type"] == "execution_error"` — **not** `"forbidden"`.
     (The graph-existence check runs first; the forbidden check never executes.)
  4. This confirms the spec requirement: "before reaching the database."

  ## Files / Areas Affected

  - `src/api/tests/integration/test_query_mcp_http.py` — two new test methods in
    a new `TestMCPTenantGraphNotFoundHTTPResponse` class

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_query_mcp_http.py \
      -v -m integration -k "graph_not_found"
  ```

  All tests in the file (existing forbidden + new graph-not-found) must pass.

  ## Implementation Notes for the Agent

  - The key difference from existing tests: do NOT include `provisioned_tenant_graph`
    in the test method's fixture parameters. Use only `api_key_secret` and the
    `async_client` (which guarantees the app lifespan has run and the default
    tenant exists in the DB, but does NOT provision an AGE graph).
  - Confirm the error message by reading
    `QueryGraphRepository._validate_graph_exists()` — the message format is
    `f"Tenant graph '{graph_name}' does not exist."`.
  - Write the tests FIRST (TDD). The production code should need no changes —
    the graph-existence guard is already implemented.
  - Follow the same fixture pattern (`_make_asgi_httpx_factory`, `fastmcp.Client`,
    `StreamableHttpTransport`) as the existing tests in the file.

  ## Caveats

  - These are `@pytest.mark.integration` and `@pytest.mark.keycloak` tests (they
    use `tenant_auth_headers` from the fake OIDC provider).
  - If the default tenant already has an AGE graph from a previous test run (dirty
    state), the test may spuriously pass. Guard by running each test in a fresh
    instance or by dropping the graph in a fixture teardown.
  - Do NOT provision the tenant graph in these tests — that is precisely the
    condition under test.
---
