# Intake Verification — Query & UI Experience Specs (Pass 3)

**Date:** 2026-05-03
**Specs processed:**
- `specs/query/mcp-server.spec.md` @ `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`
- `specs/query/query-execution.spec.md` @ `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`
- `specs/ui/experience.spec.md` @ `e77913c2cc6d8b719291e2dbb6870519a94d50da`

## Summary

No new tasks created. All three specs are fully covered by existing implementation
and/or existing tasks. Spec blob SHAs are unchanged since Pass 2 — the "modified"
flag signals the orchestrator re-queued them; the content has not changed.

## Changes Since Pass 2

Since commit `240be304c` (Pass 2), the following work landed:

| Commit | Task | What was delivered |
|--------|------|--------------------|
| `a68772128` | task-107 | Backend API alignment — parent-context scoping fixed for all CRUD operations |
| `116e7c8db` | task-108 | KG context selector — unit tests for Query Console |
| `7d0a8fac5` | task-105 | Mutations console deep-link + large-file mode implementation |
| `3bf8ecd37` | task-102 | Sidebar navigation — tenant-switch and nav section tests |
| `37f403fa3` | task-109/110 | Integration test tasks restored for per-tenant routing and KG resource |

## Backend Query Specs — Verified Fully Implemented

### `specs/query/mcp-server.spec.md` — All 6 requirements, 18 scenarios COVERED

| Requirement | Key Code Location | Test Coverage |
|---|---|---|
| Graph Query Tool | `query/presentation/mcp.py::query_graph` | `tests/unit/query/test_mcp_query_tool.py` |
| Documentation Fetch Tool | `query/infrastructure/git_repository.py` | `tests/unit/query/infrastructure/test_git_repository.py` |
| Knowledge Graphs Resource | `query/application/kg_service.py`, `presentation/mcp.py` | `tests/unit/query/test_mcp_knowledge_graphs_resource.py` |
| Agent Instructions Resource | `query/infrastructure/prompt_repository.py` | `tests/unit/query/infrastructure/test_prompt_repository.py` |
| MCP Authentication | `shared_kernel/middleware/mcp_api_key_auth.py` | `tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py` |
| Apache AGE Single-Column Return | `query/infrastructure/query_repository.py::_row_to_dict` | `tests/unit/query/test_query_repository.py` |

Notable scenario coverage details:
- **Secure enclave redaction**: `query/application/mcp_secure_enclave.py` — nodes redacted
  to `{id}`, edges to `{id, start_id, end_id}`; topology preserved; SpiceDB error → deny
  (fail-safe). Tested in `test_mcp_secure_enclave.py`.
- **Write operation rejected**: keyword blacklist + `SET TRANSACTION READ ONLY` (dual defense).
  403 response via `QueryForbiddenError`. Correlation ID always present. Confirmed in unit tests.
- **Query timeout**: `SET LOCAL statement_timeout` in each transaction; PostgreSQL
  `canceling statement` error detected and re-raised as `QueryTimeoutError`. Correlation ID present.
- **Result limiting**: default 1000, max 10000; `limit + 1` fetch for truncation detection.
  `truncated` flag set only when row `(limit+1)` exists.
- **Internal property filtering**: `_filter_internal_properties` strips `all_content_lower`
  recursively from all dicts/lists before returning to agents. Confirmed.
- **401 on no credentials, 503 on auth backend failure**: `MCPApiKeyAuthMiddleware` returns
  both. Tested in `test_mcp_auth_middleware.py::TestBearerServiceUnavailableScenarios`.
- **Agent instructions fail-fast**: `get_prompt_repository()` called at module import time;
  `FileNotFoundError` propagates to crash the process if the prompt file is absent.

Integration gap remaining: **task-110** — `knowledge-graphs://accessible` resource needs
an end-to-end integration test against real SpiceDB + Management DB.

### `specs/query/query-execution.spec.md` — All 5 requirements, 11 scenarios COVERED

| Requirement | Key Code Location | Test Coverage |
|---|---|---|
| Per-Tenant Graph Routing | `query/infrastructure/tenant_routing.py` | `tests/unit/query/test_tenant_routing.py` + `test_dependencies.py` |
| Read-Only Enforcement (primary) | `SET TRANSACTION READ ONLY` in `query_repository.py::execute_cypher` | `tests/unit/query/test_query_repository.py::test_sets_transaction_read_only` |
| Read-Only Enforcement (secondary) | `_validate_read_only` — keyword blacklist | `tests/unit/query/test_query_repository.py::TestValidateReadOnly` |
| Timeout Enforcement | `SET LOCAL statement_timeout = {ms}` | `tests/unit/query/test_query_repository.py::test_sets_statement_timeout` |
| Result Limiting | `_ensure_limit` — default 1000, cap 10000 | `tests/unit/query/test_query_repository.py::TestEnsureLimit` |
| Error Categorization | `MCPQueryService` catch clauses → typed `QueryError` | `tests/unit/query/test_mcp_query_service.py` |

Notable scenario coverage details:
- **Database-level read-only set BEFORE Cypher**: `test_database_read_only_applied_before_query`
  verifies ordering by tracking `execute_sql` vs `execute_cypher` call sequence.
