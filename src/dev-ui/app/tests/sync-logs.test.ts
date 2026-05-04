import { describe, it, expect, vi } from 'vitest'

// ── Sync Log Viewer (task-044) ────────────────────────────────────────────────
//
// Spec: ui/experience.spec.md — Requirement: Sync Monitoring
//
// Scenario: Sync logs
//   GIVEN a sync run (in progress or completed)
//   WHEN the user requests logs
//   THEN detailed logs for that run are displayed
//
// These tests cover the viewLogs / fetchRunLogs / closeLogs state machine
// in pages/data-sources/index.vue, focusing on aspects not covered by the
// generic sync-monitoring tests: data-source ID capture, loading-state
// lifecycle, empty-state handling, and log display format.

// ── Types (mirrors data-sources/index.vue) ────────────────────────────────────

interface SyncRun {
  id: string
  status: 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  error: string | null
  created_at: string
}

interface DataSourceItem {
  id: string
  name: string
  adapter_type: string
  knowledge_graph_id: string
  last_sync_at: string | null
  created_at: string
  sync_runs?: SyncRun[]
}

// ── State machine (mirrors the component) ─────────────────────────────────────

function makeLogState() {
  const logSheetOpen = { value: false }
  const selectedLogRunId = { value: null as string | null }
  const selectedLogDsId = { value: null as string | null }
  const runLogs = { value: [] as string[] }
  const logsLoading = { value: false }
  const logsError = { value: null as string | null }

  async function fetchRunLogs(
    dsId: string,
    runId: string,
    apiFetch: (url: string) => Promise<{ logs: string[] }>,
  ) {
    logsLoading.value = true
    logsError.value = null
    try {
      const result = await apiFetch(
        `/management/data-sources/${dsId}/sync-runs/${runId}/logs`,
      )
      runLogs.value = result.logs ?? []
    } catch (err) {
      logsError.value = err instanceof Error ? err.message : 'Failed to load logs'
      runLogs.value = []
    } finally {
      logsLoading.value = false
    }
  }

  async function viewLogs(
    ds: DataSourceItem,
    run: SyncRun,
    apiFetch: (url: string) => Promise<{ logs: string[] }>,
  ) {
    selectedLogDsId.value = ds.id
    selectedLogRunId.value = run.id
    runLogs.value = []
    logsError.value = null
    logSheetOpen.value = true
    await fetchRunLogs(ds.id, run.id, apiFetch)
  }

  function closeLogs() {
    logSheetOpen.value = false
    selectedLogRunId.value = null
    selectedLogDsId.value = null
    runLogs.value = []
    logsError.value = null
  }

  return {
    logSheetOpen,
    selectedLogRunId,
    selectedLogDsId,
    runLogs,
    logsLoading,
    logsError,
    viewLogs,
    fetchRunLogs,
    closeLogs,
  }
}

// ── Scenario: Sync logs — View Logs captures both dsId and runId ──────────────

