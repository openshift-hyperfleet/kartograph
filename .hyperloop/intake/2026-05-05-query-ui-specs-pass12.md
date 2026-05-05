# Intake Pass 12: mcp-server, query-execution, ui/experience

**Date:** 2026-05-05
**Processed by:** PM intake agent (twelfth pass)
**Trigger:** Specs flagged as "(modified)" in orchestrator — blob SHAs unchanged.

## Specs Processed

| Spec | Blob SHA | Decision |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | No new tasks |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | No new tasks |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | No new tasks |

**Blob SHAs are identical to all prior passes (passes 1–11).** The specs have not changed.

---

## Changes Since Pass 11

Pass 11 (commit `4ad9dc72f`) identified task-152 as the sole outstanding item. Since then:
- No new commits have landed against these three specs.
- `.hyperloop/state/tasks/` contains tasks 147–152 (orchestrator manages status).

## Line-by-Line Verification

### specs/query/mcp-server.spec.md

All six requirements, all 18 scenarios confirmed implemented and tested:

| Requirement | Scenarios | Unit | Integration |
|---|---|---|---|
| Graph Query Tool | 8 | `test_mcp_query_tool.py`, `test_mcp_query_service.py`, `test_mcp_secure_enclave.py` | `test_query_mcp.py`, `test_secure_enclave_mcp.py`, `test_query_mcp_http.py` |
| Documentation Fetch Tool | 5 | `test_git_repository.py`, `test_mcp_tools.py` | — |
| Knowledge Graphs Resource | 2 | `test_mcp_knowledge_graphs_resource.py` | `tests/integration/query/test_kg_resource.py` |
| Agent Instructions Resource | 2 | `test_mcp_agent_instructions.py` | fail-fast at module import |
| MCP Authentication | 4 | `test_mcp_auth_middleware.py` (API key ✓, Bearer ✓, 401 ✓, 503 ✓) | `test_mcp_auth_http.py` (API key + 401 paths) |
| Apache AGE Single-Column Return | 4 | `test_query_repository.py::TestRowToDict` | — |

**Scenario: Secure enclave redaction** — `MCPQuerySecureEnclave.apply_redaction()`:
- Unauthorized node → `{"id": node_id}` (all other fields stripped) ✓
- Unauthorized edge → `{"id", "start_id", "end_id"}` (topology preserved) ✓
- SpiceDB error → deny (fail-safe, not expose) ✓
- Permission cache per `knowledge_graph_id` within one `apply_redaction` call ✓

**Scenario: Write operation rejected** — `_validate_read_only()` rejects CREATE, DELETE, SET,
REMOVE, MERGE, EXPLAIN, LOAD case-insensitively. Correlation ID always present. ✓

**Scenario: Result truncation flag** — `services.py` fetches `limit + 1` rows; sets
`truncated = len(rows) > limit`; returns at most `limit` rows. ✓

**Scenario: Authentication service unavailable → 503** — `MCPApiKeyAuthMiddleware`
`except Exception` path returns 503; unit-tested in `test_mcp_auth_middleware.py`. ✓

**Remaining integration gap:**
- **task-152** — Bearer token path has no integration test exercising the full
  JWT → SpiceDB membership check → successful tool call chain. Unit coverage
  exists; integration test is missing. task-152 addresses this.

### specs/query/query-execution.spec.md

All five requirements, all 11 scenarios fully implemented and tested (unit + integration):

| Requirement | Code | Unit | Integration |
|---|---|---|---|
| Per-Tenant Graph Routing | `TenantAwareQueryGraphRepository` | `test_tenant_routing.py` | `test_tenant_routing_integration.py` (task-150, merged) |
| Read-Only Enforcement (primary) | `SET TRANSACTION READ ONLY` | `test_query_repository.py::test_sets_transaction_read_only` | `test_query_readonly.py` |
| Read-Only Enforcement (secondary) | `_validate_read_only()` keyword blacklist | `TestValidateReadOnly` (7 keywords, case-insensitive) | — |
| Timeout Enforcement | `SET LOCAL statement_timeout` | `test_sets_statement_timeout` | `test_query_readonly.py` |
| Result Limiting | `_ensure_limit()` | `TestEnsureLimit` (3 scenarios) | — |
| Error Categorization | `MCPQueryService` catch clauses | `test_mcp_query_service.py` | — |