- **Redacted log entry + correlation ID**: `_validate_read_only` logs the query length only
  (never raw text); always attaches a UUID correlation ID. Both forbidden and timeout errors
  carry the ID in the response.
- **Tenant graph not found rejects before DB**: `_validate_graph_exists` calls `graph_exists()`
  before any `transaction()` — confirmed by `test_rejects_query_if_tenant_graph_not_found`
  asserting `transaction.assert_not_called()`.
- **Error type mapping**: forbidden → "forbidden", timeout → "timeout",
  `QueryExecutionError` → "execution_error", catch-all → "unknown_error". All four paths
  exercised in `test_mcp_query_service.py`.

Integration gaps remaining:
- **task-109**: Per-Tenant Graph Routing needs integration tests against real PostgreSQL+AGE
  (two tenant graphs, data isolation verification).
- **task-100**: Cross-tenant isolation specifically — `tenant_a` cannot read `tenant_b` data.

## UI Experience Spec — Verified (Pass 3)

### Newly confirmed as implemented since Pass 2

| Requirement / Scenario | Implementation | Task |
|---|---|---|
| Backend API Alignment — Resource operations succeed | All CRUD ops fixed for correct endpoint + body | task-107 (impl in `a68772128`) |
| Backend API Alignment — Parent context preserved | workspace_id, knowledge_graph_id correctly scoped | task-107 (impl in `a68772128`) |
| Query Console — Knowledge graph context selector | `pages/query/index.vue::selectedKgId` + KG fetch + `knowledge_graph_id` passed to query | task-108 (tests in `116e7c8db`) |
| Mutations Console — Deep-link + large-file mode | `?view=editor`, `?template=` URL params; 5 MB large-file summary | task-105 (impl in `7d0a8fac5`) |

### Backend sync endpoints confirmed present (Sync Monitoring NOT blocked)

The previous Pass 2 note incorrectly classified Sync Monitoring as "blocked on Ingestion
context implementation." In fact, the management context already provides:
- `POST /management/data-sources/{ds_id}/sync` — trigger sync
- `GET /management/data-sources/{ds_id}/sync-runs` — list sync runs (history)
- `GET /management/data-sources/{ds_id}/sync-runs/{run_id}/logs` — fetch logs

These routes are implemented in `management/presentation/data_sources/routes.py` and
integration-tested in `tests/integration/management/test_data_source_sync_run_repository.py`.

The UI sync monitoring features (SyncPhaseIndicator, log viewer, manual trigger, history)
are implemented in `pages/data-sources/index.vue` and tested in
`tests/sync-monitoring-extended.test.ts`, `tests/sync-logs.test.ts`,
`tests/sync-phase-indicator.test.ts`.

Existing tasks:
- **task-042**: Fix sync-run phase status types and display labels in UI
- **task-044**: Implement UI — sync log viewer

### Remaining open tasks (not-started) mapped to spec requirements

| Task | Spec Requirement | Status |
|---|---|---|
| task-042 | Sync Monitoring — Active sync progress (phase labels) | not-started |
| task-043 | Ontology Design — intent, AI proposal, review, edit, re-extract warning | not-started |
| task-044 | Sync Monitoring — Sync logs viewer | not-started |
| task-059 | Navigation Structure — Mutations Console in Explore group | not-started |
| task-060 | Mutations Console — empty state, editor, preview, file upload, templates | not-started |
| task-061 | Mutations Console — floating submission progress indicator | not-started |
| task-064 | Sync Monitoring — Manual sync trigger | not-started |
| task-087 | Mutations Console — Knowledge graph selector (blocks submission) | not-started |
| task-100 | Per-Tenant Graph Routing — cross-tenant isolation integration test | not-started |
| task-102 | Navigation Structure — sidebar sections (Explore/Data/Connect/Settings) | not-started |
| task-103 | New-user landing + workspace guidance | not-started |
| task-104 | Schema Browser — cross-navigation to query console / explorer / ontology | not-started |
| task-106 | Interaction Principles — copy toast, focus rings, shortcut discovery | not-started |
| task-109 | Per-Tenant Graph Routing — integration tests (tenant-scoped AGE graphs) | not-started |
| task-110 | Knowledge Graphs Resource — integration tests (SpiceDB + Management DB) | not-started |

Note: task-105 (deep-link + large-file), task-107 (backend API alignment), and task-108
(query console KG selector) appear to have implementation delivered but the orchestrator
has not yet marked them complete.

### Ontology Design — still requires Extraction context

The **Agent-proposed ontology** scenario (lightweight data source scan + AI agent proposes
node/edge types) requires the Extraction context AI agent, which is blocked on AIHCM-174.
The current UI implementation uses a static simulation (`GITHUB_PROPOSAL_NODES/EDGES`).
task-043 exists but cannot deliver a real AI-driven proposal until Extraction is unblocked.
Other Ontology Design scenarios (review, editing, re-extract warning) are UI-only and
could be completed independently; they are covered by task-043.

## Conclusion

No new tasks required. The backlog is current. All unblocked requirements are captured
in existing tasks. Both backend query specs remain fully implemented and tested.
