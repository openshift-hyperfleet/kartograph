---
task_id: task-100
round: 18
role: spec-reviewer
verdict: fail
---
One spec deviation found in completed work. All other requirements are covered.

## Summary of Findings

All unit tests pass (99/99). The implementation is otherwise comprehensive: per-tenant routing, read-only enforcement (both database-level and keyword blacklist), timeout enforcement, result limiting, and three of four error categorization types are correctly implemented and tested.

---

### Requirement: Per-Tenant Graph Routing
Status: COVERED

Scenario: Query routed to tenant graph
- Implementation: `src/api/query/infrastructure/tenant_routing.py` (TenantAwareQueryGraphRepository, lines 42-134) enforces `tenant_{tenant_id}` graph naming. `src/api/query/infrastructure/query_repository.py` (QueryGraphRepository._validate_graph_exists, lines 150-169) also checks graph existence via `client.graph_name` and `client.graph_exists()`.
- Unit tests: `src/api/tests/unit/query/test_tenant_routing.py` (TestTenantAwareQueryGraphRepository, test_routes_query_to_tenant_graph, test_graph_name_format_is_tenant_prefix_plus_id, test_different_tenants_check_different_graphs). `src/api/tests/unit/query/test_query_repository.py` (TestTenantGraphRouting.test_proceeds_when_tenant_graph_exists, test_checks_client_graph_name_for_existence).
- Integration tests: `src/api/tests/integration/test_query_mcp.py` (TestCrossTenantIsolation.test_tenant_a_cannot_see_tenant_b_data).

Scenario: Tenant graph not found
- Implementation: `src/api/query/infrastructure/tenant_routing.py` lines 120-126 raises `QueryExecutionError` before calling inner repository. `src/api/query/infrastructure/query_repository.py` lines 164-169 raises `QueryExecutionError` if `graph_exists()` returns False.
- Unit tests: `src/api/tests/unit/query/test_tenant_routing.py` (test_raises_execution_error_when_tenant_graph_not_found, test_inner_repository_not_called_when_graph_not_found). `src/api/tests/unit/query/test_query_repository.py` (TestTenantGraphRouting.test_rejects_query_if_tenant_graph_not_found — asserts `transaction.assert_not_called()`).
- Integration tests: `src/api/tests/integration/test_query_mcp.py` (TestCrossTenantIsolation.test_tenant_graph_not_found_raises_before_db).

---

### Requirement: Read-Only Enforcement
Status: COVERED

Scenario: Database-level enforcement (primary)
- Implementation: `src/api/query/infrastructure/query_repository.py` line 121 `tx.execute_sql("SET TRANSACTION READ ONLY")` is issued before any Cypher execution.
- Unit tests: `src/api/tests/unit/query/test_query_repository.py` (TestExecuteCypher.test_sets_transaction_read_only, test_database_read_only_applied_before_query) — the latter tracks call ordering to assert READ ONLY is set before Cypher runs.
- Integration tests: `src/api/tests/integration/test_query_readonly.py` (TestDatabaseLevelReadOnlyEnforcement.test_database_rejects_write_even_when_keyword_blacklist_bypassed) — patches `_validate_read_only` to a no-op, then verifies the database itself rejects the write.

Scenario: Keyword blacklist (secondary)
- Implementation: `src/api/query/infrastructure/query_repository.py` `_validate_read_only` (lines 171-189) rejects queries containing CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD (case-insensitive). Generates `correlation_id` per rejection; raw query never logged (see `DefaultQueryServiceProbe.cypher_query_rejected` which deliberately omits query from log output).
- Unit tests: `src/api/tests/unit/query/test_query_repository.py` (TestValidateReadOnly — 14 tests covering all 7 keywords, case-insensitivity, correlation_id presence and uniqueness).
- Integration tests: `src/api/tests/integration/test_query_readonly.py` (test_keyword_blacklist_independently_blocks_same_mutation).

---

### Requirement: Timeout Enforcement
Status: COVERED

Scenario: Query within timeout
- Implementation: `src/api/query/infrastructure/query_repository.py` lines 124-125 set `LOCAL statement_timeout` in milliseconds.
- Unit tests: `src/api/tests/unit/query/test_query_repository.py` (TestExecuteCypher.test_query_within_timeout_returns_results_normally, test_sets_statement_timeout).
- Tests also via `test_mcp_query_service.py` (TestSuccessfulExecution.test_returns_cypher_query_result_on_success).

