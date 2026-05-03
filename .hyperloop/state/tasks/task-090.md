---
id: task-090
title: Per-tenant graph routing for MCP query execution
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): route MCP queries to caller's tenant-specific AGE graph"
pr_description: |
  ## What & Why

  The **Per-Tenant Graph Routing** requirement was added to
  `specs/query/query-execution.spec.md`:

  > The system SHALL route all queries to the caller's tenant-specific AGE graph.

  with two concrete scenarios:

  **Scenario: Query routed to tenant graph**
  > GIVEN an authenticated query request
  > WHEN the query is executed
  > THEN it executes against the AGE graph named `tenant_{tenant_id}` for the
  >   resolved tenant
  > AND queries never cross tenant boundaries regardless of query content

  **Scenario: Tenant graph not found**
  > GIVEN a tenant whose AGE graph has not been provisioned
  > WHEN a query is submitted
  > THEN the request is rejected with an execution error before reaching the database

  Without tenant-level graph isolation, a single AGE graph would serve all tenants
  and a query from tenant A could read data belonging to tenant B. The secure enclave
  pattern (node-level permission checks) operates as a secondary safeguard; this
  routing is the primary isolation boundary.

  ## What This PR Does

  ### 1. Domain — No changes required

  Existing `QueryExecutionError` value object is sufficient to model the rejection.

  ### 2. Infrastructure — `TenantAwareQueryGraphRepository`

  New decorator class in `src/api/query/infrastructure/tenant_routing.py`:

  ```python
  class TenantAwareQueryGraphRepository(IQueryGraphRepository):
      """Tenant-routing decorator that gates query execution on graph existence."""

      def __init__(
          self,
          tenant_id: str,
          inner_repository: IQueryGraphRepository,
          existence_check_fn: Callable[[str], bool],
      ) -> None:
          self._tenant_id = tenant_id
          self._inner = inner_repository
          self._check_exists = existence_check_fn

      @property
      def graph_name(self) -> str:
          return f"tenant_{self._tenant_id}"

      def execute_cypher(self, query: str, ...) -> list[QueryResultRow]:
          # Gate 1: reject before DB if tenant graph not provisioned
          if not self._check_exists(self.graph_name):
              raise QueryExecutionError(
                  f"Tenant graph '{self.graph_name}' has not been provisioned."
              )
          return self._inner.execute_cypher(query, ...)
  ```

  Also adds `AGEGraphExistenceChecker` — the production callable that checks
  `ag_catalog.ag_graph` for the graph name without opening an AGE connection.

  ### 3. Dependency wiring — `get_mcp_query_service()`

  Updated in `src/api/query/dependencies.py`:

  ```python
  def get_mcp_query_service() -> Iterator[MCPQueryService]:
      auth_context = get_mcp_auth_context()
      tenant_id = auth_context.tenant_id
      tenant_graph_name = f"tenant_{tenant_id}"

      existence_checker = AGEGraphExistenceChecker(connection_factory=factory)

      with mcp_graph_client_context(graph_name=tenant_graph_name) as client:
          inner_repository = QueryGraphRepository(client=client)
          repository = TenantAwareQueryGraphRepository(
              tenant_id=tenant_id,
              inner_repository=inner_repository,
              existence_check_fn=existence_checker,
          )
          yield MCPQueryService(repository=repository, probe=probe)
  ```

  The AGE client is opened with `graph_name=tenant_graph_name` so all Cypher
  executes inside the correct per-tenant graph context.

  ### 4. Tests — `tests/unit/query/test_tenant_routing.py`

  TDD unit tests cover all spec scenarios using fakes (no mocks):

  | Test | Scenario covered |
  |---|---|
  | `test_routes_query_to_tenant_graph` | Query routed to `tenant_{tenant_id}` |
  | `test_graph_name_format_is_tenant_prefix_plus_id` | Exact name format |
  | `test_different_tenants_check_different_graphs` | No cross-tenant access |
  | `test_raises_execution_error_when_tenant_graph_not_found` | Graph not found |
  | `test_inner_repository_not_called_when_graph_not_found` | Before reaching DB |
  | `test_only_rejects_missing_graph_not_valid_tenant` | Happy path unaffected |
  | `test_existence_check_uses_correct_graph_name_format` | Format contract |

  ## Files Affected

  - `src/api/query/infrastructure/tenant_routing.py` — new file:
    `TenantAwareQueryGraphRepository`, `AGEGraphExistenceChecker`
  - `src/api/query/dependencies.py` — update `get_mcp_query_service()` to
    read tenant_id from MCP auth context and construct the routing decorator
  - `src/api/tests/unit/query/test_tenant_routing.py` — new test file with
    all spec scenario coverage using fake infrastructure

  ## How to Verify

  1. `cd src/api && uv run pytest tests/unit/query/test_tenant_routing.py -v`
     — all routing scenario tests pass.
  2. `cd src/api && uv run pytest tests/unit/query/ -v` — no regressions.
  3. Integration: Start the API, authenticate as a user whose tenant has an
     AGE graph. Execute a Cypher query via MCP. Confirm the query runs against
     `tenant_{tenant_id}`. Then query as a user with no graph provisioned and
     confirm a `QueryExecutionError` is returned.

  ## Design Decisions

  - **Decorator pattern**: `TenantAwareQueryGraphRepository` wraps the inner
    `QueryGraphRepository` rather than modifying it. This keeps tenant routing
    concerns separate from query safety concerns (read-only, LIMIT, timeout).
  - **Existence check first**: The graph existence check is the very first
    operation, before keyword blacklist, LIMIT enforcement, and DB round-trip.
    This satisfies "before reaching the database."
  - **Callable for existence check**: Injecting `existence_check_fn` makes the
    decorator fully unit-testable with a lightweight fake — no DB needed.
  - **Cross-boundary access**: `AGEGraphExistenceChecker` uses a plain
    PostgreSQL connection (not an AGE-context connection) to query
    `ag_catalog.ag_graph`. This avoids the chicken-and-egg problem of needing
    an AGE context to verify the graph exists.

  ## Gap Analysis

  The spec requirement was added *after* a previous intake created tasks for
  other query requirements. The implementation landed in PR #553
  (`feat(query): route MCP queries to tenant-specific AGE graph`) but no
  intake task was created at that time. This task provides traceability between
  the spec requirement and the implementation.

  ## Spec Scenarios Verified Line-by-Line

  ### Scenario: Query routed to tenant graph

  | Spec line | Code location | Status |
  |---|---|---|
  | "executes against AGE graph named `tenant_{tenant_id}`" | `TenantAwareQueryGraphRepository.graph_name` → `f"tenant_{self._tenant_id}"` | ✅ |
  | "for the resolved tenant" | `auth_context.tenant_id` read from MCP JWT context | ✅ |
  | "queries never cross tenant boundaries" | Each `get_mcp_query_service()` call builds a fresh instance with one `tenant_id`; separate instances per request | ✅ |

  ### Scenario: Tenant graph not found

  | Spec line | Code location | Status |
  |---|---|---|
  | "request is rejected with an execution error" | `raise QueryExecutionError(...)` in `TenantAwareQueryGraphRepository.execute_cypher()` | ✅ |
  | "before reaching the database" | Check happens before `self._inner.execute_cypher()`; inner repository is never called | ✅ |
---
