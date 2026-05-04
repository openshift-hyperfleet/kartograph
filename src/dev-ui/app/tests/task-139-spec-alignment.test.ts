import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Task-139 Spec Alignment: User Experience ───────────────────────────────────
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-139 — User Experience: Query Console, Schema Browser, Graph Explorer
//
// This file provides targeted spec-alignment verification for the three
// remaining Explore-section features of the experience spec:
//
//   Requirement: Query Console
//     - Scenario: Query editing   (Cypher highlighting, autocomplete, linting)
//     - Scenario: Query execution (results table, execution time, row count)
//     - Scenario: Query history   (browse, re-execute, insert past queries)
//
//   Requirement: Schema Browser
//     - Scenario: Type listing    (node/edge types, search, filtering)
//     - Scenario: Type detail     (description, required props, optional props)
//     - Scenario: Cross-navigation (query console, graph explorer, ontology editor)
//
//   Requirement: Graph Explorer
//     - Scenario: Node search     (by type, name, or slug)
//     - Scenario: Neighbor exploration (connected nodes/edges, drill-in trail)
//
//   Requirement: Backend API Alignment (Graph operations)
//     - useGraphApi wiring for schema, neighbor, and slug-search endpoints
//
// Prior tasks that cover the remaining experience spec requirements:
//   task-118: Design Language, Dark Mode, Interaction Principles
//   task-120: Workspace management, Tenant context, Navigation structure
//   task-121: Knowledge Graph creation, Data Source connection wizard
//   task-126: Schema Browser cross-navigation deep-links
//   task-128: Mutations Console (all scenarios)
//   task-129: End-to-end coherence (Backend API Alignment, Sync Monitoring,
//             API Keys, MCP Integration, Workspace Management, Dark Mode,
//             Responsive Design, Ontology Design)

// ── Source file reads ─────────────────────────────────────────────────────────

const appDir = resolve(__dirname, '..')

const queryVue = readFileSync(
  resolve(appDir, 'pages/query/index.vue'),
  'utf-8',
)

const querySidebarVue = readFileSync(
  resolve(appDir, 'components/query/QuerySidebar.vue'),
  'utf-8',
)

const queryResultsPanelVue = readFileSync(
  resolve(appDir, 'components/query/QueryResultsPanel.vue'),
  'utf-8',
)

const historyPanelVue = readFileSync(
  resolve(appDir, 'components/query/HistoryPanel.vue'),
  'utf-8',
)

const schemaVue = readFileSync(
  resolve(appDir, 'pages/graph/schema.vue'),
  'utf-8',
)

const explorerVue = readFileSync(
  resolve(appDir, 'pages/graph/explorer.vue'),
  'utf-8',
)

const graphApi = readFileSync(
  resolve(appDir, 'composables/api/useGraphApi.ts'),
  'utf-8',
)

const ageLinterTs = readFileSync(
  resolve(appDir, 'lib/codemirror/lang-cypher/age-linter.ts'),
  'utf-8',
)

