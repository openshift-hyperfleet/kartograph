# Intake Verification — Query & UI Experience Specs (Pass 2)

**Date:** 2026-05-03
**Specs processed:**
- `specs/query/mcp-server.spec.md` @ `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`
- `specs/query/query-execution.spec.md` @ `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`
- `specs/ui/experience.spec.md` @ `e77913c2cc6d8b719251e2dbb6870519a94d50da`

## Summary

No new tasks created. All three specs are fully covered by existing implementation
and/or existing tasks (task-102 through task-108).

## Backend Query Specs — Verified Fully Implemented

Both query specs were verified line-by-line against the production code. Every
requirement and scenario is implemented and tested.

### `specs/query/mcp-server.spec.md` — All 6 requirements, 18 scenarios COVERED

| Requirement | Key Code Location | Test Coverage |
|---|---|---|
| Graph Query Tool | `presentation/mcp.py::query_graph` | `tests/unit/query/test_mcp_query_tool.py` |
| Documentation Fetch Tool | `infrastructure/git_repository.py` | `tests/unit/query/infrastructure/test_git_repository.py` |
| Knowledge Graphs Resource | `application/kg_service.py`, `presentation/mcp.py` | `tests/unit/query/test_mcp_knowledge_graphs_resource.py` |
| Agent Instructions Resource | `infrastructure/prompt_repository.py` | `tests/unit/query/infrastructure/test_prompt_repository.py` |
| MCP Authentication | `shared_kernel/middleware/mcp_api_key_auth.py` | `tests/unit/query/test_mcp_auth_wiring.py` |
| Apache AGE Single-Column Return | `infrastructure/query_repository.py::_row_to_dict` | `tests/unit/query/test_query_repository.py` |

Notable coverage details:
- Secure enclave redaction (ID-only for unauthorized nodes/edges): `application/mcp_secure_enclave.py`
- Fail-safe: SpiceDB error → deny (not expose): verified in `test_mcp_secure_enclave.py`
- `PromptRepository.__init__` validates file existence at startup (fail-fast): confirmed
- `_filter_internal_properties` strips `all_content_lower` and other internal props: confirmed
- `MCPApiKeyAuthMiddleware` returns 401 on missing creds, 503 on auth backend failure: confirmed

### `specs/query/query-execution.spec.md` — All 4 requirements, 11 scenarios COVERED

| Requirement | Key Code Location | Test Coverage |
|---|---|---|
| Per-Tenant Graph Routing | `infrastructure/tenant_routing.py` | `tests/unit/query/test_tenant_routing.py` |
| Read-Only Enforcement | `infrastructure/query_repository.py::_validate_read_only` + `SET TRANSACTION READ ONLY` | `tests/unit/query/test_query_repository.py` |
| Timeout Enforcement | `SET LOCAL statement_timeout` + PostgreSQL error detection | `tests/unit/query/test_query_repository.py` |
| Result Limiting | `infrastructure/query_repository.py::_ensure_limit` | `tests/unit/query/test_query_repository.py` |

Notable coverage details:
- Keyword blacklist (CREATE, DELETE, SET, REMOVE, MERGE, EXPLAIN, LOAD) case-insensitive: confirmed
- Redacted logging (never logs raw query text): `test_observability.py::test_cypher_query_rejected_never_logs_raw_query`
- Correlation ID on forbidden and timeout errors: confirmed in value objects and repository
- LIMIT default 1000, cap 10000: `_ensure_limit` verified
- `tenant_{tenant_id}` graph naming: `TenantAwareQueryGraphRepository` confirmed

## UI Experience Spec — Scenarios vs. Task Coverage

All scenarios in `specs/ui/experience.spec.md` are either implemented or scheduled.

### Implemented (no task needed)

The following scenarios are already implemented in `src/dev-ui/app/`:

| Scenario | Implementation |
|---|---|
| Dark mode toggle + persistent preference | `composables/useColorMode.ts` (localStorage), `layouts/default.vue` (Moon/Sun icons) |
| Query history panel | `components/query/HistoryPanel.vue` (616 lines), `pages/query/index.vue` (HISTORY_KEY, localStorage) |
| MCP page inline key creation | `pages/integrate/mcp.vue` (createDialogOpen, createForm, isCreating) |
| Secret shown once | `composables/useTransientSecret.ts` (in-memory, auto-clear after 30s) |
| MCP config snippet + copy | `pages/integrate/mcp.vue` (configSecret, mcpConfigClaudeDisplay, copy buttons) |
| Data source adapter-type-first wizard | `pages/data-sources/index.vue` (wizardStep, adapters array, selectedAdapterId) |
| GitHub name inference from URL | `pages/data-sources/index.vue` (regex match on github.com URL) |
| Credential password-type input | `pages/data-sources/index.vue` (Eye/EyeOff toggle) |
| Design language (shadcn/vue, OKLCH, Tailwind) | Established across the entire dev-ui codebase |
| Responsive design (sidebar collapse) | `layouts/default.vue` (dark: variants preserved) |

### Scheduled (tasks 102–108)

| Task | Scenarios covered |
|---|---|
| task-102 | Navigation Structure (sidebar sections), Tenant selector |
| task-103 | New user landing, Workspace guidance |
| task-104 | Schema Browser cross-navigation |
| task-105 | Mutations Console deep-link + large-file mode |
| task-106 | Copy-to-clipboard toast, focus rings, shortcut tooltips |
| task-107 | Backend API alignment (all CRUD + parent-context scoping) |
| task-108 | Query console KG context selector |

### Blocked (Extraction / Ingestion contexts not yet implemented)

| Requirement | Reason blocked |
|---|---|
| Ontology Design (5 scenarios) | Blocked on Extraction context (AIHCM-174 spike) |
| Sync Monitoring (4 scenarios) | Blocked on Ingestion context implementation |

## Conclusion

No new tasks required. The backlog is current. All unblocked UI gaps are captured
in tasks 102–108. Both backend query specs remain fully implemented and tested.
