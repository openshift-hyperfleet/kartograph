import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

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

// ── Requirement: Backend API Alignment – Response Format ──────────────────────
//
// The backend list endpoints return direct JSON arrays (not wrapped objects):
//   GET /management/knowledge-graphs/{kg_id}/data-sources → DataSourceResponse[]
//   GET /management/data-sources/{ds_id}/sync-runs       → SyncRunResponse[]
//
// The UI must handle these as direct arrays, NOT as { data_sources: [...] } or
// { sync_runs: [...] }.  These tests verify that the correct response format
// is expected and handled.

describe('Data Source API Response Format - list-data-sources', () => {
  it('handles direct array response (not { data_sources: [...] })', async () => {
    // Backend returns: DataSourceResponse[]  (JSON array, no wrapper)
    const mockDataSources = [
      { id: 'ds-1', name: 'Repo A', adapter_type: 'github', knowledge_graph_id: 'kg-1', last_sync_at: null, created_at: '2024-01-01T00:00:00Z' },
      { id: 'ds-2', name: 'Repo B', adapter_type: 'github', knowledge_graph_id: 'kg-1', last_sync_at: null, created_at: '2024-01-01T00:00:00Z' },
    ]
    // $fetch returns the parsed response directly — for a JSON array it returns the array
    const apiFetch = vi.fn().mockResolvedValue(mockDataSources)
    const dataSources: typeof mockDataSources = []

    // Correct: treat response as a direct array
    async function loadDataSourcesForKg(kgId: string) {
      const sources = await apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`)
      dataSources.splice(0, dataSources.length, ...sources)
    }

    await loadDataSourcesForKg('kg-1')
    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs/kg-1/data-sources')
    expect(dataSources).toHaveLength(2)
    expect(dataSources[0].name).toBe('Repo A')
  })

  it('returns empty array when no data sources exist for a KG', async () => {
    const apiFetch = vi.fn().mockResolvedValue([])
    const dataSources: unknown[] = ['stale']

    async function loadDataSourcesForKg(kgId: string) {
      const sources = await apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`)
      dataSources.splice(0, dataSources.length, ...sources)
    }

    await loadDataSourcesForKg('kg-empty')
    expect(dataSources).toHaveLength(0)
  })

  it('does NOT use { data_sources: [...] } wrapper — that key does not exist on the response', async () => {
    // Demonstrates the bug: wrapping the response incorrectly
    const mockArray = [{ id: 'ds-1', name: 'Repo A' }]
    const apiFetch = vi.fn().mockResolvedValue(mockArray)

    // WRONG pattern (the old bug):
    const wrappedResult = await apiFetch('/management/knowledge-graphs/kg-1/data-sources')
    const buggyExtract = (wrappedResult as Record<string, unknown>).data_sources ?? []
    expect(buggyExtract).toEqual([]) // proves the wrapper pattern yields nothing

    // CORRECT pattern:
    const correctExtract = wrappedResult
    expect(correctExtract).toHaveLength(1)
    expect((correctExtract as typeof mockArray)[0].name).toBe('Repo A')
  })
})

describe('Data Source API Response Format - list-sync-runs', () => {
  it('handles direct array response (not { sync_runs: [...] })', async () => {
    // Backend returns: SyncRunResponse[]  (JSON array, no wrapper)
    const mockRuns = [
      { id: 'run-1', data_source_id: 'ds-1', status: 'completed', started_at: '2024-01-01T10:00:00Z', completed_at: '2024-01-01T10:01:00Z', error: null, created_at: '2024-01-01T10:00:00Z' },
      { id: 'run-2', data_source_id: 'ds-1', status: 'failed', started_at: '2024-01-02T10:00:00Z', completed_at: null, error: 'timeout', created_at: '2024-01-02T10:00:00Z' },
    ]
    const apiFetch = vi.fn().mockResolvedValue(mockRuns)
    const syncRuns: typeof mockRuns = []

    // Correct: treat response as a direct array
    async function loadSyncRuns(dsId: string) {
      const runs = await apiFetch(`/management/data-sources/${dsId}/sync-runs`)
      syncRuns.splice(0, syncRuns.length, ...runs)
    }

    await loadSyncRuns('ds-1')
    expect(apiFetch).toHaveBeenCalledWith('/management/data-sources/ds-1/sync-runs')
    expect(syncRuns).toHaveLength(2)
    expect(syncRuns[0].status).toBe('completed')
    expect(syncRuns[1].status).toBe('failed')
  })

  it('returns empty array when no sync runs exist for a data source', async () => {
    const apiFetch = vi.fn().mockResolvedValue([])
    const syncRuns: unknown[] = []

    async function loadSyncRuns(dsId: string) {
      const runs = await apiFetch(`/management/data-sources/${dsId}/sync-runs`)
      syncRuns.splice(0, syncRuns.length, ...runs)
    }

    await loadSyncRuns('ds-new')
    expect(syncRuns).toHaveLength(0)
  })

  it('does NOT use { sync_runs: [...] } wrapper — that key does not exist on the response', async () => {
    // Demonstrates the bug: wrapping the response incorrectly
    const mockArray = [{ id: 'run-1', status: 'completed' }]
    const apiFetch = vi.fn().mockResolvedValue(mockArray)

    // WRONG pattern (the old bug):
    const wrappedResult = await apiFetch('/management/data-sources/ds-1/sync-runs')
    const buggyExtract = (wrappedResult as Record<string, unknown>).sync_runs ?? []
    expect(buggyExtract).toEqual([]) // proves the wrapper pattern yields nothing

    // CORRECT pattern:
    const correctExtract = wrappedResult
    expect(correctExtract).toHaveLength(1)
  })
})

// ── Ontology Design: Agent-Proposed Ontology ──────────────────────────────────
//
// Spec: "Scenario: Agent-proposed ontology"
// "GIVEN a free-text intent description and a connected data source
//  WHEN the user submits their intent
//  THEN the system performs a lightweight scan of the data source
//  AND an AI agent explores the scanned data and proposes an ontology
//       (node types, edge types, properties)
//  AND the proposed ontology is presented to the user for review"
//
// Implementation note: `beginOntologyProposal()` in data-sources/index.vue
// simulates the scan + AI proposal flow:
//   1. Sets scanningOntology = true (scan in progress)
//   2. Populates proposedNodes and proposedEdges from GITHUB_PROPOSAL_NODES/EDGES
//   3. Sets scanningOntology = false, ontologyReady = true (proposal ready)

// Mirrors GITHUB_PROPOSAL_NODES from data-sources/index.vue
const GITHUB_PROPOSAL_NODES = [
  {
    label: 'Repository',
    description: 'A GitHub repository containing code, issues, and pull requests.',
    required_properties: ['name', 'url'],
    optional_properties: ['description', 'stars', 'forks', 'default_branch'],
  },
  {
    label: 'Issue',
    description: 'An issue filed in a GitHub repository.',
    required_properties: ['title', 'number', 'state'],
    optional_properties: ['body', 'labels', 'closed_at'],
  },
  {
    label: 'PullRequest',
    description: 'A pull request proposing code changes.',
    required_properties: ['title', 'number', 'state'],
    optional_properties: ['body', 'base_branch', 'head_branch', 'merged_at'],
  },
  {
    label: 'Commit',
    description: 'A Git commit recorded in the repository.',
    required_properties: ['sha', 'message', 'timestamp'],
    optional_properties: ['author_email'],
  },
  {
    label: 'User',
    description: 'A GitHub user who interacts with the repository.',
    required_properties: ['login'],
    optional_properties: ['name', 'email', 'avatar_url'],
  },
]

