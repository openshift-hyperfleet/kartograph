# Intake Verification — Query & UI Experience Specs (Pass 4)

**Date:** 2026-05-03
**Specs processed:**
- `specs/query/mcp-server.spec.md` @ `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`
- `specs/query/query-execution.spec.md` @ `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2`
- `specs/ui/experience.spec.md` @ `e77913c2cc6d8b719291e2dbb6870519a94d50da`

## Summary

No new tasks created. All three specs are fully covered by existing implementation
and/or existing not-started tasks. Spec blob SHAs are unchanged since Pass 3.

## Changes Since Pass 3

Since commit `55c1b4bb5` (Pass 3), the following work landed:

| Commit | Task | What was delivered |
|--------|------|--------------------|
| `081f0d930` | task-110 | Integration tests for `knowledge-graphs://accessible` MCP resource (SpiceDB + Management DB) |
| `ed6c92d90` | task-109 | Integration tests for per-tenant graph routing (two tenant AGE graphs, isolation verified) |

## Backend Query Specs — Fully Implemented and Tested

### `specs/query/mcp-server.spec.md` — All 6 requirements, 18 scenarios COVERED

| Requirement | Key Code Location | Test Coverage |
|---|---|---|
| Graph Query Tool | `query/presentation/mcp.py::query_graph` | `tests/unit/query/test_mcp_query_tool.py`, `tests/integration/test_query_mcp.py` |
| Documentation Fetch Tool | `query/infrastructure/git_repository.py` | `tests/unit/query/infrastructure/test_git_repository.py` |
| Knowledge Graphs Resource | `query/application/kg_service.py`, `presentation/mcp.py` | `tests/unit/query/test_mcp_knowledge_graphs_resource.py`, `tests/integration/query/test_kg_resource.py` |
| Agent Instructions Resource | `query/infrastructure/prompt_repository.py` | `tests/unit/query/infrastructure/test_prompt_repository.py` |
| MCP Authentication | `shared_kernel/middleware/mcp_api_key_auth.py` | `tests/unit/shared_kernel/middleware/test_mcp_auth_middleware.py` |
| Apache AGE Single-Column Return | `query/infrastructure/query_repository.py::_row_to_dict` | `tests/unit/query/test_query_repository.py` |

**task-110 now complete:** `tests/integration/query/test_kg_resource.py` added —
four integration tests cover both Knowledge Graphs Resource scenarios against real
SpiceDB and Management DB.

### `specs/query/query-execution.spec.md` — All 5 requirements, 11 scenarios COVERED

| Requirement | Key Code Location | Test Coverage |
|---|---|---|
| Per-Tenant Graph Routing | `query/infrastructure/tenant_routing.py` | `tests/unit/query/test_tenant_routing.py`, `tests/integration/query/test_tenant_routing.py` |
| Read-Only Enforcement (primary) | `SET TRANSACTION READ ONLY` in `query_repository.py` | `tests/unit/query/test_query_repository.py::test_sets_transaction_read_only` |
| Read-Only Enforcement (secondary) | `_validate_read_only` — keyword blacklist | `tests/unit/query/test_query_repository.py::TestValidateReadOnly` |
| Timeout Enforcement | `SET LOCAL statement_timeout = {ms}` | `tests/unit/query/test_query_repository.py::test_sets_statement_timeout` |
| Result Limiting | `_ensure_limit` — default 1000, cap 10000 | `tests/unit/query/test_query_repository.py::TestEnsureLimit` |
| Error Categorization | `MCPQueryService` catch clauses → typed `QueryError` | `tests/unit/query/test_mcp_query_service.py` |

**task-109 now complete:** `tests/integration/query/test_tenant_routing.py` added —
two integration tests:
1. `test_query_executes_in_tenant_graph`: two provisioned AGE graphs, data written to tenant A,
   verified absent in tenant B (cross-tenant isolation).
2. `test_tenant_graph_not_found_raises_before_db`: ghost tenant ID → `QueryExecutionError`
   raised before any Cypher delegation.

## UI Experience Spec — No Change Since Pass 3

Spec SHA unchanged (`e77913c2cc6d8b719291e2dbb6870519a94d50da`). No new scenarios added.
All requirements remain covered by existing not-started tasks.

## Remaining Open Tasks (updated after task-109 and task-110 completions)

| Task | Spec Requirement |
|---|---|
| task-042 | Sync Monitoring — Active sync progress (phase labels) |
| task-043 | Ontology Design — intent, AI proposal, review, edit, re-extract warning (partially blocked on Extraction) |
| task-044 | Sync Monitoring — Sync logs viewer |
| task-059 | Navigation Structure — Mutations Console in Explore group |
| task-060 | Mutations Console — empty state, editor, preview, file upload, templates |
| task-061 | Mutations Console — floating submission progress indicator |
| task-064 | Sync Monitoring — Manual sync trigger |
| task-087 | Mutations Console — Knowledge graph selector (blocks submission) |
| task-100 | Per-Tenant Graph Routing — cross-tenant isolation integration test |
| task-102 | Navigation Structure — sidebar sections (Explore/Data/Connect/Settings) |
| task-103 | New-user landing + workspace guidance |
| task-104 | Schema Browser — cross-navigation to query console / explorer / ontology |
| task-106 | Interaction Principles — copy toast, focus rings, shortcut discovery |

## Conclusion

No new tasks required. The backlog is current. All unblocked requirements are captured
in existing tasks. Both backend query specs are now fully implemented AND fully
integration-tested (task-109 and task-110 completed since Pass 3).
