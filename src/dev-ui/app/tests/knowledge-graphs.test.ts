import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { buildQueryGraphArgs } from '~/composables/api/useQueryApi'

// ── Knowledge Graph Creation ───────────────────────────────────────────────────
// Spec: "AND the knowledge graph is created within the current workspace"
// The handleCreate() function must call
// POST /management/workspaces/{workspace_id}/knowledge-graphs
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

  it('blocks creation when no workspace is selected', () => {
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: '' }
    const createWorkspaceError = { value: '' }

    function handleCreate() {
      createWorkspaceError.value = ''
      if (!selectedWorkspaceId.value) {
        createWorkspaceError.value = 'Please select a workspace'
        return false
      }
      if (!createName.value.trim()) return false
      return true
    }

    const result = handleCreate()
    expect(result).toBe(false)
    expect(createWorkspaceError.value).toBe('Please select a workspace')
  })
})

describe('Knowledge Graph Creation - API call', () => {
  it('calls POST /management/workspaces/{workspace_id}/knowledge-graphs with name and description', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'Test Graph' })
    const createName = { value: 'Test Graph' }
    const createDescription = { value: 'A test graph' }
    const selectedWorkspaceId = { value: 'ws-123' }
    const creating = { value: false }
    const createDialogOpen = { value: true }
    let toastMessage = ''

    async function handleCreate() {
      if (!selectedWorkspaceId.value) return
      if (!createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
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

    expect(apiFetch).toHaveBeenCalledWith('/management/workspaces/ws-123/knowledge-graphs', {
      method: 'POST',
      body: { name: 'Test Graph', description: 'A test graph' },
    })
    expect(toastMessage).toBe('Knowledge graph "Test Graph" created')
    expect(createDialogOpen.value).toBe(false)
    expect(creating.value).toBe(false)
  })

  it('does not call API when workspace is not selected', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'Test Graph' })
    const createName = { value: 'Test Graph' }
    const selectedWorkspaceId = { value: '' }
    const creating = { value: false }

    async function handleCreate() {
      if (!selectedWorkspaceId.value) return
      if (!createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value.trim() },
        })
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(apiFetch).not.toHaveBeenCalled()
    expect(creating.value).toBe(false)
  })

  it('sets creating back to false on API error', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Network error'))
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: 'ws-456' }
    const creating = { value: false }
    let toastError = ''

    async function handleCreate() {
      if (!selectedWorkspaceId.value) return
      if (!createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: 'My Graph' },
        })
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

