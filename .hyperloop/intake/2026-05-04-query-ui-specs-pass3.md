# Intake Pass 3: mcp-server, query-execution, ui/experience — No New Tasks

**Date:** 2026-05-04
**Processed by:** PM intake agent (third pass, triggered by "(modified)" flag on all three specs)
**Specs processed:**

| Spec | Blob SHA | Status |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | ✅ Fully implemented |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | ✅ Fully implemented |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | ✅ Fully implemented (Ontology Design blocked) |

**Blob SHAs are identical to the prior intake (2026-05-04-query-ui-specs-intake.md).** The specs have not changed; this pass confirms the prior conclusion.

---

## Verification: `specs/query/mcp-server.spec.md`

### Requirement: Graph Query Tool — 8 Scenarios

| Scenario | Code Location | Test |
|---|---|---|
| Successful query | `query/presentation/mcp.py::query_graph` | `test_mcp_query_tool.py` |
| Optional KG filter | `mcp.py::_filter_by_knowledge_graph()` | `test_mcp_query_tool.py` |
| Secure enclave redaction | `application/mcp_secure_enclave.py::MCPQuerySecureEnclave.apply_redaction()` | `test_mcp_secure_enclave.py` |
| Write operation rejected | `infrastructure/query_repository.py::_validate_read_only()` | `test_query_repository.py::TestValidateReadOnly` |
| Query timeout | `SET LOCAL statement_timeout` in `execute_cypher` | `test_query_repository.py::TestExecuteCypher` |
| Result limiting | `query_repository.py::_ensure_limit()` | `test_query_repository.py::TestEnsureLimit` |
| Result truncation flag | `services.py`: fetch `limit+1`, truncated = len > limit | `test_mcp_query_service.py` |
| Internal property filtering | `mcp.py::_filter_internal_properties()` | `test_mcp_query_tool.py` |

**Verification notes:**
- Secure enclave: unauthorized nodes → ID-only (`{"id": ...}` only); unauthorized edges → `{"id", "start_id", "end_id"}` only. Topology preserved (entities remain in results). SpiceDB error → redact (fail-safe). All confirmed in `test_mcp_secure_enclave.py`.
- Internal property filtering: strips `all_content_lower` recursively; confirmed in code.
- Truncation: `execute_cypher` called with `limit + 1`; `truncated = len(rows) > limit`; `rows[:limit]` returned. ✓

### Requirement: Documentation Fetch Tool — 5 Scenarios

| Scenario | Code Location |
|---|---|
| Fetch from GitHub | `GithubRepository._parse_url()` + `_build_api_url()` (api.github.com) |
| Fetch from GitLab | `GitLabRepository._parse_url()` + `_build_api_url()` (api/v4) |
| Private repo with token | `access_token` → `Authorization: Bearer` (GitHub) / `PRIVATE-TOKEN` (GitLab) |
| Self-hosted instance | GitHub Enterprise: `/api/v3` path; GitLab: hostname used directly |
| Invalid URL format | `GitRepositoryFactory.create_from_url()` raises `InvalidRemoteFileURL` |

**Verification notes:**
- AsciiDoc stripping: `_strip_asciidoc_metadata()` strips everything before the first `= Title` line. Applied to all providers. ✓
- `x-github-pat` and `x-gitlab-pat` headers are read in `mcp.py::fetch_documentation_source()` and passed to factory. ✓
- Self-hosted GitHub: `_build_api_url()` checks `hostname_lower == "github.com"` → api.github.com; else → `https://{hostname}/api/v3`. ✓
- GitLab self-hosted: `_build_api_url()` uses `parsed.hostname` directly (no domain check needed). ✓

### Requirement: Knowledge Graphs Resource — 2 Scenarios

`knowledge-graphs://accessible` resource in `mcp.py` calls `get_accessible_knowledge_graphs_for_mcp()` and returns `[{id, name, description}]`. Returns `[]` for empty. Tested in `test_mcp_knowledge_graphs_resource.py`. ✓

### Requirement: Agent Instructions Resource — 2 Scenarios

`instructions://agent` resource returns cached content from `_prompt_repository`. Module-level `_prompt_repository = get_prompt_repository()` causes fail-fast at startup if instructions file is missing. ✓

### Requirement: MCP Authentication — 4 Scenarios

All verified in `shared_kernel/middleware/mcp_api_key_auth.py::MCPApiKeyAuthMiddleware`:
- API key (X-API-Key header) → auth from key.created_by_user_id, key.tenant_id ✓
- Bearer token (Authorization: Bearer) → JWT validation, tenant from X-Tenant-ID header ✓
- No credentials → 401 "X-API-Key header is required" ✓
- Service unavailable → 503 "Authentication service temporarily unavailable" (from `except Exception`) ✓