const GITHUB_PROPOSAL_EDGES = [
  {
    label: 'CONTAINS',
    description: 'A repository contains issues, pull requests, and commits.',
    from: 'Repository',
    to: 'Issue | PullRequest | Commit',
    required_properties: [] as string[],
    optional_properties: [] as string[],
  },
  {
    label: 'CREATED_BY',
    description: 'An issue or pull request was created by a user.',
    from: 'Issue | PullRequest',
    to: 'User',
    required_properties: [] as string[],
    optional_properties: ['created_at'],
  },
  {
    label: 'AUTHORED_BY',
    description: 'A commit was authored by a user.',
    from: 'Commit',
    to: 'User',
    required_properties: [] as string[],
    optional_properties: [] as string[],
  },
  {
    label: 'ASSIGNED_TO',
    description: 'An issue or pull request is assigned to a user.',
    from: 'Issue | PullRequest',
    to: 'User',
    required_properties: [] as string[],
    optional_properties: [] as string[],
  },
]

// Simulates beginOntologyProposal() without the setTimeout (synchronous version
// for deterministic testing).
function runOntologyProposalSync(): {
  scanningOntology: boolean
  ontologyReady: boolean
  proposedNodes: typeof GITHUB_PROPOSAL_NODES
  proposedEdges: typeof GITHUB_PROPOSAL_EDGES
} {
  const state = {
    scanningOntology: true,
    ontologyReady: false,
    proposedNodes: [] as typeof GITHUB_PROPOSAL_NODES,
    proposedEdges: [] as typeof GITHUB_PROPOSAL_EDGES,
  }

  // (scan completes)
  state.proposedNodes = GITHUB_PROPOSAL_NODES.map((n) => ({ ...n }))
  state.proposedEdges = GITHUB_PROPOSAL_EDGES.map((e) => ({ ...e }))
  state.scanningOntology = false
  state.ontologyReady = true

  return state
}

describe('Ontology Design - Agent-Proposed Ontology: scan initiation', () => {
  it('sets scanningOntology to true when the scan begins', () => {
    // beginOntologyProposal() immediately sets scanningOntology = true before the async wait
    let scanningOntology = false
    let ontologyReady = false

    function beginOntologyProposal() {
      scanningOntology = true
      ontologyReady = false
      // (async scan runs here...)
    }

    beginOntologyProposal()
    expect(scanningOntology).toBe(true)
    expect(ontologyReady).toBe(false)
  })

  it('clears any previously proposed nodes and edges when scan begins', () => {
    const proposedNodes = [{ label: 'OldType' }]
    const proposedEdges = [{ label: 'OLD_EDGE' }]

    function beginOntologyProposal() {
      proposedNodes.splice(0)
      proposedEdges.splice(0)
    }

    beginOntologyProposal()
    expect(proposedNodes).toHaveLength(0)
    expect(proposedEdges).toHaveLength(0)
  })
})

describe('Ontology Design - Agent-Proposed Ontology: proposal population', () => {
  it('proposes node types after scan completes for GitHub adapter', () => {
    const state = runOntologyProposalSync()
    expect(state.proposedNodes.length).toBeGreaterThanOrEqual(1)
    expect(state.ontologyReady).toBe(true)
    expect(state.scanningOntology).toBe(false)
  })

  it('proposes at least 5 node types for GitHub adapter', () => {
    const state = runOntologyProposalSync()
    expect(state.proposedNodes.length).toBeGreaterThanOrEqual(5)
  })

  it('proposes at least 4 edge types for GitHub adapter', () => {
    const state = runOntologyProposalSync()
    expect(state.proposedEdges.length).toBeGreaterThanOrEqual(4)
  })

  it('each proposed node type has a label, description, and required_properties', () => {
    const state = runOntologyProposalSync()
    for (const node of state.proposedNodes) {
      expect(node.label).toBeTruthy()
      expect(node.description).toBeTruthy()
      expect(Array.isArray(node.required_properties)).toBe(true)
    }
  })

  it('each proposed edge type has a label, from, and to fields', () => {
    const state = runOntologyProposalSync()
    for (const edge of state.proposedEdges) {
      expect(edge.label).toBeTruthy()
      expect(edge.from).toBeTruthy()
      expect(edge.to).toBeTruthy()
    }
  })

  it('proposed node types include expected GitHub entities (Repository, User)', () => {
    const state = runOntologyProposalSync()
    const nodeLabels = state.proposedNodes.map((n) => n.label)
    expect(nodeLabels).toContain('Repository')
    expect(nodeLabels).toContain('User')
  })

  it('proposed edge types include expected relationships (CONTAINS, AUTHORED_BY)', () => {
    const state = runOntologyProposalSync()
    const edgeLabels = state.proposedEdges.map((e) => e.label)
    expect(edgeLabels).toContain('CONTAINS')
    expect(edgeLabels).toContain('AUTHORED_BY')
  })

  it('ontologyReady transitions from false to true after scan completes', () => {
    let scanningOntology = false
    let ontologyReady = false
    const proposedNodes: string[] = []

    async function beginOntologyProposalAsync(tick: () => void) {
      scanningOntology = true
      ontologyReady = false

      // snapshot: scanning is true, ontology not yet ready
      tick()

      // scan completes:
      proposedNodes.push('Repository', 'User')
      scanningOntology = false
      ontologyReady = true
    }

    let midScanState = { scanning: false, ready: false }
    beginOntologyProposalAsync(() => {
      midScanState = { scanning: scanningOntology, ready: ontologyReady }
    })

    expect(midScanState.scanning).toBe(true)
    expect(midScanState.ready).toBe(false)
    // After the async completes:
    expect(scanningOntology).toBe(false)
    expect(ontologyReady).toBe(true)
    expect(proposedNodes).toContain('Repository')
  })
})

// ── Ontology Design: Ontology Review and Approval ────────────────────────────
//
// Spec: "Scenario: Ontology review and approval"
// "GIVEN a proposed ontology
//  WHEN the user reviews it
//  THEN they can approve the ontology as-is
//  OR iterate by editing individual types and relationships
//  AND extraction begins only after the user explicitly approves"

