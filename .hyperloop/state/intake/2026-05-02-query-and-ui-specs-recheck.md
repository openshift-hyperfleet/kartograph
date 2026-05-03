# Intake: Query and UI Spec Recheck — 2026-05-02

## Specs Processed

- `specs/query/mcp-server.spec.md` (SHA: 2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e)
- `specs/query/query-execution.spec.md` (SHA: dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2)
- `specs/ui/experience.spec.md` (SHA: e77913c2cc6d8b719291e2dbb6870519a94d50da)

## Finding: All Requirements Covered — No New Tasks Created

A line-by-line review of all three specs against the codebase and existing tasks found
**complete coverage**. No new task files are needed.

---

## `specs/query/mcp-server.spec.md`

| Requirement | Scenarios | Status |
|---|---|---|
| Graph Query Tool — `query_graph` | 8 | ✅ Implemented (`query/presentation/mcp.py`). Specific gaps: task-086 (truncation fix) and task-011 (KG filter + enclave — code exists but task stale) |
| Documentation Fetch Tool | 5 | ✅ Fully implemented (`query/infrastructure/git_repository.py`) |
| Knowledge Graphs Resource (`knowledge_graphs://accessible`) | 2 | ❌ Not implemented — **task-085** covers |
| Agent Instructions Resource | 2 | ✅ Fully implemented (fail-fast at startup, cached content) |
| MCP Authentication | 4 | ✅ Fully implemented (API key + Bearer, 401 no-creds, 503 unavailable) |
| Apache AGE Single-Column Return | 4 | ✅ Fully implemented (`_row_to_dict` in query_repository) |

### Stale task note

**task-011** (`not-started`) was created before `_filter_by_knowledge_graph()` and
`MCPQuerySecureEnclave` were implemented. Both features exist in production code. The
spec-alignment-reviewer should close task-011. Unit tests for these two functions are
missing — this is a TDD debt item for the spec-alignment-reviewer to surface.

---

## `specs/query/query-execution.spec.md`

| Requirement | Scenarios | Status |
|---|---|---|
| Per-Tenant Graph Routing | 2 | ❌ Not implemented — **task-084** covers |
| Read-Only Enforcement | 2 | ✅ Fully implemented (DB read-only + keyword blacklist) |
| Timeout Enforcement | 2 | ✅ Fully implemented (`statement_timeout`, `QueryTimeoutError`) |
| Result Limiting | 3 | ✅ Implemented; truncation accuracy fix in task-086 |
| Error Categorization | 4 | ✅ All four error types implemented and tested |

---

## `specs/ui/experience.spec.md`

All 18 requirements and 40+ scenarios are covered by existing tasks. Key coverage map:

| Requirement | Tasks |
|---|---|
| Backend API Alignment | task-050, task-068, task-072, task-075 |
| Navigation Structure | task-014 ✅complete, task-059, task-046 |
| Tenant/Workspace Context | task-058, task-062 |
| Knowledge Graph Creation | task-040, task-015, task-071 |
| Data Source Connection | task-015, task-068, task-069 |
| Ontology Design | task-043, task-063, task-082 |
| Sync Monitoring | task-042, task-044, task-064, task-073, task-083 |
| Get Started Querying (MCP) | task-051 |
| Query Console | task-016 ✅complete, task-045 |
| Schema Browser | task-016 ✅complete, task-048 |
| Graph Explorer | task-016 ✅complete |
| Mutations Console | task-059, task-060, task-061, task-065, task-074, task-076 |
| API Key Management | task-014 ✅complete, task-051 |
| Workspace Management | task-014 ✅complete |
| Design Language | task-052, task-066, task-067 |
| Interaction Principles | task-049, task-053, task-054, task-057, task-070, task-079 |
| Responsive Design | task-055 |
| Dark Mode | task-056 |

### Additional stale task notes

- **task-077** (`not-started`): workspace_id filter for KG listing is already implemented
  in `GET /management/knowledge-graphs` (query param `workspace_id` present in routes.py).
- **task-078** (`not-started`): flat data-sources list with latest_sync_run is already
  implemented (`GET /management/data-sources` with `DataSourceWithSyncResponse`).

Both tasks should be reviewed by the spec-alignment-reviewer for closure.