describe('Sync Logs - viewLogs captures both dsId and runId', () => {
  it('sets selectedLogDsId when View Logs is clicked', async () => {
    const state = makeLogState()
    const ds: DataSourceItem = { id: 'ds-abc', name: 'my-repo', adapter_type: 'github', knowledge_graph_id: 'kg-1', last_sync_at: null, created_at: '2024-01-01T00:00:00Z' }
    const run: SyncRun = { id: 'run-1', status: 'completed', started_at: '2024-01-01T10:00:00Z', completed_at: '2024-01-01T10:01:00Z', error: null, created_at: '2024-01-01T10:00:00Z' }
    const apiFetch = vi.fn().mockResolvedValue({ logs: [] })

    await state.viewLogs(ds, run, apiFetch)

    expect(state.selectedLogDsId.value).toBe('ds-abc')
    expect(state.selectedLogRunId.value).toBe('run-1')
  })

  it('opens the log sheet immediately (before fetch completes)', async () => {
    const state = makeLogState()
    const ds: DataSourceItem = { id: 'ds-1', name: 'repo', adapter_type: 'github', knowledge_graph_id: 'kg-1', last_sync_at: null, created_at: '2024-01-01T00:00:00Z' }
    const run: SyncRun = { id: 'run-2', status: 'ingesting', started_at: '2024-01-01T10:00:00Z', completed_at: null, error: null, created_at: '2024-01-01T10:00:00Z' }
    let sheetOpenDuringFetch = false

    const apiFetch = vi.fn().mockImplementation(async () => {
      // capture sheet state while "fetch is in progress"
      sheetOpenDuringFetch = state.logSheetOpen.value
      return { logs: ['log line'] }
    })

    await state.viewLogs(ds, run, apiFetch)

    expect(sheetOpenDuringFetch).toBe(true)
  })

  it('clears previous logs when a new run is selected', async () => {
    const state = makeLogState()
    // Seed stale log data from a previous selection
    state.runLogs.value = ['stale log from previous run']

    const ds: DataSourceItem = { id: 'ds-1', name: 'repo', adapter_type: 'github', knowledge_graph_id: 'kg-1', last_sync_at: null, created_at: '2024-01-01T00:00:00Z' }
    const run: SyncRun = { id: 'run-new', status: 'completed', started_at: '2024-01-02T10:00:00Z', completed_at: '2024-01-02T10:01:00Z', error: null, created_at: '2024-01-02T10:00:00Z' }
    const apiFetch = vi.fn().mockResolvedValue({ logs: ['fresh log line'] })

    await state.viewLogs(ds, run, apiFetch)

    expect(state.runLogs.value).toEqual(['fresh log line'])
    expect(state.runLogs.value).not.toContain('stale log from previous run')
  })
})

// ── Scenario: Sync logs — Loading state lifecycle ─────────────────────────────

describe('Sync Logs - loading state lifecycle', () => {
  it('sets logsLoading to true while fetch is in progress', async () => {
    const state = makeLogState()
    const loadingValues: boolean[] = []

    const apiFetch = vi.fn().mockImplementation(async () => {
      loadingValues.push(state.logsLoading.value)
      return { logs: ['line 1'] }
    })

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    // logsLoading was true during the fetch
    expect(loadingValues).toContain(true)
  })

  it('resets logsLoading to false after a successful fetch', async () => {
    const state = makeLogState()
    const apiFetch = vi.fn().mockResolvedValue({ logs: ['log line'] })

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    expect(state.logsLoading.value).toBe(false)
  })

  it('resets logsLoading to false after a failed fetch', async () => {
    const state = makeLogState()
    const apiFetch = vi.fn().mockRejectedValue(new Error('Network failure'))

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    expect(state.logsLoading.value).toBe(false)
  })
})

// ── Scenario: Sync logs — Log fetch uses correct endpoint ─────────────────────

describe('Sync Logs - API endpoint construction', () => {
  it('includes both dsId and runId in the fetch URL', async () => {
    const state = makeLogState()
    const apiFetch = vi.fn().mockResolvedValue({ logs: [] })

    await state.fetchRunLogs('ds-xyz-123', 'run-abc-456', apiFetch)

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/data-sources/ds-xyz-123/sync-runs/run-abc-456/logs',
    )
  })

  it('calls the logs endpoint for an in-progress sync run', async () => {
    const state = makeLogState()
    const apiFetch = vi.fn().mockResolvedValue({ logs: ['ingesting batch 1/10'] })

    await state.fetchRunLogs('ds-1', 'run-inprogress', apiFetch)

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/data-sources/ds-1/sync-runs/run-inprogress/logs',
    )
    expect(state.runLogs.value).toContain('ingesting batch 1/10')
  })
})

// ── Scenario: Sync logs — Empty state ────────────────────────────────────────

describe('Sync Logs - empty state handling', () => {
  it('runLogs is empty when API returns an empty logs array', async () => {
    const state = makeLogState()
    const apiFetch = vi.fn().mockResolvedValue({ logs: [] })

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    expect(state.runLogs.value).toHaveLength(0)
  })

  it('runLogs defaults to empty when API omits the logs key', async () => {
    const state = makeLogState()
    // Defensive: API may return {} without a logs key
    const apiFetch = vi.fn().mockResolvedValue({} as { logs: string[] })

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    expect(state.runLogs.value).toHaveLength(0)
  })
})