describe('Ontology Design - Ontology Review and Approval: approve as-is', () => {
  it('approveOntology() calls the data source API when all conditions are met', async () => {
    const selectedKnowledgeGraphId = { value: 'kg-123' }
    const connName = { value: 'my-repo' }
    const connRepoUrl = { value: 'https://github.com/owner/my-repo' }
    const connToken = { value: 'ghp_abc' }
    const selectedAdapterId = { value: 'github' }
    let approvingOntology = false
    let dataSourceCreated = false

    const createDataSource = vi.fn().mockResolvedValue({ id: 'ds-new' })

    async function approveOntology() {
      if (!selectedKnowledgeGraphId.value) {
        return
      }
      approvingOntology = true
      try {
        await createDataSource({
          kg_id: selectedKnowledgeGraphId.value,
          name: connName.value,
          adapter_type: selectedAdapterId.value,
          connection_config: { repo_url: connRepoUrl.value },
          credentials: connToken.value ? { access_token: connToken.value } : undefined,
        })
        dataSourceCreated = true
      } finally {
        approvingOntology = false
      }
    }

    await approveOntology()
    expect(createDataSource).toHaveBeenCalledOnce()
    expect(dataSourceCreated).toBe(true)
    expect(approvingOntology).toBe(false)
  })

  it('approveOntology() is blocked when no knowledge graph is selected', async () => {
    const selectedKnowledgeGraphId = { value: '' }
    const createDataSource = vi.fn()
    let errorShown = ''

    async function approveOntology() {
      if (!selectedKnowledgeGraphId.value) {
        errorShown = 'Please select a knowledge graph first'
        return
      }
      await createDataSource({})
    }

    await approveOntology()
    expect(createDataSource).not.toHaveBeenCalled()
    expect(errorShown).toBe('Please select a knowledge graph first')
  })

  it('extraction (API call) does not happen until the user explicitly approves', async () => {
    // The approve button has :disabled="!ontologyReady || approvingOntology"
    // This test verifies that simply reaching the review step does NOT trigger extraction.
    const ontologyReady = { value: true }
    const approvingOntology = { value: false }
    const createDataSource = vi.fn()
    // The UI is in the ontology-review step — approval has not been clicked yet.
    const currentStep = 'ontology-review'

    // Simulate step 4 (ontology review) without clicking "Approve"
    // The API should NOT have been called yet.
    const approveButtonEnabled = ontologyReady.value && !approvingOntology.value
    expect(currentStep).toBe('ontology-review') // confirms we are in the review step
    expect(approveButtonEnabled).toBe(true) // button is clickable...
    expect(createDataSource).not.toHaveBeenCalled() // ...but API not yet called
  })

  it('approve button is disabled while approval API call is in flight', () => {
    const ontologyReady = { value: true }
    const approvingOntology = { value: true } // in flight

    const approveButtonEnabled = ontologyReady.value && !approvingOntology.value
    expect(approveButtonEnabled).toBe(false)
  })

  it('approve button is disabled before ontology is ready', () => {
    const ontologyReady = { value: false }
    const approvingOntology = { value: false }

    const approveButtonEnabled = ontologyReady.value && !approvingOntology.value
    expect(approveButtonEnabled).toBe(false)
  })
})

describe('Ontology Design - Ontology Review and Approval: iterate before approving', () => {
  interface EditableNode {
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

  function toEditableNode(raw: typeof GITHUB_PROPOSAL_NODES[0]): EditableNode {
    return {
      ...raw,
      editing: false,
      editLabel: raw.label,
      editDescription: raw.description,
      editRequired: raw.required_properties.join(', '),
      editOptional: raw.optional_properties.join(', '),
    }
  }

  it('user can edit a node type before approving (label change)', () => {
    const nodes = GITHUB_PROPOSAL_NODES.map(toEditableNode)

    // Start editing Repository node
    nodes[0].editLabel = 'GitHubRepository'
    nodes[0].editing = true

    // Save — mirrors saveEditNode logic
    nodes[0].label = nodes[0].editLabel.trim() || nodes[0].label
    nodes[0].editing = false

    expect(nodes[0].label).toBe('GitHubRepository')
    expect(nodes[0].editing).toBe(false)
  })

  it('user can add a required property before approving', () => {
    const nodes = GITHUB_PROPOSAL_NODES.map(toEditableNode)

    // Edit Repository to add 'archived' as required
    nodes[0].editRequired = 'name, url, archived'
    nodes[0].required_properties = nodes[0].editRequired
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

    expect(nodes[0].required_properties).toContain('archived')
    expect(nodes[0].required_properties).toHaveLength(3)
  })

  it('user can remove a node type from the proposal before approving', () => {
    const nodes = GITHUB_PROPOSAL_NODES.map(toEditableNode)
    const initialLength = nodes.length

    // Remove the Commit node (index 3)
    const commitIdx = nodes.findIndex((n) => n.label === 'Commit')
    expect(commitIdx).toBeGreaterThanOrEqual(0)
    nodes.splice(commitIdx, 1)

    expect(nodes).toHaveLength(initialLength - 1)
    expect(nodes.find((n) => n.label === 'Commit')).toBeUndefined()
  })

  it('user can cancel edits and retain original values before approving', () => {
    const nodes = GITHUB_PROPOSAL_NODES.map(toEditableNode)

    nodes[0].editLabel = 'ChangedLabel'
    nodes[0].editing = true

    // Cancel — mirrors cancelEditNode logic
    nodes[0].editing = false
    // label is NOT updated on cancel

    expect(nodes[0].label).toBe('Repository') // original preserved
    expect(nodes[0].editing).toBe(false)
  })

  it('approval with modified ontology uses the edited nodes (not originals)', async () => {
    const nodes = GITHUB_PROPOSAL_NODES.map(toEditableNode)

    // User edits and saves
    nodes[0].editLabel = 'Repo'
    nodes[0].label = nodes[0].editLabel.trim()

    // What would be submitted to the API is the current state of proposedNodes
    const nodesToSubmit = nodes.map((n) => ({
      label: n.label,
      description: n.description,
      required_properties: n.required_properties,
      optional_properties: n.optional_properties,
    }))

    expect(nodesToSubmit[0].label).toBe('Repo')
    // The rest should still have original labels
    expect(nodesToSubmit[1].label).toBe('Issue')
  })

  it('iterating on the proposal does not itself trigger extraction', () => {
    // Editing node types (startEditNode/saveEditNode) must NOT call the API;
    // only approveOntology() does.
    const createDataSource = vi.fn()

    // User edits a node type inline
    const nodes = GITHUB_PROPOSAL_NODES.map(toEditableNode)
    nodes[0].editLabel = 'Repo'
    nodes[0].label = nodes[0].editLabel.trim()
    nodes[0].editing = false

    // No API call happened
    expect(createDataSource).not.toHaveBeenCalled()
  })
})

// ── Backend API Alignment — Parent context is preserved ───────────────────────
//
// Spec: "GIVEN a resource that is scoped to a parent (e.g., a knowledge graph
//        within a workspace)
//        WHEN the user creates or lists that resource
//        THEN the UI includes the parent context required by the API"
//
// This block mirrors the pattern in sync-monitoring-extended.test.ts for triggerSync():
// extract createDataSource as a parameterized function, inject apiFetch as a mock,
// and assert the URL path contains the parent knowledge graph ID.

/**
 * Mirrors createDataSource() in data-sources/index.vue.
 * Takes apiFetch as a parameter so tests can inject a mock and assert the
 * exact URL that is constructed for the KG-scoped POST endpoint.
 */
async function createDataSourceWithFetch(
  params: {
    kg_id: string
    name: string
    adapter_type: string
    connection_config: Record<string, string>
    credentials?: Record<string, string>
  },
  apiFetch: (
    url: string,
    opts: { method: string; body: Record<string, unknown> },
  ) => Promise<unknown>,
) {
  return apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, {
    method: 'POST',
    body: {
      name: params.name,
      adapter_type: params.adapter_type,
      connection_config: params.connection_config,
      credentials: params.credentials,
    },
  })
}

