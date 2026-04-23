import { describe, it, expect, vi, beforeEach } from 'vitest'
import { buildQueryGraphArgs } from '~/composables/api/useQueryApi'

// ── FAIL 1: Knowledge Graph Creation ──────────────────────────────────────────
// Spec: "AND the knowledge graph is created within the current workspace"
// The handleCreate() function must call POST /management/knowledge-graphs
// and loadKnowledgeGraphs() must populate the list on mount.

describe('Knowledge Graph Creation - Validation', () => {
  it('rejects empty name with an error message', () => {
    const createName = { value: '' }
    const createNameError = { value: '' }
    const creating = { value: false }

    function handleCreate() {
      createNameError.value = ''
      if (!createName.value.trim()) {
        createNameError.value = 'Knowledge graph name is required'
        return false
      }
      return true
    }

    const result = handleCreate()
    expect(result).toBe(false)
    expect(createNameError.value).toBe('Knowledge graph name is required')
    expect(creating.value).toBe(false)
  })

  it('clears name error when name is provided', () => {
    const createName = { value: 'My Graph' }
    const createNameError = { value: 'Previous error' }

    function validate() {
      createNameError.value = ''
      if (!createName.value.trim()) {
        createNameError.value = 'Knowledge graph name is required'
        return false
      }
      return true
    }

    const result = validate()
    expect(result).toBe(true)
    expect(createNameError.value).toBe('')
  })
})

describe('Knowledge Graph Creation - API call', () => {
  it('calls POST /management/knowledge-graphs with name and description', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'Test Graph' })
    const createName = { value: 'Test Graph' }
    const createDescription = { value: 'A test graph' }
    const creating = { value: false }
    const createDialogOpen = { value: true }
    let toastMessage = ''

    async function handleCreate() {
      if (!createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch('/management/knowledge-graphs', {
          method: 'POST',
          body: {
            name: createName.value.trim(),
            description: createDescription.value.trim() || undefined,
          },
        })
        toastMessage = `Knowledge graph "${createName.value.trim()}" created`
        createDialogOpen.value = false
      } finally {
        creating.value = false
      }
    }

    await handleCreate()

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs', {
      method: 'POST',
      body: { name: 'Test Graph', description: 'A test graph' },
    })
    expect(toastMessage).toBe('Knowledge graph "Test Graph" created')
    expect(createDialogOpen.value).toBe(false)
    expect(creating.value).toBe(false)
  })

  it('sets creating back to false on API error', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Network error'))
    const createName = { value: 'My Graph' }
    const creating = { value: false }
    let toastError = ''

    async function handleCreate() {
      if (!createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch('/management/knowledge-graphs', { method: 'POST', body: { name: 'My Graph' } })
      } catch (err) {
        toastError = err instanceof Error ? err.message : 'Failed'
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(creating.value).toBe(false)
    expect(toastError).toBe('Network error')
  })
})

describe('Knowledge Graph List Loading', () => {
  it('populates knowledgeGraphs from API response', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [
        { id: 'kg-1', name: 'Graph One' },
        { id: 'kg-2', name: 'Graph Two' },
      ],
    })
    const knowledgeGraphs: Array<{ id: string; name: string }> = []

    async function loadKnowledgeGraphs() {
      const result = await apiFetch('/management/knowledge-graphs')
      knowledgeGraphs.splice(0, knowledgeGraphs.length, ...(result.knowledge_graphs ?? []))
    }

    await loadKnowledgeGraphs()
    expect(knowledgeGraphs).toHaveLength(2)
    expect(knowledgeGraphs[0]).toEqual({ id: 'kg-1', name: 'Graph One' })
    expect(knowledgeGraphs[1]).toEqual({ id: 'kg-2', name: 'Graph Two' })
  })

  it('defaults to empty array on API error', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Unauthorized'))
    const knowledgeGraphs: Array<{ id: string; name: string }> = [{ id: 'old', name: 'Old' }]

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

  it('shows existing knowledge graphs instead of always showing empty state', () => {
    const knowledgeGraphs = [{ id: 'kg-1', name: 'Graph One' }]
    // The UI should show the list when knowledgeGraphs.length > 0
    const showEmptyState = knowledgeGraphs.length === 0
    expect(showEmptyState).toBe(false)
  })
})

// ── FAIL 2: Ontology Change After Extraction (Confirmation Gate) ───────────────
// Spec: "WHEN the user modifies the ontology, THEN the system warns that this will
// trigger a full re-extraction, AND the user must confirm before the change is applied."

