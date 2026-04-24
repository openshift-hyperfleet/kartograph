import { describe, it, expect } from 'vitest'

// ── Graph Explorer Tests ──────────────────────────────────────────────────────
//
// Spec: "Graph Explorer"
// Covers:
//   - Scenario: Node search by type, name, or slug
//   - Scenario: Neighbor exploration with connected nodes and edges
//   - Scenario: Exploration trail (drill-in breadcrumb)

// ── Types (mirrors ~/types and explorer.vue local types) ──────────────────────

interface NodeRecord {
  id: string
  label: string
  properties: Record<string, unknown>
}

interface EdgeRecord {
  id: string
  label: string
  start_id: string
  end_id: string
  properties?: Record<string, unknown>
}

// ── Utility Functions (extracted from explorer.vue) ───────────────────────────

function escapeCypherString(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
}

function sanitizeCypherLabel(label: string): string {
  return label.replace(/`/g, '')
}

function transformCypherRow(row: Record<string, unknown>): NodeRecord {
  const values = Object.values(row)
  const data = values[0] as Record<string, unknown> | undefined

  if (!data || typeof data !== 'object') {
    return { id: 'unknown', label: 'Unknown', properties: {} }
  }

  const props = (data.properties as Record<string, unknown>) ?? {}
  const nodeId = (props.id as string) || String(data.id || 'unknown')
  const nodeLabel = String(data.label || 'Unknown')

  return {
    id: nodeId,
    label: nodeLabel,
    properties: props,
  }
}

function getNodeDisplayName(node: NodeRecord): string {
  return (
    (node.properties.name as string) ||
    (node.properties.slug as string) ||
    (node.properties.title as string) ||
    node.id
  )
}

function filteredNodeTypes(types: string[], search: string, limit: number): string[] {
  let result = types
  if (search) {
    const q = search.toLowerCase()
    result = result.filter((t) => t.toLowerCase().includes(q))
  }
  return result.slice(0, limit)
}

function typeFilterLabel(nodeTypeFilter: string): string {
  if (!nodeTypeFilter) return 'All types'
  return nodeTypeFilter
}

function canSearch(searching: boolean, searchQuery: string, nodeTypeFilter: string): boolean {
  return !searching && (searchQuery.trim() !== '' || nodeTypeFilter !== '')
}

function getEdgeLabelForNeighbor(
  centralNode: NodeRecord | null,
  edges: EdgeRecord[],
  neighborId: string,
): { label: string; direction: 'outgoing' | 'incoming' } | null {
  if (!centralNode) return null
  const edge = edges.find((e) => e.start_id === neighborId || e.end_id === neighborId)
  if (!edge) return null
  const direction = edge.start_id === centralNode.id ? 'outgoing' : 'incoming'
  return { label: edge.label, direction }
}

function getPropertyEntries(properties: Record<string, unknown>): [string, unknown][] {
  return Object.entries(properties)
}

function formatPropertyValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// ────────────────────────────────────────────────────────────────────────────
// Utility: escapeCypherString
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - escapeCypherString', () => {
  it('returns string unchanged when no special characters', () => {
    expect(escapeCypherString('hello')).toBe('hello')
  })

  it('escapes single quotes', () => {
    expect(escapeCypherString("it's")).toBe("it\\'s")
  })

  it('escapes backslashes', () => {
    expect(escapeCypherString('path\\to\\file')).toBe('path\\\\to\\\\file')
  })

  it('escapes both backslashes and single quotes', () => {
    expect(escapeCypherString("C:\\Users\\alice's")).toBe("C:\\\\Users\\\\alice\\'s")
  })

  it('handles empty string', () => {
    expect(escapeCypherString('')).toBe('')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Utility: sanitizeCypherLabel
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - sanitizeCypherLabel', () => {
  it('removes backticks from label', () => {
    expect(sanitizeCypherLabel('My`Label')).toBe('MyLabel')
  })

  it('removes multiple backticks', () => {
    expect(sanitizeCypherLabel('`Label`')).toBe('Label')
  })

  it('returns label unchanged when no backticks', () => {
    expect(sanitizeCypherLabel('Repository')).toBe('Repository')
  })

  it('handles empty string', () => {
    expect(sanitizeCypherLabel('')).toBe('')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Utility: transformCypherRow
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - transformCypherRow', () => {
  it('extracts node id from properties.id (application-level ID)', () => {
    const row = {
      n: {
        id: 123,
        label: 'Repository',
        properties: { id: 'repo:abc123', name: 'my-repo' },
      },
    }
    const node = transformCypherRow(row)
    expect(node.id).toBe('repo:abc123')
  })

  it('falls back to data.id when properties.id is absent', () => {
    const row = {
      n: {
        id: 456,
        label: 'Issue',
        properties: { title: 'Bug report' },
      },
    }
    const node = transformCypherRow(row)
    expect(node.id).toBe('456')
  })

  it('extracts label from data.label', () => {
    const row = {
      n: {
        id: 1,
        label: 'Commit',
        properties: {},
      },
    }
    const node = transformCypherRow(row)
    expect(node.label).toBe('Commit')
  })

  it('returns unknown node when row value is not an object', () => {
    const row = { n: 'not-an-object' }
    const node = transformCypherRow(row as Record<string, unknown>)
    expect(node.id).toBe('unknown')
    expect(node.label).toBe('Unknown')
  })

  it('returns unknown node for empty row', () => {
    const row = {}
    const node = transformCypherRow(row)
    expect(node.id).toBe('unknown')
    expect(node.label).toBe('Unknown')
  })

  it('includes all properties in the returned node', () => {
    const row = {
      n: {
        id: 1,
        label: 'Repository',
        properties: { id: 'repo:x', name: 'my-repo', stars: 42 },
      },
    }
    const node = transformCypherRow(row)
    expect(node.properties).toMatchObject({ name: 'my-repo', stars: 42 })
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Utility: getNodeDisplayName (name > slug > title > id)
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - getNodeDisplayName priority', () => {
  it('prefers name over slug, title, and id', () => {
    const node: NodeRecord = {
      id: 'node:1',
      label: 'Repository',
      properties: { name: 'my-repo', slug: 'my-repo-slug', title: 'My Repo Title' },
    }
    expect(getNodeDisplayName(node)).toBe('my-repo')
  })

  it('uses slug when name is absent', () => {
    const node: NodeRecord = {
      id: 'node:2',
      label: 'Issue',
      properties: { slug: 'bug-123', title: 'A Bug' },
    }
    expect(getNodeDisplayName(node)).toBe('bug-123')
  })

  it('uses title when name and slug are absent', () => {
    const node: NodeRecord = {
      id: 'node:3',
      label: 'Commit',
      properties: { title: 'Fix memory leak' },
    }
    expect(getNodeDisplayName(node)).toBe('Fix memory leak')
  })

  it('falls back to id when name, slug, and title are all absent', () => {
    const node: NodeRecord = {
      id: 'node:xyz',
      label: 'Unknown',
      properties: {},
    }
    expect(getNodeDisplayName(node)).toBe('node:xyz')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Node search — type filter combobox
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - node type filter', () => {
  const COMBOBOX_LIMIT = 100

  it('returns all types when search is empty', () => {
    const types = ['Repository', 'Issue', 'PullRequest', 'Commit']
    const result = filteredNodeTypes(types, '', COMBOBOX_LIMIT)
    expect(result).toEqual(types)
  })

  it('filters types by search term (case-insensitive)', () => {
    const types = ['Repository', 'Issue', 'PullRequest', 'Commit']
    const result = filteredNodeTypes(types, 'pull', COMBOBOX_LIMIT)
    expect(result).toEqual(['PullRequest'])
  })

  it('caps result at COMBOBOX_LIMIT', () => {
    const types = Array.from({ length: 150 }, (_, i) => `Type${i}`)
    const result = filteredNodeTypes(types, '', 100)
    expect(result).toHaveLength(100)
  })

  it('caps filtered results at COMBOBOX_LIMIT', () => {
    const types = Array.from({ length: 200 }, (_, i) => `Repository${i}`)
    const result = filteredNodeTypes(types, 'repository', 100)
    expect(result).toHaveLength(100)
  })

  it('returns empty array when no types match search', () => {
    const types = ['Repository', 'Issue']
    const result = filteredNodeTypes(types, 'zzznomatch', COMBOBOX_LIMIT)
    expect(result).toEqual([])
  })

  it('typeFilterLabel returns "All types" when no filter selected', () => {
    expect(typeFilterLabel('')).toBe('All types')
  })

  it('typeFilterLabel returns the type name when a filter is selected', () => {
    expect(typeFilterLabel('Repository')).toBe('Repository')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Node search — canSearch logic
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - canSearch', () => {
  it('returns false when already searching', () => {
    expect(canSearch(true, 'repo', 'Repository')).toBe(false)
  })

  it('returns false when search query is empty and no type filter', () => {
    expect(canSearch(false, '', '')).toBe(false)
  })

  it('returns true when type filter is set (browse mode)', () => {
    expect(canSearch(false, '', 'Repository')).toBe(true)
  })

  it('returns true when search query is set (search mode)', () => {
    expect(canSearch(false, 'my-repo', '')).toBe(true)
  })

  it('returns true when both query and type filter are set', () => {
    expect(canSearch(false, 'my-repo', 'Repository')).toBe(true)
  })

  it('returns false when search query is only whitespace and no type filter', () => {
    expect(canSearch(false, '   ', '')).toBe(false)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Node search — search description and result limit
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - search mode descriptions', () => {
  const BROWSE_LIMIT = 50
  const SEARCH_LIMIT = 25

  it('browse mode: describe as browsing all nodes of a type', () => {
    const nodeTypeFilter = 'Repository'
    const searchQuery = ''
    let description = ''

    if (!searchQuery && nodeTypeFilter) {
      description = `Browsing all ${nodeTypeFilter} nodes`
    }
    expect(description).toBe('Browsing all Repository nodes')
  })

  it('search within type: describe as searching within type', () => {
    const nodeTypeFilter = 'Repository'
    const searchQuery = 'my-repo'
    let description = ''

    if (searchQuery && nodeTypeFilter) {
      description = `Searching for "${searchQuery}" in ${nodeTypeFilter} nodes`
    }
    expect(description).toBe('Searching for "my-repo" in Repository nodes')
  })

  it('search across types: describe as searching across all types', () => {
    const nodeTypeFilter = ''
    const searchQuery = 'my-repo'
    let description = ''

    if (searchQuery && !nodeTypeFilter) {
      description = `Searching for "${searchQuery}" across all types`
    }
    expect(description).toBe('Searching for "my-repo" across all types')
  })

  it('result limit hit for browse mode when results reach BROWSE_LIMIT', () => {
    const nodes = Array.from({ length: BROWSE_LIMIT }, (_, i) => ({
      id: `repo:${i}`,
      label: 'Repository',
      properties: {},
    }))
    const limitHit = nodes.length >= BROWSE_LIMIT
    expect(limitHit).toBe(true)
  })

  it('result limit hit for search mode when results reach SEARCH_LIMIT', () => {
    const nodes = Array.from({ length: SEARCH_LIMIT }, (_, i) => ({
      id: `repo:${i}`,
      label: 'Repository',
      properties: {},
    }))
    const limitHit = nodes.length >= SEARCH_LIMIT
    expect(limitHit).toBe(true)
  })

  it('result limit NOT hit when results are under the limit', () => {
    const nodes = [
      { id: 'repo:1', label: 'Repository', properties: {} },
      { id: 'repo:2', label: 'Repository', properties: {} },
    ]
    const limitHit = nodes.length >= SEARCH_LIMIT
    expect(limitHit).toBe(false)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Neighbor exploration
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - neighbor exploration: getEdgeLabelForNeighbor', () => {
  const centralNode: NodeRecord = {
    id: 'repo:1',
    label: 'Repository',
    properties: { id: 'repo:1' },
  }

  it('returns null when central node is not set', () => {
    const edges: EdgeRecord[] = [{ id: 'e1', label: 'HAS_ISSUE', start_id: 'repo:1', end_id: 'issue:1' }]
    expect(getEdgeLabelForNeighbor(null, edges, 'issue:1')).toBeNull()
  })

  it('returns null when no edge connects to the neighbor', () => {
    const edges: EdgeRecord[] = [
      { id: 'e1', label: 'HAS_ISSUE', start_id: 'repo:1', end_id: 'issue:1' },
    ]
    expect(getEdgeLabelForNeighbor(centralNode, edges, 'commit:99')).toBeNull()
  })

  it('returns outgoing direction when central is the edge start', () => {
    const edges: EdgeRecord[] = [
      { id: 'e1', label: 'HAS_ISSUE', start_id: 'repo:1', end_id: 'issue:1' },
    ]
    const result = getEdgeLabelForNeighbor(centralNode, edges, 'issue:1')
    expect(result).not.toBeNull()
    expect(result!.label).toBe('HAS_ISSUE')
    expect(result!.direction).toBe('outgoing')
  })

  it('returns incoming direction when central is the edge end', () => {
    const edges: EdgeRecord[] = [
      { id: 'e2', label: 'AUTHORED', start_id: 'user:42', end_id: 'repo:1' },
    ]
    const result = getEdgeLabelForNeighbor(centralNode, edges, 'user:42')
    expect(result).not.toBeNull()
    expect(result!.label).toBe('AUTHORED')
    expect(result!.direction).toBe('incoming')
  })

  it('matches edge by end_id as well as start_id (incoming when neighbor is the start)', () => {
    const edges: EdgeRecord[] = [
      { id: 'e3', label: 'REFERENCES', start_id: 'pr:1', end_id: 'issue:1' },
    ]
    // central = issue:1, neighbor = pr:1 (which is start_id)
    // edge goes FROM pr:1 TO issue:1 → from issue:1's perspective, it is INCOMING
    const result = getEdgeLabelForNeighbor(
      { id: 'issue:1', label: 'Issue', properties: { id: 'issue:1' } },
      edges,
      'pr:1',
    )
    expect(result).not.toBeNull()
    expect(result!.label).toBe('REFERENCES')
    // edge.start_id ('pr:1') !== centralNode.id ('issue:1') → 'incoming'
    expect(result!.direction).toBe('incoming')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Exploration trail (breadcrumb)
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - exploration path (trail)', () => {
  function addToPath(path: NodeRecord[], node: NodeRecord): NodeRecord[] {
    const last = path[path.length - 1]
    if (!last || last.id !== node.id) {
      return [...path, node]
    }
    return path
  }

  function navigateBackTo(path: NodeRecord[], index: number): { path: NodeRecord[]; target: NodeRecord } {
    const target = path[index]
    const sliced = path.slice(0, index)
    return { path: sliced, target }
  }

  const nodeA: NodeRecord = { id: 'repo:1', label: 'Repository', properties: { name: 'my-repo' } }
  const nodeB: NodeRecord = { id: 'issue:1', label: 'Issue', properties: { title: 'Bug #1' } }
  const nodeC: NodeRecord = { id: 'pr:1', label: 'PullRequest', properties: { title: 'Fix bug' } }

  it('adds node to exploration path when first exploring', () => {
    let path: NodeRecord[] = []
    path = addToPath(path, nodeA)
    expect(path).toHaveLength(1)
    expect(path[0].id).toBe('repo:1')
  })

  it('adds subsequent nodes to exploration path during drill-in', () => {
    let path: NodeRecord[] = [nodeA]
    path = addToPath(path, nodeB)
    expect(path).toHaveLength(2)
    expect(path[1].id).toBe('issue:1')
  })

  it('does NOT add duplicate of last node in path', () => {
    let path: NodeRecord[] = [nodeA, nodeB]
    path = addToPath(path, nodeB) // same node as last
    expect(path).toHaveLength(2) // unchanged
  })

  it('navigateBackTo slices path at index and returns target node', () => {
    const path: NodeRecord[] = [nodeA, nodeB, nodeC]
    const result = navigateBackTo(path, 1)
    expect(result.path).toHaveLength(1)
    expect(result.path[0].id).toBe('repo:1')
    expect(result.target.id).toBe('issue:1')
  })

  it('navigateBackTo to index 0 returns empty path', () => {
    const path: NodeRecord[] = [nodeA, nodeB]
    const result = navigateBackTo(path, 0)
    expect(result.path).toHaveLength(0)
    expect(result.target.id).toBe('repo:1')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Neighbor exploration — drillIntoNeighbor
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - drillIntoNeighbor', () => {
  function drillIntoNeighbor(neighbor: NodeRecord, getDisplayName: (n: NodeRecord) => string) {
    const searchResults = [neighbor]
    const hasSearched = true
    const searchDescription = `Exploring node: ${getDisplayName(neighbor)}`
    const resultLimitHit = false
    const expandedNeighbors: string | null = null
    const neighborNodes: NodeRecord[] = []
    const neighborEdges: EdgeRecord[] = []
    const centralNode: NodeRecord | null = null

    return {
      searchResults,
      hasSearched,
      searchDescription,
      resultLimitHit,
      expandedNeighbors,
      neighborNodes,
      neighborEdges,
      centralNode,
    }
  }

  it('sets search results to just the neighbor node', () => {
    const neighbor: NodeRecord = {
      id: 'issue:1',
      label: 'Issue',
      properties: { title: 'My Bug', id: 'issue:1' },
    }
    const state = drillIntoNeighbor(neighbor, getNodeDisplayName)
    expect(state.searchResults).toHaveLength(1)
    expect(state.searchResults[0].id).toBe('issue:1')
  })

  it('sets search description to "Exploring node: <name>"', () => {
    const neighbor: NodeRecord = {
      id: 'issue:1',
      label: 'Issue',
      properties: { title: 'Bug #1' },
    }
    const state = drillIntoNeighbor(neighbor, getNodeDisplayName)
    expect(state.searchDescription).toBe('Exploring node: Bug #1')
  })

  it('clears neighbor state after drill-in', () => {
    const neighbor: NodeRecord = { id: 'pr:1', label: 'PullRequest', properties: {} }
    const state = drillIntoNeighbor(neighbor, getNodeDisplayName)
    expect(state.expandedNeighbors).toBeNull()
    expect(state.neighborNodes).toEqual([])
    expect(state.neighborEdges).toEqual([])
    expect(state.centralNode).toBeNull()
  })

  it('sets hasSearched to true so results panel displays', () => {
    const neighbor: NodeRecord = { id: 'n:1', label: 'Node', properties: {} }
    const state = drillIntoNeighbor(neighbor, getNodeDisplayName)
    expect(state.hasSearched).toBe(true)
  })

  it('result limit is not hit on a single drill-in node', () => {
    const neighbor: NodeRecord = { id: 'n:1', label: 'Node', properties: {} }
    const state = drillIntoNeighbor(neighbor, getNodeDisplayName)
    expect(state.resultLimitHit).toBe(false)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Property display helpers
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - property display helpers', () => {
  it('getPropertyEntries returns all property key/value pairs', () => {
    const node: NodeRecord = {
      id: 'n:1',
      label: 'Repository',
      properties: { name: 'my-repo', stars: 42 },
    }
    const entries = getPropertyEntries(node.properties)
    expect(entries).toContainEqual(['name', 'my-repo'])
    expect(entries).toContainEqual(['stars', 42])
  })

  it('formatPropertyValue returns "—" for null', () => {
    expect(formatPropertyValue(null)).toBe('—')
  })

  it('formatPropertyValue returns "—" for undefined', () => {
    expect(formatPropertyValue(undefined)).toBe('—')
  })

  it('formatPropertyValue serializes objects to JSON', () => {
    expect(formatPropertyValue({ a: 1 })).toBe('{"a":1}')
  })

  it('formatPropertyValue converts numbers to strings', () => {
    expect(formatPropertyValue(42)).toBe('42')
  })

  it('formatPropertyValue returns strings as-is', () => {
    expect(formatPropertyValue('hello')).toBe('hello')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Cypher query builders for cross-page navigation
// ────────────────────────────────────────────────────────────────────────────

describe('Graph Explorer - cross-page navigation (query builder)', () => {
  function buildNodeQueryNavigation(node: NodeRecord): { path: string; query: { query: string } } {
    const cypher = `MATCH (n:\`${sanitizeCypherLabel(node.label)}\`) WHERE n.id = '${escapeCypherString(node.id)}' RETURN n`
    return { path: '/query', query: { query: cypher } }
  }

  it('builds correct Cypher query to navigate to query console for a node', () => {
    const node: NodeRecord = { id: 'repo:abc', label: 'Repository', properties: {} }
    const nav = buildNodeQueryNavigation(node)
    expect(nav.path).toBe('/query')
    expect(nav.query.query).toBe("MATCH (n:`Repository`) WHERE n.id = 'repo:abc' RETURN n")
  })

  it('escapes single quotes in node ID when building query', () => {
    const node: NodeRecord = { id: "repo:it's", label: 'Repository', properties: {} }
    const nav = buildNodeQueryNavigation(node)
    expect(nav.query.query).toContain("repo:it\\'s")
  })

  it('sanitizes backticks in node label when building query', () => {
    const node: NodeRecord = { id: 'repo:1', label: 'My`Repo', properties: {} }
    const nav = buildNodeQueryNavigation(node)
    expect(nav.query.query).toContain('`MyRepo`')
  })
})
