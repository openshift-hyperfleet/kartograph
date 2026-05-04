# Intake: mcp-server, query-execution, ui/experience — no new tasks

**Date:** 2026-05-04
**Specs processed:** specs/query/mcp-server.spec.md, specs/query/query-execution.spec.md, specs/ui/experience.spec.md

## Verification Summary

### specs/query/mcp-server.spec.md
**Blob SHA:** `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`

All requirements are fully implemented and tested:

- **Graph Query Tool** — `query_graph` in `src/api/query/presentation/mcp.py`
  - Successful query, KG filter, secure enclave redaction, write rejection, timeout, result
    limiting, truncation flag, internal property filtering: all implemented and covered by
    unit tests (`test_mcp_query_tool.py`, `test_mcp_query_tool_wiring.py`,
    `test_mcp_query_service.py`, `test_mcp_secure_enclave.py`) and integration tests.
- **Documentation Fetch Tool** — `fetch_documentation_source` in `mcp.py`
  - GitHub, GitLab, private repo PAT, self-hosted instances, invalid URL error: implemented
    in `src/api/query/infrastructure/git_repository.py`, tested in
    `tests/unit/query/infrastructure/test_git_repository.py`.
- **Knowledge Graphs Resource** — `knowledge-graphs://accessible`
  - Accessible list and empty list scenarios: implemented, tested in
    `tests/unit/query/test_mcp_knowledge_graphs_resource.py`.
- **Agent Instructions Resource** — `instructions://agent`
  - Read instructions and fail-fast at startup: implemented via module-level
    `_prompt_repository = get_prompt_repository()`.
- **MCP Authentication** — `MCPApiKeyAuthMiddleware`
  - API key, Bearer token, 401 no credentials, 503 service unavailable: all implemented
    and tested in `tests/unit/query/test_mcp_auth_wiring.py`.
- **Apache AGE Single-Column Return** — `_row_to_dict` in `query_repository.py`
  - Node, edge, map, scalar return formats: implemented and tested in
    `tests/unit/query/test_query_repository.py`.

**Integration test tasks** (task-140, task-141, task-142) were previously queued. Their
branches (`hyperloop/task-140`, `hyperloop/task-141`, `hyperloop/task-142`) still exist.
The `.hyperloop/state/` was deleted by commit `7770840ef` and needs to be repopulated by
the orchestrator from branch state.

**Decision: No new tasks.**

---

### specs/query/query-execution.spec.md
**Blob SHA:** `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`

All requirements are fully implemented:

- **Per-Tenant Graph Routing** — `_validate_graph_exists()` in `QueryGraphRepository`
  calls `client.graph_exists()` before any Cypher; rejects with `QueryExecutionError` if
  absent. Tested in `TestTenantGraphRouting` in `test_query_repository.py`.
- **Read-Only Enforcement** — primary: `SET TRANSACTION READ ONLY` in every transaction;
  secondary: `_validate_read_only()` keyword blacklist (CREATE, DELETE, SET, REMOVE,
  MERGE, EXPLAIN, LOAD). Both tested with ordering verification in
  `TestExecuteCypher`.
- **Timeout Enforcement** — `SET LOCAL statement_timeout = {ms}` per transaction;
  timeout exception mapped to `QueryTimeoutError` with correlation ID. Tested.
- **Result Limiting** — `_ensure_limit()` appends LIMIT when absent, caps at 10000.
  Tested in `TestEnsureLimit`.
- **Error Categorization** — four types (forbidden, timeout, execution_error,
  unknown_error) mapped by `MCPQueryService.execute_cypher_query()`. Verified that
  subclass ordering is correct (QueryForbiddenError / QueryTimeoutError caught before
  base QueryExecutionError). Tested in `TestErrorCategorization`.

**Decision: No new tasks.**

---

### specs/ui/experience.spec.md
**Blob SHA:** `e77913c2cc6d8b719291e2dbb6870519a94d50da`

The UI is implemented in `src/dev-ui`. Analysis by requirement:

- **Backend API Alignment** — Workspace-scoped KG creation fixed (commit `e01f0e4df`).
  Direct-array response handling tested.
- **Navigation Structure** — `src/dev-ui/app/layouts/default.vue` has exactly the four
  groups (Explore, Data, Connect, Settings) with all items from the spec. Tenant selector
  implemented. Mobile sheet overlay and collapsible desktop sidebar present.
- **Tenant and Workspace Context** — Multi-tenant selector in sidebar. Workspace
  guidance toast on first tenant entry with zero workspaces.
- **Knowledge Graph Creation** — Workspace selector dialog implemented. Post-create
  prompt to add data source.
- **Data Source Connection** — Adapter type selection, connection configuration, and
  credential handling are implemented.
- **Ontology Design** — BLOCKED: Requires Extraction context (AI agent, lightweight scan,
  ontology proposal backend). Per guidelines, no tasks until AIHCM-174 spike completes.
- **Sync Monitoring** — Implemented in `src/dev-ui/app/pages/data-sources/` (commit
  `0be217eff`). Status, history, logs, manual trigger present.
- **Get Started Querying (MCP)** — `src/dev-ui/app/pages/integrate/mcp.vue` implements
  inline API key creation, copy-paste snippet, secret shown once.
- **Query Console** — `/query` page with CodeMirror editor, syntax highlighting,
  autocomplete, query history, KG context selector.
- **Schema Browser** — `src/dev-ui/app/pages/graph/schema.vue` with type listing,
  detail panel, cross-navigation.
- **Graph Explorer** — `src/dev-ui/app/pages/graph/explorer.vue` with node search and
  neighbor traversal.
- **Mutations Console** — `src/dev-ui/app/pages/graph/mutations.vue` with JSONL editor,
  live preview, file upload, KG selection, floating submission indicator, deep-link
  support (commit `e403c7f78`).
- **API Key Management** — `src/dev-ui/app/pages/api-keys/` with create, list, revoke.
- **Workspace Management** — `src/dev-ui/app/pages/workspaces/` with create and member
  management.
- **Design Language** — shadcn/vue + Reka UI, Tailwind CSS with OKLCH palette, Lucide
  Vue Next icons, CVA variants.
- **Interaction Principles** — Toast notifications, copy-to-clipboard, keyboard
  shortcuts (Ctrl/Cmd+Enter, /), focus rings, inline editing.
- **Responsive Design** — Collapsible sidebar (md breakpoint), sheet overlay on mobile.
- **Dark Mode** — Toggle in header, preference persistence.

**Decision: No new tasks.** Ontology Design deferred pending AIHCM-174.