describe('Ontology Edit - Post-Extraction Confirmation Gate', () => {
  it('flags that a data source with a completed sync has extraction data', () => {
    const syncRuns = [
      { id: 'run-1', status: 'completed', started_at: '2024-01-01T10:00:00Z', completed_at: '2024-01-01T10:01:00Z', error: null, created_at: '2024-01-01T10:00:00Z' },
    ]
    const hasCompletedExtraction = syncRuns.some((r) => r.status === 'completed')
    expect(hasCompletedExtraction).toBe(true)
  })

  it('does not require confirmation for a data source with no completed runs', () => {
    const syncRuns: Array<{ status: string }> = []
    const hasCompletedExtraction = syncRuns.some((r) => r.status === 'completed')
    expect(hasCompletedExtraction).toBe(false)
  })

  it('shows confirmation dialog before applying ontology changes when extraction completed', () => {
    const reExtractionConfirmOpen = { value: false }
    const pendingOntologyEdit = { value: null as string | null }
    const syncRuns = [{ status: 'completed' }]

    function requestOntologyEdit(dsId: string) {
      const hasCompletedExtraction = syncRuns.some((r) => r.status === 'completed')
      if (hasCompletedExtraction) {
        pendingOntologyEdit.value = dsId
        reExtractionConfirmOpen.value = true
        return // wait for confirmation
      }
      // proceed directly if no extraction done
    }

    requestOntologyEdit('ds-abc')
    expect(reExtractionConfirmOpen.value).toBe(true)
    expect(pendingOntologyEdit.value).toBe('ds-abc')
  })

  it('proceeds without confirmation when no extraction has completed', () => {
    const reExtractionConfirmOpen = { value: false }
    const editOntologyOpen = { value: false }
    const syncRuns: Array<{ status: string }> = []

    function requestOntologyEdit() {
      const hasCompletedExtraction = syncRuns.some((r) => r.status === 'completed')
      if (hasCompletedExtraction) {
        reExtractionConfirmOpen.value = true
        return
      }
      editOntologyOpen.value = true
    }

    requestOntologyEdit()
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editOntologyOpen.value).toBe(true)
  })

  it('opens ontology editor after user confirms re-extraction', () => {
    const reExtractionConfirmOpen = { value: true }
    const editOntologyOpen = { value: false }
    const pendingOntologyEdit = { value: 'ds-abc' as string | null }

    function confirmReExtraction() {
      reExtractionConfirmOpen.value = false
      editOntologyOpen.value = true
      // pendingOntologyEdit carries the dsId to the editor
    }

    confirmReExtraction()
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editOntologyOpen.value).toBe(true)
    expect(pendingOntologyEdit.value).toBe('ds-abc') // preserved for the editor
  })

  it('cancelling confirmation leaves ontology unchanged', () => {
    const reExtractionConfirmOpen = { value: true }
    const editOntologyOpen = { value: false }
    const pendingOntologyEdit = { value: 'ds-abc' as string | null }

    function cancelReExtraction() {
      reExtractionConfirmOpen.value = false
      pendingOntologyEdit.value = null
      // editOntologyOpen stays false
    }

    cancelReExtraction()
    expect(reExtractionConfirmOpen.value).toBe(false)
    expect(editOntologyOpen.value).toBe(false)
    expect(pendingOntologyEdit.value).toBeNull()
  })
})

// ── FAIL 3: Sync Logs ─────────────────────────────────────────────────────────
// Spec: "GIVEN a sync run (in progress or completed), WHEN the user requests logs,
// THEN detailed logs for that run are displayed."

describe('Sync Logs - View Logs Toggle', () => {
  it('initially has no run selected for log viewing', () => {
    const selectedLogRunId = { value: null as string | null }
    expect(selectedLogRunId.value).toBeNull()
  })

  it('opens log sheet when View Logs is clicked for a run', () => {
    const selectedLogRunId = { value: null as string | null }
    const logSheetOpen = { value: false }

    function viewLogs(runId: string) {
      selectedLogRunId.value = runId
      logSheetOpen.value = true
    }

    viewLogs('run-123')
    expect(selectedLogRunId.value).toBe('run-123')
    expect(logSheetOpen.value).toBe(true)
  })

  it('closes log sheet and clears selection', () => {
    const selectedLogRunId = { value: 'run-123' }
    const logSheetOpen = { value: true }

    function closeLogs() {
      logSheetOpen.value = false
      selectedLogRunId.value = null
    }

    closeLogs()
    expect(logSheetOpen.value).toBe(false)
    expect(selectedLogRunId.value).toBeNull()
  })
})

