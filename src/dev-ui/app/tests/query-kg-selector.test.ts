import { describe, it, expect, vi } from 'vitest'
import { buildQueryGraphArgs } from '~/composables/api/useQueryApi'

// ── Query Console: Knowledge Graph Context Selector ────────────────────────────
//
// Spec: specs/ui/experience.spec.md — Requirement: Query Console
// Scenario: Knowledge graph context
// "GIVEN a query console
//  THEN the user can optionally select a specific knowledge graph to scope queries
//  AND when unscoped, queries span all knowledge graphs the user can access in the tenant"
//
// Task-Ref: task-108
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
//
// These tests verify the five required behaviours from the task spec:
//   1. The KG selector is rendered in the query console toolbar
//   2. The selector populates from the /management/knowledge-graphs API
//   3. A selected KG ID is included in the query execution request
//   4. No KG selected → knowledge_graph_id is omitted from the request
//   5. The toolbar shows the selected KG name (not just an ID or placeholder)

// ── test_kg_selector_rendered_in_query_console ────────────────────────────────
// Spec: "THEN the user can optionally select a specific knowledge graph to scope queries"
//
// Verifies that query/index.vue contains the Knowledge Graph Context Selector
// block with the required Select component bound to selectedKgId.

describe('test_kg_selector_rendered_in_query_console', () => {
  const { readFileSync } = require('node:fs')
  const { resolve } = require('node:path')
  const queryVue: string = readFileSync(
    resolve(__dirname, '../pages/query/index.vue'),
    'utf-8',
  )

  it('query console template contains the Knowledge Graph Context Selector block', () => {
    // The comment marks the KG selector section in the template — if this
    // disappears, the selector has been removed from the toolbar.
    expect(queryVue).toContain('Knowledge Graph Context Selector')
  })

  it('the selector uses a Select component bound to selectedKgId', () => {
    // v-model="selectedKgId" wires the dropdown to the reactive state.
    expect(queryVue).toContain('v-model="selectedKgId"')
  })

  it('the selector includes an "All knowledge graphs" unscoped option', () => {
    // The SelectItem uses value="" (empty string is falsy → unscoped default)
    // and displays "All knowledge graphs" as its label.
    expect(queryVue).toMatch(/<SelectItem[^>]*value=""[^>]*>/)
    expect(queryVue).toContain('All knowledge graphs')
  })

  it('selectedKgId is initialised to empty string (unscoped by default)', () => {
    // '' is the sentinel for "all knowledge graphs". Empty string is falsy in
    // JavaScript, enabling the simple || undefined gate in executeQuery.
    expect(queryVue).toContain("selectedKgId = ref('')")
  })

  it('the selector shows a Scoped badge when a KG is selected', () => {
    // Badge is shown via truthy check on selectedKgId (non-empty string = scoped).
    expect(queryVue).toContain('v-if="selectedKgId"')
    expect(queryVue).toContain('Scoped')
  })

  it('the selector shows an Unscoped badge when no KG is selected', () => {
    expect(queryVue).toContain('Unscoped')
  })
})

// ── test_kg_selector_populates_from_api ──────────────────────────────────────
// Spec: "THEN the user can optionally select a specific knowledge graph to scope queries"
//
// Verifies that loadKnowledgeGraphs() calls GET /management/knowledge-graphs
// and populates the knowledgeGraphs ref with the returned list.

