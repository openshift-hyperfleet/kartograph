# Intake Pass 6: mcp-server, query-execution, ui/experience

**Date:** 2026-05-05
**Processed by:** PM intake agent (sixth pass)
**Trigger:** Specs flagged as "(modified)" in orchestrator — same blob SHAs as all prior passes.

## Specs Processed

| Spec | Blob SHA | Decision |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | No new tasks |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | No new tasks |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | No new tasks |

Blob SHAs are identical to all prior passes. The specs have not changed.

---

## Verification: specs/query/mcp-server.spec.md

### Requirement: Graph Query Tool — All 8 scenarios ✅

| Scenario | Code | Tests |
|---|---|---|
| Successful query | `MCPQueryService.execute_cypher_query()` | `test_mcp_query_service.py` |
| Optional KG filter | `_filter_by_knowledge_graph()` | `test_mcp_query_tool.py` |
| Secure enclave redaction | `MCPQuerySecureEnclave.apply_redaction()` | `test_mcp_secure_enclave.py`, `test_secure_enclave_mcp.py` |
| Write operation rejected | `QueryGraphRepository._validate_read_only()` | `test_query_repository.py::TestValidateReadOnly` |
| Query timeout | `SET LOCAL statement_timeout` + `QueryTimeoutError` | `test_query_repository.py::TestExecuteCypher`, `test_query_mcp_http.py` |
| Result limiting | `_ensure_limit()` + `limit+1` fetch | `test_query_repository.py::TestEnsureLimit` |
| Result truncation flag | `truncated = len(rows) > limit` | `test_mcp_query_service.py` |
| Internal property filtering | `_filter_internal_properties()` | `test_mcp_query_tool.py::TestFilterInternalProperties` |

### Requirement: Documentation Fetch Tool — All 5 scenarios ✅

| Scenario | Code |
|---|---|
| Fetch from GitHub | `GithubRepository._build_api_url()` |
| Fetch from GitLab | `GitLabRepository._build_api_url()` |
| Private repo with token | `x-github-pat` / `x-gitlab-pat` headers extracted in `mcp.py` |
| Self-hosted instance | GHE: `api.github.com` vs `{host}/api/v3`; GitLab: hostname-based |
| Invalid URL format | `InvalidRemoteFileURL` → `RemoteFileRepositoryResponse(success=False)` |

### Requirement: Knowledge Graphs Resource — All 2 scenarios ✅

- `get_accessible_knowledge_graphs()` resource in `query/presentation/mcp.py`
- Unit tests: `test_mcp_knowledge_graphs_resource.py`
- Integration tests: `tests/integration/query/test_kg_resource.py`
  - `TestAccessibleKnowledgeGraphsListsPermittedKGs` covers "List accessible"
  - `TestAccessibleKnowledgeGraphsReturnsEmptyListWhenNoAccess` covers "No accessible"
- **Note:** task-151 (queued to add these integration tests) is stale — the tests
  were already added by a prior task (task-110). The orchestrator will discover
  this when it runs task-151.

### Requirement: Agent Instructions Resource — All 2 scenarios ✅

- `instructions://agent` resource + module-level `_prompt_repository = get_prompt_repository()`
  (fail-fast at startup if file missing)
- Unit tests: `test_mcp_agent_instructions.py`

### Requirement: MCP Authentication — All 4 scenarios ✅

| Scenario | Code | Tests |
|---|---|---|
| API key authentication | `MCPApiKeyAuthMiddleware._authenticate_api_key()` | `test_mcp_auth_middleware.py` |
| Bearer token authentication | `MCPApiKeyAuthMiddleware._authenticate_bearer()` | `test_mcp_auth_middleware.py` |
| No credentials → 401 | `_send_json_error(send, 401, …)` | `test_mcp_auth_http.py` |
| Auth service unavailable → 503 | `except Exception: _send_json_error(send, 503, …)` | `test_mcp_auth_middleware.py` lines 318, 615 |

- **Note:** task-149 (queued to add 503 tests) is stale — 503 unit tests already exist
  in `test_mcp_auth_middleware.py` at `TestMCPApiKeyAuthMiddlewareValidationError.test_returns_503_when_validator_raises`
  and `TestMCPBearerValidationError.test_returns_503_when_bearer_validator_raises`
  (added in commit `54052d3ac`). The orchestrator will discover this when it runs task-149.

### Requirement: Apache AGE Single-Column Return — All 4 scenarios ✅

