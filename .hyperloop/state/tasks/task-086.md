---
id: task-086
title: Route MCP queries to tenant-scoped AGE graph
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): route MCP queries to per-tenant AGE graph"
pr_description: |
  ## What & Why

  `query-execution.spec.md` was updated with a new requirement:

  > **Requirement: Per-Tenant Graph Routing**
  > The system SHALL route all queries to the caller's tenant-specific AGE graph.

  with two scenarios:

  **Scenario: Query routed to tenant graph**
  > GIVEN an authenticated query request
  > WHEN the query is executed
  > THEN it executes against the AGE graph named `tenant_{tenant_id}` for the resolved tenant
  > AND queries never cross tenant boundaries regardless of query content

  **Scenario: Tenant graph not found**
  > GIVEN a tenant whose AGE graph has not been provisioned
  > WHEN a query is submitted
  > THEN the request is rejected with an execution error before reaching the database

  Currently `get_mcp_query_service()` in `src/api/query/dependencies.py` creates an
  `AgeGraphClient` without a `graph_name` override, so all MCP queries execute against
  the default graph name from settings — a single shared graph for all tenants. This
  violates tenant isolation.

  `AgeGraphClient` already accepts a `graph_name` constructor parameter (defaulting to
  `settings.graph_name`) and `auto_create=False` prevents accidental graph provisioning.
  `get_mcp_auth_context()` already exposes `tenant_id`. The wiring is simply missing.

  ## What This PR Does

  ### 1. Tenant-scoped client in `query/dependencies.py`

  Modify `mcp_graph_client_context()` to read the MCP auth context and pass the
  tenant-specific graph name to `AgeGraphClient`:

  ```python
  @contextmanager
  def mcp_graph_client_context() -> Generator["AgeGraphClient", None, None]:
      from graph.infrastructure.age_client import AgeGraphClient
      from shared_kernel.middleware.mcp_auth import get_mcp_auth_context

      auth_context = get_mcp_auth_context()
      graph_name = f"tenant_{auth_context.tenant_id}"

      pool = get_age_connection_pool()
      settings = get_database_settings()
      factory = ConnectionFactory(settings, pool=pool)
      client = AgeGraphClient(settings, connection_factory=factory, graph_name=graph_name)
      client.connect()
      try:
          yield client
      finally:
          client.disconnect()
  ```

  ### 2. Graph existence check in `QueryGraphRepository`

  Add a `_verify_graph_exists(tx)` helper that runs before any Cypher query:

  ```python
  def _verify_graph_exists(self, tx) -> None:
      """Check that the tenant's AGE graph is provisioned.

      Raises:
          QueryExecutionError: If the graph does not exist in ag_catalog.ag_graph.
      """
      result = tx.execute_sql(
          "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
          (self._client.graph_name,),
      )
      if not result:
          raise QueryExecutionError(
              f"Tenant graph '{self._client.graph_name}' has not been provisioned.",
          )
  ```

  Call `_verify_graph_exists(tx)` as the first step inside the transaction block in
  `execute_cypher()`, before the Cypher query is issued. This satisfies the spec's
  "rejected with an execution error **before reaching the database**" intent — the check
  queries the catalog (metadata), not the tenant graph itself, so the Cypher query
  never fires against the missing graph.

  Note: If `tx.execute_sql` doesn't return rows natively, use the raw psycopg2
  cursor pattern consistent with how `_ensure_graph_exists()` works in `AgeGraphClient`.
  Inspect the `GraphTransactionProtocol` to find the right API surface; adapt as needed
  and keep the unit test mockable.

  ### 3. Unit tests

  Add a new test class (or extend `TestExecuteCypher`) in
  `src/api/tests/unit/query/test_query_repository.py`:

  - **`test_execute_cypher_uses_client_graph_name`** — create `QueryGraphRepository`
    with a mock client whose `graph_name` is `"tenant_abc123"`; assert the graph name
    stored on the client is used, not a hardcoded default.
  - **`test_tenant_isolation_different_tenant_ids_produce_different_graph_names`** —
    two repositories built with clients named `"tenant_aaa"` and `"tenant_bbb"` must
    have distinct `_client.graph_name` values.
  - **`test_raises_execution_error_when_tenant_graph_not_found`** — mock the
    graph-existence SQL check to return an empty result; assert `QueryExecutionError`
    is raised before `execute_cypher` is called on the transaction.
  - **`test_execution_error_before_cypher_when_graph_missing`** — same setup; confirm
    that `mock_transaction.execute_cypher` is **never** called.

  Also add a test in `src/api/tests/unit/query/test_dependencies.py` (or a new
  `test_mcp_graph_routing.py`):

  - **`test_mcp_graph_client_uses_tenant_graph_name`** — mock `get_mcp_auth_context()`
    to return a context with `tenant_id="t1"`, then assert that `AgeGraphClient` is
    constructed with `graph_name="tenant_t1"`.

  ## Files Affected

  - `src/api/query/dependencies.py` — read `auth_context.tenant_id` in
    `mcp_graph_client_context()` and pass `graph_name` to `AgeGraphClient`
  - `src/api/query/infrastructure/query_repository.py` — add graph-existence check
    inside `execute_cypher()` before query dispatch
  - `src/api/tests/unit/query/test_query_repository.py` — new test cases for
    tenant routing and missing-graph rejection
  - `src/api/tests/unit/query/test_dependencies.py` — new test for graph name wiring

  ## How to Verify

  1. Unit tests pass: `make test-unit`
  2. With a running instance: authenticate as a tenant whose AGE graph exists, execute
     a `query_graph` call, confirm results come back. Then attempt a call with a
     fabricated tenant whose graph does not exist and confirm a `QueryExecutionError`
     is returned (not a raw psycopg2 error).
  3. Confirm that two tenants cannot read each other's data even if both graphs exist
     (tenant isolation is structural — each query is wired to its own graph name).

  ## Design Decisions

  - **Where to read the tenant ID** — `mcp_graph_client_context()` is the correct
    call site because it owns the `AgeGraphClient` lifecycle. Reading it there ensures
    the graph name is fixed for the entire request; the repository never needs to be
    aware of the auth context.
  - **Graph existence check location** — inside the transaction in
    `QueryGraphRepository.execute_cypher()`. This keeps the repository self-contained
    and mockable, and runs the check in the same transaction context as the query.
  - **No `auto_create` for query path** — the query path must never provision graphs
    (that is the responsibility of the provisioning/admin path). `auto_create` stays
    `False` (the default).
  - **Error type** — `QueryExecutionError` is the correct type per the spec's
    "execution error" language. It maps to `"execution_error"` in the `MCPQueryService`
    error categorization.

  ## Caveats

  The `GraphTransactionProtocol` may not expose a raw SQL execution method that
  returns rows. If that is the case, either extend the protocol or execute the
  existence check using the client's raw connection before starting the transaction.
  The key invariant is: the Cypher query must never be dispatched if the graph is
  absent.
---