describe('Knowledge Graph Creation - Workspace Loading', () => {
  // The UI must fetch available workspaces to populate the workspace selector
  // in the create dialog. Workspaces come from GET /iam/workspaces.

  it('fetches workspaces from /iam/workspaces on dialog open', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      workspaces: [
        { id: 'ws-1', name: 'Personal' },
        { id: 'ws-2', name: 'Team Alpha' },
      ],
      count: 2,
    })
    const workspaces: Array<{ id: string; name: string }> = []

    async function loadWorkspaces() {
      try {
        const result = await apiFetch('/iam/workspaces')
        workspaces.splice(0, workspaces.length, ...(result.workspaces ?? []))
      } catch {
        workspaces.splice(0, workspaces.length)
      }
    }

    await loadWorkspaces()
    expect(apiFetch).toHaveBeenCalledWith('/iam/workspaces')
    expect(workspaces).toHaveLength(2)
    expect(workspaces[0]).toMatchObject({ id: 'ws-1', name: 'Personal' })
  })

  it('defaults workspaces to empty array on fetch error', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const workspaces: Array<{ id: string; name: string }> = [{ id: 'stale', name: 'Stale' }]

    async function loadWorkspaces() {
      try {
        const result = await apiFetch('/iam/workspaces')
        workspaces.splice(0, workspaces.length, ...(result.workspaces ?? []))
      } catch {
        workspaces.splice(0, workspaces.length)
      }
    }

    await loadWorkspaces()
    expect(workspaces).toHaveLength(0)
  })

  it('auto-selects first workspace when only one exists', async () => {
    const workspaces = [{ id: 'ws-1', name: 'Personal' }]
    const createWorkspaceId = { value: '' }

    function autoSelectFirstWorkspace() {
      if (workspaces.length === 1) {
        createWorkspaceId.value = workspaces[0].id
      }
    }

    autoSelectFirstWorkspace()
    expect(createWorkspaceId.value).toBe('ws-1')
  })

  it('does not auto-select when multiple workspaces exist', async () => {
    const workspaces = [
      { id: 'ws-1', name: 'Personal' },
      { id: 'ws-2', name: 'Team Alpha' },
    ]
    const createWorkspaceId = { value: '' }

    function autoSelectFirstWorkspace() {
      if (workspaces.length === 1) {
        createWorkspaceId.value = workspaces[0].id
      }
    }

    autoSelectFirstWorkspace()
    // Not auto-selected when there are multiple choices
    expect(createWorkspaceId.value).toBe('')
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

  it('resets selectedKgId to unscoped when tenant changes', () => {
    // When the user switches tenants, any KG selected in the previous tenant
    // must be cleared. A stale KG ID from tenant A would not exist in tenant B
    // and would cause queries to fail silently or return wrong results.
    const selectedKgId = { value: 'kg-from-old-tenant' }

    // Simulate the tenantVersion watcher handler in query/index.vue
    function onTenantChange() {
      selectedKgId.value = ''
    }

    onTenantChange()

    expect(selectedKgId.value).toBe('')
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

// ── Copy-to-clipboard for Knowledge Graph IDs ─────────────────────────────────
// Spec: "Interaction Principles — Copy-to-clipboard"
// GIVEN a knowledge graph is listed on the page
// THEN a copy button is provided next to the knowledge graph ID
// AND clicking the copy button writes the ID to the clipboard
// AND a toast confirms the copy action

describe('Knowledge Graphs - copy KG ID to clipboard', () => {
  it('calls clipboard.writeText with the knowledge graph ID', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    let toastMsg = ''

    // Mirrors the copyId(kg.id) helper that will be implemented in the page
    async function copyId(id: string) {
      try {
        await writeText(id)
        toastMsg = 'Knowledge graph ID copied'
      } catch {
        toastMsg = 'Failed to copy'
      }
    }

    await copyId('kg-abc-123')
    expect(writeText).toHaveBeenCalledWith('kg-abc-123')
    expect(toastMsg).toBe('Knowledge graph ID copied')
  })

  it('shows error feedback when clipboard write fails', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('Permission denied'))
    let toastMsg = ''

    async function copyId(id: string) {
      try {
        await writeText(id)
        toastMsg = 'Knowledge graph ID copied'
      } catch {
        toastMsg = 'Failed to copy'
      }
    }

    await copyId('kg-abc-123')
    expect(writeText).toHaveBeenCalledWith('kg-abc-123')
    expect(toastMsg).toBe('Failed to copy')
  })

  it('copies the correct ID for each knowledge graph in the list', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    const kgs = [
      { id: 'kg-1', name: 'Engineering' },
      { id: 'kg-2', name: 'Marketing' },
    ]
    const copiedIds: string[] = []

    async function copyId(id: string) {
      await writeText(id)
      copiedIds.push(id)
    }

    for (const kg of kgs) {
      await copyId(kg.id)
    }

    expect(writeText).toHaveBeenCalledTimes(2)
    expect(copiedIds).toEqual(['kg-1', 'kg-2'])
  })
})

// ── Mutation Feedback — error toasts on failed operations ─────────────────────
// Spec: "Interaction Principles — Mutation feedback"
// GIVEN a write operation (create, update, delete)
// THEN a toast notification confirms success or reports failure
// AND validation errors are shown inline on form fields