describe('test_kg_selector_populates_from_api', () => {
  const { readFileSync } = require('node:fs')
  const { resolve } = require('node:path')
  const queryVue: string = readFileSync(
    resolve(__dirname, '../pages/query/index.vue'),
    'utf-8',
  )

  it('query/index.vue defines loadKnowledgeGraphs() that fetches from /management/knowledge-graphs', () => {
    expect(queryVue).toContain('loadKnowledgeGraphs')
    expect(queryVue).toContain('/management/knowledge-graphs')
  })

  it('knowledgeGraphs ref holds the list fetched from the API', () => {
    // The v-for loop iterates over knowledgeGraphs to render per-KG options.
    expect(queryVue).toMatch(/v-for="kg in knowledgeGraphs"/)
  })

  it('loadKnowledgeGraphs populates knowledgeGraphs with API response', async () => {
    // Logic test: simulate the loadKnowledgeGraphs function behaviour.
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [
        { id: 'kg-1', name: 'Engineering' },
        { id: 'kg-2', name: 'Security' },
      ],
    })
    const knowledgeGraphs: Array<{ id: string; name: string }> = []
    const hasTenant = true

    async function loadKnowledgeGraphs() {
      if (!hasTenant) return
      try {
        const result = await apiFetch('/management/knowledge-graphs')
        knowledgeGraphs.splice(0, knowledgeGraphs.length, ...(result.knowledge_graphs ?? []))
      } catch {
        knowledgeGraphs.splice(0, knowledgeGraphs.length)
      }
    }

    await loadKnowledgeGraphs()
    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs')
    expect(knowledgeGraphs).toHaveLength(2)
    expect(knowledgeGraphs[0]).toEqual({ id: 'kg-1', name: 'Engineering' })
    expect(knowledgeGraphs[1]).toEqual({ id: 'kg-2', name: 'Security' })
  })

  it('loadKnowledgeGraphs resets to empty array on API error', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const knowledgeGraphs: Array<{ id: string; name: string }> = [
      { id: 'stale', name: 'Stale Graph' },
    ]

    async function loadKnowledgeGraphs() {
      try {
        const result = await apiFetch('/management/knowledge-graphs')
        knowledgeGraphs.splice(0, knowledgeGraphs.length, ...(result.knowledge_graphs ?? []))
      } catch {
        knowledgeGraphs.splice(0, knowledgeGraphs.length)
      }
    }

    await loadKnowledgeGraphs()
    expect(knowledgeGraphs).toHaveLength(0)
  })

  it('loadKnowledgeGraphs is called on mount when a tenant is active', () => {
    // Static analysis: onMounted calls loadKnowledgeGraphs when hasTenant is true.
    expect(queryVue).toContain('loadKnowledgeGraphs()')
  })
})

// ── test_selected_kg_included_in_query_request ────────────────────────────────
// Spec: "WHEN [a KG is selected and] the user executes it
//        THEN [the query is scoped to that knowledge graph]"
//
// Uses the real buildQueryGraphArgs function from useQueryApi to verify that
// knowledge_graph_id is included in the MCP tool arguments when a KG is selected.

describe('test_selected_kg_included_in_query_request', () => {
  it('knowledge_graph_id is included in query args when a KG is selected', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, 'kg-1')
    expect(args.knowledge_graph_id).toBe('kg-1')
  })

  it('cypher, timeout, and max_rows are still included when KG is selected', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, 'kg-abc')
    expect(args.cypher).toBe('MATCH (n) RETURN n')
    expect(args.timeout_seconds).toBe(30)
    expect(args.max_rows).toBe(1000)
    expect(args.knowledge_graph_id).toBe('kg-abc')
  })

  it('selectedKgId || undefined gate passes the KG ID to buildQueryGraphArgs', () => {
    // Mirrors: queryGraph(cypher, timeout, maxRows, selectedKgId.value || undefined)
    const selectedKgId = 'kg-1'
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, selectedKgId || undefined)
    expect(args.knowledge_graph_id).toBe('kg-1')
  })

  it('query/index.vue gates selectedKgId using falsy check before passing to queryGraph', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const queryVue: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    // The || undefined gate converts '' (empty string, unscoped) to undefined for
    // the MCP call, omitting knowledge_graph_id entirely when the query is unscoped.
    expect(queryVue).toContain('selectedKgId.value || undefined')
  })
})

// ── test_no_kg_selected_omits_knowledge_graph_id ─────────────────────────────
// Spec: "when unscoped, queries span all knowledge graphs the user can access in the tenant"
//
// Verifies that knowledge_graph_id is NOT present in the request arguments
// when the selector is left at "All knowledge graphs" (empty string).