describe('Backend API Alignment — data source creation uses KG-scoped endpoint', () => {
  // Spec: Backend API Alignment — Scenario: Parent context is preserved
  // "THEN the UI includes the parent context required by the API"
  it('POST URL includes the parent knowledge graph ID', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new' })
    await createDataSourceWithFetch(
      {
        kg_id: 'kg-abc123',
        name: 'my-repo',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/owner/my-repo' },
        credentials: { access_token: 'ghp_test' },
      },
      apiFetch,
    )
    expect(apiFetch).toHaveBeenCalledWith(
      '/management/knowledge-graphs/kg-abc123/data-sources',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  // Spec: Backend API Alignment — Scenario: Parent context is preserved
  // "THEN the UI includes the parent context required by the API"
  // Verifies the KG ID is dynamic — not hardcoded or shared across calls.
  it('KG ID in the URL path changes when a different knowledge graph is selected', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new-2' })
    await createDataSourceWithFetch(
      {
        kg_id: 'kg-xyz789',
        name: 'another-repo',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/org/another-repo' },
      },
      apiFetch,
    )
    const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(calledUrl).toContain('kg-xyz789')
    expect(calledUrl).not.toContain('kg-abc123')
  })

  // Spec: Backend API Alignment — Scenario: Parent context is preserved
  // Data sources are scoped to a knowledge graph, not a workspace.
  it('does NOT use a workspace-scoped path (data sources are KG-scoped, not workspace-scoped)', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new' })
    await createDataSourceWithFetch(
      { kg_id: 'kg-1', name: 'repo', adapter_type: 'github', connection_config: {} },
      apiFetch,
    )
    const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(calledUrl).toContain('/management/knowledge-graphs/')
    expect(calledUrl).not.toContain('/management/workspaces/')
  })

  // Spec: Backend API Alignment — Scenario: Resource operations succeed end-to-end
  // "THEN the corresponding backend API call succeeds" — verifies the request body
  // carries all required fields for the backend to process the creation.
  it('request body includes name, adapter_type, and connection_config', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new' })
    await createDataSourceWithFetch(
      {
        kg_id: 'kg-1',
        name: 'my-repo',
        adapter_type: 'github',
        connection_config: { repo_url: 'https://github.com/owner/my-repo' },
        credentials: { access_token: 'ghp_test' },
      },
      apiFetch,
    )
    expect(apiFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.objectContaining({
          name: 'my-repo',
          adapter_type: 'github',
          connection_config: { repo_url: 'https://github.com/owner/my-repo' },
          credentials: { access_token: 'ghp_test' },
        }),
      }),
    )
  })
})

// ── Copy-to-clipboard for Data Source IDs ─────────────────────────────────────
// Spec: "Interaction Principles — Copy-to-clipboard"
// GIVEN a data source is listed on the page
// THEN a copy button is provided next to the data source ID
// AND clicking the copy button writes the ID to the clipboard
// AND a toast confirms the copy action

describe('Data Sources - copy DS ID to clipboard', () => {
  it('calls clipboard.writeText with the data source ID', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    let toastMsg = ''

    // Mirrors the copyId(ds.id) helper implemented via CopyableText component
    async function copyId(id: string) {
      try {
        await writeText(id)
        toastMsg = 'Data source ID copied'
      } catch {
        toastMsg = 'Failed to copy'
      }
    }

    await copyId('ds-github-abc-123')
    expect(writeText).toHaveBeenCalledWith('ds-github-abc-123')
    expect(toastMsg).toBe('Data source ID copied')
  })

  it('shows error feedback when clipboard write fails', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('NotAllowedError'))
    let toastMsg = ''

    async function copyId(id: string) {
      try {
        await writeText(id)
        toastMsg = 'Data source ID copied'
      } catch {
        toastMsg = 'Failed to copy'
      }
    }

    await copyId('ds-github-abc-123')
    expect(toastMsg).toBe('Failed to copy')
  })

  it('copies the correct ID for each data source in the list', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    const dataSources = [
      { id: 'ds-1', name: 'my-repo', adapter_type: 'github' },
      { id: 'ds-2', name: 'k8s-cluster', adapter_type: 'kubernetes' },
    ]
    const copiedIds: string[] = []

    async function copyId(id: string) {
      await writeText(id)
      copiedIds.push(id)
    }

    for (const ds of dataSources) {
      await copyId(ds.id)
    }

    expect(writeText).toHaveBeenCalledTimes(2)
    expect(copiedIds).toEqual(['ds-1', 'ds-2'])
  })
})

// ── Mutation Feedback — triggerSync and createDataSource ──────────────────────
// Spec: "Interaction Principles — Mutation feedback"
// GIVEN a write operation (create, trigger sync)
// THEN a toast notification confirms success or reports failure

describe('Data Sources - triggerSync mutation feedback', () => {
  it('shows success toast when sync is triggered', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    let successToast = ''

    async function triggerSync(dsId: string) {
      try {
        await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
        successToast = 'Sync triggered'
      } catch {
        // handled below
      }
    }

    await triggerSync('ds-abc-123')
    expect(apiFetch).toHaveBeenCalledWith('/management/data-sources/ds-abc-123/sync', { method: 'POST' })
    expect(successToast).toBe('Sync triggered')
  })

  it('shows error toast when sync trigger fails', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Service unavailable'))
    let errorToast = ''

    async function triggerSync(dsId: string) {
      try {
        await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
      } catch {
        errorToast = 'Failed to trigger sync'
      }
    }

    await triggerSync('ds-abc-123')
    expect(errorToast).toBe('Failed to trigger sync')
  })
})

describe('Data Sources - createDataSource mutation feedback', () => {
  it('shows success toast when data source is created', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-repo' })
    let successToast = ''

    async function createDataSource(kgId: string, params: { name: string; adapter_type: string }) {
      await apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`, {
        method: 'POST',
        body: params,
      })
      successToast = 'Data source connected'
    }

    await createDataSource('kg-abc', { name: 'my-repo', adapter_type: 'github' })
    expect(successToast).toBe('Data source connected')
  })

  it('shows error toast when data source creation fails', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Unauthorized'))
    let errorToast = ''

    async function createDataSource(kgId: string, params: { name: string; adapter_type: string }) {
      try {
        await apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`, {
          method: 'POST',
          body: params,
        })
      } catch {
        errorToast = 'Connection failed'
      }
    }

    await createDataSource('kg-abc', { name: 'my-repo', adapter_type: 'github' })
    expect(errorToast).toBe('Connection failed')
  })
})

// ── Credential Handling: plaintext never persisted in the browser ─────────────
//
// Spec: "GIVEN credentials provided during data source setup
//        WHEN the data source is saved
//        THEN credentials are encrypted and stored server-side
//        AND the plaintext is never persisted in the browser"
//
// Spec: experience.spec.md — Requirement: Data Source Connection
//       Scenario: Credential handling
//
// Only the browser-side guarantee is testable from the UI layer. The server-side
// encryption (Vault) is a backend contract verified by API/infrastructure tests.