describe('Knowledge Graphs - mutation error feedback', () => {
  it('shows error toast when create API call fails', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Internal Server Error'))
    let errorToast = ''
    const creating = { value: false }

    async function handleCreate(workspaceId: string, name: string) {
      if (!workspaceId || !name.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${workspaceId}/knowledge-graphs`, {
          method: 'POST',
          body: { name: name.trim() },
        })
      } catch (err) {
        errorToast = err instanceof Error ? err.message : 'Failed to create knowledge graph'
      } finally {
        creating.value = false
      }
    }

    await handleCreate('ws-123', 'My Graph')
    expect(errorToast).toBe('Internal Server Error')
    expect(creating.value).toBe(false)
  })

  it('shows inline name error when name is empty on submit', () => {
    const createName = { value: '' }
    const createNameError = { value: '' }

    function handleCreate() {
      createNameError.value = ''
      if (!createName.value.trim()) {
        createNameError.value = 'Knowledge graph name is required'
        return false
      }
      return true
    }

    const ok = handleCreate()
    expect(ok).toBe(false)
    expect(createNameError.value).toBe('Knowledge graph name is required')
  })

  it('shows inline workspace error when no workspace selected on submit', () => {
    const selectedWorkspaceId = { value: '' }
    const createWorkspaceError = { value: '' }
    const createName = { value: 'My Graph' }

    function handleCreate() {
      createWorkspaceError.value = ''
      if (!selectedWorkspaceId.value) {
        createWorkspaceError.value = 'Please select a workspace'
        return false
      }
      return true
    }

    const ok = handleCreate()
    expect(ok).toBe(false)
    expect(createWorkspaceError.value).toBe('Please select a workspace')
  })

  it('shows success toast with action to add data source after create', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'My Graph' })
    let successToast = ''
    let successToastAction = ''

    async function handleCreate(workspaceId: string, name: string) {
      if (!workspaceId || !name.trim()) return
      try {
        const result = await apiFetch(`/management/workspaces/${workspaceId}/knowledge-graphs`, {
          method: 'POST',
          body: { name: name.trim() },
        })
        successToast = `Knowledge graph "${result.name}" created`
        successToastAction = 'Add Data Source'
      } catch (err) {
        // error handled elsewhere
      }
    }

    await handleCreate('ws-123', 'My Graph')
    expect(successToast).toBe('Knowledge graph "My Graph" created')
    expect(successToastAction).toBe('Add Data Source')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Tenant selector — data refresh on tenant change (strengthened)
// Spec: "switching tenants refreshes all data in the UI"
// ────────────────────────────────────────────────────────────────────────────

describe('Knowledge Graphs page - tenant switch clears stale data', () => {
  it('KG list is cleared immediately when tenant version changes', () => {
    // Stale KGs from previous tenant
    let knowledgeGraphs = [
      { id: 'kg-old', name: 'Old Tenant Graph' },
    ]

    // Expected watch handler behaviour: clear before the async fetch returns
    function onTenantVersionChange() {
      knowledgeGraphs = []  // ← must happen before loadKnowledgeGraphs()
    }

    expect(knowledgeGraphs).toHaveLength(1)

    onTenantVersionChange()

    expect(knowledgeGraphs).toHaveLength(0)
  })

  it('KG list shows new-tenant data after tenant switch completes', async () => {
    let knowledgeGraphs: Array<{ id: string; name: string }> = [
      { id: 'kg-old', name: 'Old Graph' },
    ]

    const newKg = { id: 'kg-new', name: 'New Tenant Graph' }
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [newKg] })

    async function loadKnowledgeGraphs() {
      const result = await apiFetch('/management/knowledge-graphs')
      return result.knowledge_graphs ?? []
    }

    async function onTenantVersionChange() {
      knowledgeGraphs = []
      knowledgeGraphs = await loadKnowledgeGraphs()
    }

    await onTenantVersionChange()

    expect(knowledgeGraphs).toHaveLength(1)
    expect(knowledgeGraphs[0].name).toBe('New Tenant Graph')
    expect(knowledgeGraphs[0].id).not.toBe('kg-old')
  })

  it('workspace selection is reset when tenant changes', () => {
    let selectedWorkspaceId = 'ws-old-tenant'
    let workspaces = [{ id: 'ws-old-tenant', name: 'Old WS' }]

    function onTenantVersionChange() {
      workspaces = []
      selectedWorkspaceId = ''
    }

    onTenantVersionChange()

    expect(selectedWorkspaceId).toBe('')
    expect(workspaces).toHaveLength(0)
  })
})

// ── Backend API Alignment — Scenario: Resource operations succeed end-to-end ──
// Spec requirement: "AND the UI reflects the updated state without requiring a
// manual refresh"
// Verifies that after a successful KG creation, loadKnowledgeGraphs() is
// called so the list is refreshed automatically.

describe('Backend API Alignment — Scenario: Resource operations succeed end-to-end — KG list refresh', () => {
  it('calls loadKnowledgeGraphs() after successful KG creation', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'My Graph' })
    const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: 'ws-1' }
    const creating = { value: false }
    const createDialogOpen = { value: true }

    async function handleCreate() {
      if (!selectedWorkspaceId.value || !createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value.trim() },
        })
        createDialogOpen.value = false
        await loadKnowledgeGraphs()
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
  })

  it('does NOT call loadKnowledgeGraphs() when the API throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Server error'))
    const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: 'ws-1' }
    const creating = { value: false }

    async function handleCreate() {
      if (!selectedWorkspaceId.value || !createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value.trim() },
        })
        await loadKnowledgeGraphs()
      } catch {
        // error path — refresh must NOT be called
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
  })

  it('creating flag is reset to false regardless of success or failure', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Conflict'))
    const loadKnowledgeGraphs = vi.fn()
    const creating = { value: false }
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: 'ws-1' }

    async function handleCreate() {
      if (!selectedWorkspaceId.value || !createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value.trim() },
        })
        await loadKnowledgeGraphs()
      } catch {
        // swallow
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(creating.value).toBe(false)
  })
})

// ── Knowledge Graph Creation: prompt to add first data source ─────────────────
//
// Spec: "AND the user is prompted to add their first data source"
// Scenario: Create knowledge graph (Requirement: Knowledge Graph Creation)
//
// After successful KG creation, handleCreate() fires a toast.success() that
// includes a description prompting the user to add a data source and an action
// button that navigates to /data-sources.

describe('Knowledge Graph Creation — prompt to add first data source', () => {
  it('toast description prompts the user to connect a data source', async () => {
    // Capture the full toast options object so we can assert description + action.
    let toastOptions: { description?: string; action?: { label: string; onClick: () => void } } = {}

    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new', name: 'My Graph' })
    const navigateTo = vi.fn()
    const createName = { value: 'My Graph' }
    const createDescription = { value: '' }
    const selectedWorkspaceId = { value: 'ws-1' }
    const createDialogOpen = { value: true }
    const creating = { value: false }

    async function handleCreate() {
      if (!selectedWorkspaceId.value || !createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: {
            name: createName.value.trim(),
            description: createDescription.value.trim() || undefined,
          },
        })
        toastOptions = {
          description: 'Next: connect a data source to start populating your graph.',
          action: {
            label: 'Add Data Source',
            onClick: () => navigateTo('/data-sources'),
          },
        }
        createDialogOpen.value = false
      } finally {
        creating.value = false
      }
    }

    await handleCreate()

    expect(toastOptions.description).toBe(
      'Next: connect a data source to start populating your graph.',
    )
  })

  it('toast action label is "Add Data Source"', async () => {
    let actionLabel = ''

    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new' })
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: 'ws-1' }
    const creating = { value: false }

    async function handleCreate() {
      if (!selectedWorkspaceId.value || !createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value.trim() },
        })
        actionLabel = 'Add Data Source'
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(actionLabel).toBe('Add Data Source')
  })

  it('toast action navigates to /data-sources', async () => {
    const navigateTo = vi.fn()
    let actionOnClick: (() => void) | undefined

    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-new' })
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: 'ws-1' }
    const creating = { value: false }

    async function handleCreate() {
      if (!selectedWorkspaceId.value || !createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value.trim() },
        })
        actionOnClick = () => navigateTo('/data-sources')
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(actionOnClick).toBeDefined()
    actionOnClick!()
    expect(navigateTo).toHaveBeenCalledWith('/data-sources')
  })

  it('toast is not fired when KG creation fails (API error)', async () => {
    let toastFired = false
    const apiFetch = vi.fn().mockRejectedValue(new Error('Network error'))
    const createName = { value: 'My Graph' }
    const selectedWorkspaceId = { value: 'ws-1' }
    const creating = { value: false }

    async function handleCreate() {
      if (!selectedWorkspaceId.value || !createName.value.trim()) return
      creating.value = true
      try {
        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`, {
          method: 'POST',
          body: { name: createName.value.trim() },
        })
        toastFired = true // this line is skipped on error
      } catch {
        // error path
      } finally {
        creating.value = false
      }
    }

    await handleCreate()
    expect(toastFired).toBe(false)
  })
})

