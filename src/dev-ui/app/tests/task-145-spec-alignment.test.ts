import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildQueryGraphArgs } from '~/composables/api/useQueryApi'

// ── Task-145 Spec Alignment: Query Console KG Selector Sentinel Fix ───────────
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-145 — fix: use __all__ sentinel for unscoped KG selector
//
// ROOT CAUSE FIXED:
//   Reka UI (shadcn/vue Select component) reserves value="" for clearing a
//   selection. Using ref('') as the unscoped sentinel caused the Select to
//   interpret the initial state as "clear selection" rather than "All KGs",
//   which broke 16 tests across query.test.ts, query-kg-selector.test.ts,
//   query-history.test.ts, task-125-spec-alignment.test.ts, and
//   task-129-spec-alignment.test.ts.
//
// SPEC SCENARIOS COVERED:
//
//   Requirement: Query Console
//   Scenario: Knowledge graph context
//   "GIVEN a query console
//    THEN the user can optionally select a specific knowledge graph to scope queries
//    AND when unscoped, queries span all knowledge graphs the user can access in the tenant"
//
//   The sentinel value '__all__' represents the "unscoped" state (all KGs
//   accessible in the tenant). When selectedKgId === '__all__', the
//   knowledge_graph_id parameter is OMITTED from the query request so the
//   backend spans all graphs the user has access to.
//
// Task-Ref: task-145
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da

const QUERY_VUE = readFileSync(
  resolve(__dirname, '../pages/query/index.vue'),
  'utf-8',
)

// ── Sentinel correctness: __all__ (not empty string) ─────────────────────────
describe('task-145: __all__ sentinel for unscoped KG selection', () => {
  it('selectedKgId is initialised to __all__ (Reka UI sentinel, not empty string)', () => {
    // Empty string is reserved by Reka UI's Select for clearing selection.
    // Using '' caused the unscoped default to behave as "clear" — broken UX.
    expect(QUERY_VUE).toContain("selectedKgId = ref('__all__')")
    expect(QUERY_VUE).not.toContain("selectedKgId = ref('')")
  })

  it('the SelectItem for the unscoped option uses value="__all__" (not empty string)', () => {
    // The SelectItem must use value="__all__" so Reka UI does not interpret
    // the initial state as a cleared selection.
    expect(QUERY_VUE).toMatch(/<SelectItem[^>]*value="__all__"[^>]*>/)
    expect(QUERY_VUE).not.toMatch(/<SelectItem[^>]*value=""[^>]*>All knowledge graphs/)
  })

  it('the sentinel gate uses strict equality (=== __all__), not truthiness check', () => {
    // The sentinel check must be === '__all__' to distinguish the unscoped
    // default from a real KG ID. A truthiness check (|| undefined) would
    // fail for KG IDs that are falsy (though in practice UUIDs are truthy,
    // the explicit check is more correct and spec-aligned).
    expect(QUERY_VUE).toContain("selectedKgId.value === '__all__' ? undefined : selectedKgId.value")
  })

  it('the Scoped badge is hidden when selectedKgId is __all__', () => {
    // The badge should only appear when a specific KG is selected.
    expect(QUERY_VUE).toContain("v-if=\"selectedKgId !== '__all__'\"")
  })
})

// ── Query API integration: unscoped omits knowledge_graph_id ─────────────────
describe('task-145: unscoped query omits knowledge_graph_id from API request', () => {
  it('buildQueryGraphArgs with no KG returns args without knowledge_graph_id', () => {
    // Spec: "when unscoped, queries span all knowledge graphs the user can
    // access in the tenant" — so knowledge_graph_id must be omitted.
    const args = buildQueryGraphArgs('MATCH (n) RETURN n')
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('buildQueryGraphArgs with undefined KG omits knowledge_graph_id', () => {
    // The __all__ sentinel maps to undefined before being passed to
    // buildQueryGraphArgs. Verify the function handles undefined correctly.
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', undefined, undefined, undefined)
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('buildQueryGraphArgs with a real KG ID includes knowledge_graph_id', () => {
    // Spec: "the selected knowledge graph is used as the API target"
    const kgId = 'abc123-uuid-here'
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', undefined, undefined, kgId)
    expect(args).toHaveProperty('knowledge_graph_id', kgId)
  })
})