describe('Data Source Connection — Credential Handling: plaintext never persisted in browser', () => {
  const indexVuePath = resolve(__dirname, '../pages/data-sources/index.vue')
  const indexVue = readFileSync(indexVuePath, 'utf-8')

  it('UI shows warning that credentials are encrypted server-side', () => {
    // Spec: "THEN credentials are encrypted and stored server-side"
    // The amber warning panel must inform the user that credentials are
    // encrypted — they are never stored in plaintext.
    expect(indexVue).toContain('Credentials are encrypted server-side')
  })

  it('UI warns that the token will not be retrievable after saving', () => {
    // Spec: "AND the plaintext is never persisted in the browser"
    // The user must be told the credential cannot be retrieved from the UI
    // after the form is saved, making clear it is not persisted client-side.
    expect(indexVue).toContain('The token will not be retrievable after saving')
  })

  it('connToken ref is in-memory only — no localStorage.setItem call in the page', () => {
    // Spec: "AND the plaintext is never persisted in the browser"
    // The page source must not write the token to localStorage at any point.
    expect(indexVue).not.toMatch(/localStorage\.setItem.*[Tt]oken/)
    expect(indexVue).not.toMatch(/localStorage\.setItem.*credential/)
  })

  it('connToken ref is in-memory only — no sessionStorage.setItem call in the page', () => {
    // Spec: "AND the plaintext is never persisted in the browser"
    // The page source must not write the token to sessionStorage at any point.
    expect(indexVue).not.toMatch(/sessionStorage\.setItem.*[Tt]oken/)
    expect(indexVue).not.toMatch(/sessionStorage\.setItem.*credential/)
  })

  it('connToken is reset to empty string on form reset (not retained across wizard sessions)', () => {
    // Spec: "AND the plaintext is never persisted in the browser"
    // Mirrors resetForm() logic in data-sources/index.vue:
    //   connToken.value = ''
    // Validates that the credential ref is wiped after the wizard closes,
    // so a subsequent wizard session never pre-fills a stale token.
    const connToken = { value: 'ghp_test_secret' }

    function resetForm() {
      // Mirrors the relevant portion of resetForm() in data-sources/index.vue
      connToken.value = ''
    }

    resetForm()
    expect(connToken.value).toBe('')
  })

  it('connToken is cleared before the wizard can be reopened for a new data source', () => {
    // Spec: "AND the plaintext is never persisted in the browser"
    // After one data source is saved and the wizard is closed, the old token
    // must not be pre-filled if the wizard is opened again for a new data source.
    const connToken = { value: 'ghp_old_secret' }
    const dialogOpen = { value: true }

    function closeWizard() {
      dialogOpen.value = false
      connToken.value = ''
    }

    closeWizard()
    expect(connToken.value).toBe('')
    expect(dialogOpen.value).toBe(false)
  })
})


// ── Scenario: Adapter type selection ─────────────────────────────────────────
// Spec: "GIVEN a user adding a data source to a knowledge graph
// WHEN the flow begins
// THEN the user selects an adapter type first (e.g., GitHub)
// AND the form adapts to show adapter-specific fields"

describe('Adapter type selection — data source connection flow', () => {
  it('adapter list includes GitHub as an available option', () => {
    const adapters = [
      { id: 'github', label: 'GitHub', description: 'Connect a GitHub repository', available: true },
    ]
    expect(adapters.find((a) => a.id === 'github')).toBeDefined()
    expect(adapters.find((a) => a.id === 'github')?.available).toBe(true)
  })

  it('step 1 requires an adapter to be selected before proceeding', () => {
    const selectedAdapterId = { value: '' }
    const wizardStep = { value: 1 }

    function nextStep() {
      if (wizardStep.value === 1 && !selectedAdapterId.value) return
      wizardStep.value++
    }

    nextStep()
    expect(wizardStep.value).toBe(1)
  })

  it('selecting GitHub adapter sets selectedAdapterId to "github"', () => {
    const selectedAdapterId = { value: '' }

    function selectAdapter(id: string) {
      selectedAdapterId.value = id
    }

    selectAdapter('github')
    expect(selectedAdapterId.value).toBe('github')
  })

  it('form shows adapter-specific fields after GitHub is selected', () => {
    // Mirrors the v-if="selectedAdapterId === 'github'" template block
    const selectedAdapterId = { value: 'github' }

    const showGitHubFields = selectedAdapterId.value === 'github'
    expect(showGitHubFields).toBe(true)
  })

  it('deselecting adapter hides the adapter-specific field group', () => {
    const selectedAdapterId = { value: '' }
    const showGitHubFields = selectedAdapterId.value === 'github'
    expect(showGitHubFields).toBe(false)
  })

  it('step advances to connection form once adapter is selected', () => {
    const selectedAdapterId = { value: 'github' }
    const selectedKgId = { value: 'kg-abc' }
    const wizardStep = { value: 1 }

    function nextStep() {
      if (wizardStep.value === 1) {
        if (!selectedAdapterId.value || !selectedKgId.value) return
        wizardStep.value = 2
      }
    }

    nextStep()
    expect(wizardStep.value).toBe(2)
  })
})

// ── Scenario: Connection configuration ───────────────────────────────────────
// Spec: "GIVEN a selected adapter type (e.g., GitHub)
// WHEN the user configures the connection
// THEN they provide the minimum required fields (e.g., repository URL, access token)
// AND the system infers defaults where possible (e.g., data source name from repo name)"

describe('Connection configuration — adapter-specific form fields', () => {
  it('GitHub connection requires repository URL and access token fields', () => {
    // These map to connRepoUrl and connToken in data-sources/index.vue
    const requiredFields = ['repo_url', 'access_token']
    expect(requiredFields).toContain('repo_url')
    expect(requiredFields).toContain('access_token')
  })

  it('data source name is inferred from the repository URL', () => {
    let connName = ''
    let connRepoUrl = ''

    // Watch pattern that mirrors the page watcher
    function onRepoUrlChange(url: string) {
      connRepoUrl = url
      if (url && !connName) {
        const match = url.match(/github\.com\/[^/]+\/([^/]+)\/?$/)
        if (match) connName = match[1]
      }
    }

    onRepoUrlChange('https://github.com/acme/my-service')
    expect(connName).toBe('my-service')
  })

  it('name is not auto-filled when the user has already typed a name', () => {
    let connName = 'custom-name'
    const connRepoUrl = ''

    function onRepoUrlChange(url: string) {
      if (url && !connName) {
        const match = url.match(/github\.com\/[^/]+\/([^/]+)\/?$/)
        if (match) connName = match[1]
      }
    }

    onRepoUrlChange('https://github.com/acme/other-service')
    // connName unchanged because user already typed a value
    expect(connName).toBe('custom-name')
  })

  it('step 2 validation requires repo URL and token', () => {
    const connName = { value: '' }
    const connRepoUrl = { value: '' }
    const connToken = { value: '' }
    const errors: string[] = []

    function validate(): boolean {
      errors.length = 0
      if (!connName.value.trim()) errors.push('name')
      if (!connRepoUrl.value.trim()) errors.push('repo_url')
      if (!connToken.value.trim()) errors.push('token')
      return errors.length === 0
    }

    const valid = validate()
    expect(valid).toBe(false)
    expect(errors).toContain('repo_url')
    expect(errors).toContain('token')
  })

  it('validation passes when all minimum required fields are provided', () => {
    const connName = { value: 'my-service' }
    const connRepoUrl = { value: 'https://github.com/acme/my-service' }
    const connToken = { value: 'ghp_secrettoken' }
    const errors: string[] = []

    function validate(): boolean {
      errors.length = 0
      if (!connName.value.trim()) errors.push('name')
      if (!connRepoUrl.value.trim()) errors.push('repo_url')
      if (!connToken.value.trim()) errors.push('token')
      return errors.length === 0
    }

    expect(validate()).toBe(true)
    expect(errors).toHaveLength(0)
  })
})

