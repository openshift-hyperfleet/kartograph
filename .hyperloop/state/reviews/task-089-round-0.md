---
task_id: task-089
round: 0
role: spec-reviewer
verdict: fail
---
## Summary

All 5 spec requirements from `specs/query/query-execution.spec.md` are implemented and all scenario tests pass (86/86). However, the implementation fails the testing NFR (`specs/nfr/testing.spec.md`) which contains SHALL requirements prohibiting mock libraries for repositories and probe protocols.

---

## Requirement Status

### 1. Per-Tenant Graph Routing — COVERED

Implementation: `/home/jsell/code/kartograph/worktrees/workers/task-089/src/api/query/infrastructure/tenant_routing.py`

- `TenantAwareQueryGraphRepository` routes to `tenant_{tenant_id}` via `graph_name` property (line 87).
- `AGEGraphExistenceChecker` queries `ag_catalog.ag_graph` before any database round-trip.

Tests: `/home/jsell/code/kartograph/worktrees/workers/task-089/src/api/tests/unit/query/test_tenant_routing.py`

- Scenario "Query routed to tenant graph": covered by `test_routes_query_to_tenant_graph`, `test_graph_name_format_is_tenant_prefix_plus_id`, `test_different_tenants_check_different_graphs`.
- Scenario "Tenant graph not found": covered by `test_raises_execution_error_when_tenant_graph_not_found`, `test_inner_repository_not_called_when_graph_not_found` (confirms rejection before database).
- Uses correct fakes (no mock libraries).

### 2. Read-Only Enforcement — COVERED

Implementation: `/home/jsell/code/kartograph/worktrees/workers/task-089/src/api/query/infrastructure/query_repository.py`

- Database-level enforcement: `SET TRANSACTION READ ONLY` issued before any Cypher query (line 117).
- Keyword blacklist: `MUTATION_KEYWORDS = frozenset(["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "EXPLAIN", "LOAD"])` (line 55–57); case-insensitive check via `query.upper()`.
- Redacted logging: `QueryForbiddenError` carries `correlation_id`; `DefaultQueryServiceProbe.cypher_query_rejected` explicitly omits `query` from the log call (observability.py line 108–113).

Tests: `/home/jsell/code/kartograph/worktrees/workers/task-089/src/api/tests/unit/query/test_query_repository.py`

- Database-level enforcement: `test_sets_transaction_read_only`, `test_database_read_only_applied_before_query`.
- Keyword blacklist: `test_rejects_create`, `test_rejects_delete`, `test_rejects_set`, `test_rejects_remove`, `test_rejects_merge`, `test_rejects_explain`, `test_rejects_load`, `test_case_insensitive`.
- Correlation ID present: `test_forbidden_error_has_correlation_id`, `test_forbidden_error_correlation_id_is_unique`.
- Redacted logging test: `TestDefaultQueryServiceProbe::test_cypher_query_rejected_does_not_log_raw_query` confirms raw query never reaches logger.

### 3. Timeout Enforcement — COVERED

Implementation: `query_repository.py` lines 119–135.

- `SET LOCAL statement_timeout = {timeout_seconds * 1000}` issued per transaction.
- `QueryTimeoutError` raised when exception message contains "timeout" or "canceling statement".
- `QueryTimeoutError` carries `correlation_id`.

Tests: `test_query_repository.py`

- Scenario "Query within timeout": `test_uses_transaction_context`, `test_returns_empty_list_on_no_results`.
- Scenario "Query exceeds timeout": `test_timeout_raises_query_timeout_error`, `test_timeout_error_has_correlation_id`.
- Timeout milliseconds correctly computed: `test_sets_statement_timeout` (5 seconds → 5000ms).

### 4. Result Limiting — COVERED

Implementation: `query_repository.py` `_ensure_limit` method (lines 166–196).

- No LIMIT present: appends `LIMIT {max_rows}` where default is 1000 (`DEFAULT_LIMIT = 1000`).
- Explicit LIMIT within bounds (≤ 10000): preserved as-is.
- Explicit LIMIT exceeding 10000 (`MAX_LIMIT = 10000`): replaced with `LIMIT 10000`.

