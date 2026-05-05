# Intake: mcp-server, query-execution, ui/experience — no new tasks (pass 5)

**Date:** 2026-05-05
**Specs processed:**
- `specs/query/mcp-server.spec.md` (blob SHA: `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`)
- `specs/query/query-execution.spec.md` (blob SHA: `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`)
- `specs/ui/experience.spec.md` (blob SHA: `e77913c2cc6d8b719291e2dbb6870519a94d50da`)

---

## specs/query/mcp-server.spec.md

Spec SHA unchanged from prior intake (`2ac8d03`). All six requirements verified
line-by-line against the implementation.

### Requirement: Graph Query Tool
All 8 scenarios implemented in `src/api/query/presentation/mcp.py` (`query_graph` tool):

| Scenario | Implementation | Tests |
|---|---|---|
| Successful query | `MCPQueryService.execute_cypher_query()` | `test_mcp_query_service.py`, `test_mcp_query_tool.py` |
| Optional KG filter | `_filter_by_knowledge_graph()` | `test_mcp_tools.py::TestFilterByKnowledgeGraph` |
| Secure enclave redaction | `MCPQuerySecureEnclave.apply_redaction()` | `test_mcp_secure_enclave.py` |
| Write operation rejected | `QueryGraphRepository._validate_read_only()` | `test_query_repository.py::TestValidateReadOnly` |
| Query timeout | `QueryTimeoutError` + `correlation_id` | `test_query_repository.py::TestExecuteCypher` |
| Result limiting | `_ensure_limit()` + `limit+1` fetch | `test_query_repository.py::TestEnsureLimit` |
| Result truncation flag | `truncated = len(rows) > limit` | `test_mcp_query_service.py` |
| Internal property filtering | `_filter_internal_properties()` | `test_mcp_tools.py::TestFilterInternalProperties` |

### Requirement: Documentation Fetch Tool
All 5 scenarios implemented in `git_repository.py` (`GitRepositoryFactory`,
`GithubRepository`, `GitLabRepository`):

| Scenario | Status |
|---|---|
| Fetch from GitHub | ✅ `GithubRepository._build_api_url()` |
| Fetch from GitLab | ✅ `GitLabRepository._build_api_url()` |
| Private repo with token | ✅ PAT headers in `mcp.py`; tested in `test_mcp_tools.py` |
| Self-hosted instance | ✅ GHE: `https://{host}/api/v3`; GitLab: hostname-based |
| Invalid URL format | ✅ `InvalidRemoteFileURL` → `RemoteFileRepositoryResponse(success=False)` |

### Requirement: Knowledge Graphs Resource
- `knowledge-graphs://accessible` resource in `mcp.py`
- Unit tests: `test_mcp_knowledge_graphs_resource.py`
- Integration test gap → **task-151** (already queued)

### Requirement: Agent Instructions Resource
- `instructions://agent` resource + module-level `_prompt_repository` fail-fast
- Unit tests: `test_mcp_agent_instructions.py`

### Requirement: MCP Authentication
- `MCPApiKeyAuthMiddleware` wraps the ASGI app; handles API key + Bearer token + 401 + 503
- Structural test: `test_mcp_auth_wiring.py`
- 503 unit test gap → **task-149** (already queued)

### Requirement: Apache AGE Single-Column Return
- `QueryGraphRepository._row_to_dict()` produces `{"node":…}`, `{"edge":…}`, `{"value":…}`,
  and map results
- Unit tests: `test_query_repository.py::TestRowToDict`

**Decision: No new tasks.** All scenarios covered; gaps addressed by task-149 and task-151.

---

## specs/query/query-execution.spec.md

Spec SHA unchanged from prior intake (`dbcf0d7`). All five requirements verified.

### Requirement: Per-Tenant Graph Routing
- `QueryGraphRepository._validate_graph_exists()` calls `client.graph_exists()` before Cypher
- `TenantAwareQueryGraphRepository` wraps inner repository with graph-name routing
- Unit tests: `test_query_repository.py::TestTenantGraphRouting`, `test_tenant_routing.py`
- Integration test gap → **task-150** (already queued)

### Requirement: Read-Only Enforcement
- Primary: `SET TRANSACTION READ ONLY` before every Cypher execution
- Secondary: `_validate_read_only()` keyword blacklist (CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD)
- Unit tests: `test_query_repository.py::TestValidateReadOnly` + ordering verification
- Integration test: `tests/integration/test_query_readonly.py`

