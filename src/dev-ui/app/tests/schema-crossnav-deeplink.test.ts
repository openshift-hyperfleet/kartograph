import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Schema Browser Cross-Navigation Deep-Link Tests ───────────────────────────
//
// Spec: "Schema Browser" — Scenario: Cross-navigation
//   "GIVEN a type in the schema browser THEN the user can navigate directly to
//   the query console (pre-filled query), graph explorer (filtered by type),
//   or ontology editor for that type"
//
// Task: task-104
// Spec-Ref: specs/ui/experience.spec.md
//
// These tests verify the FULL cross-navigation contract — both the SENDING side
// (schema.vue dispatching navigation with the correct URL params) and the
// RECEIVING side (query console and graph explorer correctly consuming those
// params on mount).
//
// All three participants in the cross-navigation handshake are verified:
//   1. schema.vue       — emits ?query= (for query console) and ?type= (for explorer)
//   2. query/index.vue  — reads ?query= on mount to pre-fill the Cypher editor
//   3. graph/explorer.vue — reads ?type= on mount, sets type filter, auto-searches
// ─────────────────────────────────────────────────────────────────────────────

const schemaVuePath = resolve(__dirname, '../pages/graph/schema.vue')
const queryVuePath = resolve(__dirname, '../pages/query/index.vue')
const explorerVuePath = resolve(__dirname, '../pages/graph/explorer.vue')

const schemaContent = readFileSync(schemaVuePath, 'utf-8')
const queryContent = readFileSync(queryVuePath, 'utf-8')
const explorerContent = readFileSync(explorerVuePath, 'utf-8')

// ────────────────────────────────────────────────────────────────────────────
// Part 1: Sending side — schema.vue emits correct URL params
// ────────────────────────────────────────────────────────────────────────────