Tests: `test_query_repository.py::TestEnsureLimit`

- Scenario "No LIMIT in query": `test_adds_limit_when_missing`.
- Scenario "Explicit LIMIT within bounds": `test_preserves_existing_limit`, `test_respects_limit_at_absolute_maximum`, `test_respects_limit_within_absolute_maximum`.
- Scenario "Explicit LIMIT exceeds maximum": `test_caps_limit_above_absolute_maximum`, `test_caps_limit_well_above_absolute_maximum`.

### 5. Error Categorization — COVERED

Implementation: `services.py` `execute_cypher_query` exception handlers (lines 95–139).

- `QueryForbiddenError` → `error_type = "forbidden"`.
- `QueryTimeoutError` → `error_type = "timeout"`.
- `QueryExecutionError` → `error_type = "execution_error"`.
- `Exception` (catch-all) → `error_type = "unknown_error"`.

Tests: `test_application_services.py::TestExecuteCypherQuery`

- Scenario "Forbidden query": `test_categorizes_forbidden_error`.
- Scenario "Timeout error": `test_categorizes_timeout_error`.
- Scenario "Execution error": `test_categorizes_execution_error`.
- Scenario "Unexpected error": `test_categorizes_unknown_error`.

---

## NFR Violations

### Testing NFR — FAIL (SHALL NOT violated)

File: `/home/jsell/code/kartograph/worktrees/workers/task-089/src/api/tests/unit/query/test_application_services.py`

The testing NFR (`specs/nfr/testing.spec.md`) has a SHALL requirement:

> "The system's tests SHALL NOT use mocking libraries (e.g., `unittest.mock.MagicMock`, `AsyncMock`, `patch`) to replace domain or application-layer collaborators."

And explicitly:

> "mocking is NOT acceptable for: domain services, repositories, event handlers, or probe protocols"

> "it is NOT replaced with `MagicMock(spec=ProbeProtocol)`"

Violations in `test_application_services.py`:

1. Line 22: `create_autospec(IQueryGraphRepository, instance=True)` — `IQueryGraphRepository` is a repository port. Testing NFR explicitly prohibits mocking repositories.
2. Line 28: `create_autospec(QueryServiceProbe, instance=True)` — `QueryServiceProbe` is a probe protocol. Testing NFR explicitly prohibits mocking probe protocols.

**What is needed:** Replace both mock fixtures with fake implementations:

- Create a `FakeQueryGraphRepository` (similar to `FakeInnerRepository` in `test_tenant_routing.py`) that records calls and returns configured results.
- Create a `FakeQueryServiceProbe` (a concrete recording class implementing `QueryServiceProbe`) instead of `create_autospec(QueryServiceProbe, instance=True)`.

### Observability NFR — PASS

`DefaultQueryServiceProbe` correctly uses structlog and never logs raw query text. Domain probe patterns are followed throughout.

### Architecture NFR — PASS

All 32 architecture tests pass. Query bounded context is properly isolated from IAM, Management, Ingestion, Graph domain/application layers.

---

## What the Implementer Must Fix

Replace the two mock fixtures in `/home/jsell/code/kartograph/worktrees/workers/task-089/src/api/tests/unit/query/test_application_services.py`:

1. `mock_repository` fixture (line 21–23): Replace `create_autospec(IQueryGraphRepository, instance=True)` with a `FakeQueryGraphRepository` concrete class that records `execute_cypher` calls and supports configuring return values and side effects.

2. `mock_probe` fixture (line 26–28): Replace `create_autospec(QueryServiceProbe, instance=True)` with a `FakeQueryServiceProbe` concrete class that records calls to `cypher_query_received`, `cypher_query_executed`, `cypher_query_rejected`, and `cypher_query_failed`.

The reference implementation for the correct approach is in `test_tenant_routing.py` (`FakeInnerRepository`, `FakeGraphExistenceChecker`).