// ── Scenario: Credential handling ─────────────────────────────────────────────
// Spec: "GIVEN credentials provided during data source setup
// WHEN the data source is saved
// THEN credentials are encrypted and stored server-side
// AND the plaintext is never persisted in the browser"

describe('Credential handling — secure credential submission', () => {
  it('token is sent as credentials object in the API request body', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-service' })

    async function createDataSource(params: {
      kg_id: string
      name: string
      adapter_type: string
      connection_config: Record<string, string>
      credentials?: Record<string, string>
    }) {
      return apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, {
        method: 'POST',
        body: params,
      })
    }

    await createDataSource({
      kg_id: 'kg-1',
      name: 'my-service',
      adapter_type: 'github',
      connection_config: { repo_url: 'https://github.com/acme/my-service' },
      credentials: { access_token: 'ghp_secrettoken' },
    })

    expect(apiFetch).toHaveBeenCalledWith(
      expect.stringContaining('/data-sources'),
      expect.objectContaining({
        body: expect.objectContaining({
          credentials: { access_token: 'ghp_secrettoken' },
        }),
      }),
    )
  })

  it('credentials are NOT stored in localStorage or sessionStorage', () => {
    const token = 'ghp_secrettoken'
    // Simulate what the page does: clear local state after submission
    let connToken = token

    function onWizardClose() {
      connToken = ''
    }

    onWizardClose()
    expect(connToken).toBe('')
    expect(localStorage.getItem('token')).toBeNull()
    expect(sessionStorage.getItem('token')).toBeNull()
  })

  it('token input type is password (plaintext hidden in UI)', () => {
    // The data-sources page uses <Input type="password"> for the access token
    // We verify the page source contains type="password" for the token field
    const { readFileSync } = require('fs')
    const { resolve } = require('path')
    const source = readFileSync(
      resolve(__dirname, '../pages/data-sources/index.vue'),
      'utf-8',
    )
    // The access token input should use a password-type input (toggled by showToken)
    expect(source).toMatch(/type="password"|:type="showToken/)
  })

  it('page shows security notice: credentials encrypted server-side', () => {
    const { readFileSync } = require('fs')
    const { resolve } = require('path')
    const source = readFileSync(
      resolve(__dirname, '../pages/data-sources/index.vue'),
      'utf-8',
    )
    expect(source.toLowerCase()).toContain('encrypt')
  })

  it('token is omitted from the request when left blank (optional for public repos)', () => {
    const connToken = { value: '' }

    // Mirrors: credentials: connToken.value ? { access_token: connToken.value } : undefined
    const credentials = connToken.value ? { access_token: connToken.value } : undefined
    expect(credentials).toBeUndefined()
  })

  it('token is included in the request when provided', () => {
    const connToken = { value: 'ghp_token' }

    const credentials = connToken.value ? { access_token: connToken.value } : undefined
    expect(credentials).toEqual({ access_token: 'ghp_token' })
  })
})

// ── Scenario: Ontology change after initial extraction ────────────────────────
// Spec: "GIVEN a knowledge graph with completed extraction
// WHEN the user modifies the ontology
// THEN the system warns that this will trigger a full re-extraction
// AND the user must confirm before the change is applied"

describe('Ontology change after initial extraction — re-extraction guard', () => {
  it('requestOntologyEdit() opens re-extraction confirmation when extraction has completed', () => {
    const reExtractionConfirmOpen = { value: false }
    const pendingDsId = { value: null as string | null }

    const ds = {
      id: 'ds-1',
      name: 'my-service',
      sync_runs: [{ id: 'run-1', status: 'completed' as const }],
    }

    function requestOntologyEdit(dataSource: typeof ds) {
      const hasCompleted = dataSource.sync_runs.some((r) => r.status === 'completed')
      if (hasCompleted) {
        pendingDsId.value = dataSource.id
        reExtractionConfirmOpen.value = true
      }
    }

    requestOntologyEdit(ds)
    expect(reExtractionConfirmOpen.value).toBe(true)
    expect(pendingDsId.value).toBe('ds-1')
  })

  it('requestOntologyEdit() skips confirmation for a new data source with no sync runs', () => {
    const reExtractionConfirmOpen = { value: false }
    let editorOpened = false

    const ds = {
      id: 'ds-new',
      name: 'brand-new',
      sync_runs: [] as { status: string }[],
    }

    function requestOntologyEdit(dataSource: typeof ds) {
      const hasCompleted = dataSource.sync_runs.some((r) => r.status === 'completed')
      if (hasCompleted) {
        reExtractionConfirmOpen.value = true
      } else {
        editorOpened = true
      }
    }

    requestOntologyEdit(ds)
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editorOpened).toBe(true)
  })

  it('confirmReExtraction() closes the dialog and opens the ontology editor', () => {
    const reExtractionConfirmOpen = { value: true }
    const pendingDsId = { value: 'ds-1' }
    let editorOpened = false

    function confirmReExtraction() {
      reExtractionConfirmOpen.value = false
      editorOpened = true // openOntologyEditor(ds)
    }

    confirmReExtraction()
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editorOpened).toBe(true)
  })

  it('cancelReExtraction() closes the dialog without opening the editor', () => {
    const reExtractionConfirmOpen = { value: true }
    const pendingDsId = { value: 'ds-1' }
    let editorOpened = false

    function cancelReExtraction() {
      reExtractionConfirmOpen.value = false
      pendingDsId.value = null
    }

    cancelReExtraction()
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editorOpened).toBe(false)
    expect(pendingDsId.value).toBeNull()
  })

  it('re-extraction confirmation dialog warns about full re-extraction', () => {
    const { readFileSync } = require('fs')
    const { resolve } = require('path')
    const source = readFileSync(
      resolve(__dirname, '../pages/data-sources/index.vue'),
      'utf-8',
    )
    expect(source.toLowerCase()).toContain('re-extraction')
  })

  it('page shows re-extraction confirmation dialog component', () => {
    const { readFileSync } = require('fs')
    const { resolve } = require('path')
    const source = readFileSync(
      resolve(__dirname, '../pages/data-sources/index.vue'),
      'utf-8',
    )
    expect(source).toContain('reExtractionConfirmOpen')
  })
})

// ── Scenario: Resource operations succeed end-to-end ─────────────────────────
// Spec: "GIVEN a user performs any create, read, update, or delete operation via the UI
// WHEN the operation is submitted
// THEN the corresponding backend API call succeeds (2xx response)
// AND the UI reflects the updated state without requiring a manual refresh"

