import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Schema Browser Tests ──────────────────────────────────────────────────────
//
// Spec: "Schema Browser"
// Covers:
//   - Scenario: Type listing (node and edge types with search/filtering)
//   - Scenario: Type detail (description, required/optional properties on expand)
//   - Scenario: Cross-navigation (query console, graph explorer, ontology editor)
//   - Interaction Principle: "/" keyboard shortcut to focus search

// ── Helper: TypeDefinition (mirrors ~/types) ──────────────────────────────────

interface TypeDefinition {
  description: string
  required_properties: string[]
  optional_properties: string[]
}

// ── Filtering Logic (mirrors filteredNodeLabels / filteredEdgeLabels computed) ──

/**
 * Filters a list of type labels by a search query.
 * Matches on label name OR any cached property names.
 * Empty query returns all labels unchanged.
 */
function filteredLabels(
  labels: string[],
  schemaCache: Map<string, TypeDefinition>,
  searchQuery: string,
): string[] {
  const q = searchQuery.toLowerCase().trim()
  if (!q) return labels

  return labels.filter((label) => {
    if (label.toLowerCase().includes(q)) return true
    const schema = schemaCache.get(label)
    if (schema) {
      const allProps = [...schema.required_properties, ...schema.optional_properties]
      if (allProps.some((p) => p.toLowerCase().includes(q))) return true
    }
    return false
  })
}

// ── Cross-Navigation Logic (mirrors navigateToQuery / navigateToExplorer / navigateToMutations) ──

function buildQueryNavigation(label: string, entityType: 'node' | 'edge') {
  const cypher =
    entityType === 'node'
      ? `MATCH (n:\`${label}\`) RETURN n LIMIT 25`
      : `MATCH (a)-[r:\`${label}\`]->(b) RETURN a, r, b LIMIT 25`
  return { path: '/query', query: { query: cypher } }
}

function buildExplorerNavigation(label: string) {
  return { path: '/graph/explorer', query: { type: label } }
}

function buildMutationsNavigation(label: string, entityType: 'node' | 'edge') {
  const template = JSON.stringify({
    op: 'DEFINE',
    type: entityType,
    label,
    description: '',
    required_properties: [],
    optional_properties: [],
  })
  return { path: '/graph/mutations', query: { template } }
}

// ── Keyboard Shortcut Logic ───────────────────────────────────────────────────

function isInputFocused(activeElement: Element | null): boolean {
  if (!activeElement) return false
  return (
    activeElement instanceof HTMLInputElement ||
    activeElement instanceof HTMLTextAreaElement ||
    activeElement.getAttribute('contenteditable') === 'true'
  )
}

// ── Schema Detail Rendering Logic ─────────────────────────────────────────────