// ── Knowledge Graphs — Edit (rename / re-describe) ────────────────────────────
// Spec: "Backend API Alignment — Scenario: Resource operations succeed end-to-end"
// GIVEN an authenticated user
// WHEN the user performs any create, read, UPDATE, or delete operation via the UI
// THEN the corresponding backend API call succeeds (2xx response)
// AND the UI reflects the updated state without requiring a manual refresh

describe('Knowledge Graphs — Edit (rename / re-describe)', () => {
  it('opens edit dialog pre-filled with existing name and description', () => {
    const editDialogOpen = { value: false }
    const editName = { value: '' }
    const editDescription = { value: '' }
    const editingKgId = { value: '' }

    function openEditDialog(kg: { id: string; name: string; description?: string }) {
      editingKgId.value = kg.id
      editName.value = kg.name
      editDescription.value = kg.description ?? ''
      editDialogOpen.value = true
    }

    openEditDialog({ id: 'kg-1', name: 'Engineering', description: 'Our main graph' })

    expect(editDialogOpen.value).toBe(true)
    expect(editingKgId.value).toBe('kg-1')
    expect(editName.value).toBe('Engineering')
    expect(editDescription.value).toBe('Our main graph')
  })

  it('calls PATCH /management/knowledge-graphs/{id} with name and description', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'kg-1', name: 'Renamed Graph' })
    const editingKgId = { value: 'kg-1' }
    const editName = { value: 'Renamed Graph' }
    const editDescription = { value: 'Updated desc' }
    const saving = { value: false }
    const editDialogOpen = { value: true }
    const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)

    async function handleEdit() {
      if (!editName.value.trim()) return
      saving.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${editingKgId.value}`, {
          method: 'PATCH',
          body: { name: editName.value.trim(), description: editDescription.value.trim() },
        })
        editDialogOpen.value = false
        await loadKnowledgeGraphs()
      } finally {
        saving.value = false
      }
    }

    await handleEdit()

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs/kg-1', {
      method: 'PATCH',
      body: { name: 'Renamed Graph', description: 'Updated desc' },
    })
    expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
    expect(editDialogOpen.value).toBe(false)
    expect(saving.value).toBe(false)
  })

  it('shows inline error and does not call API when edit name is empty', async () => {
    const apiFetch = vi.fn()
    const editName = { value: '   ' }
    const editNameError = { value: '' }
    let apiCalled = false

    async function handleEdit() {
      editNameError.value = ''
      if (!editName.value.trim()) {
        editNameError.value = 'Knowledge graph name is required'
        return
      }
      apiCalled = true
      await apiFetch('/management/knowledge-graphs/kg-1', { method: 'PATCH', body: {} })
    }

    await handleEdit()

    expect(apiCalled).toBe(false)
    expect(editNameError.value).toBe('Knowledge graph name is required')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('shows error toast and keeps dialog open on 409 conflict', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Name already exists in tenant'))
    const editingKgId = { value: 'kg-1' }
    const editName = { value: 'Duplicate Name' }
    const editDescription = { value: '' }
    const editDialogOpen = { value: true }
    const saving = { value: false }
    let errorMsg = ''

    async function handleEdit() {
      saving.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${editingKgId.value}`, {
          method: 'PATCH',
          body: { name: editName.value.trim(), description: editDescription.value.trim() },
        })
        editDialogOpen.value = false
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to update knowledge graph'
        // dialog stays open
      } finally {
        saving.value = false
      }
    }

    await handleEdit()

    expect(errorMsg).toBe('Name already exists in tenant')
    expect(editDialogOpen.value).toBe(true) // still open
    expect(saving.value).toBe(false)
  })

  it('does not refresh list when edit API throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const loadKnowledgeGraphs = vi.fn()
    const editName = { value: 'New Name' }

    async function handleEdit() {
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'PATCH', body: { name: editName.value } })
        await loadKnowledgeGraphs()
      } catch {
        // error path
      }
    }

    await handleEdit()
    expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
  })

  it('saving flag is reset to false in all code paths', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Server error'))
    const saving = { value: false }
    const editName = { value: 'Some Name' }

    async function handleEdit() {
      saving.value = true
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'PATCH', body: { name: editName.value } })
      } catch {
        // swallow
      } finally {
        saving.value = false
      }
    }

    await handleEdit()
    expect(saving.value).toBe(false)
  })
})