- `QueryGraphRepository._row_to_dict()` produces `{"node":…}`, `{"edge":…}`,
  `{"value":…}`, and map results
- Unit tests: `test_query_repository.py::TestRowToDict`

**Decision: No new tasks.**

---

## Verification: specs/query/query-execution.spec.md

### Requirement: Per-Tenant Graph Routing ✅ (integration tests pending task-150)

- `TenantAwareQueryGraphRepository` wraps `QueryGraphRepository` with graph-name routing
- `graph_name = f"tenant_{tenant_id}"` set in `get_mcp_query_service()` (DI layer)
- `AGEGraphExistenceChecker` validates graph exists via `ag_catalog.ag_graph` before execution
- Unit tests: `test_tenant_routing.py`, `test_query_repository.py::TestTenantGraphRouting`
- Integration test for explicit cross-tenant isolation and "Tenant graph not found" rejection →
  **task-150 (still valid, not yet implemented)**

### Requirement: Read-Only Enforcement — Both scenarios ✅

- Primary (database-level): `SET TRANSACTION READ ONLY` before every Cypher execution
- Secondary (keyword blacklist): `_validate_read_only()` — CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD
- Correlation ID generated on rejection; raw query text never logged
- Unit tests: `test_query_repository.py::TestValidateReadOnly` + `test_database_read_only_applied_before_query`
- Integration test: `tests/integration/test_query_readonly.py`

### Requirement: Timeout Enforcement — Both scenarios ✅

- `SET LOCAL statement_timeout = {ms}` per transaction
- PostgreSQL cancels → `QueryTimeoutError` with `correlation_id`
- Unit tests: `test_query_repository.py::TestExecuteCypher`
- Integration test: `tests/integration/test_query_mcp_http.py`

### Requirement: Result Limiting — All 3 scenarios ✅

- `_ensure_limit()`: appends `LIMIT 1000` when absent; caps explicit `LIMIT > 10000` to `10000`
- Unit tests: `test_query_repository.py::TestEnsureLimit`

### Requirement: Error Categorization — All 4 scenarios ✅

- `MCPQueryService.execute_cypher_query()` maps exception types to error_type strings
- Unit tests: `test_mcp_query_service.py`

**Decision: No new tasks.** task-150 remains valid (per-tenant routing integration tests).

---

## Verification: specs/ui/experience.spec.md

All 18 requirements / 43 scenarios verified against `src/dev-ui/app/`:

| Requirement | Status | Open Tasks |
|---|---|---|
| Backend API Alignment | ✅ | — |
| Navigation Structure | ✅ | — |
| Tenant and Workspace Context | ✅ | — |
| Knowledge Graph Creation | ✅ | — |
| Data Source Connection | ✅ | — |
| Ontology Design | ✅ (UI only; backend deferred per AIHCM-174) | — |
| Sync Monitoring | ✅ | — |
| Get Started Querying (MCP) | ✅ | — |
| Query Console | ✅ (implementation and tests both use `__all__` sentinel; tests pass) | task-147, task-148 (sentinel refactoring) |
| Schema Browser | ✅ | — |
| Graph Explorer | ✅ | — |
| Mutations Console | ✅ | — |
| API Key Management | ✅ | — |
| Workspace Management | ✅ | — |
| Design Language | ✅ | — |
| Interaction Principles | ✅ | — |
| Responsive Design | ✅ | — |
| Dark Mode | ✅ | — |

**UI test suite passes:** 2493 tests in 53 files, 0 failures.

**Note on task-147 / task-148:** Both were created when the tests expected `''` (empty string)
but the implementation had `__all__`. Since then, commit `0035863e4` updated the tests to match
the `__all__` implementation, so all 2493 tests now pass. Tasks 147 and 148 represent a
desired code-quality refactoring (changing the sentinel to `''`) rather than a spec compliance
gap — the current behavior satisfies the spec's behavioral requirements. The orchestrator
will assess whether to run these tasks.

**Decision: No new tasks.**

---

## Summary

**New tasks created this pass: 0**

**Open tasks:**
- task-147: Query console KG selector sentinel `__all__` → `''` (code quality; tests pass with current impl)
- task-148: Update test assertions to match `''` sentinel (follows task-147)
- task-149: 503 auth service unavailable unit test — **likely stale** (tests already at `test_mcp_auth_middleware.py`)
- task-150: Per-tenant graph routing integration tests — **valid, not yet implemented**
- task-151: KG resource integration tests — **likely stale** (tests already at `tests/integration/query/test_kg_resource.py`)