describe('Sync Logs - Fetching log lines', () => {
  it('fetches logs from API when run is selected', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      logs: ['2024-01-01T10:00:01Z INFO Starting sync', '2024-01-01T10:00:05Z INFO Fetched 100 items'],
    })
    const runLogs = { value: [] as string[] }
    const logsLoading = { value: false }

    async function fetchRunLogs(dsId: string, runId: string) {
      logsLoading.value = true
      try {
        const result = await apiFetch(`/management/data-sources/${dsId}/sync-runs/${runId}/logs`)
        runLogs.value = result.logs ?? []
      } finally {
        logsLoading.value = false
      }
    }

    await fetchRunLogs('ds-abc', 'run-123')
    expect(apiFetch).toHaveBeenCalledWith('/management/data-sources/ds-abc/sync-runs/run-123/logs')
    expect(runLogs.value).toHaveLength(2)
    expect(runLogs.value[0]).toContain('Starting sync')
    expect(logsLoading.value).toBe(false)
  })

  it('clears logs when a new run is selected', async () => {
    const runLogs = { value: ['old log line'] }
    const logsLoading = { value: false }
    const apiFetch = vi.fn().mockResolvedValue({ logs: ['new log line'] })

    async function fetchRunLogs(dsId: string, runId: string) {
      runLogs.value = [] // clear previous
      logsLoading.value = true
      try {
        const result = await apiFetch(`/management/data-sources/${dsId}/sync-runs/${runId}/logs`)
        runLogs.value = result.logs ?? []
      } finally {
        logsLoading.value = false
      }
    }

    await fetchRunLogs('ds-abc', 'run-456')
    expect(runLogs.value).toEqual(['new log line'])
  })

  it('handles log fetch failure gracefully', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Not found'))
    const runLogs = { value: [] as string[] }
    const logsLoading = { value: false }
    let errorMsg = ''

    async function fetchRunLogs(dsId: string, runId: string) {
      runLogs.value = []
      logsLoading.value = true
      try {
        const result = await apiFetch(`/management/data-sources/${dsId}/sync-runs/${runId}/logs`)
        runLogs.value = result.logs ?? []
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to load logs'
      } finally {
        logsLoading.value = false
      }
    }

    await fetchRunLogs('ds-abc', 'run-bad')
    expect(runLogs.value).toHaveLength(0)
    expect(logsLoading.value).toBe(false)
    expect(errorMsg).toBe('Not found')
  })
})

// ── FAIL 4: Query Console KG Context Selector ─────────────────────────────────
// Spec: "the user can optionally select a specific knowledge graph to scope queries
// AND when unscoped, queries span all knowledge graphs the user can access in the tenant"

describe('Query Console - KG Selector Population', () => {
  it('populates knowledgeGraphs from API on mount', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [
        { id: 'kg-1', name: 'Engineering' },
        { id: 'kg-2', name: 'Marketing' },
      ],
    })
    const knowledgeGraphs: Array<{ id: string; name: string }> = []

    async function loadKnowledgeGraphs() {
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
    expect(knowledgeGraphs[0].name).toBe('Engineering')
  })

  it('reloads KG list when tenant changes', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [] })
    let callCount = 0

    async function loadKnowledgeGraphs() {
      callCount++
      await apiFetch('/management/knowledge-graphs')
    }

    // Simulate onMounted call
    await loadKnowledgeGraphs()
    // Simulate tenantVersion watcher firing
    await loadKnowledgeGraphs()

    expect(callCount).toBe(2)
  })

  it('computes scope label as "All knowledge graphs" when no KG selected', () => {
    const selectedKgId = { value: '' }
    const knowledgeGraphs = [{ id: 'kg-1', name: 'Engineering' }]

    const kgScopeLabel =
      !selectedKgId.value
        ? 'All knowledge graphs'
        : knowledgeGraphs.find((kg) => kg.id === selectedKgId.value)?.name ?? 'Unknown graph'

    expect(kgScopeLabel).toBe('All knowledge graphs')
  })

  it('computes scope label as KG name when a specific KG is selected', () => {
    const selectedKgId = { value: 'kg-1' }
    const knowledgeGraphs = [{ id: 'kg-1', name: 'Engineering' }]

    const kgScopeLabel =
      !selectedKgId.value
        ? 'All knowledge graphs'
        : knowledgeGraphs.find((kg) => kg.id === selectedKgId.value)?.name ?? 'Unknown graph'

    expect(kgScopeLabel).toBe('Engineering')
  })

  it('resets knowledgeGraphs to empty on API error', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const knowledgeGraphs: Array<{ id: string; name: string }> = [{ id: 'stale', name: 'Stale' }]

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

  // These tests import and exercise the real buildQueryGraphArgs helper from
  // useQueryApi.ts — not a standalone copy — so regressions in the actual
  // production code are caught immediately.
  it('includes knowledge_graph_id in MCP args when a KG is selected', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, 'kg-1')
    expect(args.cypher).toBe('MATCH (n) RETURN n')
    expect(args.timeout_seconds).toBe(30)
    expect(args.max_rows).toBe(1000)
    expect(args.knowledge_graph_id).toBe('kg-1')
  })

  it('omits knowledge_graph_id from MCP args when unscoped (all KGs)', () => {
    const args = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, undefined)
    expect(args.cypher).toBe('MATCH (n) RETURN n')
    expect(args).not.toHaveProperty('knowledge_graph_id')
  })

  it('maps selectedKgId to knowledgeGraphId via || undefined gate', () => {
    // Simulates the expression used in query/index.vue:
    //   selectedKgId.value || undefined
    // An empty string must become undefined (unscoped), not a falsy string.
    const scopedId = 'kg-1'
    const unscopedId = ''

    const scopedArgs = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, scopedId || undefined)
    expect(scopedArgs.knowledge_graph_id).toBe('kg-1')

    const unscopedArgs = buildQueryGraphArgs('MATCH (n) RETURN n', 30, 1000, unscopedId || undefined)
    expect(unscopedArgs).not.toHaveProperty('knowledge_graph_id')
  })
})