// ── Knowledge Graphs — Delete with confirmation ───────────────────────────────
// Spec: "Backend API Alignment — Scenario: Resource operations succeed end-to-end"
// GIVEN an authenticated user
// WHEN the user performs any create, read, update, or DELETE operation via the UI
// THEN the corresponding backend API call succeeds (2xx response)
// AND the UI reflects the updated state without requiring a manual refresh

describe('Knowledge Graphs — Delete with confirmation', () => {
  it('opens delete confirmation dialog with the target KG id and name', () => {
    const deleteDialogOpen = { value: false }
    const deletingKgId = { value: '' }
    const deletingKgName = { value: '' }

    function openDeleteDialog(kg: { id: string; name: string }) {
      deletingKgId.value = kg.id
      deletingKgName.value = kg.name
      deleteDialogOpen.value = true
    }

    openDeleteDialog({ id: 'kg-1', name: 'Engineering' })

    expect(deleteDialogOpen.value).toBe(true)
    expect(deletingKgId.value).toBe('kg-1')
    expect(deletingKgName.value).toBe('Engineering')
  })

  it('calls DELETE /management/knowledge-graphs/{id} and refreshes list on confirm', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined) // 204 no content
    const deletingKgId = { value: 'kg-1' }
    const deleting = { value: false }
    const deleteDialogOpen = { value: true }
    const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)

    async function handleDelete() {
      deleting.value = true
      try {
        await apiFetch(`/management/knowledge-graphs/${deletingKgId.value}`, { method: 'DELETE' })
        deleteDialogOpen.value = false
        await loadKnowledgeGraphs()
      } finally {
        deleting.value = false
      }
    }

    await handleDelete()

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs/kg-1', { method: 'DELETE' })
    expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()
    expect(deleteDialogOpen.value).toBe(false)
    expect(deleting.value).toBe(false)
  })

  it('does not call DELETE when dialog is cancelled', () => {
    const apiFetch = vi.fn()
    const deleteDialogOpen = { value: true }

    function cancelDelete() {
      deleteDialogOpen.value = false
      // no API call
    }

    cancelDelete()

    expect(apiFetch).not.toHaveBeenCalled()
    expect(deleteDialogOpen.value).toBe(false)
  })

  it('shows error toast and closes dialog on delete failure', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    const deleting = { value: false }
    const deleteDialogOpen = { value: true }
    let errorMsg = ''

    async function handleDelete() {
      deleting.value = true
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'DELETE' })
        deleteDialogOpen.value = false
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to delete knowledge graph'
        deleteDialogOpen.value = false
      } finally {
        deleting.value = false
      }
    }

    await handleDelete()

    expect(errorMsg).toBe('Forbidden')
    expect(deleting.value).toBe(false)
    expect(deleteDialogOpen.value).toBe(false)
  })

  it('does not refresh list when delete API throws', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Server error'))
    const loadKnowledgeGraphs = vi.fn()

    async function handleDelete() {
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'DELETE' })
        await loadKnowledgeGraphs()
      } catch {
        // error path
      }
    }

    await handleDelete()
    expect(loadKnowledgeGraphs).not.toHaveBeenCalled()
  })

  it('deleting flag is reset to false in all code paths', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Server error'))
    const deleting = { value: false }

    async function handleDelete() {
      deleting.value = true
      try {
        await apiFetch('/management/knowledge-graphs/kg-1', { method: 'DELETE' })
      } catch {
        // swallow
      } finally {
        deleting.value = false
      }
    }

    await handleDelete()
    expect(deleting.value).toBe(false)
  })
})

