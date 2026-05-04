import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Task-126 Spec Alignment: Schema Browser ────────────────────────────────────
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-126 — UI Schema Browser: Ontology Explorer with Type Detail and
//                   Cross-Navigation
//
// Requirement: Schema Browser
//   - Scenario: Type listing (node and edge types with search/filtering)
//   - Scenario: Type detail (description, required/optional properties on expand)
//   - Scenario: Cross-navigation (query console, graph explorer, ontology editor)
//
// Testing approach: source-level inspection via readFileSync.
// Source inspection is the accepted pattern for design-system and layout
// verification throughout this project (see schema-browser.test.ts,
// design-system.test.ts, focus-ring.test.ts).
//
// Key aspects verified here:
//   1. Schema page uses the correct backend API endpoints
//   2. Progressive disclosure (expand/collapse) is implemented
//   3. Cross-navigation sends the right URL params (schema → explorer, query)
//   4. Target pages correctly receive cross-nav params (explorer ← schema,
//      query ← schema) — end-to-end contract verification

// ── Source paths ──────────────────────────────────────────────────────────────

const appDir = resolve(__dirname, '..')

const schemaVuePath = resolve(appDir, 'pages/graph/schema.vue')
const schemaVue = readFileSync(schemaVuePath, 'utf-8')

const explorerVuePath = resolve(appDir, 'pages/graph/explorer.vue')
const explorerVue = readFileSync(explorerVuePath, 'utf-8')

const queryVuePath = resolve(appDir, 'pages/query/index.vue')
const queryVue = readFileSync(queryVuePath, 'utf-8')

const graphApiPath = resolve(appDir, 'composables/api/useGraphApi.ts')
const graphApi = readFileSync(graphApiPath, 'utf-8')

const layoutPath = resolve(appDir, 'layouts/default.vue')
const layoutVue = readFileSync(layoutPath, 'utf-8')

// ── Scenario: Type listing ────────────────────────────────────────────────────

describe('Task-126 Schema Browser — Scenario: Type listing', () => {
  it('schema page fetches node labels from /graph/schema/nodes endpoint', () => {
    // useGraphApi.listNodeLabels() calls /graph/schema/nodes
    expect(graphApi).toContain("'/graph/schema/nodes'")
  })

  it('schema page fetches edge labels from /graph/schema/edges endpoint', () => {
    // useGraphApi.listEdgeLabels() calls /graph/schema/edges
    expect(graphApi).toContain("'/graph/schema/edges'")
  })

  it('schema.vue calls listNodeLabels() to populate node type listing', () => {
    expect(schemaVue).toContain('listNodeLabels')
    expect(schemaVue).toContain('fetchNodeLabels')
  })

  it('schema.vue calls listEdgeLabels() to populate edge type listing', () => {
    expect(schemaVue).toContain('listEdgeLabels')
    expect(schemaVue).toContain('fetchEdgeLabels')
  })

  it('schema.vue provides a searchQuery for client-side filtering', () => {
    expect(schemaVue).toContain('searchQuery')
  })

  it('schema.vue has separate computed for filtered node labels', () => {
    expect(schemaVue).toContain('filteredNodeLabels')
  })

  it('schema.vue has separate computed for filtered edge labels', () => {
    expect(schemaVue).toContain('filteredEdgeLabels')
  })

  it('schema.vue has node tab and edge tab (two entity type views)', () => {
    // Spec: "node types and edge types are listed"
    expect(schemaVue).toContain('nodes')
    expect(schemaVue).toContain('edges')
    expect(schemaVue).toContain('Node Types')
    expect(schemaVue).toContain('Edge Types')
  })

  it('schema.vue is registered in the layout under Explore section', () => {
    // Spec: Schema Browser appears in Explore group of navigation
    expect(layoutVue).toContain('Schema Browser')
    expect(layoutVue).toContain('/graph/schema')
  })

  it('useGraphApi exports listNodeLabels and listEdgeLabels', () => {
    expect(graphApi).toContain('listNodeLabels')
    expect(graphApi).toContain('listEdgeLabels')
  })
})

