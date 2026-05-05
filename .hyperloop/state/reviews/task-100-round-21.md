---
task_id: task-100
round: 21
role: spec-reviewer
verdict: fail
---
One SHALL requirement has a spec/implementation mismatch. All other requirements are fully implemented and tested.

## Requirement: Per-Tenant Graph Routing — COVERED

Scenario: Query routed to tenant graph
- Implementation: `src/api/query/infrastructure/tenant_routing.py` — `TenantAwareQueryGraphRepository.execute_cypher()` checks `tenant_{tenant_id}` via `existence_check_fn` before delegating to the inner repo. `src/api/query/infrastructure/query_repository.py` — `QueryGraphRepository._validate_graph_exists()` calls `self._client.graph_exists(graph_name)` using the client's configured graph name.
- Unit tests: `src/api/tests/unit/query/test_tenant_routing.py` — `test_routes_query_to_tenant_graph`, `test_graph_name_format_is_tenant_prefix_plus_id`, `test_different_tenants_check_different_graphs`. `src/api/tests/unit/query/test_query_repository.py::TestTenantGraphRouting::test_proceeds_when_tenant_graph_exists`, `test_checks_client_graph_name_for_existence`.
- Integration tests: `src/api/tests/integration/test_query_mcp.py::TestCrossTenantIsolation::test_tenant_a_cannot_see_tenant_b_data` — verifies no cross-tenant data leakage against real AGE graphs.

Scenario: Tenant graph not found
- Implementation: `TenantAwareQueryGraphRepository.execute_cypher()` raises `QueryExecutionError` before calling the inner repository when graph is absent. `QueryGraphRepository._validate_graph_exists()` raises `QueryExecutionError` when `client.graph_exists()` returns False, before opening a transaction.
- Unit tests: `test_raises_execution_error_when_tenant_graph_not_found`, `test_inner_repository_not_called_when_graph_not_found`, `test_graph_not_found_check_happens_before_query_validation` (tenant_routing); `test_rejects_query_if_tenant_graph_not_found` asserts `mock_client.transaction.assert_not_called()` (query_repository).
- Integration tests: `TestCrossTenantIsolation::test_tenant_graph_not_found_raises_before_db`.

## Requirement: Read-Only Enforcement — COVERED

Scenario: Database-level enforcement (primary)
- Implementation: `query_repository.py` line 121 — `tx.execute_sql("SET TRANSACTION READ ONLY")` is called before any Cypher execution inside every `execute_cypher` call.
- Tests: `test_sets_transaction_read_only` asserts `"READ ONLY"` appears in `execute_sql` calls. `test_database_read_only_applied_before_query` uses call-order tracking to assert `SET TRANSACTION READ ONLY` is issued before `execute_cypher`.

Scenario: Keyword blacklist (secondary)
- Implementation: `QueryGraphRepository._validate_read_only()` checks all 7 keywords (CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD) case-insensitively. Generates a `correlation_id` UUID per rejection, attaches to `QueryForbiddenError`. `DefaultQueryServiceProbe.cypher_query_rejected()` logs only the correlation_id and reason, never the raw query.
- Tests: Individual keyword tests in `TestValidateReadOnly`. `test_forbidden_error_has_correlation_id` and `test_forbidden_error_correlation_id_is_unique`. `TestDefaultQueryServiceProbe::test_cypher_query_rejected_does_not_log_raw_query` directly asserts the raw query is absent from all logger call arguments.

## Requirement: Timeout Enforcement — COVERED

Scenario: Query within timeout
- Implementation: `execute_cypher` with `SET LOCAL statement_timeout` in milliseconds. Returns rows normally on success.
- Tests: `test_query_within_timeout_returns_results_normally` — asserts no exception, data present.

Scenario: Query exceeds timeout
- Implementation: `query_repository.py` lines 132-140 — catches Exception, checks for "timeout"/"canceling statement" in message, raises `QueryTimeoutError` with a `correlation_id`.
- Tests: `test_timeout_raises_query_timeout_error`, `test_timeout_error_has_correlation_id`. `test_sets_statement_timeout` verifies `statement_timeout` SQL is sent with correct millisecond value.

## Requirement: Result Limiting — COVERED

Scenario: No LIMIT in query
- Implementation: `_ensure_limit()` appends `\nLIMIT {max_rows}` when no LIMIT is found. Default `max_rows=1000` in `execute_cypher` signature.
- Tests: `test_adds_default_limit_of_1000_when_max_rows_not_specified`, `test_default_limit_of_1000_appended_when_query_has_no_limit`.

Scenario: Explicit LIMIT within bounds
- Implementation: `_ensure_limit()` returns query unchanged when LIMIT <= `MAX_LIMIT` (10000).
- Tests: `test_respects_limit_at_absolute_maximum`, `test_respects_limit_within_absolute_maximum`.

Scenario: Explicit LIMIT exceeds maximum
- Implementation: `_ensure_limit()` replaces LIMIT with `MAX_LIMIT` (10000) when existing LIMIT > 10000.
- Tests: `test_caps_limit_above_absolute_maximum`, `test_caps_limit_well_above_absolute_maximum`.

## Requirement: Error Categorization — PARTIAL (1 scenario FAIL)

Scenario: Forbidden query → error_type "forbidden" — COVERED
- Implementation: `services.py` line 112 — `error_type="forbidden"`.
- Tests: `test_forbidden_error_type_when_repo_raises_query_forbidden_error` asserts `result.error_type == "forbidden"`.

Scenario: Timeout error → error_type "timeout" — COVERED
- Implementation: `services.py` line 127 — `error_type="timeout"`.
- Tests: `test_timeout_error_type_when_repo_raises_query_timeout_error` asserts `result.error_type == "timeout"`.

Scenario: Execution error → error_type "execution_error" — COVERED
- Implementation: `services.py` line 136 — `error_type="execution_error"`.
- Tests: `test_execution_error_type_when_repo_raises_query_execution_error` asserts `result.error_type == "execution_error"`.

Scenario: Unexpected error → error_type "unknown_error" — FAIL
- Spec (line 86): `THEN the error type is "unknown_error"`
- Implementation (`src/api/query/application/services.py` line 145): `error_type="unexpected_error"` — WRONG VALUE
- Tests (`src/api/tests/unit/query/test_mcp_query_service.py` lines 303-333, `test_application_services.py` line 542, `test_mcp_query_tool.py` lines 198/206/214/221/234): all assert `"unexpected_error"` — tests pass but are wrong per spec
- Required fix: Change `error_type="unexpected_error"` to `error_type="unknown_error"` in `services.py` line 145, and update all test assertions accordingly (tracked as task-158 in `.hyperloop/state/tasks/task-158.md`).

## Summary

All 4 requirements have full implementation. 3 of 4 requirements are fully spec-aligned. The Error Categorization requirement is PARTIAL: the unexpected-error scenario emits `"unexpected_error"` instead of the spec-mandated `"unknown_error"`. This is a SHALL requirement with a literal string mismatch. All 131 unit tests pass, but the tests themselves assert the wrong string value.