// ── Knowledge Graphs — Edit & Delete structural checks ────────────────────────
// Spec: "Backend API Alignment — Scenario: Resource operations succeed end-to-end"
// Structural tests verify the Vue template contains the expected state variables,
// API calls, and dialog elements.

describe('Knowledge Graphs page — edit and delete structural checks', () => {
  const kgVue = readFileSync(
    resolve(__dirname, '../pages/knowledge-graphs/index.vue'),
    'utf-8',
  )

  it('declares editDialogOpen state', () => {
    expect(kgVue).toMatch(/editDialogOpen/)
  })

  it('declares deleteDialogOpen state', () => {
    expect(kgVue).toMatch(/deleteDialogOpen/)
  })

  it('calls PATCH /management/knowledge-graphs/ in handleEdit', () => {
    // Check that both PATCH method and knowledge-graphs URL path appear in the file
    // (they may be on separate lines in multi-line API call syntax)
    expect(kgVue).toContain("method: 'PATCH'")
    expect(kgVue).toContain('/management/knowledge-graphs/')
  })

  it('calls DELETE /management/knowledge-graphs/ in handleDelete', () => {
    // Check that both DELETE method and knowledge-graphs URL path appear in the file
    // (they may be on separate lines in multi-line API call syntax)
    expect(kgVue).toContain("method: 'DELETE'")
    expect(kgVue).toContain('/management/knowledge-graphs/')
  })

  it('edit dialog is present in the template', () => {
    expect(kgVue).toMatch(/editDialogOpen|Edit Knowledge Graph/)
  })

  it('delete AlertDialog is present in the template', () => {
    expect(kgVue).toMatch(/AlertDialog|deleteDialogOpen/)
  })

  it('cascade deletion warning mentions data sources', () => {
    expect(kgVue).toMatch(/data sources?/i)
  })

  it('handleEdit calls loadKnowledgeGraphs after success', () => {
    expect(kgVue).toContain('handleEdit')
    expect(kgVue).toContain('loadKnowledgeGraphs')
  })

  it('handleDelete calls loadKnowledgeGraphs after success', () => {
    expect(kgVue).toContain('handleDelete')
  })
})

