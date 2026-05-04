---
task_id: task-100
round: 11
role: spec-reviewer
verdict: fail
---
One SHALL requirement has a direct spec/implementation mismatch in Error Categorization.

### Per-Tenant Graph Routing
- Scenario "Query routed to tenant graph": COVERED — `TenantAwareQueryGraphRepository` constructs graph name as `tenant_{tenant_id}`, checks existence via `AGEGraphExistenceChecker`, delegates to inner `QueryGraphRepository`. Unit tests (`test_tenant_routing.py`) and integration tests (`TestCrossTenantIsolation` in `test_query_mcp.py`) cover cross-tenant isolation.
- Scenario "Tenant graph not found": COVERED — Both `TenantAwareQueryGraphRepository.execute_cypher` and `QueryGraphRepository._validate_graph_exists` raise `QueryExecutionError` before any Cypher reaches the database. Unit and integration tests confirm this path.

### Read-Only Enforcement
- Scenario "Database-level enforcement (primary)": COVERED — `execute_cypher` calls `tx.execute_sql("SET TRANSACTION READ ONLY")` before any Cypher. Unit test `test_sets_transaction_read_only` and `test_database_read_only_applied_before_query` verify ordering.
- Scenario "Keyword blacklist (secondary)": COVERED — `MUTATION_KEYWORDS` frozenset includes all 7 spec keywords (CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD). Case-insensitive check via `.upper()`. `QueryForbiddenError` carries a `correlation_id`; `DefaultQueryServiceProbe.cypher_query_rejected` logs only the correlation_id, not the raw query text (`observability.py:107-112`). Tests cover all keywords, case-insensitivity, correlation ID uniqueness, and log redaction.

### Timeout Enforcement
- Scenario "Query within timeout": COVERED — `test_query_within_timeout_returns_results_normally` and `TestSuccessfulExecution.test_returns_cypher_query_result_on_success` verify normal result return.
- Scenario "Query exceeds timeout": COVERED — `execute_cypher` converts timeout-bearing exceptions to `QueryTimeoutError` with a `correlation_id`. Unit test `test_timeout_raises_query_timeout_error` and `test_timeout_error_has_correlation_id` verify this. Integration test `test_timeout_enforcement` exercises at real DB level.

### Result Limiting
- Scenario "No LIMIT in query": COVERED — `_ensure_limit` appends `LIMIT {max_rows}` (default 1000) when absent. Tests: `test_adds_default_limit_of_1000_when_max_rows_not_specified`, `test_default_limit_of_1000_appended_when_query_has_no_limit`.
- Scenario "Explicit LIMIT within bounds": COVERED — query unchanged when LIMIT <= 10000. Tests: `test_respects_limit_at_absolute_maximum`, `test_respects_limit_within_absolute_maximum`.
- Scenario "Explicit LIMIT exceeds maximum": COVERED — LIMIT replaced with MAX_LIMIT (10000). Tests: `test_caps_limit_above_absolute_maximum`, `test_caps_limit_well_above_absolute_maximum`.

### Error Categorization
- Scenario "Forbidden query" — error type "forbidden": COVERED — `MCPQueryService` catches `QueryForbiddenError` and returns `QueryError(error_type="forbidden", ...)`. Test: `test_forbidden_error_type_when_repo_raises_query_forbidden_error`.
- Scenario "Timeout error" — error type "timeout": COVERED — catches `QueryTimeoutError`, returns `error_type="timeout"`. Test: `test_timeout_error_type_when_repo_raises_query_timeout_error`.
- Scenario "Execution error" — error type "execution_error": COVERED — catches `QueryExecutionError`, returns `error_type="execution_error"`. Test: `test_execution_error_type_when_repo_raises_query_execution_error`.
- Scenario "Unexpected error" — error type "unexpected_error": FAIL — Spec requires `error_type="unexpected_error"`. Implementation at `/home/jsell/code/kartograph/worktrees/workers/task-100/src/api/query/application/services.py:145` uses `error_type="unknown_error"`. Unit tests in `test_mcp_query_service.py:313` and `test_application_services.py:542` assert `"unknown_error"`, which means the tests validate the broken implementation rather than the spec. This is a direct SHALL violation.

### Specific Misalignment

- File: `/home/jsell/code/kartograph/worktrees/workers/task-100/src/api/query/application/services.py`, line 145
  - Spec: `error_type` MUST be `"unexpected_error"` for catch-all exception handler
  - Code: `error_type="unknown_error"`
- Tests asserting `"unknown_error"` (must also be corrected to match spec):
  - `/home/jsell/code/kartograph/worktrees/workers/task-100/src/api/tests/unit/query/test_mcp_query_service.py` lines 313, 322, 331
  - `/home/jsell/code/kartograph/worktrees/workers/task-100/src/api/tests/unit/query/test_application_services.py` line 542
  - `/home/jsell/code/kartograph/worktrees/workers/task-100/src/api/tests/unit/query/test_mcp_query_tool.py` lines 198, 206, 208, 214, 221, 230