### Requirement: Apache AGE Single-Column Return — 4 Scenarios

All in `query_repository.py::_row_to_dict()`:
- `AgeVertex` → `{"node": {id, label, properties}}` ✓
- `AgeEdge` → `{"edge": {id, label, start_id, end_id, properties}}` ✓
- `dict` → preserve keys, convert nested vertices/edges to dicts ✓
- scalar → `{"value": item}` ✓

**Decision: No new tasks for `specs/query/mcp-server.spec.md`.**

---

## Verification: `specs/query/query-execution.spec.md`

### Requirement: Per-Tenant Graph Routing — 2 Scenarios

| Scenario | Code Location |
|---|---|
| Query routed to tenant graph | `infrastructure/tenant_routing.py::TenantAwareQueryGraphRepository` wraps client with `tenant_{tenant_id}` graph name |
| Tenant graph not found | `query_repository.py::_validate_graph_exists()` → `QueryExecutionError` before any Cypher; tested in `TestTenantGraphRouting` |

### Requirement: Read-Only Enforcement — 2 Scenarios

- **Database-level (primary):** `tx.execute_sql("SET TRANSACTION READ ONLY")` in `execute_cypher()` before any Cypher statement. Rejects writes at DB level regardless of query content. ✓
- **Keyword blacklist (secondary):** `_validate_read_only()` rejects CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD (case-insensitive). Correlation ID generated per rejection. Raw query never logged (verified in `test_observability.py::test_raw_query_not_in_log_event`). ✓

### Requirement: Timeout Enforcement — 2 Scenarios

`SET LOCAL statement_timeout = {timeout_seconds * 1000}` per transaction. PostgreSQL timeout → `QueryTimeoutError` with correlation ID. Tested in `TestExecuteCypher`. ✓

### Requirement: Result Limiting — 3 Scenarios

`_ensure_limit()`: no LIMIT → append `LIMIT max_rows`; explicit LIMIT ≤ 10000 → preserve; explicit LIMIT > 10000 → cap to 10000. All three tested in `TestEnsureLimit`. ✓

### Requirement: Error Categorization — 4 Scenarios

All four in `application/services.py::MCPQueryService.execute_cypher_query()`:
- `QueryForbiddenError` → `error_type="forbidden"` ✓
- `QueryTimeoutError` → `error_type="timeout"` ✓
- `QueryExecutionError` → `error_type="execution_error"` ✓
- `Exception` (catch-all) → `error_type="unknown_error"` ✓

Subclass ordering correct: `QueryForbiddenError` and `QueryTimeoutError` caught before `QueryExecutionError` (both are subclasses). ✓

**Decision: No new tasks for `specs/query/query-execution.spec.md`.**

---

## Verification: `specs/ui/experience.spec.md`

### Requirement: Backend API Alignment — 2 Scenarios ✅

Verified via `tests/api-alignment.test.ts`: workspace-scoped KG creation uses `/management/workspaces/${workspaceId}/knowledge-graphs`; state reloads on success without manual refresh. Parent context (workspace ID) included in scoped API calls. ✓

### Requirement: Navigation Structure — 3 Scenarios ✅

`layouts/default.vue`: Sidebar presents exactly the four groups (Explore, Data, Connect, Settings) with all spec-listed items. Default landing, new-user prompt implemented. Tested in `tests/navigation-structure.test.ts`, `tests/new-user-landing.test.ts`. ✓

### Requirement: Tenant and Workspace Context — 2 Scenarios ✅

Multi-tenant selector in sidebar (`useTenant.ts`). Workspace guidance (`components/workspaces/WorkspaceGuidance.vue`). Tested in `tests/tenant-switch.test.ts`, `tests/workspace-guidance.test.ts`. ✓

### Requirement: Knowledge Graph Creation — 1 Scenario ✅

Workspace-scoped KG creation dialog in `pages/knowledge-graphs/index.vue`. Post-create prompt to add data source. Tested in `tests/knowledge-graphs.test.ts`. ✓

### Requirement: Data Source Connection — 3 Scenarios ✅

Adapter-type-first wizard in `pages/data-sources/index.vue`. GitHub URL → name inference. Credential input with password toggle. Tested in `tests/data-source-connection-wizard.test.ts`. ✓

### Requirement: Ontology Design — 5 Scenarios ⚠️ BLOCKED

UI-side utilities implemented (`utils/ontologyWizard.ts`, tested in `tests/ontology-design.test.ts`). **Backend API blocked:** AI agent lightweight scan, ontology proposal, and approval flow require the Extraction context (AIHCM-174 spike, not yet implemented). **Per guidelines, no tasks created until spike completes.**

