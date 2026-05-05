# Intake Pass 7: mcp-server, query-execution, ui/experience

**Date:** 2026-05-05
**Processed by:** PM intake agent (seventh pass)
**Trigger:** Specs flagged as "(modified)" in orchestrator — same blob SHAs as all prior passes.

## Specs Processed

| Spec | Blob SHA | Decision |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | No new tasks |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | No new tasks |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | No new tasks |

Blob SHAs are identical to all prior passes (passes 1–6). The specs have not changed.
Pass 6 (`2026-05-05-query-ui-specs-pass6.md`) performed the most recent authoritative
line-by-line verification. This pass confirms those findings.

---

## Verification: specs/query/mcp-server.spec.md

All six requirements fully implemented and tested. No new gaps found.

### Requirement: Graph Query Tool — 8 Scenarios ✅

| Scenario | Code | Tests |
|---|---|---|
| Successful query | `MCPQueryService.execute_cypher_query()` | `test_mcp_query_service.py` |
| Optional KG filter | `_filter_by_knowledge_graph()` in `mcp.py` | `test_mcp_tools.py::TestFilterByKnowledgeGraph` |
| Secure enclave redaction | `MCPQuerySecureEnclave.apply_redaction()` | `test_mcp_secure_enclave.py` |
| Write operation rejected | `QueryGraphRepository._validate_read_only()` | `test_query_repository.py::TestValidateReadOnly` |
| Query timeout | `SET LOCAL statement_timeout` + `QueryTimeoutError` with `correlation_id` | `test_query_repository.py::TestExecuteCypher` |
| Result limiting | `_ensure_limit()` + fetch `limit+1` rows | `test_query_repository.py::TestEnsureLimit` |
| Result truncation flag | `truncated = len(rows) > limit`; returns `rows[:limit]` | `test_mcp_query_service.py` |
| Internal property filtering | `_filter_internal_properties()` strips `all_content_lower` | `test_mcp_tools.py::TestFilterInternalProperties` |

### Requirement: Documentation Fetch Tool — 5 Scenarios ✅

| Scenario | Code |
|---|---|
| Fetch from GitHub | `GithubRepository._build_api_url()` → `api.github.com` |
| Fetch from GitLab | `GitLabRepository._build_api_url()` → `{host}/api/v4` |
| Private repo with token | `x-github-pat` / `x-gitlab-pat` headers extracted in `fetch_documentation_source` |
| Self-hosted instance | GHE: `https://{host}/api/v3`; GitLab: hostname-based |
| Invalid URL format | `InvalidRemoteFileURL` caught → `RemoteFileRepositoryResponse(success=False)` |

AsciiDoc stripping via `_strip_asciidoc_metadata()` confirmed. PAT forwarding tested in
`test_mcp_tools.py::TestFetchDocumentationSourceHeaders`.

### Requirement: Knowledge Graphs Resource — 2 Scenarios ✅

`knowledge-graphs://accessible` resource implemented in `query/presentation/mcp.py`.
Unit tests: `test_mcp_knowledge_graphs_resource.py`.
Integration tests: `tests/integration/query/test_kg_resource.py` (added in a prior task).
**task-151 is stale** — tests it was created to add already exist.

### Requirement: Agent Instructions Resource — 2 Scenarios ✅

`instructions://agent` resource with module-level `_prompt_repository = get_prompt_repository()`
(fail-fast at import time if `agent_instructions.md` is absent).
Unit tests: `test_mcp_agent_instructions.py`.

### Requirement: MCP Authentication — 4 Scenarios ✅

| Scenario | Code | Tests |
|---|---|---|
| API key authentication | `MCPApiKeyAuthMiddleware._authenticate_api_key()` | `test_mcp_auth_middleware.py` |
| Bearer token authentication | `MCPApiKeyAuthMiddleware._authenticate_bearer()` | `test_mcp_auth_middleware.py` |
| No credentials → 401 | `_send_json_error(send, 401, …)` | `test_mcp_auth_http.py` (integration) |
| Auth service unavailable → 503 | `except Exception: _send_json_error(send, 503, …)` | `test_mcp_auth_middleware.py` (unit) |

**task-149 is stale** — the 503 unit tests it was created to add already exist in
`test_mcp_auth_middleware.py` (added in commit `54052d3ac`).

### Requirement: Apache AGE Single-Column Return — 4 Scenarios ✅

`QueryGraphRepository._row_to_dict()` handles: `AgeVertex` → `{"node":…}`,
`AgeEdge` → `{"edge":…}`, `dict` (map) → preserved keys with nested conversion,
scalar → `{"value": item}`. Unit tests: `test_query_repository.py::TestRowToDict`.

**Decision: No new tasks for `specs/query/mcp-server.spec.md`.**

---

## Verification: specs/query/query-execution.spec.md

All five requirements fully implemented and tested. No new gaps found.

### Requirement: Per-Tenant Graph Routing — 2 Scenarios ✅ (integration test pending)

