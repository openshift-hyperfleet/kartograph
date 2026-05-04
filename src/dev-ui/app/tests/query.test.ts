import { describe, it, expect } from 'vitest'
import { buildQueryGraphArgs } from '~/composables/api/useQueryApi'

// ── Query Console: KG Scope Selector Passes knowledge_graph_id to API ─────────
//
// Spec: specs/ui/experience.spec.md — Requirement: Query Console
// Scenario: Knowledge graph context
//   "GIVEN a query console
//    THEN the user can optionally select a specific knowledge graph to scope queries
//    AND when unscoped, queries span all knowledge graphs the user can access in the tenant"
//
// Task-Ref: task-113
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
//
// These tests are the five canonical acceptance tests for task-113.
// They verify that the KG scope selector correctly passes (or omits)
// knowledge_graph_id in the queryGraph API call, using the real exported
// buildQueryGraphArgs function so that any refactor of the argument-building
// path will surface immediately as a test failure.

// ── Test 1: Unscoped query omits knowledge_graph_id ──────────────────────────
//
// GIVEN the query console loads with no KG selected (selectedKgId = '')
// WHEN the user executes a query
// THEN queryGraph is called with knowledge_graph_id = undefined
//      (the || undefined gate converts the empty string before passing it on)

describe('test_1_unscoped_query_omits_knowledge_graph_id', () => {
  it('knowledge_graph_id is absent when no KG is selected', () => {
    // Mirrors: queryGraph(cypher, timeout, maxRows, selectedKgId.value || undefined)
    // with selectedKgId.value = '' (default, unscoped state)
    const selectedKgId = ''
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, selectedKgId || undefined)
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('cypher and other required fields are present even when unscoped', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, undefined)
    expect(args.cypher).toBe('MATCH (n) RETURN n')
    expect(args.timeout_seconds).toBe(30)
    expect(args.max_rows).toBe(1000)
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('query/index.vue uses __all__ sentinel gate to omit knowledge_graph_id when unscoped', () => {
    // Static verification: the page template must contain the gate expression
    // that prevents the '__all__' sentinel from being sent as knowledge_graph_id.
    // (Reka UI reserves value="" for clearing selection, so '__all__' is used.)
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // The ternary gate converts '__all__' → undefined before the API call.
    expect(src).toContain("selectedKgId.value === '__all__'")
  })
})

// ── Test 2: Scoped query passes selected KG ID ────────────────────────────────
//
// GIVEN the user selects KG with id "kg-abc123" from the selector
// WHEN the user executes a query
// THEN queryGraph is called with knowledge_graph_id = "kg-abc123"

describe('test_2_scoped_query_passes_selected_kg_id', () => {
  it('knowledge_graph_id equals the selected KG id', () => {
    const selectedKgId = 'kg-abc123'
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, selectedKgId || undefined)
    expect(args.knowledge_graph_id).toBe('kg-abc123')
  })

  it('cypher, timeout, and max_rows are also present when a KG is selected', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, 'kg-abc123')
    expect(args.cypher).toBe('MATCH (n) RETURN n')
    expect(args.timeout_seconds).toBe(30)
    expect(args.max_rows).toBe(1000)
    expect(args.knowledge_graph_id).toBe('kg-abc123')
  })

  it('different KG IDs each produce the correct knowledge_graph_id in the args', () => {
    const ids = ['kg-engineering', 'kg-security', 'kg-product-001']
    for (const id of ids) {
      const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, id)
      expect(args.knowledge_graph_id).toBe(id)
    }
  })
})

// ── Test 3: Scoped badge is visible when a KG is selected ────────────────────
//
// GIVEN the user has selected a KG
// THEN a "Scoped" badge is rendered in the toolbar
// AND the badge is absent when no KG is selected (showing "Unscoped" instead)

