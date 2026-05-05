# Intake Pass 13: mcp-server, query-execution, ui/experience

**Date:** 2026-05-05
**Processed by:** PM intake agent (thirteenth pass)
**Trigger:** Specs flagged as "(modified)" in orchestrator — blob SHAs unchanged.

## Specs Processed

| Spec | Blob SHA | Decision |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | No new tasks |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | No new tasks |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | No new tasks |

**Blob SHAs are identical to all prior passes (passes 1–12).** The specs have not changed.

---

## Changes Since Pass 12

Pass 12 (commit `9db4f4ba5`) confirmed task-152 as the sole outstanding item. Since then:
- No commits have landed against these three specs.
- HEAD is still at `9db4f4ba5` — no new code since pass 12.
- `test_mcp_bearer_auth.py` does not exist — task-152 remains outstanding.
- The query console KG selector uses `ref('')` with empty-string sentinel — task-147 confirmed done in code.

## Verification Summary

### specs/query/mcp-server.spec.md

All six requirements, all 18 scenarios remain fully implemented and tested. See pass 12
for the complete line-by-line breakdown. No code has changed since pass 12.

**Sole remaining gap:**
- **task-152** — Bearer token MCP auth integration test. `validate_mcp_bearer_token`
  is implemented; `test_mcp_bearer_auth.py` has not been created yet.

### specs/query/query-execution.spec.md

All five requirements, all 11 scenarios fully implemented and tested. No code has
changed since pass 12. No gaps.

### specs/ui/experience.spec.md

All 18 requirements verified. Ontology Design remains blocked on AIHCM-174 (Extraction
context spike). All other requirements have implementation and test coverage.

Query console KG selector: `pages/query/index.vue` uses `const selectedKgId = ref('')`
with `selectedKgId.value || undefined` gate — correct per spec and test assertions.

---

## Current Task State

| Task | Title | Status |
|---|---|---|
| task-147 | Fix query console KG selector sentinel | Done (code verified) |
| task-148 | Update KG selector tests | Stale/superceded by task-147 |
| task-149 | MCP auth 503 unit tests | Completed in prior cycles |
| task-150 | Per-tenant routing integration tests | Completed in prior cycles |
| task-151 | MCP KG resource integration tests | Completed in prior cycles |
| task-152 | Bearer token MCP auth integration tests | **Outstanding** |

---

## Summary

**New tasks created this pass: 0**

Specs are unchanged (identical blob SHAs across all 13 passes). The sole outstanding
unimplemented item is **task-152** (Bearer token MCP authentication integration test).
All other spec requirements are fully implemented and tested.