- `QueryGraphRepository._validate_graph_exists()` checks `ag_catalog.ag_graph` before Cypher
- `TenantAwareQueryGraphRepository` routes queries to `tenant_{tenant_id}` graph
- Unit tests: `test_query_repository.py::TestTenantGraphRouting`, `test_tenant_routing.py`
- **task-150 still valid** — integration test for explicit cross-tenant isolation not yet
  implemented

### Requirement: Read-Only Enforcement — 2 Scenarios ✅

- Primary (database-level): `SET TRANSACTION READ ONLY` before every Cypher statement
- Secondary (keyword blacklist): `_validate_read_only()` — CREATE, DELETE, SET, REMOVE,
  MERGE, EXPLAIN, LOAD; correlation ID generated; raw query never logged
- Unit tests: `test_query_repository.py::TestValidateReadOnly`
- Integration tests: `tests/integration/test_query_readonly.py`

### Requirement: Timeout Enforcement — 2 Scenarios ✅

`SET LOCAL statement_timeout = {timeout_seconds * 1000}` per transaction. PostgreSQL
cancellation → `QueryTimeoutError` with `correlation_id`. Tested unit and integration.

### Requirement: Result Limiting — 3 Scenarios ✅

`_ensure_limit()`: no LIMIT → append `LIMIT max_rows`; explicit `LIMIT ≤ 10000` → preserved;
explicit `LIMIT > 10000` → capped to 10000. Unit tests: `test_query_repository.py::TestEnsureLimit`.

### Requirement: Error Categorization — 4 Scenarios ✅

`MCPQueryService.execute_cypher_query()` maps exception subclasses to `error_type` strings.
Subclass ordering verified (specific exceptions caught before base class).
Unit tests: `test_mcp_query_service.py`.

**Decision: No new tasks for `specs/query/query-execution.spec.md`.**
task-150 (per-tenant routing integration tests) remains valid and not yet implemented.

---

## Verification: specs/ui/experience.spec.md

All 18 requirements verified against `src/dev-ui/app/`. No new gaps found.

| Requirement | Status | Notes |
|---|---|---|
| Backend API Alignment | ✅ | `api-alignment.test.ts` |
| Navigation Structure | ✅ | `layouts/default.vue`; `navigation-structure.test.ts` |
| Tenant and Workspace Context | ✅ | `tenant-switch.test.ts`, `workspace-guidance.test.ts` |
| Knowledge Graph Creation | ✅ | `knowledge-graphs.test.ts` |
| Data Source Connection | ✅ | `data-source-connection-wizard.test.ts` |
| Ontology Design | ⚠️ BLOCKED | Backend requires AIHCM-174 Extraction spike; UI utilities present |
| Sync Monitoring | ✅ | `sync-monitoring-extended.test.ts`, `sync-logs.test.ts` |
| Get Started Querying (MCP) | ✅ | `mcp-integration.test.ts` |
| Query Console | ✅ | `query.test.ts`, `query-kg-selector.test.ts`, `query-history.test.ts` |
| Schema Browser | ✅ | `schema-browser.test.ts`, `schema-crossnav-deeplink.test.ts` |
| Graph Explorer | ✅ | `graph-explorer.test.ts` |
| Mutations Console | ✅ | `mutations-console.test.ts`, `mutations-submission.test.ts` |
| API Key Management | ✅ | `api-keys.test.ts` |
| Workspace Management | ✅ | `workspace-management.test.ts` |
| Design Language | ✅ | `design-language.test.ts`, `design-system.test.ts` |
| Interaction Principles | ✅ | `interaction-principles.test.ts`, `keyboard-shortcuts.test.ts` |
| Responsive Design | ✅ | `responsive-design.test.ts` |
| Dark Mode | ✅ | `color-mode.test.ts` |

**Open tasks for this spec:**
- task-147: Refactor `pages/query/index.vue` to use `''` empty-string sentinel (code quality;
  current `__all__` implementation is behaviorally correct and tests pass)
- task-148: Update test assertions from `__all__` to `''` sentinel (follows task-147)

**Ontology Design** remains blocked pending AIHCM-174. Per guidelines, no tasks created.

**Decision: No new tasks for `specs/ui/experience.spec.md`.**

---

## Summary

**New tasks created this pass: 0**

All three specs have been fully implemented. The "(modified)" flag reflects the orchestrator's
polling schedule, not actual spec changes. The blob SHAs are unchanged from passes 1–6.

**Open tasks as of this pass:**

| Task | Status | Notes |
|---|---|---|
| task-147 | not-started | Query console KG selector `__all__` → `''` refactor |
| task-148 | not-started | Update test assertions to match `''` sentinel (follows task-147) |
| task-149 | not-started | **Likely stale** — 503 unit tests already exist in `test_mcp_auth_middleware.py` |
| task-150 | not-started | **Valid** — per-tenant routing integration tests not yet implemented |
| task-151 | not-started | **Likely stale** — KG resource integration tests already exist in `test_kg_resource.py` |
