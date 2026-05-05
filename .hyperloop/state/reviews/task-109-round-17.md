---
task_id: task-109
round: 17
role: spec-reviewer
verdict: fail
---
## Summary

One spec requirement has a direct value mismatch between the spec and implementation. All other requirements are fully covered.

---

## Requirement Status

### Requirement: Per-Tenant Graph Routing — COVERED

**Implementation:**
- `src/api/query/infrastructure/tenant_routing.py`: `TenantAwareQueryGraphRepository` routes to `tenant_{tenant_id}` and rejects before the DB if the graph is absent.
- `src/api/query/infrastructure/query_repository.py`: `QueryGraphRepository._validate_graph_exists()` uses `client.graph_exists()` and raises `QueryExecutionError` before opening a transaction.

**Tests — Scenario: Query routed to tenant graph:**
- Unit: `src/api/tests/unit/query/test_tenant_routing.py` — `test_routes_query_to_tenant_graph`, `test_graph_name_format_is_tenant_prefix_plus_id`, `test_different_tenants_check_different_graphs`.
- Integration (infra-layer): `src/api/tests/integration/query/test_tenant_routing.py::TestPerTenantGraphRouting::test_query_executes_in_tenant_graph`.
- Integration (HTTP-layer): `TestPerTenantGraphRoutingHTTP::test_query_executes_in_tenant_graph`.

**Tests — Scenario: Tenant graph not found:**
- Unit: `test_raises_execution_error_when_tenant_graph_not_found`, `test_inner_repository_not_called_when_graph_not_found`.
- Integration (infra-layer): `TestPerTenantGraphRouting::test_tenant_graph_not_found_raises_before_db`.
- Integration (HTTP-layer): `TestPerTenantGraphRoutingHTTP::test_tenant_graph_not_found_returns_structured_error`.

---

### Requirement: Read-Only Enforcement — COVERED

**Implementation:**
- Primary: `SET TRANSACTION READ ONLY` issued before every Cypher call in `QueryGraphRepository.execute_cypher` (line 121).
- Secondary: `_validate_read_only()` checks all 7 keywords (CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD) case-insensitively.
- Redacted logging: `DefaultQueryServiceProbe.cypher_query_rejected` passes only `reason` and `correlation_id` to the logger — never the raw query.
- Correlation ID: generated per rejection in `_validate_read_only()`.

**Tests — Scenario: Database-level enforcement (primary):**
- Integration: `src/api/tests/integration/test_query_readonly.py::TestDatabaseLevelReadOnlyEnforcement::test_database_rejects_write_even_when_keyword_blacklist_bypassed` — patches secondary defense out and proves DB-level read-only blocks writes.
- Unit: `test_query_repository.py::TestExecuteCypher::test_sets_transaction_read_only`, `test_database_read_only_applied_before_query`.

**Tests — Scenario: Keyword blacklist (secondary):**
- Unit: `TestValidateReadOnly` class (13 tests covering all 7 keywords, case-insensitivity, correlation ID generation, query redaction).
- `TestDefaultQueryServiceProbe::test_cypher_query_rejected_does_not_log_raw_query` — proves raw query absent from log.
- `test_forbidden_error_includes_correlation_id_in_response` and `test_forbidden_error_correlation_id_included_in_probe_call`.

---

### Requirement: Timeout Enforcement — COVERED

**Implementation:**
- `SET LOCAL statement_timeout = {timeout_seconds * 1000}` issued in each transaction.
- Timeout exceptions detected by matching "timeout" or "canceling statement" in error string; wrapped as `QueryTimeoutError` with a correlation ID.

**Tests — Scenario: Query within timeout:**
- Unit: `test_query_within_timeout_returns_results_normally`.

**Tests — Scenario: Query exceeds timeout:**
- Unit: `test_timeout_raises_query_timeout_error`, `test_timeout_error_has_correlation_id`.
- `test_timeout_error_includes_correlation_id_in_response` (service level).

---

### Requirement: Result Limiting — COVERED

**Implementation:**
- `_ensure_limit()`: appends `LIMIT 1000` if absent; caps values above 10000 to 10000; respects values at or below 10000.

**Tests — Scenario: No LIMIT in query:**
- Unit: `test_adds_default_limit_of_1000_when_max_rows_not_specified`, `test_default_limit_of_1000_appended_when_query_has_no_limit`.

**Tests — Scenario: Explicit LIMIT within bounds:**
- Unit: `test_preserves_existing_limit`, `test_respects_limit_at_absolute_maximum`, `test_respects_limit_within_absolute_maximum`.

**Tests — Scenario: Explicit LIMIT exceeds maximum:**
- Unit: `test_caps_limit_above_absolute_maximum`, `test_caps_limit_well_above_absolute_maximum`.

---

### Requirement: Error Categorization — FAIL

**Spec says:**
```
Scenario: Unexpected error
- GIVEN an unexpected failure during query execution
- THEN the error type is "unknown_error"
```

**Implementation produces:**
```python
# src/api/query/application/services.py line 145
error_type="unexpected_error"
```

**Tests assert `"unexpected_error"`** (not `"unknown_error"`):
- `src/api/tests/unit/query/test_application_services.py` line 542: `assert result.error_type == "unexpected_error"`
- `src/api/tests/unit/query/test_mcp_query_service.py` lines 315, 324, 333: all assert `"unexpected_error"`
- `src/api/tests/unit/query/test_mcp_query_tool.py` lines 206, 221, 234: all reference `"unexpected_error"`

The implementation and tests are internally consistent but contradict the spec. The spec value `"unknown_error"` matches none of the implementation strings.

**Other Error Categorization scenarios:**
- "forbidden" — COVERED: `services.py:112`, tested in `test_categorizes_forbidden_error`.
- "timeout" — COVERED: `services.py:127`, tested in `test_categorizes_timeout_error`.
- "execution_error" — COVERED: `services.py:136`, tested in `test_categorizes_execution_error`.

---

## Fix Required

In `src/api/query/application/services.py` (line 145), change:

```python
error_type="unexpected_error",
```

to:

```python
error_type="unknown_error",
```

Then update all tests asserting `"unexpected_error"` for the catch-all branch to assert `"unknown_error"` instead:

- `src/api/tests/unit/query/test_application_services.py` line 542
- `src/api/tests/unit/query/test_mcp_query_service.py` lines 315, 324, 333
- `src/api/tests/unit/query/test_mcp_query_tool.py` lines 198, 206, 208, 211, 214, 221, 234

Note: test method names (`test_categorizes_unexpected_error`, `test_unexpected_error_type_when_repo_raises_unexpected_exception`, etc.) can keep their descriptive names — only the asserted string value needs to change.