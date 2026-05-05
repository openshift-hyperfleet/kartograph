---
task_id: task-100
round: 19
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review: Query Execution

### FAIL: Error Categorization — Unexpected Error scenario

**Spec** (`specs/query/query-execution.spec.md`, line 86):
> GIVEN an unexpected failure during query execution
> THEN the error type is "unknown_error"

**Code** (`src/api/query/application/services.py`, line 145):
```python
error_type="unexpected_error",
```

**Tests** (multiple files, e.g. `src/api/tests/unit/query/test_application_services.py:542`):
```python
assert result.error_type == "unexpected_error"
```

The implementation and all tests consistently use `"unexpected_error"`. The spec requires `"unknown_error"`. No occurrence of `"unknown_error"` exists anywhere in the codebase. The most recent commit (`cca8328d3 fix(query): align error_type with alpha's unexpected_error convention`) explicitly changed the value away from something, indicating a deliberate choice — but it contradicts the spec's literal contract.

---

## Per-Requirement Status

### Requirement: Per-Tenant Graph Routing — COVERED
- Implementation: `src/api/query/infrastructure/tenant_routing.py` (TenantAwareQueryGraphRepository) and `src/api/query/infrastructure/query_repository.py:150-168` (_validate_graph_exists)
- Graph name format `tenant_{tenant_id}` enforced at line 87 of tenant_routing.py
- Tests: `src/api/tests/unit/query/test_tenant_routing.py` (20 tests — all pass), `src/api/tests/unit/query/test_query_repository.py::TestTenantGraphRouting` (6 tests — all pass)
- Cross-tenant isolation verified by `test_different_tenants_check_different_graphs`

### Requirement: Per-Tenant Graph Routing / Tenant graph not found — COVERED
- Implementation: `src/api/query/infrastructure/tenant_routing.py:121-126` rejects before any DB contact
- Tests: `test_raises_execution_error_when_tenant_graph_not_found`, `test_inner_repository_not_called_when_graph_not_found` (both pass)

### Requirement: Read-Only Enforcement / Database-level (primary) — COVERED
- Implementation: `src/api/query/infrastructure/query_repository.py:121` — `tx.execute_sql("SET TRANSACTION READ ONLY")`
- Tests: `test_sets_transaction_read_only`, `test_database_read_only_applied_before_query` (both pass)

### Requirement: Read-Only Enforcement / Keyword blacklist (secondary) — COVERED
- Implementation: `src/api/query/infrastructure/query_repository.py:171-189` — rejects CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD case-insensitively; assigns correlation_id
- Redaction: `src/api/query/application/observability.py:101-113` — DefaultQueryServiceProbe.cypher_query_rejected does NOT log raw query
- Tests: `TestValidateReadOnly` (14 tests covering all 7 keywords + case-insensitivity + correlation_id uniqueness), `TestDefaultQueryServiceProbe` (3 tests verifying redaction + correlation_id in log)
- All pass

### Requirement: Timeout Enforcement / Query within timeout — COVERED
- Implementation: `src/api/query/infrastructure/query_repository.py:124-125` sets statement_timeout
- Tests: `test_query_within_timeout_returns_results_normally` (passes)

### Requirement: Timeout Enforcement / Query exceeds timeout — COVERED
- Implementation: `src/api/query/infrastructure/query_repository.py:134-140` converts timeout exception to QueryTimeoutError with correlation_id
- Tests: `test_timeout_raises_query_timeout_error`, `test_timeout_error_has_correlation_id` (both pass)

### Requirement: Result Limiting / No LIMIT in query — COVERED
- Implementation: `src/api/query/infrastructure/query_repository.py:220-221` appends LIMIT 1000
- Tests: `test_adds_default_limit_of_1000_when_max_rows_not_specified`, `test_default_limit_of_1000_appended_when_query_has_no_limit` (both pass)

### Requirement: Result Limiting / Explicit LIMIT within bounds — COVERED
- Implementation: `src/api/query/infrastructure/query_repository.py:218` — returns query unchanged when limit <= MAX_LIMIT
- Tests: `test_preserves_existing_limit`, `test_respects_limit_at_absolute_maximum`, `test_respects_limit_within_absolute_maximum` (all pass)

### Requirement: Result Limiting / Explicit LIMIT exceeds maximum — COVERED
- Implementation: `src/api/query/infrastructure/query_repository.py:209-215` caps to MAX_LIMIT (10000)
- Tests: `test_caps_limit_above_absolute_maximum`, `test_caps_limit_well_above_absolute_maximum` (both pass)

### Requirement: Error Categorization / Forbidden — COVERED
- Implementation: `src/api/query/application/services.py:104-117` returns error_type="forbidden"
- Tests: `test_categorizes_forbidden_error` (passes)

### Requirement: Error Categorization / Timeout — COVERED
- Implementation: `src/api/query/application/services.py:118-131` returns error_type="timeout"
- Tests: `test_categorizes_timeout_error` (passes)

### Requirement: Error Categorization / Execution error — COVERED
- Implementation: `src/api/query/application/services.py:132-138` returns error_type="execution_error"
- Tests: `test_categorizes_execution_error`, `test_categorizes_tenant_graph_not_found_as_execution_error` (both pass)

### Requirement: Error Categorization / Unexpected error — FAIL
- Spec: error_type must be "unknown_error"
- Implementation: `src/api/query/application/services.py:145` returns error_type="unexpected_error"
- Tests assert "unexpected_error" — tests pass but test the wrong value
- No occurrence of "unknown_error" exists anywhere in the codebase

---

## NFR Compliance

### Domain Probes — PASS
- `src/api/query/application/observability.py` defines QueryServiceProbe protocol and DefaultQueryServiceProbe
- Services use probe exclusively; no direct logger.* calls in application or domain layers
- `cypher_query_received`, `cypher_query_executed`, `cypher_query_rejected`, `cypher_query_failed` are the domain-oriented probe methods

### Fakes vs Mocks — PASS (with one acceptable exception)
- `src/api/tests/unit/query/test_tenant_routing.py`: FakeInnerRepository, FakeGraphExistenceChecker — no mocks
- `src/api/tests/unit/query/test_application_services.py`: FakeQueryGraphRepository, FakeQueryServiceProbe — no mocks for repositories/probes
- `src/api/tests/unit/query/test_query_repository.py`: uses create_autospec on GraphClientProtocol — acceptable since GraphClientProtocol is infrastructure protocol, not a domain repository
- `test_application_services.py::TestDefaultQueryServiceProbe`: mocks structlog logger — acceptable per spec (logger is infrastructure)

---

## Action Required (Stage 5/6 fix)

- Change `error_type="unexpected_error"` to `error_type="unknown_error"` in `src/api/query/application/services.py:145`
- Update all tests that assert `result.error_type == "unexpected_error"` for the catch-all Exception branch to assert `"unknown_error"` instead
- Affected test files: `src/api/tests/unit/query/test_application_services.py`, `src/api/tests/unit/query/test_mcp_query_service.py`, `src/api/tests/unit/query/test_mcp_query_tool.py`