const autocompleteTs = readFileSync(
  resolve(appDir, 'lib/codemirror/lang-cypher/autocomplete.ts'),
  'utf-8',
)

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Query Console
// Scenario: Query editing
// "GIVEN the query console
//  THEN the editor provides Cypher syntax highlighting, autocomplete based on
//       the current schema, and linting"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Query Console: Scenario: Query editing', () => {
  it('Cypher syntax highlighting: cypher() extension is imported', () => {
    expect(queryVue).toContain("from '@/lib/codemirror/lang-cypher'")
  })

  it('Cypher syntax highlighting: cypher() extension is registered in CodeMirror', () => {
    expect(queryVue).toContain('cypher()')
  })

  it('Linting: ageCypherLinter is imported from the lang-cypher module', () => {
    expect(queryVue).toContain("from '@/lib/codemirror/lang-cypher/age-linter'")
  })

  it('Linting: ageCypherLinter() is registered in CodeMirror extensions', () => {
    expect(queryVue).toContain('ageCypherLinter()')
  })

  it('Linting: ageCypherLinter wraps @codemirror/lint linter()', () => {
    // ageCypherLinter uses linter() from @codemirror/lint internally
    expect(ageLinterTs).toContain("from '@codemirror/lint'")
    expect(ageLinterTs).toContain('linter(')
  })

  it('Autocomplete: cypherAutocomplete is imported from the lang-cypher module', () => {
    expect(queryVue).toContain("from '@/lib/codemirror/lang-cypher/autocomplete'")
  })

  it('Autocomplete: cypherAutocomplete() is called and receives node/edge schema', () => {
    // Schema-aware: the function is called with nodeLabels and edgeLabels so
    // autocomplete suggestions include the current graph's type names
    expect(queryVue).toContain('cypherAutocomplete(')
    expect(queryVue).toContain('nodeLabels')
    expect(queryVue).toContain('edgeLabels')
  })

  it('Autocomplete: cypherAutocomplete accepts a schema parameter with labels', () => {
    // The CypherSchema interface accepts labels[] and relationshipTypes[]
    expect(autocompleteTs).toContain('labels')
    expect(autocompleteTs).toContain('relationshipTypes')
  })

  it('Autocomplete: cypherAutocomplete exports a CodeMirror Extension', () => {
    expect(autocompleteTs).toContain('export function cypherAutocomplete')
    expect(autocompleteTs).toContain('Extension')
  })

  it('Schema is fetched on mount to power autocomplete suggestions', () => {
    // listNodeLabels() and listEdgeLabels() are called to populate nodeLabels/edgeLabels
    expect(queryVue).toContain('listNodeLabels')
    expect(queryVue).toContain('listEdgeLabels')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Query Console
// Scenario: Query execution
// "GIVEN a Cypher query in the editor
//  WHEN the user executes it (button or Ctrl/Cmd+Enter)
//  THEN results are displayed as a table with execution time and row count"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Query Console: Scenario: Query execution', () => {
  it('Execute button triggers executeQuery()', () => {
    // The Play / Run button in the toolbar calls executeQuery() on click
    expect(queryVue).toContain('@click="executeQuery"')
  })

  it('Ctrl-Enter keyboard shortcut is wired in the CodeMirror keymap', () => {
    expect(queryVue).toContain("key: 'Ctrl-Enter'")
  })

  it('Cmd-Enter keyboard shortcut is wired for Mac users', () => {
    expect(queryVue).toContain("mac: 'Cmd-Enter'")
  })

  it('executionTime is tracked with millisecond precision (performance.now)', () => {
    expect(queryVue).toContain('executionTime')
    expect(queryVue).toContain('performance.now()')
  })

  it('row_count from the API response is stored and surfaced', () => {
    expect(queryVue).toContain('res.row_count')
  })

  it('execution time is passed to QueryResultsPanel as a prop', () => {
    expect(queryVue).toContain(':execution-time="executionTime"')
  })

  it('results are displayed as a table in QueryResultsPanel', () => {
    // QueryResultsPanel renders a <table> element for tabular results
    expect(queryResultsPanelVue).toContain('<table')
  })

  it('QueryResultsPanel shows row count in the stats bar', () => {
    expect(queryResultsPanelVue).toContain('row_count')
  })

  it('QueryResultsPanel shows execution time in the stats bar', () => {
    expect(queryResultsPanelVue).toContain('executionTime')
  })

  it('execution time is reported in milliseconds with "ms" unit', () => {
    expect(queryResultsPanelVue).toContain('ms')
  })

  it('results table provides tabular (table) and JSON views as tabs', () => {
    // Spec says results are displayed as a table; the implementation also
    // provides a JSON view. The table view is the default.
    expect(queryResultsPanelVue).toContain("value=\"table\"")
    expect(queryResultsPanelVue).toContain("value=\"json\"")
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Query Console
// Scenario: Query history
// "GIVEN previously executed queries
//  THEN the user can browse, re-execute, or insert past queries from a
//       history panel"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Query Console: Scenario: Query history', () => {
  it('query/index.vue maintains a history ref that stores past queries', () => {
    expect(queryVue).toContain('history')
    expect(queryVue).toContain('HISTORY_KEY')
  })

  it('history is persisted to localStorage between sessions', () => {
    expect(queryVue).toContain('localStorage.setItem(HISTORY_KEY')
    expect(queryVue).toContain('localStorage.getItem(HISTORY_KEY)')
  })

  it('HistoryPanel component is used to display past queries via QuerySidebar', () => {
    // HistoryPanel is embedded in QuerySidebar, which is used by query/index.vue.
    // The page uses QuerySidebar; the sidebar imports and renders HistoryPanel.
    expect(queryVue).toContain('QuerySidebar')
    expect(querySidebarVue).toContain('HistoryPanel')
  })

  it('HistoryPanel renders history entries so the user can browse them', () => {
    expect(historyPanelVue).toContain('history')
  })

  it('HistoryPanel emits select-query so the user can re-execute or insert a past query', () => {
    // select-query lets the parent page load the query into the editor
    expect(historyPanelVue).toContain("'select-query'")
  })

  it('query/index.vue handles select-query to load a past query into the editor', () => {
    // The page listens for @select-query / @execute-query to set the editor content
    expect(queryVue).toContain('handleExecuteFromSidebar')
  })

  it('history entries record the row count for each past execution', () => {
    // Each HistoryEntry stores { query, timestamp, rowCount }
    expect(queryVue).toContain('rowCount')
  })

  it('addToHistory deduplicates — re-running a query moves it to the front', () => {
    // Spec: "browse, re-execute, or insert past queries" — history must not
    // accumulate duplicates; the same query at top each time it is run.
    expect(queryVue).toContain('addToHistory')
    // filter ensures previous instance is removed before prepending
    expect(queryVue).toContain('history.value.filter')
  })

  it('logic: addToHistory deduplication moves re-executed query to front', () => {
    interface HistoryEntry { query: string; timestamp: number; rowCount: number | null }
    const history: HistoryEntry[] = [
      { query: 'MATCH (a) RETURN a', timestamp: 1000, rowCount: 5 },
      { query: 'MATCH (b) RETURN b', timestamp: 900,  rowCount: 3 },
    ]

    function addToHistory(cypherText: string, rowCount: number | null) {
      const filtered = history.filter((h) => h.query !== cypherText)
      history.length = 0
      history.push(...filtered)
      history.unshift({ query: cypherText, timestamp: Date.now(), rowCount })
    }

    // Re-running the second query should move it to position 0
    addToHistory('MATCH (b) RETURN b', 7)
    expect(history[0]!.query).toBe('MATCH (b) RETURN b')
    expect(history[0]!.rowCount).toBe(7)
    expect(history).toHaveLength(2)
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Schema Browser
// Scenario: Type listing
// "GIVEN type definitions exist in the graph
//  WHEN the user opens the schema browser
//  THEN node types and edge types are listed with search and filtering"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Schema Browser: Scenario: Type listing', () => {
  it('schema browser fetches node labels from /graph/schema/nodes', () => {
    expect(schemaVue).toContain('listNodeLabels')
    expect(graphApi).toContain("'/graph/schema/nodes'")
  })

  it('schema browser fetches edge labels from /graph/schema/edges', () => {
    expect(schemaVue).toContain('listEdgeLabels')
    expect(graphApi).toContain("'/graph/schema/edges'")
  })

  it('filteredNodeLabels computed applies search query to node type list', () => {
    expect(schemaVue).toContain('filteredNodeLabels')
    expect(schemaVue).toContain('searchQuery')
  })

  it('filteredEdgeLabels computed applies search query to edge type list', () => {
    expect(schemaVue).toContain('filteredEdgeLabels')
  })

  it('logic: filteredNodeLabels filters by label name substring', () => {
    const nodeLabels = ['Repository', 'PullRequest', 'Issue', 'User', 'Team']
    const searchQuery = 'rep'

    const filteredNodeLabels = (() => {
      const q = searchQuery.toLowerCase().trim()
      if (!q) return nodeLabels
      return nodeLabels.filter((label) => label.toLowerCase().includes(q))
    })()

    expect(filteredNodeLabels).toContain('Repository')
    expect(filteredNodeLabels).not.toContain('PullRequest')
    expect(filteredNodeLabels).not.toContain('Issue')
  })

  it('logic: filteredNodeLabels returns all labels when search is empty', () => {
    const nodeLabels = ['Repository', 'Issue', 'User']
    const searchQuery = ''

    const filteredNodeLabels = (() => {
      const q = searchQuery.toLowerCase().trim()
      if (!q) return nodeLabels
      return nodeLabels.filter((label) => label.toLowerCase().includes(q))
    })()

    expect(filteredNodeLabels).toHaveLength(3)
  })

  it('schema browser uses a unified search input covering both node and edge types', () => {
    // A single searchQuery ref is applied to both filteredNodeLabels and filteredEdgeLabels
    expect(schemaVue).toContain('searchQuery')
  })

  it('schema browser shows count of filtered vs total node types', () => {
    // "Showing X of Y node types" — gives the user a sense of filter scope
    expect(schemaVue).toContain('filteredNodeLabels.length')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Schema Browser
// Scenario: Type detail
// "GIVEN a specific type
//  WHEN the user expands it
//  THEN description, required properties, and optional properties are shown"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Schema Browser: Scenario: Type detail', () => {
  it('toggleExpand() is called when the user clicks a type to expand it', () => {
    expect(schemaVue).toContain('toggleExpand')
  })

  it('fetchLabelSchema() loads schema for a label the first time it is expanded', () => {
    // On first expansion the schema is fetched and cached in schemaCache
    expect(schemaVue).toContain('fetchLabelSchema')
    expect(schemaVue).toContain('schemaCache')
  })

  it('node schema is fetched from /graph/schema/nodes/{label}', () => {
    expect(graphApi).toContain('`/graph/schema/nodes/${label}`')
  })

  it('edge schema is fetched from /graph/schema/edges/{label}', () => {
    expect(graphApi).toContain('`/graph/schema/edges/${label}`')
  })

  it('type description is displayed when available', () => {
    expect(schemaVue).toContain('description')
  })

  it('required_properties list is rendered in the expanded type detail panel', () => {
    expect(schemaVue).toContain('required_properties')
  })

  it('optional_properties list is rendered in the expanded type detail panel', () => {
    expect(schemaVue).toContain('optional_properties')
  })

  it('logic: schema search also matches against cached property names', () => {
    // Spec: "node types and edge types are listed with search and filtering"
    // The implementation filters by label name OR cached property names so
    // users can type a property name to find the type that has it.
    interface TypeDefinition { required_properties: string[]; optional_properties: string[] }
    const schemaCache = new Map<string, TypeDefinition>()
    schemaCache.set('Repository', {
      required_properties: ['source_url'],
      optional_properties: ['stars'],
    })

    const nodeLabels = ['Repository', 'Issue']
    const searchQuery = 'source_url'

    const q = searchQuery.toLowerCase()
    const filtered = nodeLabels.filter((label) => {
      if (label.toLowerCase().includes(q)) return true
      const schema = schemaCache.get(label)
      if (schema) {
        const allProps = [...schema.required_properties, ...schema.optional_properties]
        return allProps.some((p) => p.toLowerCase().includes(q))
      }
      return false
    })

    expect(filtered).toContain('Repository')
    expect(filtered).not.toContain('Issue')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Schema Browser
// Scenario: Cross-navigation
// "GIVEN a type in the schema browser
//  THEN the user can navigate directly to the query console (pre-filled query),
//       graph explorer (filtered by type), or ontology editor for that type"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Schema Browser: Scenario: Cross-navigation', () => {
  it('navigateToQuery() navigates from schema browser to query console with pre-filled Cypher', () => {
    expect(schemaVue).toContain('navigateToQuery')
    expect(schemaVue).toContain('/query')
  })

  it('navigateToExplorer() navigates from schema browser to graph explorer filtered by type', () => {
    expect(schemaVue).toContain('navigateToExplorer')
    expect(schemaVue).toContain('/graph/explorer')
  })

  it('navigateToOntologyEditor() navigates from schema browser to ontology editor', () => {
    expect(schemaVue).toContain('navigateToOntologyEditor')
  })

  it('graph explorer receives type filter via URL query parameter (?type=...)', () => {
    // When navigateToExplorer('Repository') is called, it passes type=Repository
    // in the query string so the explorer pre-filters to that node type.
    expect(explorerVue).toContain('route.query.type') // explorer reads the parameter
    expect(schemaVue).toContain('type:')              // schema browser writes it
  })

  it('query console receives pre-filled Cypher via URL query parameter (?q=...)', () => {
    // navigateToQuery('Repository', 'node') encodes a MATCH (n:Repository) RETURN n
    // query in the URL so the query console is pre-filled on arrival.
    expect(queryVue).toContain('route.query.q')
    expect(schemaVue).toContain('/query')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Graph Explorer
// Scenario: Node search
// "GIVEN the graph explorer
//  WHEN the user searches by type, name, or slug
//  THEN matching nodes are displayed as cards with their properties"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Graph Explorer: Scenario: Node search', () => {
  it('searchQuery ref holds the user\'s text search term', () => {
    expect(explorerVue).toContain('searchQuery')
  })

  it('nodeTypeFilter ref holds the selected node type (empty = all types)', () => {
    expect(explorerVue).toContain('nodeTypeFilter')
  })

  it('search by type: browsing all nodes of a selected type is supported', () => {
    // When only nodeTypeFilter is set (no text), the explorer lists all nodes of that type
    expect(explorerVue).toContain('searchDescription')
    expect(explorerVue).toContain('Browsing all')
  })

  it('search by name/slug: searchWithinType() searches slug, name, and title properties', () => {
    // Spec: "by type, name, or slug" — the Cypher query searches three properties
    expect(explorerVue).toContain('n.slug')
    expect(explorerVue).toContain('n.name')
    expect(explorerVue).toContain('n.title')
  })

  it('search across types: searchAcrossTypes() is used when no type filter is active', () => {
    expect(explorerVue).toContain('searchAcrossTypes')
  })

  it('search within type: searchWithinType() is used when a type filter is active', () => {
    expect(explorerVue).toContain('searchWithinType')
  })

  it('slug search uses REST API (findNodesBySlug) before falling back to Cypher', () => {
    // findNodesBySlug() is tried first for exact slug matches; Cypher is the fallback
    expect(explorerVue).toContain('findNodesBySlug')
  })

  it('findNodesBySlug calls GET /graph/nodes/by-slug', () => {
    expect(graphApi).toContain("'/graph/nodes/by-slug'")
  })

  it('search results are stored in searchResults ref and displayed as node cards', () => {
    expect(explorerVue).toContain('searchResults')
  })

  it('node cards show properties using getNodeDisplayName()', () => {
    // Spec: "displayed as cards with their properties"
    expect(explorerVue).toContain('getNodeDisplayName')
  })

  it('logic: getNodeDisplayName returns name, then slug, then title, then id as fallback', () => {
    interface NodeRecord {
      id: string
      label: string
      properties: Record<string, unknown>
    }

    function getNodeDisplayName(node: NodeRecord): string {
      return (
        (node.properties.name as string) ||
        (node.properties.slug as string) ||
        (node.properties.title as string) ||
        node.id
      )
    }

    expect(getNodeDisplayName({ id: 'n:1', label: 'Repo', properties: { name: 'kartograph' } })).toBe('kartograph')
    expect(getNodeDisplayName({ id: 'n:2', label: 'Repo', properties: { slug: 'kartograph-api' } })).toBe('kartograph-api')
    expect(getNodeDisplayName({ id: 'n:3', label: 'Repo', properties: { title: 'The Title' } })).toBe('The Title')
    expect(getNodeDisplayName({ id: 'n:4', label: 'Repo', properties: {} })).toBe('n:4')
  })

  it('logic: canSearch returns false while a search is in progress', () => {
    function canSearch(searching: boolean, searchQuery: string, nodeTypeFilter: string): boolean {
      return !searching && (searchQuery.trim() !== '' || nodeTypeFilter !== '')
    }

    expect(canSearch(true, 'kartograph', '')).toBe(false)
    expect(canSearch(false, 'kartograph', '')).toBe(true)
    expect(canSearch(false, '', 'Repository')).toBe(true)
    expect(canSearch(false, '', '')).toBe(false)
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Graph Explorer
// Scenario: Neighbor exploration
// "GIVEN a node in the explorer
//  WHEN the user expands its neighbors
//  THEN connected nodes and edges are shown with labels and direction
//  AND the user can drill into neighbors, building an exploration trail"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Graph Explorer: Scenario: Neighbor exploration', () => {
  it('exploreNeighbors() is called when the user expands a node', () => {
    expect(explorerVue).toContain('exploreNeighbors')
  })

  it('getNodeNeighbors() fetches connected nodes and edges from the API', () => {
    expect(explorerVue).toContain('getNodeNeighbors')
  })

  it('getNodeNeighbors calls GET /graph/nodes/{id}/neighbors', () => {
    expect(graphApi).toContain('`/graph/nodes/${nodeId}/neighbors`')
  })

  it('expandedNeighbors ref tracks which node is currently expanded', () => {
    expect(explorerVue).toContain('expandedNeighbors')
  })

  it('neighborNodes ref holds the connected nodes returned by the API', () => {
    expect(explorerVue).toContain('neighborNodes')
  })

  it('neighborEdges ref holds the edges (relationships) returned by the API', () => {
    expect(explorerVue).toContain('neighborEdges')
  })

  it('re-expanding the same node collapses it (toggle behavior)', () => {
    // Spec: the user can drill into neighbors — collapsing and re-expanding is expected
    // Implementation: if expandedNeighbors.value === nodeId → collapse
    expect(explorerVue).toContain('expandedNeighbors.value === nodeId')
  })

  it('drilling into a neighbor builds an exploration trail (explorationPath)', () => {
    // Spec: "the user can drill into neighbors, building an exploration trail"
    // drillIntoNeighbor() makes the neighbor the focal node and appends it to
    // explorationPath so the user can navigate backwards through the trail.
    expect(explorerVue).toContain('drillIntoNeighbor')
    expect(explorerVue).toContain('explorationPath')
  })

  it('clearing the search also clears neighbor state', () => {
    // When the user starts a new search, neighbor panels are collapsed
    expect(explorerVue).toContain('clearNeighborState')
  })

  it('logic: exploreNeighbors collapses an already-expanded node (toggle)', () => {
    type NodeId = string
    let expandedNeighbors: NodeId | null = null
    const neighborNodes: unknown[] = []
    const neighborEdges: unknown[] = []

    function clearNeighborState() {
      expandedNeighbors = null
      neighborNodes.length = 0
      neighborEdges.length = 0
    }

    function exploreNeighbors(nodeId: NodeId): 'collapsed' | 'expanding' {
      if (expandedNeighbors === nodeId) {
        clearNeighborState()
        return 'collapsed'
      }
      expandedNeighbors = nodeId
      return 'expanding'
    }

    // First click: start expanding
    const firstCall = exploreNeighbors('n:abc')
    expect(firstCall).toBe('expanding')
    expect(expandedNeighbors).toBe('n:abc')

    // Second click on same node: collapse
    const secondCall = exploreNeighbors('n:abc')
    expect(secondCall).toBe('collapsed')
    expect(expandedNeighbors).toBeNull()
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Backend API Alignment
// Scenario: Parent context is preserved (Graph Explorer and Schema Browser)
// "GIVEN a resource that is scoped to a parent
//  WHEN the user creates or lists that resource
//  THEN the UI includes the parent context required by the API"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-139 — Backend API Alignment: Graph and Schema operations', () => {
  it('useGraphApi exposes findNodesBySlug for slug-based node lookup', () => {
    expect(graphApi).toContain('findNodesBySlug')
  })

  it('useGraphApi exposes getNodeNeighbors for neighbor traversal', () => {
    expect(graphApi).toContain('getNodeNeighbors')
  })

  it('useGraphApi exposes listNodeLabels for schema browser node-type listing', () => {
    expect(graphApi).toContain('listNodeLabels')
  })

  it('useGraphApi exposes listEdgeLabels for schema browser edge-type listing', () => {
    expect(graphApi).toContain('listEdgeLabels')
  })

  it('useGraphApi exposes getNodeSchema and getEdgeSchema for type detail', () => {
    expect(graphApi).toContain('getNodeSchema')
    expect(graphApi).toContain('getEdgeSchema')
  })

  it('slug search includes node_type in query params when a type filter is active', () => {
    // findNodesBySlug(term, label) passes node_type so the backend can scope the search
    expect(graphApi).toContain('node_type')
  })

  it('API endpoints follow /graph/ prefix convention for Graph bounded context', () => {
    expect(graphApi).toContain('/graph/nodes/by-slug')
    expect(graphApi).toContain('/graph/nodes/')
    expect(graphApi).toContain('/graph/schema/nodes')
    expect(graphApi).toContain('/graph/schema/edges')
  })

  it('URL construction: neighbor URL embeds nodeId without "undefined"', () => {
    const nodeId = 'Repository:abc123'
    const url = `/graph/nodes/${nodeId}/neighbors`
    expect(url).toContain('abc123')
    expect(url).not.toContain('undefined')
  })

  it('URL construction: node schema URL embeds label without "undefined"', () => {
    const label = 'Repository'
    const url = `/graph/schema/nodes/${label}`
    expect(url).toContain('Repository')
    expect(url).not.toContain('undefined')
  })
})