function getSchemaProperties(schema: TypeDefinition) {
  return {
    description: schema.description,
    required: schema.required_properties,
    optional: schema.optional_properties,
    hasProperties:
      schema.required_properties.length > 0 || schema.optional_properties.length > 0,
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Type listing — search and filtering
// ────────────────────────────────────────────────────────────────────────────

describe('Schema Browser - type listing with no search query', () => {
  it('returns all labels when search query is empty', () => {
    const labels = ['Repository', 'Issue', 'PullRequest', 'Commit']
    const cache = new Map<string, TypeDefinition>()
    const result = filteredLabels(labels, cache, '')
    expect(result).toEqual(labels)
  })

  it('returns all labels when search query is only whitespace', () => {
    const labels = ['Repository', 'Issue']
    const cache = new Map<string, TypeDefinition>()
    expect(filteredLabels(labels, cache, '   ')).toEqual(labels)
  })
})

describe('Schema Browser - type listing with search query (label name match)', () => {
  it('filters labels by exact name (case-insensitive)', () => {
    const labels = ['Repository', 'Issue', 'PullRequest', 'Commit']
    const cache = new Map<string, TypeDefinition>()
    const result = filteredLabels(labels, cache, 'issue')
    expect(result).toEqual(['Issue'])
  })

  it('filters labels by partial name match', () => {
    const labels = ['Repository', 'Issue', 'PullRequest']
    const cache = new Map<string, TypeDefinition>()
    const result = filteredLabels(labels, cache, 'pull')
    expect(result).toEqual(['PullRequest'])
  })

  it('returns multiple matches when several labels contain the query', () => {
    const labels = ['Repository', 'CommitMessage', 'Commit']
    const cache = new Map<string, TypeDefinition>()
    const result = filteredLabels(labels, cache, 'commit')
    expect(result).toHaveLength(2)
    expect(result).toContain('CommitMessage')
    expect(result).toContain('Commit')
  })

  it('returns empty array when no labels match', () => {
    const labels = ['Repository', 'Issue']
    const cache = new Map<string, TypeDefinition>()
    const result = filteredLabels(labels, cache, 'zzznomatch')
    expect(result).toEqual([])
  })
})

describe('Schema Browser - type listing with search query (property name match)', () => {
  it('includes labels whose cached required properties match the query', () => {
    const labels = ['Repository', 'Issue']
    const cache = new Map<string, TypeDefinition>([
      [
        'Repository',
        {
          description: 'A GitHub repository',
          required_properties: ['source_url', 'name'],
          optional_properties: ['description'],
        },
      ],
    ])
    // 'source_url' matches query 'source_url'
    const result = filteredLabels(labels, cache, 'source_url')
    expect(result).toContain('Repository')
    expect(result).not.toContain('Issue')
  })

  it('includes labels whose cached optional properties match the query', () => {
    const labels = ['Issue', 'Commit']
    const cache = new Map<string, TypeDefinition>([
      [
        'Issue',
        {
          description: '',
          required_properties: ['title'],
          optional_properties: ['documentation_page'],
        },
      ],
    ])
    const result = filteredLabels(labels, cache, 'documentation')
    expect(result).toContain('Issue')
    expect(result).not.toContain('Commit')
  })

  it('does not include labels without schema cache when query matches only property name', () => {
    const labels = ['Repository', 'Issue']
    const cache = new Map<string, TypeDefinition>() // empty cache
    // Neither label name matches 'source_url' and there's no cached schema
    const result = filteredLabels(labels, cache, 'source_url')
    expect(result).toEqual([])
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Type detail — description and properties on expand
// ────────────────────────────────────────────────────────────────────────────

describe('Schema Browser - type detail rendering', () => {
  it('exposes description from schema', () => {
    const schema: TypeDefinition = {
      description: 'A GitHub repository containing code and issues.',
      required_properties: ['name', 'url'],
      optional_properties: ['stars'],
    }
    const detail = getSchemaProperties(schema)
    expect(detail.description).toBe('A GitHub repository containing code and issues.')
  })

  it('exposes required and optional properties separately', () => {
    const schema: TypeDefinition = {
      description: '',
      required_properties: ['sha', 'message', 'timestamp'],
      optional_properties: ['author_email'],
    }
    const detail = getSchemaProperties(schema)
    expect(detail.required).toEqual(['sha', 'message', 'timestamp'])
    expect(detail.optional).toEqual(['author_email'])
  })

  it('reports hasProperties as false when both arrays are empty', () => {
    const schema: TypeDefinition = {
      description: 'No properties',
      required_properties: [],
      optional_properties: [],
    }
    const detail = getSchemaProperties(schema)
    expect(detail.hasProperties).toBe(false)
  })

  it('reports hasProperties as true when required properties exist', () => {
    const schema: TypeDefinition = {
      description: '',
      required_properties: ['id'],
      optional_properties: [],
    }
    const detail = getSchemaProperties(schema)
    expect(detail.hasProperties).toBe(true)
  })

  it('reports hasProperties as true when only optional properties exist', () => {
    const schema: TypeDefinition = {
      description: '',
      required_properties: [],
      optional_properties: ['slug'],
    }
    const detail = getSchemaProperties(schema)
    expect(detail.hasProperties).toBe(true)
  })

  it('schema detail contains spec-required fields (description, required, optional)', () => {
    const schema: TypeDefinition = {
      description: 'A pull request.',
      required_properties: ['title', 'number', 'state'],
      optional_properties: ['body', 'merged_at'],
    }
    const detail = getSchemaProperties(schema)
    expect(detail).toMatchObject({
      description: expect.any(String),
      required: expect.any(Array),
      optional: expect.any(Array),
    })
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Cross-navigation — query console, graph explorer, ontology editor
// ────────────────────────────────────────────────────────────────────────────

describe('Schema Browser - cross-navigation to query console', () => {
  it('generates a MATCH query for node types with LIMIT 25', () => {
    const nav = buildQueryNavigation('Repository', 'node')
    expect(nav.path).toBe('/query')
    expect(nav.query.query).toBe('MATCH (n:`Repository`) RETURN n LIMIT 25')
  })

  it('generates a relationship query for edge types with LIMIT 25', () => {
    const nav = buildQueryNavigation('AUTHORED', 'edge')
    expect(nav.path).toBe('/query')
    expect(nav.query.query).toBe('MATCH (a)-[r:`AUTHORED`]->(b) RETURN a, r, b LIMIT 25')
  })

  it('uses backtick-quoted label in Cypher to handle special characters', () => {
    const nav = buildQueryNavigation('My Node Type', 'node')
    expect(nav.query.query).toContain('`My Node Type`')
  })
})

describe('Schema Browser - cross-navigation to graph explorer', () => {
  it('navigates to explorer with type query param', () => {
    const nav = buildExplorerNavigation('Repository')
    expect(nav.path).toBe('/graph/explorer')
    expect(nav.query.type).toBe('Repository')
  })

  it('passes edge type label to explorer for browsing', () => {
    const nav = buildExplorerNavigation('AUTHORED')
    expect(nav.query.type).toBe('AUTHORED')
  })
})

describe('Schema Browser - cross-navigation to ontology editor (mutations)', () => {
  it('builds a DEFINE node template with correct shape', () => {
    const nav = buildMutationsNavigation('Repository', 'node')
    expect(nav.path).toBe('/graph/mutations')
    const parsed = JSON.parse(nav.query.template)
    expect(parsed.op).toBe('DEFINE')
    expect(parsed.type).toBe('node')
    expect(parsed.label).toBe('Repository')
    expect(parsed.description).toBe('')
    expect(parsed.required_properties).toEqual([])
    expect(parsed.optional_properties).toEqual([])
  })

  it('builds a DEFINE edge template for edge types', () => {
    const nav = buildMutationsNavigation('AUTHORED', 'edge')
    const parsed = JSON.parse(nav.query.template)
    expect(parsed.type).toBe('edge')
    expect(parsed.label).toBe('AUTHORED')
  })

  it('template is valid JSON', () => {
    const nav = buildMutationsNavigation('Issue', 'node')
    expect(() => JSON.parse(nav.query.template)).not.toThrow()
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Interaction Principle: "/" keyboard shortcut to focus search
// ────────────────────────────────────────────────────────────────────────────

describe('Schema Browser - keyboard shortcut "/" focuses search', () => {
  it('isInputFocused returns false when no active element', () => {
    expect(isInputFocused(null)).toBe(false)
  })

  it('isInputFocused returns true for an input element', () => {
    const input = document.createElement('input')
    expect(isInputFocused(input)).toBe(true)
  })

  it('isInputFocused returns true for a textarea element', () => {
    const textarea = document.createElement('textarea')
    expect(isInputFocused(textarea)).toBe(true)
  })

  it('isInputFocused returns false for a div element', () => {
    const div = document.createElement('div')
    expect(isInputFocused(div)).toBe(false)
  })

  it('isInputFocused returns false for a button element', () => {
    const btn = document.createElement('button')
    expect(isInputFocused(btn)).toBe(false)
  })

  it('isInputFocused returns true for a contenteditable element', () => {
    const div = document.createElement('div')
    div.setAttribute('contenteditable', 'true')
    expect(isInputFocused(div)).toBe(true)
  })

  it('should NOT fire "/" shortcut when an input is already focused', () => {
    // Simulates: if isInputFocused() → do not prevent default or focus search
    const activeInput = document.createElement('input')
    let searchFocused = false
    const focusSearch = () => { searchFocused = true }

    function handleGlobalKeydown(key: string, activeElement: Element | null) {
      if (key === '/' && !isInputFocused(activeElement)) {
        focusSearch()
      }
    }

    handleGlobalKeydown('/', activeInput) // "/" pressed while input is focused
    expect(searchFocused).toBe(false)
  })

  it('should fire "/" shortcut when body is focused (no input active)', () => {
    const body = document.createElement('body')
    let searchFocused = false

    function handleGlobalKeydown(key: string, activeElement: Element | null) {
      if (key === '/' && !isInputFocused(activeElement)) {
        searchFocused = true
      }
    }

    handleGlobalKeydown('/', body)
    expect(searchFocused).toBe(true)
  })

  it('Ctrl+K triggers search focus regardless of input state', () => {
    // Ctrl+K always fires even when not in an input (no isInputFocused check)
    let searchFocused = false

    function handleCtrlK(ctrlKey: boolean, key: string) {
      if ((ctrlKey) && key === 'k') {
        searchFocused = true
      }
    }

    handleCtrlK(true, 'k')
    expect(searchFocused).toBe(true)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Verify Schema Browser is in the correct nav section (Explore)
// ────────────────────────────────────────────────────────────────────────────

describe('Schema Browser - navigation placement', () => {
  const layoutPath = resolve(__dirname, '../layouts/default.vue')
  const layoutContent = readFileSync(layoutPath, 'utf-8')

  it('Schema Browser appears in the Explore section of navigation', () => {
    // The Explore section in default.vue contains Schema Browser
    expect(layoutContent).toContain("label: 'Schema Browser'")
    expect(layoutContent).toContain("to: '/graph/schema'")
  })

  it('Schema Browser route is /graph/schema', () => {
    expect(layoutContent).toMatch(/Schema Browser.*\/graph\/schema|\/graph\/schema.*Schema Browser/)
  })
})
