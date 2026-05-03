# Intake: Query and UI Specs — 2026-05-03

## Specs Processed

| Spec | Blob SHA |
|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` |

## Result: No New Tasks Created

All three specs were verified line-by-line against the codebase and the existing
task backlog. Since the prior second-pass intake (`2026-05-02-query-and-ui-specs-second-pass.md`),
one additional implementation commit landed:

- `66cd9810c fix(query): implement fetch-limit+1 truncation detection in MCPQueryService (#563)` — task-097 implemented

The blob SHAs for all three specs are **identical** to the prior pass — no spec
content changed. The full coverage tables below confirm no gaps remain for any
requirement or scenario.

---

## `specs/query/mcp-server.spec.md`

### Requirement: Graph Query Tool

| Scenario | Status | Evidence |
|---|---|---|
| Successful query | ✅ Implemented | `query_graph` in `query/presentation/mcp.py`; returns rows, row_count, truncated, execution_time_ms |
| Optional KnowledgeGraph filter | ✅ Implemented | `_filter_by_knowledge_graph()` in `mcp.py`; tests in `test_mcp_tools.py` |
| Secure enclave redaction | ✅ Implemented | `MCPQuerySecureEnclave.apply_redaction()` called in `query_graph`; nodes → `{id}`, edges → `{id, start_id, end_id}`; tests in `test_mcp_secure_enclave.py` |
| Write operation rejected | ✅ Implemented | `_validate_read_only()` rejects CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD; tests in `test_query_repository.py` |
| Query timeout | ✅ Implemented | `SET LOCAL statement_timeout` via SQL; `QueryTimeoutError` → `error_type: "timeout"` |
| Result limiting | ✅ Implemented | `_ensure_limit()` appends `LIMIT max_rows`; `max_rows=limit+1` from service (via task-097) |
| Result truncation flag | ✅ Implemented | Service passes `max_rows=limit+1`; `truncated = len(rows) > limit`; trims to `limit` rows. Commit `66cd9810c`. Tests in `test_application_services.py` |
| Internal property filtering | ✅ Implemented | `_filter_internal_properties()` strips `all_content_lower`; tests in `test_mcp_query_tool.py` |

### Requirement: Documentation Fetch Tool

| Scenario | Status | Evidence |
|---|---|---|
| Fetch from GitHub | ✅ Implemented | `GithubRepository._build_api_url()` → GitHub Contents API; `_strip_asciidoc_metadata()` applied |
| Fetch from GitLab | ✅ Implemented | `GitLabRepository._build_api_url()` → GitLab Files API |
| Private repository with token | ✅ Implemented | `x-github-pat` / `x-gitlab-pat` headers read; tests in `test_mcp_tools.py` |
| Self-hosted instance | ✅ Implemented | `GitRepositoryFactory.create_from_url()` detects provider by URL pattern; tests in `test_git_repository.py` |
| Invalid URL format | ✅ Implemented | Factory raises `ValueError` → FastMCP error response; tests in `test_git_repository.py` |

### Requirement: Knowledge Graphs Resource

| Scenario | Status | Evidence |
|---|---|---|
| List accessible knowledge graphs | ✅ Implemented | `@mcp.resource(uri="knowledge-graphs://accessible")` in `mcp.py`; SpiceDB VIEW permission check; returns `[{id, name, description}]`; tests in `test_mcp_knowledge_graphs_resource.py` |
| No accessible knowledge graphs | ✅ Implemented | Returns `[]` when no KGs pass permission filter; tested |

Note: URI uses hyphen (`knowledge-graphs://`) rather than underscore per RFC 3986;
the code comment in `mcp.py` documents this known deviation from spec notation.

### Requirement: Agent Instructions Resource

| Scenario | Status | Evidence |
|---|---|---|
| Read instructions | ✅ Implemented | `get_agent_instructions()` returns `_prompt_repository.get_agent_instructions()` (cached at startup); tests in `test_mcp_agent_instructions.py` |
| Missing instructions at startup | ✅ Implemented | Module-level `_prompt_repository = get_prompt_repository()` raises `FileNotFoundError` on missing file → fail-fast; tests in `test_mcp_agent_instructions.py` |

### Requirement: MCP Authentication

| Scenario | Status | Evidence |
|---|---|---|
| API key authentication | ✅ Implemented | `MCPApiKeyAuthMiddleware` checks `X-API-Key`; resolves tenant/user from key; tests in `test_mcp_auth_middleware.py` |
| Bearer token authentication | ✅ Implemented | Fallback to `Authorization: Bearer`; tenant from `X-Tenant-ID` header; tests in `test_mcp_auth_middleware.py` |
| No credentials → 401 | ✅ Implemented | `_send_json_error(send, 401, "X-API-Key header is required")` |
| Authentication service unavailable → 503 | ✅ Implemented | Exception in validator → `_send_json_error(send, 503, "Authentication service temporarily unavailable")` |

### Requirement: Apache AGE Single-Column Return

| Scenario | Status | Evidence |
|---|---|---|
| Node return | ✅ Implemented | `_row_to_dict()`: AgeVertex → `{"node": {...properties...}}`; tests in `test_query_repository.py` |
| Edge return | ✅ Implemented | `_row_to_dict()`: AgeEdge → `{"edge": {...properties...}}`; tests in `test_query_repository.py` |
| Map return (multiple values) | ✅ Implemented | `_row_to_dict()`: dict → keys preserved, nested vertices/edges converted |
| Scalar return | ✅ Implemented | `_row_to_dict()`: scalar → `{"value": scalar}` |

---

## `specs/query/query-execution.spec.md`

### Requirement: Per-Tenant Graph Routing

| Scenario | Status | Evidence |
|---|---|---|
| Query routed to tenant graph | ✅ Implemented | `get_mcp_query_service()` reads `auth_context.tenant_id`, constructs `graph_name=f"tenant_{tenant_id}"`; `TenantAwareQueryGraphRepository` enforces routing; tests in `test_tenant_routing.py` |
| Tenant graph not found | ✅ Implemented | `TenantAwareQueryGraphRepository._check_exists(self.graph_name)` → raises `QueryExecutionError` before DB; tests in `test_tenant_routing.py` |

Integration test gap (cross-tenant isolation): covered by **task-100** (`not-started`).

### Requirement: Read-Only Enforcement

| Scenario | Status | Evidence |
|---|---|---|
| Database-level enforcement (primary) | ✅ Implemented | `tx.execute_sql("SET TRANSACTION READ ONLY")` before Cypher; tests verify read-only is applied before query |
| Keyword blacklist (secondary) | ✅ Implemented | `_validate_read_only()` rejects all 7 keywords (CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD) case-insensitively; correlation ID generated per rejection; probe logs correlation_id (not raw query); error response includes correlation_id |

### Requirement: Timeout Enforcement

| Scenario | Status | Evidence |
|---|---|---|
| Query within timeout | ✅ Implemented | Normal execution path returns results |
| Query exceeds timeout | ✅ Implemented | `SET LOCAL statement_timeout = {ms}` → DB cancels → `QueryTimeoutError` with correlation_id → `error_type: "timeout"` |

### Requirement: Result Limiting

| Scenario | Status | Evidence |
|---|---|---|
| No LIMIT in query | ✅ Implemented | `_ensure_limit()` appends `LIMIT max_rows` where `max_rows = limit + 1` from service |
| Explicit LIMIT within bounds | ✅ Implemented | `_ensure_limit()` keeps existing LIMIT when ≤ MAX_LIMIT (10000) |
| Explicit LIMIT exceeds maximum | ✅ Implemented | `_ensure_limit()` caps to `LIMIT 10000` (MAX_LIMIT) |

Note: The explicit-LIMIT-exceeds-maximum truncation detection edge case (correct
`truncated` flag when user provides `LIMIT N > 10000`) is tracked in **task-086**
(`not-started`). The primary truncation scenario (no-LIMIT case) is correctly
implemented via the service's `max_rows=limit+1` strategy (task-097, completed).

### Requirement: Error Categorization

| Scenario | Status | Evidence |
|---|---|---|
| Forbidden query → "forbidden" | ✅ Implemented | `QueryForbiddenError` → `MCPQueryService` → `QueryError(error_type="forbidden")`; tests in `test_mcp_query_service.py` |
| Timeout error → "timeout" | ✅ Implemented | `QueryTimeoutError` → `QueryError(error_type="timeout")`; tests in `test_mcp_query_service.py` |
| Execution error → "execution_error" | ✅ Implemented | `QueryExecutionError` → `QueryError(error_type="execution_error")`; tests in `test_mcp_query_service.py` |
| Unexpected error → "unknown_error" | ✅ Implemented | `except Exception` → `QueryError(error_type="unknown_error")`; tests in `test_mcp_query_service.py` |

---

## `specs/ui/experience.spec.md`

Blob SHA `e77913c2cc6d8b719291e2dbb6870519a94d50da` — unchanged since the prior
two passes (2026-05-02). All 18 requirements and 40+ scenarios are confirmed
covered by existing tasks.

Recent spec additions (from commits `97bf3eeef` and `e3d22bccf`):

| New Content | Coverage |
|---|---|
| Requirement: Backend API Alignment (2 scenarios) | task-040, task-050, task-058, task-065, task-068, task-072, task-075, task-077, task-078, task-079, task-080, task-081, task-082 |
| Mutations Console — Scenario: Knowledge graph selection | task-065, task-087 |

The coverage map from `2026-05-01-experience-spec-intake-final.md` remains accurate
for all other requirements (Navigation Structure, Tenant/Workspace Context, KG
Creation, Data Source Connection, Ontology Design, Sync Monitoring, Get Started
Querying, Query Console, Schema Browser, Graph Explorer, Mutations Console, API Key
Management, Workspace Management, Design Language, Interaction Principles, Responsive
Design, Dark Mode).

---

## Open Tasks for These Specs

| Task | Title | Status | Note |
|---|---|---|---|
| task-086 | Fix result truncation detection — fetch limit+1 rows (cap case) | not-started | Partial fix landed via task-097; cap case still pending |
| task-100 | Add cross-tenant boundary enforcement integration test for MCP queries | not-started | Unit tests exist; integration test still needed |

All previously `not-started` tasks created by prior intake passes remain the
authoritative work items. No new tasks were created in this pass.

## Conclusion

**No new task files created.** All three specs at their current blob SHAs are
fully covered by existing code, tests, and the task backlog above.