### Requirement: Sync Monitoring — 4 Scenarios ✅

All four scenarios (active sync progress, sync history, sync logs, manual trigger) implemented in `pages/data-sources/index.vue`. Tested in `tests/sync-monitoring-extended.test.ts`, `tests/sync-phase-indicator.test.ts`, `tests/sync-logs.test.ts`. ✓

### Requirement: Get Started Querying (MCP Connection) — 3 Scenarios ✅

`pages/integrate/mcp.vue`: inline API key creation, copy-paste config snippet, secret shown once via `composables/useTransientSecret.ts`. Tested in `tests/mcp-integration.test.ts`. ✓

### Requirement: Query Console — 4 Scenarios ✅

`pages/query/index.vue`: CodeMirror with Cypher highlighting, `ageCypherLinter`, `cypherAutocomplete` (schema-aware). Ctrl/Cmd+Enter keyboard shortcut. Results as table with execution time and row count. History panel with localStorage persistence and deduplication. KG context selector. All tested in `tests/task-139-spec-alignment.test.ts`, `tests/query.test.ts`, `tests/query-history.test.ts`, `tests/query-kg-selector.test.ts`. ✓

### Requirement: Schema Browser — 3 Scenarios ✅

`pages/graph/schema.vue`: type listing with search/filter for both node and edge types. Type detail (description, required/optional properties) fetched on expand, cached in `schemaCache`. Cross-navigation to Query Console, Graph Explorer, Ontology Editor. Tested in `tests/schema-browser.test.ts`, `tests/schema-crossnav-deeplink.test.ts`, `tests/task-139-spec-alignment.test.ts`. ✓

### Requirement: Graph Explorer — 2 Scenarios ✅

`pages/graph/explorer.vue`: node search by type/name/slug (REST + Cypher fallback). Neighbor expansion with `getNodeNeighbors`. `explorationPath` trail for drill-in. Toggle collapse. Tested in `tests/graph-explorer.test.ts`, `tests/task-139-spec-alignment.test.ts`. ✓

### Requirement: Mutations Console — 9 Scenarios ✅

`pages/graph/mutations.vue`: JSONL editor with syntax highlighting, linting, autocomplete. Live preview panel. File upload (drag-drop, picker). Large-file mode (>5MB). KG selector scoped to user's `edit` permission. Floating progress indicator (persists across navigation, minimizable). Submission failure display. Template insertion. Deep-link (?view=editor, ?template=...). Tested in `tests/mutations-console.test.ts`, `tests/mutations-submission.test.ts`, `tests/mutations-indicator-persistence.test.ts`, `tests/mutations-kg-selector.test.ts`. ✓

### Requirement: API Key Management — 3 Scenarios ✅

`pages/api-keys/index.vue`: create (secret shown once), list (status, dates), revoke. Tested in `tests/api-keys.test.ts`. ✓

### Requirement: Workspace Management — 2 Scenarios ✅

`pages/workspaces/index.vue`: create workspace, member management (add/remove/role change). Tested in `tests/workspace-management.test.ts`. ✓

### Requirement: Design Language — 5 Scenarios ✅

shadcn/vue + Reka UI + Tailwind CSS + OKLCH palette. CVA variants. Lucide Vue Next. Border radius, elevation, typography tokens. Tested in `tests/design-language.test.ts`, `tests/design-language-extended.test.ts`, `tests/design-system.test.ts`. ✓

### Requirement: Interaction Principles — 6 Scenarios ✅

Toast notifications, inline/side-panel editing, copy-to-clipboard with toast, keyboard shortcuts (Ctrl/Cmd+Enter, /), focus rings. Tested in `tests/interaction-principles.test.ts`, `tests/focus-ring.test.ts`, `tests/keyboard-shortcuts.test.ts`. ✓

### Requirement: Responsive Design — 2 Scenarios ✅

Collapsible sidebar (desktop), sheet overlay (mobile/tablet). Tested in `tests/responsive-design.test.ts`. ✓

### Requirement: Dark Mode — 1 Scenario ✅

`composables/useColorMode.ts` with localStorage persistence. Toggle in header. Tested in `tests/color-mode.test.ts`. ✓

**Decision: No new tasks for `specs/ui/experience.spec.md`. Ontology Design deferred pending AIHCM-174.**

---

## Conclusion

All three specs are fully implemented and tested at current blob SHAs. No implementation gaps were found in non-blocked requirements. The `.hyperloop/state/tasks/` directory remains empty (prior state was deleted in commit `7770840ef`); no task files are created because there are no unimplemented requirements to schedule.

The sole blocked item (Ontology Design) is excluded per project guidelines until the AIHCM-174 Extraction context spike produces a backend API.
