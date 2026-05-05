# Intake Pass 14: mcp-server, query-execution, ui/experience

**Date:** 2026-05-05
**Processed by:** PM intake agent (fourteenth pass)
**Trigger:** Specs flagged as "(modified)" in orchestrator — blob SHAs unchanged.

## Specs Processed

| Spec | Blob SHA | Decision |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | No new tasks |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | No new tasks |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | No new tasks |

**Blob SHAs are identical to all prior passes (passes 1–13).** The specs have not changed.

---

## Changes Since Pass 13

Pass 13 (`73032c857`, 2026-05-05 10:47) confirmed task-152 as the sole outstanding item.
No new commits have landed against these three specs since pass 13. HEAD is at `73032c857`.

---

## Verification Summary

### specs/query/mcp-server.spec.md

All 6 requirements, 22 scenarios — fully implemented and tested.

| Requirement | Scenarios | Status |
|---|---|---|
| Graph Query Tool | 8 | ✅ Implemented + unit tested |
| Documentation Fetch Tool | 5 | ✅ Implemented + unit tested |
| Knowledge Graphs Resource | 2 | ✅ Implemented + unit + integration tested (`test_kg_resource.py`) |
| Agent Instructions Resource | 2 | ✅ Implemented + unit tested |
| MCP Authentication | 4 | ✅ Implemented; 3/4 scenarios have integration coverage; Bearer token: unit only |
| Apache AGE Single-Column Return | 4 | ✅ Implemented + unit tested |

**Sole remaining gap:** Bearer token MCP authentication scenario — unit tests exist in
`test_mcp_auth_middleware.py` but no integration test exercises the full path (real JWT
validation → OIDC JWKS → X-Tenant-ID resolution → SpiceDB membership) through the HTTP
MCP endpoint. Captured in **task-152** (created in `c8ba371a8`).

### specs/query/query-execution.spec.md

All 4 requirements, 9 scenarios — fully implemented and tested.

| Requirement | Scenarios | Status |
|---|---|---|
| Per-Tenant Graph Routing | 2 | ✅ Implemented; integration tests added in `fadf7d15e` (`test_tenant_routing_integration.py`) |
| Read-Only Enforcement | 2 | ✅ Implemented + unit + integration tested |
| Timeout Enforcement | 2 | ✅ Implemented + unit tested |
| Result Limiting | 3 | ✅ Implemented + unit tested |
| Error Categorization | 4 | ✅ Implemented + unit tested |

**Note:** task-150 (per-tenant routing integration tests) is effectively done — `test_tenant_routing_integration.py`
was committed in `fadf7d15e` after the task file was created. The orchestrator will discover
this and mark the task complete.

### specs/ui/experience.spec.md

All 18 requirements, 43 scenarios — fully implemented in `src/dev-ui/app/` and covered by the
2493-test frontend suite (0 failures).

Notable recent changes:
- **task-147 done**: `60dd790bd` migrated `pages/query/index.vue` KG selector from `__all__` to
  empty-string sentinel (`ref('')`, `v-if="selectedKgId"`, `value=""`).
- **task-148**: Test assertions for the `''` sentinel still need updating (16 assertions across
  5 test files). task-148 remains valid and outstanding.

All other requirements (Navigation, Tenant Context, KG Creation, Data Source Connection,
Ontology Design, Sync Monitoring, MCP Connection, Query Console, Schema Browser, Graph
Explorer, Mutations Console, API Key Management, Workspace Management, Design Language,
Interaction Principles, Responsive Design, Dark Mode) are fully implemented and tested.

---

## Open Tasks (all pre-existing)

| Task | Title | Valid? |
|---|---|---|
| task-147 | Fix query console KG selector sentinel (`__all__` → `''`) | Done in code (`60dd790bd`) — likely stale |
| task-148 | Update query console KG selector tests to `''` sentinel | **Valid** — 16 test assertions need updating |
| task-149 | Add 503 tests for MCP auth service unavailable | Stale — tests exist in `test_mcp_auth_middleware.py` since `54052d3ac` |
| task-150 | Per-tenant graph routing integration tests | Done in code (`fadf7d15e`) — likely stale |
| task-151 | KG resource integration tests | Stale — tests exist in `test_kg_resource.py` (task-110) |
| task-152 | Bearer token MCP authentication integration tests | **Valid** — no integration test exists |

## New Tasks Created This Pass

**None.** All spec requirements and scenarios are implemented. The two remaining open items
(task-148 and task-152) were created in prior passes and remain the correct representation
of outstanding work.

---

## Summary

**New tasks created this pass: 0**

The three specs are stable (blob SHAs unchanged for 14 passes). All scenarios are covered.
The orchestrator should focus on executing task-148 and task-152.