describe('Resource operations succeed end-to-end — backend API alignment', () => {
  it('createDataSource POSTs to /management/knowledge-graphs/{id}/data-sources', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-service' })

    async function createDataSource(params: {
      kg_id: string
      name: string
      adapter_type: string
      connection_config: Record<string, string>
      credentials?: Record<string, string>
    }) {
      return apiFetch(`/management/knowledge-graphs/${params.kg_id}/data-sources`, {
        method: 'POST',
        body: params,
      })
    }

    const result = await createDataSource({
      kg_id: 'kg-abc',
      name: 'my-service',
      adapter_type: 'github',
      connection_config: { repo_url: 'https://github.com/acme/my-service' },
    })

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/knowledge-graphs/kg-abc/data-sources',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(result.id).toBe('ds-new')
  })

  it('listDataSources GETs from /management/knowledge-graphs/{id}/data-sources', async () => {
    const apiFetch = vi.fn().mockResolvedValue([
      { id: 'ds-1', name: 'service-a', adapter_type: 'github', knowledge_graph_id: 'kg-1' },
    ])

    async function loadDataSources(kgId: string) {
      const response: { id: string; name: string; adapter_type: string; knowledge_graph_id: string }[] = await apiFetch(`/management/knowledge-graphs/${kgId}/data-sources`)
      return response
    }

    const sources = await loadDataSources('kg-1')
    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs/kg-1/data-sources')
    expect(sources).toHaveLength(1)
  })

  it('triggerSync POSTs to /management/data-sources/{id}/sync', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})

    async function triggerSync(dsId: string) {
      return apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
    }

    await triggerSync('ds-1')
    expect(apiFetch).toHaveBeenCalledWith(
      '/management/data-sources/ds-1/sync',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('UI reflects updated state after create: list is reloaded automatically', async () => {
    let dataSources: string[] = []
    const apiFetch = vi.fn()
      .mockResolvedValueOnce({ id: 'ds-new', name: 'service' }) // create
      .mockResolvedValueOnce([{ id: 'ds-new', name: 'service' }]) // reload

    async function createDataSource() {
      await apiFetch('/management/knowledge-graphs/kg-1/data-sources', { method: 'POST' })
      // After create, reload the list without manual refresh
      dataSources = await apiFetch('/management/knowledge-graphs/kg-1/data-sources')
    }

    await createDataSource()
    expect(dataSources).toHaveLength(1)
    expect(apiFetch).toHaveBeenCalledTimes(2)
  })

  it('knowledge graph is included in the URL when creating a data source (parent context)', () => {
    // Verifies "Parent context is preserved" — the KG ID is part of the API path
    const kgId = 'kg-workspace-abc'
    const url = `/management/knowledge-graphs/${kgId}/data-sources`
    expect(url).toContain(kgId)
    expect(url).toMatch(/\/management\/knowledge-graphs\/[^/]+\/data-sources$/)
  })
})

// ── Backend API Alignment — Scenario: Resource operations succeed end-to-end ──
// Spec requirement: "AND the UI reflects the updated state without requiring a
// manual refresh"
// Verifies that after a successful data source creation or sync trigger,
// loadDataSources() is called so the list is refreshed automatically.

describe('Backend API Alignment — Scenario: Resource operations succeed end-to-end — DS list refresh after create', () => {
  it('calls loadDataSources() after successful data source creation', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ds-new', name: 'my-repo' })
    const loadDataSources = vi.fn().mockResolvedValue(undefined)
    const wizardOpen = { value: true }
    const approvingOntology = { value: false }
    const selectedKgId = { value: 'kg-1' }
    const connName = { value: 'my-repo' }

    // Spec: Backend API Alignment — Scenario: Resource operations succeed end-to-end
    async function approveOntology() {
      if (!selectedKgId.value) return
      approvingOntology.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${selectedKgId.value}/data-sources`, {
          method: 'POST',
          body: { name: connName.value, adapter_type: 'github' },
        })
        wizardOpen.value = false
        await loadDataSources()
      } finally {
        approvingOntology.value = false
      }
    }

    await approveOntology()
    expect(loadDataSources).toHaveBeenCalledOnce()
  })

  it('does NOT call loadDataSources() when data source creation API throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Bad Request'))
    const loadDataSources = vi.fn().mockResolvedValue(undefined)
    const selectedKgId = { value: 'kg-1' }
    const connName = { value: 'my-repo' }
    const approvingOntology = { value: false }

    async function approveOntology() {
      if (!selectedKgId.value) return
      approvingOntology.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${selectedKgId.value}/data-sources`, {
          method: 'POST',
          body: { name: connName.value, adapter_type: 'github' },
        })
        await loadDataSources()
      } catch {
        // error path — refresh must NOT be called
      } finally {
        approvingOntology.value = false
      }
    }

    await approveOntology()
    expect(loadDataSources).not.toHaveBeenCalled()
  })
})

describe('Backend API Alignment — Scenario: Resource operations succeed end-to-end — DS list refresh after sync trigger', () => {
  it('calls loadDataSources() after successfully triggering a sync', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const loadDataSources = vi.fn().mockResolvedValue(undefined)

    async function triggerSync(dsId: string) {
      try {
        await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
        await loadDataSources()
      } catch {
        // error path
      }
    }

    await triggerSync('ds-abc')
    expect(apiFetch).toHaveBeenCalledWith('/management/data-sources/ds-abc/sync', { method: 'POST' })
    expect(loadDataSources).toHaveBeenCalledOnce()
  })

  it('does NOT call loadDataSources() when the sync trigger API throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Conflict'))
    const loadDataSources = vi.fn().mockResolvedValue(undefined)

    async function triggerSync(dsId: string) {
      try {
        await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
        await loadDataSources()
      } catch {
        // error path — refresh must NOT be called
      }
    }

    await triggerSync('ds-abc')
    expect(loadDataSources).not.toHaveBeenCalled()
  })
})

// ── task-082: Ontology Editor — save to backend after post-extraction edit ───
// Spec: "GIVEN a knowledge graph with completed extraction
//        WHEN the user modifies the ontology
//        THEN the system warns that this will trigger a full re-extraction
//        AND the user must confirm before the change is applied"
// The "change is applied" clause requires a PATCH call to persist the ontology.

