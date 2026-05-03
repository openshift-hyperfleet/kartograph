# Intake: Query and UI Specs (Second Pass) — 2026-05-02

## Specs Processed

| Spec | Blob SHA |
|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` |

## Result: No New Tasks Created

All three specs were verified line-by-line against the codebase. Since the first
pass (`2026-05-02-query-and-ui-specs-recheck.md`), two additional implementation
commits landed:

- `f61a72b31 feat(query): route MCP queries to per-tenant AGE graph (#552)` — task-084 implemented
- `4c5c49f9d feat(query): add knowledge-graphs://accessible MCP resource` — task-085 implemented

The only outstanding item is **task-086** (truncation flag accuracy), which was
already captured in the first pass and remains `not-started`.

---

## `specs/query/mcp-server.spec.md`

### Requirement: Graph Query Tool

| Scenario | Status | Evidence |
|---|---|---|
| Successful query | ✅ Implemented | `query_graph` in `query/presentation/mcp.py`; returns rows, row_count, truncated, execution_time_ms |
| Optional KnowledgeGraph filter | ✅ Implemented | `_filter_by_knowledge_graph()` in `mcp.py` |
| Secure enclave redaction | ✅ Implemented | `MCPQuerySecureEnclave.apply_redaction()` called in `query_graph`; nodes → `{id}`, edges → `{id, start_id, end_id}`, topology preserved |
| Write operation rejected | ✅ Implemented | `_validate_read_only()` rejects CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD |
| Query timeout | ✅ Implemented | `statement_timeout` set via SQL; `QueryTimeoutError` mapped to `error_type: "timeout"` |
| Result limiting | ✅ Implemented (partial) | `_ensure_limit()` appends LIMIT 1000 default, caps at 10000; task-086 fixes +1 strategy |
| Result truncation flag | ⚠️ task-086 | Current: `len(rows) >= limit` (false positives). Spec SHOULD: fetch `limit+1`, set truncated iff `len > limit` |
| Internal property filtering | ✅ Implemented | `_filter_internal_properties()` strips `all_content_lower` and any future internal fields |

### Requirement: Documentation Fetch Tool

| Scenario | Status | Evidence |
|---|---|---|
| Fetch from GitHub | ✅ Implemented | `GithubRepository._build_api_url()` → GitHub Contents API; `_strip_asciidoc_metadata()` applied |
| Fetch from GitLab | ✅ Implemented | `GitLabRepository._build_api_url()` → GitLab Files API |
| Private repository with token | ✅ Implemented | `x-github-pat` / `x-gitlab-pat` headers read in `fetch_documentation_source` |
| Self-hosted instance | ✅ Implemented | `GitRepositoryFactory.create_from_url()` detects provider by URL pattern; non-`github.com` → `/api/v3/` path |
| Invalid URL format | ✅ Implemented | Factory raises `ValueError`; `AbstractGitRemoteFileRepository.get_file()` raises `InvalidRemoteFileURL`; FastMCP converts to error response |

### Requirement: Knowledge Graphs Resource

| Scenario | Status | Evidence |
|---|---|---|
| List accessible knowledge graphs | ✅ Implemented | `@mcp.resource(uri="knowledge-graphs://accessible")` in `mcp.py`; calls `get_accessible_knowledge_graphs_for_mcp()` with SpiceDB VIEW permission check; returns `[{id, name, description}]` |
| No accessible knowledge graphs | ✅ Implemented | `get_accessible_knowledge_graphs_for_mcp()` returns `[]` when no KGs pass permission filter |

Note: URI uses hyphen (`knowledge-graphs://`) rather than underscore per RFC 3986; clients discover via `resources/list`.

### Requirement: Agent Instructions Resource

| Scenario | Status | Evidence |
|---|---|---|
| Read instructions | ✅ Implemented | `get_agent_instructions()` returns `_prompt_repository.get_agent_instructions()` (cached at startup) |
| Missing instructions at startup | ✅ Implemented | `_prompt_repository = get_prompt_repository()` at module level; raises `FileNotFoundError` on missing file → fail-fast |

### Requirement: MCP Authentication

| Scenario | Status | Evidence |
|---|---|---|
| API key authentication | ✅ Implemented | `MCPApiKeyAuthMiddleware` checks `X-API-Key`; resolves tenant from key |
| Bearer token authentication | ✅ Implemented | Fallback to `Authorization: Bearer`; tenant from `X-Tenant-ID` header |
| No credentials → 401 | ✅ Implemented | `_send_json_error(send, 401, "X-API-Key header is required")` |
| Authentication service unavailable → 503 | ✅ Implemented | Exception in validator → `_send_json_error(send, 503, "Authentication service temporarily unavailable")` |

### Requirement: Apache AGE Single-Column Return

| Scenario | Status | Evidence |
|---|---|---|
| Node return | ✅ Implemented | `_row_to_dict()`: AgeVertex → `{"node": {...properties...}}` |
| Edge return | ✅ Implemented | `_row_to_dict()`: AgeEdge → `{"edge": {...properties...}}` |
| Map return (multiple values) | ✅ Implemented | `_row_to_dict()`: dict → keys preserved, nested vertices/edges converted |
| Scalar return | ✅ Implemented | `_row_to_dict()`: scalar → `{"value": scalar}` |

---

## `specs/query/query-execution.spec.md`

### Requirement: Per-Tenant Graph Routing

| Scenario | Status | Evidence |
|---|---|---|
| Query routed to tenant graph | ✅ Implemented | `get_mcp_query_service()` reads `auth_context.tenant_id`, passes `graph_name=f"tenant_{tenant_id}"` to `AgeGraphClient`; tested in `TestTenantGraphRouting` |
| Tenant graph not found | ✅ Implemented | `_validate_graph_exists()` checks `ag_catalog.ag_graph`; raises `QueryExecutionError` before any Cypher execution |

### Requirement: Read-Only Enforcement

| Scenario | Status | Evidence |
|---|---|---|
| Database-level enforcement (primary) | ✅ Implemented | `tx.execute_sql("SET TRANSACTION READ ONLY")` called before Cypher; verified in `test_sets_transaction_read_only` and `test_database_read_only_applied_before_query` |
| Keyword blacklist (secondary) | ✅ Implemented | `_validate_read_only()` rejects all 7 keywords case-insensitively; correlation ID generated; `cypher_query_rejected` probe does NOT log raw query (only correlation_id + reason); error response includes correlation_id in `QueryError` |

### Requirement: Timeout Enforcement

| Scenario | Status | Evidence |
|---|---|---|
| Query within timeout | ✅ Implemented | Normal execution path |
| Query exceeds timeout | ✅ Implemented | `SET LOCAL statement_timeout = {ms}` → DB cancels → `QueryTimeoutError` with correlation_id; mapped to `error_type: "timeout"` |

### Requirement: Result Limiting

| Scenario | Status | Evidence |
|---|---|---|
| No LIMIT in query | ⚠️ task-086 | Appends `LIMIT 1000` (correct default). task-086 changes to `LIMIT 1001` for accurate truncation detection |
| Explicit LIMIT within bounds | ✅ Implemented | `_ensure_limit()` keeps existing LIMIT when ≤ 10000 |
| Explicit LIMIT exceeds maximum | ⚠️ task-086 | Caps to 10000. task-086 changes cap to 10001 for truncation detection |

### Requirement: Error Categorization

| Scenario | Status | Evidence |
|---|---|---|
| Forbidden query → "forbidden" | ✅ Implemented | `QueryForbiddenError` → `MCPQueryService` → `QueryError(error_type="forbidden")` |
| Timeout error → "timeout" | ✅ Implemented | `QueryTimeoutError` → `QueryError(error_type="timeout")` |
| Execution error → "execution_error" | ✅ Implemented | `QueryExecutionError` → `QueryError(error_type="execution_error")` |
| Unexpected error → "unknown_error" | ✅ Implemented | `except Exception` → `QueryError(error_type="unknown_error")` |

---

## `specs/ui/experience.spec.md`

Blob SHA `e77913c2cc6d8b719291e2dbb6870519a94d50da` — unchanged since the prior two
passes. All 18 requirements and 40+ scenarios are confirmed covered by existing tasks.
The coverage map from `2026-05-01-experience-spec-intake-final.md` remains accurate.

---

## Open Tasks for These Specs

| Task | Title | Status |
|---|---|---|
| task-086 | Fix result truncation detection — fetch limit+1 rows | not-started |

All other previously created tasks (task-084, task-085) have been implemented
since the prior intake and await status updates from the orchestrator's
spec-alignment-reviewer.

## Conclusion

**No new task files created.** All three specs at their current blob SHAs are
covered by existing code and the one outstanding not-started task (task-086).