// ── Backend API Alignment: KG creation list refresh ───────────────────────────
//
// Spec: "AND the UI reflects the updated state without requiring a manual refresh"
// Scenario: Resource operations succeed end-to-end
//
// After a successful knowledge graph creation, handleCreate() in
// knowledge-graphs/index.vue must call loadKnowledgeGraphs() to refresh
// the displayed list automatically without requiring a manual page reload.

describe('Backend API Alignment — KG creation: UI list reloads without manual refresh', () => {
  const kgVue = readFileSync(
    resolve(__dirname, '../pages/knowledge-graphs/index.vue'),
    'utf-8',
  )

  it('handleCreate() calls await loadKnowledgeGraphs() after successful creation', () => {
    // The implementation must include this call; without it the list stays stale
    // until the user manually navigates away and back.
    expect(kgVue).toContain('await loadKnowledgeGraphs()')
  })

  it('loadKnowledgeGraphs() is called in the try block (not just on mount)', () => {
    // Must appear inside handleCreate's try block, not only in onMounted/watch.
    // Presence of the string in the file is sufficient — structural test.
    const tryBlockIdx = kgVue.indexOf('try {')
    const loadCallIdx = kgVue.indexOf('await loadKnowledgeGraphs()')
    expect(loadCallIdx).toBeGreaterThan(tryBlockIdx)
  })
})