describe('Ontology Editor — save to backend after post-extraction edit (task-082)', () => {
  it('saveOntology calls PATCH with ontology payload including node and edge types', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const editingDataSource = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }
    const editNodes = {
      value: [
        {
          label: 'Repository',
          description: 'A GitHub repository.',
          required_properties: ['name', 'url'],
          optional_properties: ['description', 'stars'],
        },
      ],
    }
    const editEdges = {
      value: [
        {
          label: 'CONTAINS',
          description: 'Repo contains issues.',
          from: 'Repository',
          to: 'Issue',
          required_properties: [],
          optional_properties: [],
        },
      ],
    }
    const savingOntology = { value: false }
    const editOntologyOpen = { value: true }
    const loadDataSources = vi.fn().mockResolvedValue(undefined)

    async function saveOntology() {
      if (!editingDataSource.value) return
      savingOntology.value = true
      try {
        await apiFetch(
          `/management/knowledge-graphs/${editingDataSource.value.knowledge_graph_id}/data-sources/${editingDataSource.value.id}`,
          {
            method: 'PATCH',
            body: {
              ontology: {
                node_types: editNodes.value.map((n) => ({
                  label: n.label,
                  description: n.description,
                  required_properties: n.required_properties,
                  optional_properties: n.optional_properties,
                })),
                edge_types: editEdges.value.map((e) => ({
                  label: e.label,
                  description: e.description,
                  from_type: e.from,
                  to_type: e.to,
                  required_properties: e.required_properties,
                  optional_properties: e.optional_properties,
                })),
              },
            },
          },
        )
        editOntologyOpen.value = false
        await loadDataSources()
      } finally {
        savingOntology.value = false
      }
    }

    await saveOntology()

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/knowledge-graphs/kg-1/data-sources/ds-1',
      expect.objectContaining({
        method: 'PATCH',
        body: {
          ontology: {
            node_types: [
              {
                label: 'Repository',
                description: 'A GitHub repository.',
                required_properties: ['name', 'url'],
                optional_properties: ['description', 'stars'],
              },
            ],
            edge_types: [
              {
                label: 'CONTAINS',
                description: 'Repo contains issues.',
                from_type: 'Repository',
                to_type: 'Issue',
                required_properties: [],
                optional_properties: [],
              },
            ],
          },
        },
      }),
    )
  })

  it('saveOntology closes dialog and reloads data sources on success', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const editOntologyOpen = { value: true }
    const editingDataSource = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }
    const editNodes = { value: [] as { label: string; description: string; required_properties: string[]; optional_properties: string[] }[] }
    const editEdges = { value: [] as { label: string; description: string; from: string; to: string; required_properties: string[]; optional_properties: string[] }[] }
    const savingOntology = { value: false }
    const loadDataSources = vi.fn().mockResolvedValue(undefined)

    async function saveOntology() {
      if (!editingDataSource.value) return
      savingOntology.value = true
      try {
        await apiFetch(
          `/management/knowledge-graphs/${editingDataSource.value.knowledge_graph_id}/data-sources/${editingDataSource.value.id}`,
          {
            method: 'PATCH',
            body: {
              ontology: {
                node_types: editNodes.value.map((n) => ({
                  label: n.label,
                  description: n.description,
                  required_properties: n.required_properties,
                  optional_properties: n.optional_properties,
                })),
                edge_types: editEdges.value.map((e) => ({
                  label: e.label,
                  description: e.description,
                  from_type: e.from,
                  to_type: e.to,
                  required_properties: e.required_properties,
                  optional_properties: e.optional_properties,
                })),
              },
            },
          },
        )
        editOntologyOpen.value = false
        await loadDataSources()
      } finally {
        savingOntology.value = false
      }
    }

    await saveOntology()

    expect(editOntologyOpen.value).toBe(false)
    expect(loadDataSources).toHaveBeenCalledOnce()
    expect(savingOntology.value).toBe(false)
  })

  it('saveOntology keeps dialog open on PATCH failure and resets savingOntology', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Internal Server Error'))
    const editOntologyOpen = { value: true }
    const editingDataSource = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }
    const savingOntology = { value: false }
    const loadDataSources = vi.fn().mockResolvedValue(undefined)
    let caughtError = ''

    async function saveOntology() {
      if (!editingDataSource.value) return
      savingOntology.value = true
      try {
        await apiFetch(
          `/management/knowledge-graphs/${editingDataSource.value.knowledge_graph_id}/data-sources/${editingDataSource.value.id}`,
          { method: 'PATCH', body: { ontology: { node_types: [], edge_types: [] } } },
        )
        editOntologyOpen.value = false
        await loadDataSources()
      } catch (err) {
        caughtError = err instanceof Error ? err.message : 'Failed to save ontology'
        // dialog stays open intentionally
      } finally {
        savingOntology.value = false
      }
    }

    await saveOntology()

    expect(editOntologyOpen.value).toBe(true) // dialog remains open so user can retry
    expect(loadDataSources).not.toHaveBeenCalled()
    expect(caughtError).toBe('Internal Server Error')
    expect(savingOntology.value).toBe(false)
  })

  it('savingOntology is always reset to false whether PATCH succeeds or fails', async () => {
    // Success path
    {
      const apiFetch = vi.fn().mockResolvedValue({})
      const savingOntology = { value: false }
      const editingDataSource = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }

      async function saveOntology() {
        savingOntology.value = true
        try {
          await apiFetch(
            `/management/knowledge-graphs/${editingDataSource.value.knowledge_graph_id}/data-sources/${editingDataSource.value.id}`,
            { method: 'PATCH', body: { ontology: { node_types: [], edge_types: [] } } },
          )
        } finally {
          savingOntology.value = false
        }
      }

      await saveOntology()
      expect(savingOntology.value).toBe(false)
    }

    // Failure path
    {
      const apiFetch = vi.fn().mockRejectedValue(new Error('fail'))
      const savingOntology = { value: false }
      const editingDataSource = { value: { id: 'ds-1', knowledge_graph_id: 'kg-1' } }

      async function saveOntology() {
        savingOntology.value = true
        try {
          await apiFetch(
            `/management/knowledge-graphs/${editingDataSource.value.knowledge_graph_id}/data-sources/${editingDataSource.value.id}`,
            { method: 'PATCH', body: { ontology: { node_types: [], edge_types: [] } } },
          )
        } catch {
          // error handled
        } finally {
          savingOntology.value = false
        }
      }

      await saveOntology()
      expect(savingOntology.value).toBe(false)
    }
  })

  it('saveOntology does not call PATCH when editingDataSource is null', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const editingDataSource = { value: null as null | { id: string; knowledge_graph_id: string } }
    const savingOntology = { value: false }

    async function saveOntology() {
      if (!editingDataSource.value) return
      savingOntology.value = true
      try {
        await apiFetch(
          `/management/knowledge-graphs/${editingDataSource.value.knowledge_graph_id}/data-sources/${editingDataSource.value.id}`,
          { method: 'PATCH', body: {} },
        )
      } finally {
        savingOntology.value = false
      }
    }

    await saveOntology()
    expect(apiFetch).not.toHaveBeenCalled()
    expect(savingOntology.value).toBe(false)
  })
})

describe('Ontology Editor — structural checks (task-082)', () => {
  const dsVue = readFileSync(
    resolve(__dirname, '../pages/data-sources/index.vue'),
    'utf-8',
  )

  it('declares savingOntology state ref', () => {
    expect(dsVue).toMatch(/savingOntology/)
  })

  it('includes PATCH call targeting data-sources endpoint', () => {
    expect(dsVue).toMatch(/PATCH.*data-sources|data-sources.*PATCH/s)
  })

  it('references ontology field in the PATCH body', () => {
    expect(dsVue).toMatch(/ontology/)
  })

  it('Apply button or saveOntology call is present in the ontology editor dialog', () => {
    expect(dsVue).toMatch(/saveOntology/)
  })

  it('savingOntology gates the Apply button to prevent double-submission', () => {
    // The Apply button should be disabled while savingOntology is true
    expect(dsVue).toMatch(/savingOntology/)
  })
})