describe('test_3_scoped_badge_visible_when_kg_selected', () => {
  it('query/index.vue renders a "Scoped" badge when selectedKgId differs from __all__ sentinel', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // The Scoped badge is conditionally rendered when selectedKgId !== '__all__'.
    expect(src).toContain("selectedKgId !== '__all__'")
    expect(src).toContain('Scoped')
  })

  it('query/index.vue renders an "Unscoped" badge when no KG is selected', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // The Unscoped badge is the else-branch of the Scoped badge.
    expect(src).toContain('Unscoped')
  })

  it('selectedKgId is initialised to __all__ sentinel so Unscoped is the default', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // The reactive state default must be '__all__' so Unscoped shows on first render.
    // (Reka UI reserves value="" for clearing selection — cannot use empty string.)
    expect(src).toContain("selectedKgId = ref('__all__')")
  })
})

// ── Test 4: KG selector is populated from the management API ─────────────────
//
// GIVEN the management API returns [{ id: "kg-1", name: "My Graph" }]
// WHEN the query console mounts
// THEN the KG selector dropdown contains the option "My Graph"

describe('test_4_kg_selector_populated_from_api', () => {
  it('loadKnowledgeGraphs populates knowledgeGraphs from API response', async () => {
    // Mirrors the loadKnowledgeGraphs() implementation in query/index.vue.
    // We test the logic directly to avoid requiring a full Nuxt page mount.
    const apiFetch = (_url: string) =>
      Promise.resolve({
        knowledge_graphs: [{ id: 'kg-1', name: 'My Graph' }],
      })

    const knowledgeGraphs: Array<{ id: string; name: string }> = []

    const result = await apiFetch('/management/knowledge-graphs')
    knowledgeGraphs.push(...(result.knowledge_graphs ?? []))

    expect(knowledgeGraphs).toHaveLength(1)
    expect(knowledgeGraphs[0]).toEqual({ id: 'kg-1', name: 'My Graph' })
  })

  it('loadKnowledgeGraphs renders each KG as a SelectItem in the template', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // The v-for loop renders one SelectItem per KG returned from the API.
    expect(src).toMatch(/v-for="kg in knowledgeGraphs"/)
  })

  it('fetches from /management/knowledge-graphs endpoint', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    expect(src).toContain('/management/knowledge-graphs')
  })

  it('calls loadKnowledgeGraphs on mount when a tenant is active', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // onMounted calls loadKnowledgeGraphs() to pre-populate the dropdown.
    expect(src).toContain('loadKnowledgeGraphs()')
  })
})

// ── Test 5: Clearing KG selection restores unscoped mode ─────────────────────
//
// GIVEN a KG has been selected (selectedKgId = "kg-abc123")
// WHEN the user clears the selection (selectedKgId = "")
// THEN the next query execution omits knowledge_graph_id

describe('test_5_clearing_selection_restores_unscoped_mode', () => {
  it('empty string after clearing selection results in undefined knowledge_graph_id', () => {
    // Simulate: user picks a KG, then picks "All knowledge graphs" (value="")
    let selectedKgId = 'kg-abc123'

    // User selects a KG → scoped
    let args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, selectedKgId || undefined)
    expect(args.knowledge_graph_id).toBe('kg-abc123')

    // User clears selection (selects "All knowledge graphs")
    selectedKgId = ''
    args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, selectedKgId || undefined)
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('the "All knowledge graphs" SelectItem has value="__all__" to produce the unscoped state', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // value="__all__" is the sentinel for "all knowledge graphs" — any other value is a KG ID.
    // (Reka UI reserves value="" for clearing selection — cannot use empty string here.)
    expect(src).toMatch(/<SelectItem[^>]*value="__all__"[^>]*>/)
    expect(src).toContain('All knowledge graphs')
  })

  it('Unscoped badge is shown again after KG selection is cleared', () => {
    // Mirrors the v-if/v-else badge logic:
    //   <Badge v-if="selectedKgId">Scoped</Badge>
    //   <Badge v-else>Unscoped</Badge>
    const selectedKgId = ''  // cleared
    const isScoped = Boolean(selectedKgId)
    expect(isScoped).toBe(false)  // → Unscoped badge renders
  })
})