// ── Scenario: Sync logs — Error state ────────────────────────────────────────

describe('Sync Logs - error state', () => {
  it('captures the error message when fetch fails', async () => {
    const state = makeLogState()
    const apiFetch = vi.fn().mockRejectedValue(new Error('Service Unavailable'))

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    expect(state.logsError.value).toBe('Service Unavailable')
    expect(state.runLogs.value).toHaveLength(0)
  })

  it('clears a previous error when a new fetch begins', async () => {
    const state = makeLogState()
    // Set up a previous error
    state.logsError.value = 'Previous error'

    const apiFetch = vi.fn().mockResolvedValue({ logs: ['success'] })
    await state.fetchRunLogs('ds-1', 'run-2', apiFetch)

    expect(state.logsError.value).toBeNull()
  })
})

// ── Scenario: Sync logs — Log display format ──────────────────────────────────

describe('Sync Logs - log line display format', () => {
  it('log lines are stored as strings (one line per entry)', async () => {
    const state = makeLogState()
    const logLines = [
      '2024-01-01T10:00:01Z INFO Starting sync',
      '2024-01-01T10:00:05Z INFO Fetched 100 items',
      '2024-01-01T10:00:10Z INFO Extraction complete',
    ]
    const apiFetch = vi.fn().mockResolvedValue({ logs: logLines })

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    expect(state.runLogs.value).toHaveLength(3)
    state.runLogs.value.forEach((line) => expect(typeof line).toBe('string'))
  })

  it('log lines joined by newlines produce valid monospace output', async () => {
    const state = makeLogState()
    const lines = ['INFO Starting', 'INFO Done']
    const apiFetch = vi.fn().mockResolvedValue({ logs: lines })

    await state.fetchRunLogs('ds-1', 'run-1', apiFetch)

    const rendered = state.runLogs.value.join('\n')
    expect(rendered).toBe('INFO Starting\nINFO Done')
  })
})

// ── Scenario: Sync logs — closeLogs clears all log state ─────────────────────

describe('Sync Logs - closeLogs resets full state', () => {
  it('closeLogs sets logSheetOpen to false', () => {
    const state = makeLogState()
    state.logSheetOpen.value = true

    state.closeLogs()

    expect(state.logSheetOpen.value).toBe(false)
  })

  it('closeLogs clears selectedLogRunId', () => {
    const state = makeLogState()
    state.selectedLogRunId.value = 'run-123'

    state.closeLogs()

    expect(state.selectedLogRunId.value).toBeNull()
  })

  it('closeLogs clears selectedLogDsId', () => {
    const state = makeLogState()
    state.selectedLogDsId.value = 'ds-abc'

    state.closeLogs()

    expect(state.selectedLogDsId.value).toBeNull()
  })

  it('closeLogs clears runLogs', () => {
    const state = makeLogState()
    state.runLogs.value = ['log line 1', 'log line 2']

    state.closeLogs()

    expect(state.runLogs.value).toHaveLength(0)
  })

  it('closeLogs clears logsError', () => {
    const state = makeLogState()
    state.logsError.value = 'Some error'

    state.closeLogs()

    expect(state.logsError.value).toBeNull()
  })

  it('closeLogs resets all state to initial values in one call', () => {
    const state = makeLogState()
    state.logSheetOpen.value = true
    state.selectedLogRunId.value = 'run-999'
    state.selectedLogDsId.value = 'ds-999'
    state.runLogs.value = ['line']
    state.logsError.value = 'err'

    state.closeLogs()

    expect(state.logSheetOpen.value).toBe(false)
    expect(state.selectedLogRunId.value).toBeNull()
    expect(state.selectedLogDsId.value).toBeNull()
    expect(state.runLogs.value).toHaveLength(0)
    expect(state.logsError.value).toBeNull()
  })
})
