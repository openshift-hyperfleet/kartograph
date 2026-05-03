---
id: task-084
title: Route MCP queries to per-tenant AGE graph
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): route MCP queries to per-tenant AGE graph with existence validation"
pr_description: |
  ## What & Why

  The `query-execution.spec.md` spec was updated to add a new **Requirement:
  Per-Tenant Graph Routing**. The spec requires:

  > The system SHALL route all queries to the caller's tenant-specific AGE graph.

  with two scenarios:

  **Scenario: Query routed to tenant graph**
  > GIVEN an authenticated query request
  > WHEN the query is executed
  > THEN it executes against the AGE graph named `tenant_{tenant_id}` for the
  >   resolved tenant
  > AND queries never cross tenant boundaries regardless of query content

  **Scenario: Tenant graph not found**
  > GIVEN a tenant whose AGE graph has not been provisioned
  > WHEN a query is submitted
  > THEN the request is rejected with an execution error before reaching the
  >   database

  Currently, `mcp_graph_client_context()` in `query/dependencies.py` creates
  an `AgeGraphClient` without specifying a graph name, so it falls through to
  the value in `DatabaseSettings.graph_name`. This is a single shared graph, not
  per-tenant isolation. All MCP queries from every tenant currently execute
  against the same AGE graph — a critical data isolation gap.

  ## What This PR Does

  ### 1. Thread `tenant_id` into the graph client

  Modify `mcp_graph_client_context()` in `src/api/query/dependencies.py` to:
  - Call `get_mcp_auth_context()` to retrieve the current `MCPAuthContext`
  - Pass `graph_name=f"tenant_{auth_context.tenant_id}"` to `AgeGraphClient`
  - Keep `auto_create=False` (must never auto-provision a graph during a
    read query; tenant graphs are provisioned by the admin/provisioning path)

  ### 2. Add explicit graph-existence validation

  Modify `QueryGraphRepository.execute_cypher()` in
  `src/api/query/infrastructure/query_repository.py` to call a new
  `_validate_graph_exists()` helper as the first safeguard step (before the
  keyword blacklist and before any Cypher execution):

  ```python
  def _validate_graph_exists(self, graph_name: str) -> None:
      """Check ag_catalog.ag_graph; raise QueryExecutionError if absent."""
      with self._client.transaction() as tx:
          result = tx.execute_sql(
              "SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s",
              (graph_name,),
          )
          if not result:
              raise QueryExecutionError(
                  f"Tenant graph '{graph_name}' has not been provisioned."
              )
  ```

  This satisfies "rejected with an execution error **before reaching the
  database**" — the check queries the catalog, not the graph itself.

  The `QueryGraphRepository` needs `client.graph_name` exposed or accepts the
  graph_name externally — it is already accessible via `self._client.graph_name`.

  ### 3. Update `MCPQueryService`

  `MCPQueryService` already maps `QueryExecutionError` → `error_type:
  "execution_error"`. The graph-not-found error will surface naturally via
  that path. No changes needed to the service layer.

  ## Files Affected

  - `src/api/query/dependencies.py` — `mcp_graph_client_context()` reads
    `MCPAuthContext.tenant_id` and passes `graph_name` to `AgeGraphClient`
  - `src/api/query/infrastructure/query_repository.py` — add
    `_validate_graph_exists()` called at the top of `execute_cypher()`
  - `src/api/tests/unit/query/test_query_repository.py` — new tests for
    per-tenant routing and graph-not-found scenario
  - `src/api/tests/unit/query/test_dependencies.py` — new test verifying
    `mcp_graph_client_context()` passes the correct `graph_name`

  ## How to Verify

  1. Unit tests pass: `make test-unit`
  2. A query submitted by a user in tenant `t-abc` executes against the AGE
     graph `tenant_t-abc`, not the default graph.
  3. A query submitted when no graph is provisioned returns
     `{"success": false, "error_type": "execution_error", ...}` without
     reaching the Cypher executor.

  ## Caveats

  - Task-003 (in-progress, merge-pr) implements per-tenant routing for the
    **Graph mutation** path from `specs/graph/mutations.spec.md`. This task
    addresses the **Query** path independently. If task-003 has already
    introduced a tenant-routing utility, reuse it rather than duplicating.
  - `get_mcp_auth_context()` raises `LookupError` if called outside a request
    context. The implementation must only call it inside the context manager
    body (i.e., during a live MCP tool invocation), not at import time.
---