// ── Scenario: Type detail ─────────────────────────────────────────────────────

describe('Task-126 Schema Browser — Scenario: Type detail', () => {
  it('schema.vue fetches individual node type schema from /graph/schema/nodes/{label}', () => {
    // useGraphApi.getNodeSchema(label) calls /graph/schema/nodes/{label}
    expect(graphApi).toContain('`/graph/schema/nodes/${label}`')
  })

  it('schema.vue fetches individual edge type schema from /graph/schema/edges/{label}', () => {
    // useGraphApi.getEdgeSchema(label) calls /graph/schema/edges/{label}
    expect(graphApi).toContain('`/graph/schema/edges/${label}`')
  })

  it('schema.vue uses progressive disclosure (expand/collapse per row)', () => {
    // Spec: "user expands it → description, required, optional properties shown"
    expect(schemaVue).toContain('expandedLabels')
    expect(schemaVue).toContain('toggleExpand')
  })

  it('schema.vue displays description from schema cache', () => {
    expect(schemaVue).toContain('description')
    expect(schemaVue).toContain('schemaCache')
  })

  it('schema.vue renders required_properties from schema cache', () => {
    expect(schemaVue).toContain('required_properties')
  })

  it('schema.vue renders optional_properties from schema cache', () => {
    expect(schemaVue).toContain('optional_properties')
  })

  it('schema.vue shows loading indicator while fetching type detail', () => {
    expect(schemaVue).toContain('schemaLoadingLabels')
  })

  it('useGraphApi exports getNodeSchema and getEdgeSchema', () => {
    expect(graphApi).toContain('getNodeSchema')
    expect(graphApi).toContain('getEdgeSchema')
  })
})

// ── Scenario: Cross-navigation — sender side (schema → targets) ───────────────

describe('Task-126 Schema Browser — Scenario: Cross-navigation (schema sends)', () => {
  it('schema.vue sends ?query= param when navigating to Query Console', () => {
    // Spec: "pre-filled query" in Query Console
    expect(schemaVue).toContain("path: '/query'")
    expect(schemaVue).toContain('query: cypher')
  })

  it('schema.vue pre-fills a MATCH query for node types', () => {
    // Spec: "MATCH (n:<Label>) RETURN n LIMIT 25" or similar
    expect(schemaVue).toContain('MATCH')
    expect(schemaVue).toContain('RETURN n LIMIT 25')
  })

  it('schema.vue pre-fills a relationship MATCH query for edge types', () => {
    expect(schemaVue).toContain('RETURN a, r, b LIMIT 25')
  })

  it('schema.vue sends ?type= param when navigating to Graph Explorer', () => {
    // Spec: "graph explorer (filtered by type)"
    expect(schemaVue).toContain("path: '/graph/explorer'")
    expect(schemaVue).toContain("type: label")
  })

  it('schema.vue sends ?openOntologyType= param to ontology editor', () => {
    // Spec: "ontology editor for that type"
    expect(schemaVue).toContain('openOntologyType')
    expect(schemaVue).toContain("path: '/data-sources'")
  })

  it('schema.vue uses navigateToQuery function', () => {
    expect(schemaVue).toContain('navigateToQuery')
  })

  it('schema.vue uses navigateToExplorer function', () => {
    expect(schemaVue).toContain('navigateToExplorer')
  })

  it('schema.vue uses navigateToOntologyEditor function', () => {
    expect(schemaVue).toContain('navigateToOntologyEditor')
  })
})

// ── Scenario: Cross-navigation — receiver side (targets accept params) ─────────
//
// The schema browser's cross-navigation is only useful if the target pages
// correctly receive and apply the query parameters. These tests verify the
// end-to-end contract by inspecting the target page source files.
//
// Spec: "navigate directly to the query console (pre-filled query), graph
// explorer (filtered by type)"

