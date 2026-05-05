# Intake Pass 11: mcp-server, query-execution, ui/experience

**Date:** 2026-05-05
**Processed by:** PM intake agent (eleventh pass)
**Trigger:** Specs flagged as "(modified)" in orchestrator — same blob SHAs as all prior passes.

## Specs Processed

| Spec | Blob SHA | Decision |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | No new tasks |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | No new tasks |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | No new tasks |

Blob SHAs are **identical to all prior passes (passes 1–10)**. The specs have not changed.

---

## Key Finding vs. Pass 10

Pass 10 confirmed no gaps beyond task-152 and confirmed tasks 147–151 were all stale (work
complete). This pass (11) reaches the same conclusion after a fresh line-by-line review.

**Changes since pass 10:**
- `fadf7d15e test(query): add integration tests for per-tenant graph routing` — task-150 merged
- `60dd790bd fix(ui): migrate query console KG selector from __all__ to empty-string sentinel` — task-147 merged
- `b52db5c63 test(ui): add task-149 spec-alignment tests` — task-149 UI alignment merged
- `f8d5fd80a test(query): align unknown_error test name` — minor test alignment

**Still outstanding:**
- **task-152** — Bearer token MCP authentication integration test; `test_mcp_bearer_auth.py`
  does not exist in `src/api/tests/integration/query/`

---

## Verification Results

### specs/query/mcp-server.spec.md

All six requirements fully implemented and tested. Full line-by-line verification:

| Requirement | Scenarios | Coverage |
|---|---|---|
| Graph Query Tool | 8 | Unit + integration (`test_query_mcp.py`, `test_secure_enclave_mcp.py`, `test_query_mcp_http.py`) |
| Documentation Fetch Tool | 5 | Unit (`test_git_repository.py`, `test_mcp_tools.py`) |
| Knowledge Graphs Resource | 2 | Unit + integration (`tests/integration/query/test_kg_resource.py`) |
| Agent Instructions Resource | 2 | Unit (`test_mcp_agent_instructions.py`); fail-fast at startup |
| MCP Authentication | 4 | Unit (`test_mcp_auth_middleware.py`), integration (`test_mcp_auth_http.py`) |
| Apache AGE Single-Column Return | 4 | Unit (`test_query_repository.py::TestRowToDict`) |

**Remaining gap:** Bearer token MCP authentication — **unit coverage only** (task-152).
No integration test exercises the full Bearer → JWT validate → SpiceDB chain.

### specs/query/query-execution.spec.md

All five requirements fully implemented, unit-tested, and integration-tested.

| Requirement | Scenarios | Evidence |
|---|---|---|
| Per-Tenant Graph Routing | 2 | `TenantAwareQueryGraphRepository`; `test_tenant_routing_integration.py` (task-150, merged) |
| Read-Only Enforcement | 2 | `SET TRANSACTION READ ONLY` + keyword blacklist; `test_query_repository.py` |
| Timeout Enforcement | 2 | `SET LOCAL statement_timeout`; `QueryTimeoutError`; integration tests |
| Result Limiting | 3 | `_ensure_limit()`; `test_query_repository.py::TestEnsureLimit` |
| Error Categorization | 4 | `MCPQueryService` exception mapping; `test_mcp_query_service.py` |

**No gaps.**

### specs/ui/experience.spec.md

All 18 requirements implemented.

| Requirement | Status |
|---|---|
| Backend API Alignment | ✅ `api-alignment.test.ts` |
| Navigation Structure | ✅ `layouts/default.vue`; `navigation-structure.test.ts` |
| Tenant and Workspace Context | ✅ `tenant-switch.test.ts`, `workspace-guidance.test.ts` |
| Knowledge Graph Creation | ✅ `knowledge-graphs.test.ts` |
| Data Source Connection | ✅ `data-source-connection-wizard.test.ts` |
| Ontology Design | ⚠️ BLOCKED — UI utilities present; backend (AIHCM-174 Extraction spike) not ready |
| Sync Monitoring | ✅ `sync-monitoring-extended.test.ts`, `sync-logs.test.ts`, `sync-phase-indicator.test.ts` |
| Get Started Querying (MCP) | ✅ `mcp-integration.test.ts`, `transient-secret.test.ts` |
| Query Console | ✅ `query.test.ts`, `query-kg-selector.test.ts`, `query-history.test.ts` |
| Schema Browser | ✅ `schema-browser.test.ts`, `schema-crossnav-deeplink.test.ts` |
| Graph Explorer | ✅ `graph-explorer.test.ts` |
| Mutations Console | ✅ `mutations-console.test.ts`, `mutations-submission.test.ts`, `mutations-indicator-persistence.test.ts`, `mutations-kg-selector.test.ts`, `mutations-workspace-selector.test.ts` |
| API Key Management | ✅ `api-keys.test.ts` |
| Workspace Management | ✅ `workspace-management.test.ts` |
| Design Language | ✅ `design-language.test.ts`, `design-language-extended.test.ts`, `design-system.test.ts`, `focus-ring.test.ts` |
| Interaction Principles | ✅ `interaction-principles.test.ts`, `keyboard-shortcuts.test.ts`, `copy-composable.test.ts` |
| Responsive Design | ✅ `responsive-design.test.ts` |
| Dark Mode | ✅ `color-mode.test.ts` |

KG selector sentinel: `ref('')` with `selectedKgId.value || undefined` gate — correct (tasks 147/148 merged).

**No gaps.**

---

## Summary

**New tasks created this pass: 0**

Only outstanding work across all three specs: **task-152** (Bearer token MCP auth
integration test). No new implementation gaps have emerged. All three specs are fully
covered by existing implementation and test suites.