Scenario: Query exceeds timeout
- Implementation: `src/api/query/infrastructure/query_repository.py` lines 133-140 detects "timeout" or "canceling statement" in exception message and raises `QueryTimeoutError` with `correlation_id`.
- Unit tests: `src/api/tests/unit/query/test_query_repository.py` (TestExecuteCypher.test_timeout_raises_query_timeout_error, test_timeout_error_has_correlation_id).
- Integration tests: `src/api/tests/integration/test_query_mcp.py` (TestQueryGraphRepository.test_timeout_enforcement, TestMCPQueryService.test_execute_cypher_query_timeout_error).

---

### Requirement: Result Limiting
Status: COVERED

Scenario: No LIMIT in query
- Implementation: `src/api/query/infrastructure/query_repository.py` `_ensure_limit` (lines 191-221) — if no LIMIT clause found, appends `LIMIT max_rows`. `execute_cypher` default is `max_rows=1000`.
- Unit tests: `src/api/tests/unit/query/test_query_repository.py` (TestEnsureLimit.test_adds_default_limit_of_1000_when_max_rows_not_specified, TestExecuteCypher.test_default_limit_of_1000_appended_when_query_has_no_limit).

Scenario: Explicit LIMIT within bounds
- Implementation: `src/api/query/infrastructure/query_repository.py` lines 217-218 returns query unchanged when existing limit <= MAX_LIMIT (10000).
- Unit tests: `src/api/tests/unit/query/test_query_repository.py` (TestEnsureLimit.test_preserves_existing_limit, test_respects_limit_at_absolute_maximum, test_respects_limit_within_absolute_maximum).

Scenario: Explicit LIMIT exceeds maximum
- Implementation: `src/api/query/infrastructure/query_repository.py` lines 209-215 replaces limit > MAX_LIMIT with MAX_LIMIT (10000).
- Unit tests: `src/api/tests/unit/query/test_query_repository.py` (TestEnsureLimit.test_caps_limit_above_absolute_maximum, test_caps_limit_well_above_absolute_maximum).

---

### Requirement: Error Categorization
Status: PARTIAL

Scenario: Forbidden query — error type "forbidden"
- Implementation: `src/api/query/application/services.py` line 112 `error_type="forbidden"`. COVERED.
- Tests: `src/api/tests/unit/query/test_mcp_query_service.py` (TestErrorCategorization.test_forbidden_error_type_when_repo_raises_query_forbidden_error). COVERED.

Scenario: Timeout error — error type "timeout"
- Implementation: `src/api/query/application/services.py` line 127 `error_type="timeout"`. COVERED.
- Tests: `src/api/tests/unit/query/test_mcp_query_service.py` (test_timeout_error_type_when_repo_raises_query_timeout_error). COVERED.

Scenario: Execution error — error type "execution_error"
- Implementation: `src/api/query/application/services.py` line 136 `error_type="execution_error"`. COVERED.
- Tests: `src/api/tests/unit/query/test_mcp_query_service.py` (test_execution_error_type_when_repo_raises_query_execution_error). COVERED.

Scenario: Unexpected error — error type "unexpected_error"
- FAIL: Spec requires error_type `"unexpected_error"`.
- Implementation: `src/api/query/application/services.py` line 145 uses `error_type="unknown_error"` instead.
- Tests: `src/api/tests/unit/query/test_mcp_query_service.py` line 315 asserts `result.error_type == "unknown_error"` — the test was written to match the implementation, not the spec.
- This is a spec deviation: the string `"unexpected_error"` appears nowhere in the codebase; `"unknown_error"` is used consistently instead.

---

## Specific Misalignment

- **File:** `src/api/query/application/services.py`, line 145
- **Spec:** `error_type` for unexpected failures SHALL be `"unexpected_error"`
- **Code:** `error_type="unknown_error"`
- **Test:** `src/api/tests/unit/query/test_mcp_query_service.py`, line 315 — asserts `"unknown_error"` (test tracks the deviation rather than the spec)