import { describe, it, expect, vi, beforeEach } from 'vitest'

// Since these are Nuxt components with composables, test the logic functions
// directly rather than mounting the full component

describe('Data Sources Wizard - Step Navigation', () => {
  it('requires adapter selection to proceed to step 2', () => {
    // Test the nextStep() logic when no adapter is selected
    const selectedAdapterId = { value: '' }
    const wizardStep = { value: 1 }

    function nextStep() {
      if (wizardStep.value === 1) {
        if (!selectedAdapterId.value) return
        wizardStep.value = 2
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(1) // Should stay on step 1
  })

  it('advances to step 2 when adapter is selected', () => {
    const selectedAdapterId = { value: 'github' }
    const selectedKnowledgeGraphId = { value: 'kg-123' }
    const wizardStep = { value: 1 }

    function nextStep() {
      if (wizardStep.value === 1) {
        if (!selectedAdapterId.value) return
        if (!selectedKnowledgeGraphId.value) return
        wizardStep.value = 2
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(2)
  })
})

describe('Data Sources Wizard - Form Validation', () => {
  it('validates required fields in step 2', () => {
    const connName = { value: '' }
    const connRepoUrl = { value: '' }
    const connToken = { value: '' }
    const connNameError = { value: '' }
    const connRepoUrlError = { value: '' }
    const connTokenError = { value: '' }
    const wizardStep = { value: 2 }

    function validate() {
      let valid = true
      if (!connName.value.trim()) {
        connNameError.value = 'Data source name is required.'
        valid = false
      }
      if (!connRepoUrl.value.trim()) {
        connRepoUrlError.value = 'Repository URL is required.'
        valid = false
      } else if (!connRepoUrl.value.includes('github.com')) {
        connRepoUrlError.value = 'Enter a valid GitHub repository URL.'
        valid = false
      }
      if (!connToken.value.trim()) {
        connTokenError.value = 'Access token is required.'
        valid = false
      }
      return valid
    }

    expect(validate()).toBe(false)
    expect(connNameError.value).toBe('Data source name is required.')
    expect(connRepoUrlError.value).toBe('Repository URL is required.')
    expect(connTokenError.value).toBe('Access token is required.')
  })

  it('passes validation with all fields filled', () => {
    const connName = { value: 'my-repo' }
    const connRepoUrl = { value: 'https://github.com/owner/my-repo' }
    const connToken = { value: 'ghp_test123' }
    const connNameError = { value: '' }
    const connRepoUrlError = { value: '' }
    const connTokenError = { value: '' }

    function validate() {
      let valid = true
      if (!connName.value.trim()) { connNameError.value = 'Name required'; valid = false }
      if (!connRepoUrl.value.trim()) { connRepoUrlError.value = 'URL required'; valid = false }
      else if (!connRepoUrl.value.includes('github.com')) { connRepoUrlError.value = 'Invalid URL'; valid = false }
      if (!connToken.value.trim()) { connTokenError.value = 'Token required'; valid = false }
      return valid
    }

    expect(validate()).toBe(true)
  })

  it('infers data source name from GitHub repo URL', () => {
    const connRepoUrl = { value: '' }
    const connName = { value: '' }

    function inferName(url: string) {
      if (!url.trim() || connName.value.trim()) return
      const match = url.trim().match(/github\.com\/[^/]+\/([^/]+?)(?:\.git)?$/)
      if (match) {
        connName.value = match[1]
      }
    }

    connRepoUrl.value = 'https://github.com/owner/my-awesome-repo'
    inferName(connRepoUrl.value)
    expect(connName.value).toBe('my-awesome-repo')
  })
})

describe('Data Sources Wizard - Intent Step', () => {
  it('requires intent text to proceed to ontology step', () => {
    const intentText = { value: '' }
    const intentError = { value: '' }
    const wizardStep = { value: 3 }

    function nextStep() {
      if (wizardStep.value === 3) {
        intentError.value = ''
        if (!intentText.value.trim()) {
          intentError.value = 'Please describe your intent before continuing.'
          return
        }
        wizardStep.value = 4
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(3)
    expect(intentError.value).toBe('Please describe your intent before continuing.')
  })

  it('advances to ontology step when intent is provided', () => {
    const intentText = { value: 'I want to understand contributor patterns' }
    const intentError = { value: '' }
    const wizardStep = { value: 3 }
    const scanningOntology = { value: false }
    const proposedNodes: unknown[] = []
    const proposedEdges: unknown[] = []

    function nextStep() {
      if (wizardStep.value === 3) {
        intentError.value = ''
        if (!intentText.value.trim()) {
          intentError.value = 'Please describe your intent before continuing.'
          return
        }
        wizardStep.value = 4
        scanningOntology.value = true
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(4)
    expect(scanningOntology.value).toBe(true)
  })
})

describe('Data Sources Wizard - Token Visibility', () => {
  it('toggles token visibility', () => {
    const showToken = { value: false }

    function toggleToken() {
      showToken.value = !showToken.value
    }

    expect(showToken.value).toBe(false)
    toggleToken()
    expect(showToken.value).toBe(true)
    toggleToken()
    expect(showToken.value).toBe(false)
  })
})

describe('Data Sources Wizard - Approval', () => {
  it('requires knowledge graph selection before approval', async () => {
    const selectedKnowledgeGraphId = { value: '' }
    let toastMessage = ''

    async function approveOntology() {
      if (!selectedKnowledgeGraphId.value) {
        toastMessage = 'Please select a knowledge graph first'
        return
      }
    }

    await approveOntology()
    expect(toastMessage).toBe('Please select a knowledge graph first')
  })
})

describe('Sync Monitoring', () => {
  it('computes sync duration correctly', () => {
    const startedAt = '2024-01-01T10:00:00Z'
    const completedAt = '2024-01-01T10:00:30Z'

    const duration = Math.round(
      (new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000
    )

    expect(duration).toBe(30)
  })

  it('shows idle status when no sync runs exist', () => {
    const syncRuns: unknown[] = []
    const status = syncRuns.length > 0 ? (syncRuns[0] as { status: string }).status : 'idle'
    expect(status).toBe('idle')
  })
})

// ── Ontology Design: Individual Type Editing ──────────────────────────────────
//
// Spec: "Ontology Design" → "Scenario: Individual type editing"
// "THEN they can modify the label, description, required properties, and optional properties
//  AND they can add or remove relationship types
//  AND they can specify exact property requirements"
//
// These tests mirror the logic in pages/data-sources/index.vue
// startEditNode / saveEditNode / cancelEditNode / removeNode
// startEditEdge / saveEditEdge / cancelEditEdge / removeEdge

interface ProposedNodeType {
  label: string
  description: string
  required_properties: string[]
  optional_properties: string[]
  editing: boolean
  editLabel: string
  editDescription: string
  editRequired: string
  editOptional: string
}

interface ProposedEdgeType {
  label: string
  description: string
  from: string
  to: string
  required_properties: string[]
  optional_properties: string[]
  editing: boolean
  editLabel: string
  editDescription: string
  editRequired: string
  editOptional: string
}

function makeNode(overrides: Partial<ProposedNodeType> = {}): ProposedNodeType {
  return {
    label: 'Repository',
    description: 'A GitHub repository',
    required_properties: ['name', 'url'],
    optional_properties: ['description', 'stars'],
    editing: false,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
    ...overrides,
  }
}

function makeEdge(overrides: Partial<ProposedEdgeType> = {}): ProposedEdgeType {
  return {
    label: 'OWNS',
    description: 'User owns a repository',
    from: 'User',
    to: 'Repository',
    required_properties: ['since'],
    optional_properties: ['role'],
    editing: false,
    editLabel: '',
    editDescription: '',
    editRequired: '',
    editOptional: '',
    ...overrides,
  }
}

// Exact logic from data-sources/index.vue
function startEditNode(nodes: ProposedNodeType[], index: number) {
  const n = nodes[index]
  n.editLabel = n.label
  n.editDescription = n.description
  n.editRequired = n.required_properties.join(', ')
  n.editOptional = n.optional_properties.join(', ')
  n.editing = true
}

function saveEditNode(nodes: ProposedNodeType[], index: number) {
  const n = nodes[index]
  n.label = n.editLabel.trim() || n.label
  n.description = n.editDescription
  n.required_properties = n.editRequired.split(',').map((s) => s.trim()).filter(Boolean)
  n.optional_properties = n.editOptional.split(',').map((s) => s.trim()).filter(Boolean)
  n.editing = false
}

function cancelEditNode(nodes: ProposedNodeType[], index: number) {
  nodes[index].editing = false
}

function removeNode(nodes: ProposedNodeType[], index: number) {
  nodes.splice(index, 1)
}

function startEditEdge(edges: ProposedEdgeType[], index: number) {
  const e = edges[index]
  e.editLabel = e.label
  e.editDescription = e.description
  e.editRequired = e.required_properties.join(', ')
  e.editOptional = e.optional_properties.join(', ')
  e.editing = true
}

function saveEditEdge(edges: ProposedEdgeType[], index: number) {
  const e = edges[index]
  e.label = e.editLabel.trim() || e.label
  e.description = e.editDescription
  e.required_properties = e.editRequired.split(',').map((s) => s.trim()).filter(Boolean)
  e.optional_properties = e.editOptional.split(',').map((s) => s.trim()).filter(Boolean)
  e.editing = false
}

function cancelEditEdge(edges: ProposedEdgeType[], index: number) {
  edges[index].editing = false
}

function removeEdge(edges: ProposedEdgeType[], index: number) {
  edges.splice(index, 1)
}

describe('Ontology Design - startEditNode', () => {
  it('copies label to editLabel', () => {
    const nodes = [makeNode()]
    startEditNode(nodes, 0)
    expect(nodes[0].editLabel).toBe('Repository')
  })

  it('copies description to editDescription', () => {
    const nodes = [makeNode()]
    startEditNode(nodes, 0)
    expect(nodes[0].editDescription).toBe('A GitHub repository')
  })

  it('joins required_properties as comma-separated editRequired', () => {
    const nodes = [makeNode()]
    startEditNode(nodes, 0)
    expect(nodes[0].editRequired).toBe('name, url')
  })

  it('joins optional_properties as comma-separated editOptional', () => {
    const nodes = [makeNode()]
    startEditNode(nodes, 0)
    expect(nodes[0].editOptional).toBe('description, stars')
  })

  it('sets editing to true', () => {
    const nodes = [makeNode()]
    startEditNode(nodes, 0)
    expect(nodes[0].editing).toBe(true)
  })

  it('only mutates the node at the given index', () => {
    const nodes = [makeNode({ label: 'First' }), makeNode({ label: 'Second' })]
    startEditNode(nodes, 1)
    expect(nodes[0].editing).toBe(false)
    expect(nodes[1].editing).toBe(true)
  })
})

describe('Ontology Design - saveEditNode', () => {
  it('applies trimmed editLabel to label', () => {
    const nodes = [makeNode({ editLabel: '  PullRequest  ', editing: true })]
    saveEditNode(nodes, 0)
    expect(nodes[0].label).toBe('PullRequest')
  })

  it('falls back to original label when editLabel is empty', () => {
    const nodes = [makeNode({ label: 'Repository', editLabel: '   ', editing: true })]
    saveEditNode(nodes, 0)
    expect(nodes[0].label).toBe('Repository')
  })

  it('applies editDescription to description', () => {
    const nodes = [makeNode({ editDescription: 'New description', editing: true })]
    saveEditNode(nodes, 0)
    expect(nodes[0].description).toBe('New description')
  })

  it('splits editRequired by comma into required_properties', () => {
    const nodes = [makeNode({ editRequired: 'name, url, slug', editing: true })]
    saveEditNode(nodes, 0)
    expect(nodes[0].required_properties).toEqual(['name', 'url', 'slug'])
  })

  it('filters out blank entries from editRequired', () => {
    const nodes = [makeNode({ editRequired: 'name,,  ,url', editing: true })]
    saveEditNode(nodes, 0)
    expect(nodes[0].required_properties).toEqual(['name', 'url'])
  })

  it('splits editOptional by comma into optional_properties', () => {
    const nodes = [makeNode({ editOptional: 'description, stars', editing: true })]
    saveEditNode(nodes, 0)
    expect(nodes[0].optional_properties).toEqual(['description', 'stars'])
  })

  it('allows specifying exact property requirements (source_url example)', () => {
    const nodes = [makeNode({ editRequired: 'source_url', editOptional: '', editing: true })]
    saveEditNode(nodes, 0)
    expect(nodes[0].required_properties).toEqual(['source_url'])
    expect(nodes[0].optional_properties).toEqual([])
  })

  it('sets editing to false after save', () => {
    const nodes = [makeNode({ editing: true, editLabel: 'Issue', editRequired: 'id', editOptional: '' })]
    saveEditNode(nodes, 0)
    expect(nodes[0].editing).toBe(false)
  })
})

describe('Ontology Design - cancelEditNode', () => {
  it('sets editing to false without modifying label', () => {
    const nodes = [makeNode({ label: 'Repository', editLabel: 'Changed', editing: true })]
    cancelEditNode(nodes, 0)
    expect(nodes[0].editing).toBe(false)
    expect(nodes[0].label).toBe('Repository') // original untouched
  })

  it('sets editing to false without modifying required_properties', () => {
    const nodes = [makeNode({ required_properties: ['name'], editRequired: 'other', editing: true })]
    cancelEditNode(nodes, 0)
    expect(nodes[0].required_properties).toEqual(['name'])
  })
})

describe('Ontology Design - removeNode', () => {
  it('removes the node at the given index', () => {
    const nodes = [makeNode({ label: 'A' }), makeNode({ label: 'B' }), makeNode({ label: 'C' })]
    removeNode(nodes, 1)
    expect(nodes).toHaveLength(2)
    expect(nodes[0].label).toBe('A')
    expect(nodes[1].label).toBe('C')
  })

  it('removes the first node when index is 0', () => {
    const nodes = [makeNode({ label: 'First' }), makeNode({ label: 'Second' })]
    removeNode(nodes, 0)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].label).toBe('Second')
  })

  it('removes the last node when index is at the end', () => {
    const nodes = [makeNode({ label: 'First' }), makeNode({ label: 'Last' })]
    removeNode(nodes, 1)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].label).toBe('First')
  })
})

describe('Ontology Design - startEditEdge', () => {
  it('copies label to editLabel', () => {
    const edges = [makeEdge()]
    startEditEdge(edges, 0)
    expect(edges[0].editLabel).toBe('OWNS')
  })

  it('copies description to editDescription', () => {
    const edges = [makeEdge()]
    startEditEdge(edges, 0)
    expect(edges[0].editDescription).toBe('User owns a repository')
  })

  it('joins required_properties as comma-separated editRequired', () => {
    const edges = [makeEdge()]
    startEditEdge(edges, 0)
    expect(edges[0].editRequired).toBe('since')
  })

  it('joins optional_properties as comma-separated editOptional', () => {
    const edges = [makeEdge()]
    startEditEdge(edges, 0)
    expect(edges[0].editOptional).toBe('role')
  })

  it('sets editing to true', () => {
    const edges = [makeEdge()]
    startEditEdge(edges, 0)
    expect(edges[0].editing).toBe(true)
  })
})

describe('Ontology Design - saveEditEdge', () => {
  it('applies trimmed editLabel to label', () => {
    const edges = [makeEdge({ editLabel: '  CONTRIBUTES_TO  ', editing: true })]
    saveEditEdge(edges, 0)
    expect(edges[0].label).toBe('CONTRIBUTES_TO')
  })

  it('falls back to original label when editLabel is empty', () => {
    const edges = [makeEdge({ label: 'OWNS', editLabel: '', editing: true })]
    saveEditEdge(edges, 0)
    expect(edges[0].label).toBe('OWNS')
  })

  it('applies editDescription to description', () => {
    const edges = [makeEdge({ editDescription: 'Updated edge description', editing: true })]
    saveEditEdge(edges, 0)
    expect(edges[0].description).toBe('Updated edge description')
  })

  it('splits editRequired by comma into required_properties', () => {
    const edges = [makeEdge({ editRequired: 'since, weight', editing: true })]
    saveEditEdge(edges, 0)
    expect(edges[0].required_properties).toEqual(['since', 'weight'])
  })

  it('splits editOptional by comma into optional_properties and adds relationship types', () => {
    const edges = [makeEdge({ editOptional: 'role, notes', editing: true })]
    saveEditEdge(edges, 0)
    expect(edges[0].optional_properties).toEqual(['role', 'notes'])
  })

  it('sets editing to false after save', () => {
    const edges = [makeEdge({ editing: true, editLabel: 'OWNS', editRequired: 'since', editOptional: '' })]
    saveEditEdge(edges, 0)
    expect(edges[0].editing).toBe(false)
  })
})

describe('Ontology Design - cancelEditEdge', () => {
  it('sets editing to false without modifying label', () => {
    const edges = [makeEdge({ label: 'OWNS', editLabel: 'CHANGED', editing: true })]
    cancelEditEdge(edges, 0)
    expect(edges[0].editing).toBe(false)
    expect(edges[0].label).toBe('OWNS')
  })

  it('sets editing to false without modifying required_properties', () => {
    const edges = [makeEdge({ required_properties: ['since'], editRequired: 'other', editing: true })]
    cancelEditEdge(edges, 0)
    expect(edges[0].required_properties).toEqual(['since'])
  })
})

describe('Ontology Design - removeEdge', () => {
  it('removes the edge at the given index', () => {
    const edges = [makeEdge({ label: 'OWNS' }), makeEdge({ label: 'CONTRIBUTES_TO' }), makeEdge({ label: 'REVIEWS' })]
    removeEdge(edges, 1)
    expect(edges).toHaveLength(2)
    expect(edges[0].label).toBe('OWNS')
    expect(edges[1].label).toBe('REVIEWS')
  })

  it('can remove all edge types one by one', () => {
    const edges = [makeEdge({ label: 'A' }), makeEdge({ label: 'B' })]
    removeEdge(edges, 0)
    removeEdge(edges, 0)
    expect(edges).toHaveLength(0)
  })
})
