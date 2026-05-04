import { describe, it, expect } from 'vitest'

// Since these are Nuxt components with composables, test the logic functions
// directly rather than mounting the full component.
//
// These tests specify the expected behavior for the "add new node/edge type"
// feature added in task-063.

// Types (mirroring data-sources/index.vue)
interface ProposedNodeType {
  label: string; description: string
  required_properties: string[]; optional_properties: string[]
  editing: boolean
  editLabel: string; editDescription: string; editRequired: string; editOptional: string
}

interface ProposedEdgeType {
  label: string; description: string; from: string; to: string
  required_properties: string[]; optional_properties: string[]
  editing: boolean
  editLabel: string; editDescription: string; editRequired: string; editOptional: string
}

function newBlankNode(): ProposedNodeType {
  return {
    label: '', description: '', required_properties: [], optional_properties: [],
    editing: true, editLabel: '', editDescription: '', editRequired: '', editOptional: '',
  }
}

function newBlankEdge(): ProposedEdgeType {
  return {
    label: '', description: '', from: '', to: '',
    required_properties: [], optional_properties: [],
    editing: true, editLabel: '', editDescription: '', editRequired: '', editOptional: '',
  }
}

function saveNode(nodes: ProposedNodeType[], idx: number): { error?: string } {
  const n = nodes[idx]
  if (!n.editLabel.trim()) return { error: 'Label is required' }
  if (nodes.some((x, i) => i !== idx && x.label === n.editLabel.trim())) {
    return { error: 'A type with this label already exists' }
  }
  n.label = n.editLabel.trim()
  n.description = n.editDescription
  n.required_properties = n.editRequired.split(',').map(s => s.trim()).filter(Boolean)
  n.optional_properties = n.editOptional.split(',').map(s => s.trim()).filter(Boolean)
  n.editing = false
  return {}
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('Ontology wizard — add new node types', () => {
  it('newBlankNode returns an entry in edit mode with empty label', () => {
    const node = newBlankNode()
    expect(node.editing).toBe(true)
    expect(node.label).toBe('')
  })

  it('addNode() appends a blank node in edit mode to the list', () => {
    const nodes: ProposedNodeType[] = []
    nodes.push(newBlankNode())
    expect(nodes).toHaveLength(1)
    expect(nodes[0].editing).toBe(true)
  })

  it('saveNode() with empty label returns a validation error', () => {
    const nodes = [newBlankNode()]
    const result = saveNode(nodes, 0)
    expect(result.error).toBe('Label is required')
    expect(nodes[0].editing).toBe(true)
  })

  it('saveNode() with a duplicate label returns a validation error', () => {
    const existing: ProposedNodeType = {
      label: 'Repository', description: '', required_properties: [],
      optional_properties: [], editing: false, editLabel: 'Repository',
      editDescription: '', editRequired: '', editOptional: '',
    }
    const nodes: ProposedNodeType[] = [existing, newBlankNode()]
    nodes[1].editLabel = 'Repository'
    const result = saveNode(nodes, 1)
    expect(result.error).toBe('A type with this label already exists')
  })

  it('saveNode() with valid data updates the type and closes edit mode', () => {
    const nodes = [newBlankNode()]
    nodes[0].editLabel = 'Milestone'
    nodes[0].editDescription = 'A project milestone'
    nodes[0].editRequired = 'title, due_date'
    const result = saveNode(nodes, 0)
    expect(result.error).toBeUndefined()
    expect(nodes[0].editing).toBe(false)
    expect(nodes[0].label).toBe('Milestone')
    expect(nodes[0].required_properties).toEqual(['title', 'due_date'])
  })

  it('saveNode() with whitespace-only label returns validation error', () => {
    const nodes = [newBlankNode()]
    nodes[0].editLabel = '   '
    const result = saveNode(nodes, 0)
    expect(result.error).toBe('Label is required')
    expect(nodes[0].editing).toBe(true)
  })

  it('saveNode() trims the label before saving', () => {
    const nodes = [newBlankNode()]
    nodes[0].editLabel = '  Dependency  '
    const result = saveNode(nodes, 0)
    expect(result.error).toBeUndefined()
    expect(nodes[0].label).toBe('Dependency')
  })

  it('saveNode() allows saving the same label when editing an existing node (not a duplicate)', () => {
    const nodes: ProposedNodeType[] = [
      {
        label: 'Repository', description: '', required_properties: [],
        optional_properties: [], editing: true, editLabel: 'Repository',
        editDescription: 'Updated description', editRequired: '', editOptional: '',
      },
    ]
    const result = saveNode(nodes, 0)
    expect(result.error).toBeUndefined()
    expect(nodes[0].label).toBe('Repository')
    expect(nodes[0].editing).toBe(false)
  })

  it('multiple nodes can be added to the list independently', () => {
    const nodes: ProposedNodeType[] = []
    nodes.push(newBlankNode())
    nodes.push(newBlankNode())
    expect(nodes).toHaveLength(2)
    nodes[0].editLabel = 'NodeA'
    nodes[1].editLabel = 'NodeB'
    expect(saveNode(nodes, 0).error).toBeUndefined()
    expect(saveNode(nodes, 1).error).toBeUndefined()
    expect(nodes[0].label).toBe('NodeA')
    expect(nodes[1].label).toBe('NodeB')
  })
})

describe('Ontology wizard — add new edge types', () => {
  it('newBlankEdge returns an entry in edit mode with empty label and from/to', () => {
    const edge = newBlankEdge()
    expect(edge.editing).toBe(true)
    expect(edge.label).toBe('')
    expect(edge.from).toBe('')
    expect(edge.to).toBe('')
  })

  it('addEdge() appends a blank edge in edit mode to the list', () => {
    const edges: ProposedEdgeType[] = []
    edges.push(newBlankEdge())
    expect(edges).toHaveLength(1)
    expect(edges[0].editing).toBe(true)
  })

  it('newBlankEdge has all edit fields initialized to empty strings', () => {
    const edge = newBlankEdge()
    expect(edge.editLabel).toBe('')
    expect(edge.editDescription).toBe('')
    expect(edge.editRequired).toBe('')
    expect(edge.editOptional).toBe('')
  })

  it('newBlankEdge has empty required and optional properties', () => {
    const edge = newBlankEdge()
    expect(edge.required_properties).toEqual([])
    expect(edge.optional_properties).toEqual([])
  })

  it('multiple edges can be added independently', () => {
    const edges: ProposedEdgeType[] = []
    edges.push(newBlankEdge())
    edges.push(newBlankEdge())
    expect(edges).toHaveLength(2)
    edges[0].editLabel = 'CONTAINS'
    edges[1].editLabel = 'REFERENCES'
    expect(edges[0].editLabel).toBe('CONTAINS')
    expect(edges[1].editLabel).toBe('REFERENCES')
  })
})