describe('Task-126 Schema Browser — Scenario: Cross-navigation (targets receive)', () => {
  it('explorer.vue reads ?type= route query param on mount', () => {
    // explorer.vue: const typeParam = route.query.type
    expect(explorerVue).toContain('route.query.type')
  })

  it('explorer.vue pre-selects the node type filter from ?type= param', () => {
    // nodeTypeFilter.value = typeParam.trim()
    expect(explorerVue).toContain('nodeTypeFilter.value = typeParam')
  })

  it('explorer.vue auto-browses when arriving with ?type= param', () => {
    // handleSearch() is called after setting nodeTypeFilter from route param
    const typeParamIdx = explorerVue.indexOf('route.query.type')
    const handleSearchIdx = explorerVue.indexOf('handleSearch()', typeParamIdx)
    expect(handleSearchIdx).toBeGreaterThan(typeParamIdx)
  })

  it('query/index.vue reads ?query= route query param on mount', () => {
    // query.value = route.query.query
    expect(queryVue).toContain('route.query.query')
  })

  it('query/index.vue pre-fills the editor from ?query= param', () => {
    // query.value = queryParam.trim()
    expect(queryVue).toContain('query.value = queryParam')
  })

  it('explorer.vue useRoute() is called to access query params', () => {
    expect(explorerVue).toContain('useRoute()')
  })

  it('query/index.vue useRoute() is called to access query params', () => {
    expect(queryVue).toContain('useRoute()')
  })
})

// ── API composable contract (useGraphApi) ─────────────────────────────────────

describe('Task-126 Schema Browser — API composable contract', () => {
  it('useGraphApi returns all four schema functions', () => {
    expect(graphApi).toContain('listNodeLabels,')
    expect(graphApi).toContain('listEdgeLabels,')
    expect(graphApi).toContain('getNodeSchema,')
    expect(graphApi).toContain('getEdgeSchema,')
  })

  it('listNodeLabels supports optional search and has_property params', () => {
    // Enables future server-side filtering without a breaking API change
    expect(graphApi).toContain('search?: string')
    expect(graphApi).toContain('hasProperty?: string')
  })

  it('listEdgeLabels supports optional search param', () => {
    expect(graphApi).toContain('listEdgeLabels(search?: string)')
  })

  it('getNodeSchema returns a TypeDefinition (typed return)', () => {
    expect(graphApi).toContain('Promise<TypeDefinition>')
  })
})

// ── Tenant switch data refresh ─────────────────────────────────────────────────
//
// Spec (Requirement: Tenant and Workspace Context):
//   "switching tenants refreshes all data in the UI"

describe('Task-126 Schema Browser — tenant switch refreshes data', () => {
  it('schema.vue watches tenantVersion to trigger data reload', () => {
    expect(schemaVue).toContain('watch(tenantVersion')
  })

  it('schema.vue clears nodeLabels on tenant switch', () => {
    expect(schemaVue).toContain('nodeLabels.value = []')
  })

  it('schema.vue clears edgeLabels on tenant switch', () => {
    expect(schemaVue).toContain('edgeLabels.value = []')
  })

  it('schema.vue clears schemaCache on tenant switch', () => {
    expect(schemaVue).toContain('schemaCache.clear()')
  })

  it('schema.vue reloads node labels after clearing on tenant switch', () => {
    const watchIdx = schemaVue.indexOf('watch(tenantVersion')
    const fetchNodeIdx = schemaVue.indexOf('fetchNodeLabels()', watchIdx)
    expect(fetchNodeIdx).toBeGreaterThan(watchIdx)
  })

  it('schema.vue reloads edge labels after clearing on tenant switch', () => {
    const watchIdx = schemaVue.indexOf('watch(tenantVersion')
    const fetchEdgeIdx = schemaVue.indexOf('fetchEdgeLabels()', watchIdx)
    expect(fetchEdgeIdx).toBeGreaterThan(watchIdx)
  })
})