### Requirement: Timeout Enforcement
- `SET LOCAL statement_timeout = {ms}` per transaction; maps to `QueryTimeoutError` with `correlation_id`
- Unit tests: `test_query_repository.py::TestExecuteCypher`
- Integration test: `tests/integration/test_query_mcp_http.py`

### Requirement: Result Limiting
- `_ensure_limit()`: appends LIMIT 1000 when absent; caps explicit LIMIT > 10000 to 10000
- Unit tests: `test_query_repository.py::TestEnsureLimit`

### Requirement: Error Categorization
- `MCPQueryService.execute_cypher_query()` maps:
  - `QueryForbiddenError` → `error_type="forbidden"`
  - `QueryTimeoutError` → `error_type="timeout"`
  - `QueryExecutionError` → `error_type="execution_error"`
  - `Exception` → `error_type="unknown_error"`
- Unit tests: `test_application_services.py`

**Decision: No new tasks.** All scenarios covered; gap addressed by task-150.

---

## specs/ui/experience.spec.md

Spec SHA unchanged from prior intake (`e77913c`). All requirements verified against
`src/dev-ui/app/`.

| Requirement | Implementation | Tests |
|---|---|---|
| Backend API Alignment | All pages use correct REST endpoints | `api-alignment.test.ts` |
| Navigation Structure | `layouts/default.vue` (Explore/Data/Connect/Settings) | `navigation-structure.test.ts`, `default.layout.test.ts` |
| Tenant and Workspace Context | Tenant selector; workspace guidance toast | `tenant-switch.test.ts`, `workspace-guidance.test.ts` |
| Knowledge Graph Creation | Workspace-scoped KG creation dialog | `knowledge-graphs.test.ts` |
| Data Source Connection | Adapter wizard with adapter-specific fields | `data-source-connection-wizard.test.ts`, `data-sources.test.ts` |
| Ontology Design | Utility functions (intent, type editing); **backend deferred** (AIHCM-174) | `ontology-design.test.ts`, `ontology-add-types.test.ts` |
| Sync Monitoring | Status, history, logs, manual trigger | `sync-monitoring-extended.test.ts`, `sync-logs.test.ts`, `sync-phase-indicator.test.ts` |
| Get Started Querying (MCP) | `pages/integrate/mcp.vue` with inline key creation and snippet | `mcp-integration.test.ts` |
| Query Console | CodeMirror editor, autocomplete, history, KG selector | `query.test.ts`, `query-kg-selector.test.ts`, `query-history.test.ts` |
| Schema Browser | Type listing, detail panel, cross-navigation | `schema-browser.test.ts`, `schema-crossnav-deeplink.test.ts` |
| Graph Explorer | Node search, neighbor traversal | `graph-explorer.test.ts` |
| Mutations Console | JSONL editor, live preview, file upload, KG selector, floating indicator | `mutations-console.test.ts`, `mutations-kg-selector.test.ts`, `mutations-submission.test.ts`, `mutations-indicator-persistence.test.ts` |
| API Key Management | Create, list, revoke with secret-once display | `api-keys.test.ts`, `transient-secret.test.ts` |
| Workspace Management | Create, member management | `workspace-management.test.ts` |
| Design Language | shadcn/vue + Reka UI, Tailwind/OKLCH, Lucide, CVA | `design-language.test.ts`, `design-system.test.ts` |
| Interaction Principles | Toast, copy-to-clipboard, keyboard shortcuts, focus rings | `interaction-principles.test.ts`, `keyboard-shortcuts.test.ts`, `focus-ring.test.ts` |
| Responsive Design | Collapsible sidebar (md), sheet overlay (mobile) | `responsive-design.test.ts` |
| Dark Mode | Toggle in header, preference persistence | `color-mode.test.ts` |

**Open task-147**: Fix `__all__` → `''` sentinel in `pages/query/index.vue` (implementation bug).
**Open task-148**: Update test assertions from `__all__` to `''` sentinel.

**Ontology Design backend** — deferred per guidelines: no Extraction context tasks until
AIHCM-174 spike completes.

**Decision: No new tasks.** All implementation gaps are covered by existing tasks 147–151.