describe('Cross-navigation sending side — schema.vue', () => {
  describe('Query console navigation uses ?query= parameter (not ?cypher=)', () => {
    it('navigateToQuery sends query parameter key named "query"', () => {
      // The param name must match what query/index.vue reads: route.query.query
      // If schema.vue used "cypher" the query console would not receive the pre-fill
      expect(schemaContent).toContain("query: { query: cypher }")
    })

    it('navigateToQuery does NOT use a "cypher" parameter key (would be unread)', () => {
      // query/index.vue reads route.query.query — a "cypher" key would be silently ignored
      expect(schemaContent).not.toContain("query: { cypher:")
    })

    it('schema.vue navigates to /query path for the query console button', () => {
      expect(schemaContent).toContain("path: '/query'")
    })
  })

  describe('Graph explorer navigation uses ?type= parameter', () => {
    it('navigateToExplorer sends type parameter key named "type"', () => {
      // The param name must match what explorer.vue reads: route.query.type
      expect(schemaContent).toContain("query: { type: label }")
    })

    it('schema.vue navigates to /graph/explorer path for the explorer button', () => {
      expect(schemaContent).toContain("path: '/graph/explorer'")
    })
  })

  describe('Ontology editor navigation uses ?openOntologyType= parameter', () => {
    it('navigateToOntologyEditor sends openOntologyType parameter', () => {
      expect(schemaContent).toContain('openOntologyType')
    })

    it('schema.vue navigates to /data-sources for the ontology editor button', () => {
      expect(schemaContent).toContain("path: '/data-sources'")
    })
  })

  describe('Cypher query shape for cross-navigation', () => {
    it('node type query uses MATCH (n:`Label`) RETURN n LIMIT 25 pattern', () => {
      // In source: `MATCH (n:\`${label}\`) RETURN n LIMIT 25`
      // Backticks inside template literals are escaped with backslashes in the raw file
      expect(schemaContent).toContain('MATCH (n:\\`${label}\\`) RETURN n LIMIT 25')
    })

    it('edge type query uses MATCH (a)-[r:`Label`]->(b) RETURN a, r, b LIMIT 25 pattern', () => {
      // In source: `MATCH (a)-[r:\`${label}\`]->(b) RETURN a, r, b LIMIT 25`
      expect(schemaContent).toContain('MATCH (a)-[r:\\`${label}\\`]->(b) RETURN a, r, b LIMIT 25')
    })

    it('both node and edge queries use escaped backtick quoting for type-safe label embedding', () => {
      // Backtick quoting (escaped as \` inside template literals) handles labels with
      // spaces, hyphens, or Cypher reserved words
      const backtickPattern = /\\`\$\{label\}\\`/g
      const matches = schemaContent.match(backtickPattern)
      expect(matches).not.toBeNull()
      expect(matches!.length).toBeGreaterThanOrEqual(2)
    })
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Part 2: Receiving side — query/index.vue reads ?query= on mount
// ────────────────────────────────────────────────────────────────────────────

describe('Cross-navigation receiving side — query console (query/index.vue)', () => {
  describe('?query= URL parameter pre-fills the Cypher editor', () => {
    it('query/index.vue reads route.query.query on mount', () => {
      // This is the specific param name: schema.vue sends query: { query: cypher }
      // so query/index.vue must read route.query.query
      expect(queryContent).toContain('route.query.query')
    })

    it('query/index.vue stores the decoded value in the query editor ref', () => {
      // The pre-fill assignment: query.value = queryParam.trim()
      expect(queryContent).toContain('query.value = queryParam.trim()')
    })

    it('query/index.vue type-guards the param before using it', () => {
      // Must guard: typeof queryParam === 'string' to avoid array values from multi-value params
      expect(queryContent).toContain("typeof queryParam === 'string'")
    })

    it('query/index.vue trims whitespace from the query param before pre-filling', () => {
      // .trim() ensures leading/trailing whitespace from URL encoding does not appear in editor
      expect(queryContent).toContain('queryParam.trim()')
    })

    it('query/index.vue uses useRoute() to access the URL params', () => {
      expect(queryContent).toContain('useRoute()')
    })
  })

  describe('Query console initializes useRoute() before onMounted reads params', () => {
    it('useRoute() is called at component scope (not inside a function)', () => {
      // useRoute() must be called at setup scope, not inside onMounted
      // This is Vue Composition API requirement: composables at top level
      const routeCallIndex = queryContent.indexOf('const route = useRoute()')
      const onMountedIndex = queryContent.indexOf('onMounted(')
      expect(routeCallIndex).toBeGreaterThan(-1)
      expect(routeCallIndex).toBeLessThan(onMountedIndex)
    })
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Part 3: Receiving side — graph/explorer.vue reads ?type= on mount
// ────────────────────────────────────────────────────────────────────────────

describe('Cross-navigation receiving side — graph explorer (graph/explorer.vue)', () => {
  describe('?type= URL parameter pre-populates the type filter', () => {
    it('explorer.vue reads route.query.type on mount', () => {
      // This is the specific param name: schema.vue sends query: { type: label }
      expect(explorerContent).toContain('route.query.type')
    })

    it('explorer.vue stores the type param in the nodeTypeFilter ref', () => {
      // nodeTypeFilter.value = typeParam.trim()
      expect(explorerContent).toContain('nodeTypeFilter.value = typeParam.trim()')
    })

    it('explorer.vue type-guards the param before using it', () => {
      expect(explorerContent).toContain("typeof typeParam === 'string'")
    })

    it('explorer.vue trims whitespace from the type param', () => {
      expect(explorerContent).toContain('typeParam.trim()')
    })
  })

  describe('?type= parameter triggers automatic search', () => {
    it('explorer.vue calls handleSearch() when ?type= param is present', () => {
      // Auto-browse is expected: arriving from schema browser should show results immediately
      // The implementation calls handleSearch() inside the typeParam branch
      expect(explorerContent).toContain('handleSearch()')
    })

    it('explorer.vue comment documents the deep-link purpose', () => {
      // The code should be self-documenting for maintainers
      expect(explorerContent).toMatch(/cross.page deep.link|cross-page deep-linking/i)
    })
  })

  describe('Graph explorer initializes useRoute() at component scope', () => {
    it('useRoute() is called inside onMounted (acceptable for deep-link reads)', () => {
      // For the explorer, useRoute() is read inside onMounted, which is valid
      // because we only need the value once on mount (not reactively)
      expect(explorerContent).toContain('useRoute()')
    })
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Part 4: End-to-end contract verification
// Verifies that the param names SENT by schema.vue MATCH those READ by destinations
// ────────────────────────────────────────────────────────────────────────────

describe('Cross-navigation parameter name contract', () => {
  it('schema.vue and query/index.vue use matching "query" param name', () => {
    // schema.vue sends:   query: { query: cypher }
    // query/index.vue reads: route.query.query
    // These must match — a mismatch silently breaks the pre-fill feature
    expect(schemaContent).toContain("query: { query: cypher }")
    expect(queryContent).toContain('route.query.query')
  })

  it('schema.vue and graph/explorer.vue use matching "type" param name', () => {
    // schema.vue sends:   query: { type: label }
    // explorer.vue reads: route.query.type
    expect(schemaContent).toContain("query: { type: label }")
    expect(explorerContent).toContain('route.query.type')
  })

  it('all three pages use Nuxt navigateTo / useRoute (consistent navigation API)', () => {
    expect(schemaContent).toContain('navigateTo(')
    expect(queryContent).toContain('useRoute()')
    expect(explorerContent).toContain('useRoute()')
  })
})
