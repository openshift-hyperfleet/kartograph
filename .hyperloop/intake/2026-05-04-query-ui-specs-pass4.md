# Intake Pass 4: mcp-server, query-execution, ui/experience

**Date:** 2026-05-04
**Processed by:** PM intake agent (fourth pass)
**Trigger:** Specs flagged as "(modified)" in orchestrator; state directory empty after
commit `7770840ef` deleted `.hyperloop/state/`.

## Specs Processed

| Spec | Blob SHA | Decision |
|---|---|---|
| `specs/query/mcp-server.spec.md` | `2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e` | No new tasks — fully implemented |
| `specs/query/query-execution.spec.md` | `dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2` | No new tasks — fully implemented |
| `specs/ui/experience.spec.md` | `e77913c2cc6d8b719291e2dbb6870519a94d50da` | **task-147** created |

Blob SHAs are identical to the prior passes (2026-05-04-query-ui-specs-intake.md,
2026-05-04-query-ui-specs-verification-pass2.md,
2026-05-04-query-ui-specs-verification-pass3.md). The specs themselves have not changed.

---

## Verification: specs/query/mcp-server.spec.md — No new tasks

All requirements fully implemented and tested. See pass 3 for line-by-line detail.

---

## Verification: specs/query/query-execution.spec.md — No new tasks

All requirements fully implemented and tested. See pass 3 for line-by-line detail.

---

## Verification: specs/ui/experience.spec.md — task-147 created

All requirements are implemented except one failing test discovered in this pass:

### Gap Found: Query Console KG Selector Sentinel Mismatch

**Requirement:** Query Console — Scenario: Knowledge graph context

**Spec:**
> "THEN the user can optionally select a specific knowledge graph to scope queries
>  AND when unscoped, queries span all knowledge graphs the user can access in the tenant"

**Failing tests in `tests/query-kg-selector.test.ts` (3 failures on alpha):**
- `expect(queryVue).toMatch(/<SelectItem[^>]*value=""[^>]*>/)` — FAILS
  (`pages/query/index.vue` has `value="__all__"`)
- `expect(queryVue).toContain("selectedKgId = ref('')")` — FAILS
  (`pages/query/index.vue` has `ref('__all__')`)
- `expect(queryVue).toContain('v-if="selectedKgId"')` — FAILS
  (implementation uses `selectedKgId !== '__all__'`)

**Root cause:** A prior implementer (task-141) changed the unscoped sentinel from
`''` to `'__all__'`. Three fix branches exist (hyperloop/task-143, hyperloop/task-144,
hyperloop/task-146) that revert to `''`, but none have been merged to alpha.

**Task created:** task-147 — fix `pages/query/index.vue` to use `''` sentinel.

### All Other Requirements — Confirmed Implemented ✅

- Backend API Alignment, Navigation Structure, Tenant/Workspace Context,
  Knowledge Graph Creation, Data Source Connection, Sync Monitoring,
  MCP Integration, Schema Browser, Graph Explorer, Mutations Console,
  API Key Management, Workspace Management, Design Language,
  Interaction Principles, Responsive Design, Dark Mode — all verified ✅.

- Ontology Design (Agent-proposed ontology): blocked pending AIHCM-174 Extraction
  context spike. No task created per guidelines.

---

## Summary

**1 task created:** task-147 (query console KG selector `''` sentinel fix)

**No tasks created for:** mcp-server.spec.md, query-execution.spec.md (fully implemented),
and all other experience.spec.md requirements (implemented and passing).