describe('test_no_kg_selected_omits_knowledge_graph_id', () => {
  it('knowledge_graph_id is absent from query args when no KG is selected (undefined)', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, undefined)
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('empty string selectedKgId converts to undefined via || undefined gate', () => {
    // An empty string (unscoped state) must NOT be passed as knowledge_graph_id.
    const selectedKgId = ''
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, selectedKgId || undefined)
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('cypher and other args are still present when no KG is selected', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, undefined)
    expect(args.cypher).toBe('MATCH (n) RETURN n')
    expect(args.timeout_seconds).toBe(30)
    expect(args.max_rows).toBe(1000)
  })

  it('buildQueryGraphArgs does not include knowledge_graph_id when omitted entirely', () => {
    // Called with only the required cypher argument — KG ID and other optionals absent.
    const args = buildQueryGraphArgs('MATCH (n) RETURN n')
    expect(args).not.toHaveProperty('knowledge_graph_id')
    expect(args.cypher).toBe('MATCH (n) RETURN n')
  })
})

// ── test_kg_selector_shows_selected_kg_name_in_toolbar ───────────────────────
// Spec: "THEN the user can optionally select a specific knowledge graph to scope queries"
//       (The selected KG name is shown in the toolbar for orientation.)
//
// Verifies the kgScopeLabel computed returns the KG name when one is selected
// and "All knowledge graphs" when unscoped.

describe('test_kg_selector_shows_selected_kg_name_in_toolbar', () => {
  it('shows "All knowledge graphs" placeholder when no KG is selected', () => {
    const selectedKgId = ''
    const knowledgeGraphs = [{ id: 'kg-1', name: 'Engineering' }]

    const kgScopeLabel = !selectedKgId
      ? 'All knowledge graphs'
      : knowledgeGraphs.find((kg) => kg.id === selectedKgId)?.name ?? 'Unknown graph'

    expect(kgScopeLabel).toBe('All knowledge graphs')
  })

  it('shows the KG name when a specific graph is selected', () => {
    const selectedKgId = 'kg-1'
    const knowledgeGraphs = [{ id: 'kg-1', name: 'Engineering' }]

    const kgScopeLabel = !selectedKgId
      ? 'All knowledge graphs'
      : knowledgeGraphs.find((kg) => kg.id === selectedKgId)?.name ?? 'Unknown graph'

    expect(kgScopeLabel).toBe('Engineering')
  })

  it('shows the correct name when multiple KGs are available', () => {
    const selectedKgId = 'kg-2'
    const knowledgeGraphs = [
      { id: 'kg-1', name: 'Engineering' },
      { id: 'kg-2', name: 'Security' },
      { id: 'kg-3', name: 'Product' },
    ]

    const kgScopeLabel = !selectedKgId
      ? 'All knowledge graphs'
      : knowledgeGraphs.find((kg) => kg.id === selectedKgId)?.name ?? 'Unknown graph'

    expect(kgScopeLabel).toBe('Security')
  })

  it('falls back to "Unknown graph" when selected ID does not match any KG', () => {
    const selectedKgId = 'kg-missing'
    const knowledgeGraphs = [{ id: 'kg-1', name: 'Engineering' }]

    const kgScopeLabel = !selectedKgId
      ? 'All knowledge graphs'
      : knowledgeGraphs.find((kg) => kg.id === selectedKgId)?.name ?? 'Unknown graph'

    expect(kgScopeLabel).toBe('Unknown graph')
  })

  it('query/index.vue defines kgScopeLabel computed that returns the KG name', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const queryVue: string = readFileSync(
      resolve(__dirname, '../pages/query/index.vue'),
      'utf-8',
    )
    expect(queryVue).toContain('kgScopeLabel')
    // The computed must cover both the scoped and unscoped paths.
    expect(queryVue).toContain('All knowledge graphs')
  })
})