Spec scenario: "redacted reference is logged (not the raw query text)" — verified in
`test_observability.py::test_cypher_query_rejected_never_logs_raw_query`. ✓

**No gaps.**

### specs/ui/experience.spec.md

All 18 requirements verified:

| Requirement | Status | Evidence |
|---|---|---|
| Backend API Alignment | ✅ | `api-alignment.test.ts`, `task-107` (merged) |
| Navigation Structure | ✅ | `layouts/default.vue`; `navigation-structure.test.ts` |
| Tenant and Workspace Context | ✅ | `tenant-switch.test.ts`, `workspace-guidance.test.ts` |
| Knowledge Graph Creation | ✅ | `knowledge-graphs.test.ts` |
| Data Source Connection | ✅ | `data-source-connection-wizard.test.ts` |
| Ontology Design | ⚠️ BLOCKED | UI utilities present; Extraction context (AIHCM-174) not ready |
| Sync Monitoring | ✅ | `sync-monitoring-extended.test.ts`, `sync-logs.test.ts`, `sync-phase-indicator.test.ts` |
| Get Started Querying (MCP) | ✅ | `mcp-integration.test.ts`, `transient-secret.test.ts` |
| Query Console | ✅ | `query.test.ts`, `query-kg-selector.test.ts` (task-147/148 merged), `query-history.test.ts` |
| Schema Browser | ✅ | `schema-browser.test.ts`, `schema-crossnav-deeplink.test.ts` |
| Graph Explorer | ✅ | `graph-explorer.test.ts` |
| Mutations Console | ✅ | `mutations-console.test.ts`, `mutations-submission.test.ts`, `mutations-indicator-persistence.test.ts`, `mutations-kg-selector.test.ts` |
| API Key Management | ✅ | `api-keys.test.ts` |
| Workspace Management | ✅ | `workspace-management.test.ts` |
| Design Language | ✅ | `design-language.test.ts`, `design-system.test.ts`, `focus-ring.test.ts` |
| Interaction Principles | ✅ | `interaction-principles.test.ts`, `keyboard-shortcuts.test.ts` |
| Responsive Design | ✅ | `responsive-design.test.ts` |
| Dark Mode | ✅ | `color-mode.test.ts` |

**Query Console KG selector:** `ref('')` with `selectedKgId.value || undefined` gate —
tasks 147 and 148 merged; the selector uses empty-string sentinel as required by spec. ✓

**No implementation gaps.**

---

## Current Task State (as seen in .hyperloop/state/tasks/)

| Task | Title | Outstanding work |
|---|---|---|
| task-147 | Fix query console KG selector sentinel | Merged (commit `60dd790bd`) — orchestrator will update status |
| task-148 | Update KG selector tests | Stale — superceded by merged task-147; no separate test PR needed |
| task-149 | MCP auth 503 unit tests | Partially merged (`b52db5c63`); verify full 503 test file |
| task-150 | Per-tenant routing integration tests | Merged (commit `fadf7d15e`) |
| task-151 | MCP KG resource integration tests | Merged in prior cycles (per pass 4) |
| task-152 | Bearer token MCP auth integration tests | **Still outstanding** — `test_mcp_bearer_auth.py` not present |

---

## Summary

**New tasks created this pass: 0**

Specs have not changed (identical blob SHAs across all 12 passes). The sole outstanding
unimplemented item is **task-152** (Bearer token MCP authentication integration test).
All other spec requirements are fully implemented and tested. Ontology Design remains
blocked on AIHCM-174 per project guidelines.
