import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildQueryGraphArgs } from '~/composables/api/useQueryApi'

// ── Task-145 Spec Alignment: Query Console KG Selector Context ────────────────
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-145 — spec alignment for knowledge graph context requirement
//
// IMPLEMENTATION NOTE (historical context):
//   Task-145 originally delivered a fix using '__all__' as the unscoped
//   sentinel (PR #628). That change was subsequently migrated back to using
//   an empty-string sentinel in PR #630 (fix(ui): migrate query console KG
//   selector from __all__ to empty-string sentinel). These tests verify the
//   CURRENT empty-string implementation satisfies the spec requirement.
//
// SPEC SCENARIOS COVERED:
//
//   Requirement: Query Console
//   Scenario: Knowledge graph context
//   "GIVEN a query console
//    THEN the user can optionally select a specific knowledge graph to scope queries
//    AND when unscoped, queries span all knowledge graphs the user can access in the tenant"
//
//   The empty-string sentinel represents the "unscoped" state (all KGs
//   accessible in the tenant). When selectedKgId.value is '' (falsy),
//   `selectedKgId.value || undefined` evaluates to `undefined` so the
//   knowledge_graph_id parameter is OMITTED from the query request, causing
//   the backend to span all graphs the user has access to.
//
// Task-Ref: task-145
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da

const QUERY_VUE = readFileSync(
  resolve(__dirname, '../pages/query/index.vue'),
  'utf-8',
)

// ── Sentinel correctness: empty-string for unscoped state ────────────────────
describe('task-145: KG selector correctly represents unscoped state', () => {
  it('selectedKgId is initialised to empty string (unscoped default)', () => {
    // The empty-string sentinel represents "All knowledge graphs" (unscoped).
    // The truthy check `selectedKgId.value || undefined` maps '' to undefined.
    expect(QUERY_VUE).toContain("selectedKgId = ref('')")
  })

  it('the SelectItem for the unscoped option is present for selection', () => {
    // There must be a selectable option for "All knowledge graphs" so the
    // user can clear scoping and return to the unscoped state.
    expect(QUERY_VUE).toContain('All knowledge graphs')
  })

  it('unscoped sentinel maps to undefined via truthiness check', () => {
    // The truthy check: `selectedKgId.value || undefined` converts '' to
    // undefined so knowledge_graph_id is OMITTED from the API call when unscoped.
    expect(QUERY_VUE).toContain('selectedKgId.value || undefined')
  })

  it('the Scoped badge is hidden when no KG is selected', () => {
    // The badge should only appear when a specific KG is selected (truthy value).
    expect(QUERY_VUE).toContain('v-if="selectedKgId"')
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
    // The empty-string sentinel maps to undefined before being passed to
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
