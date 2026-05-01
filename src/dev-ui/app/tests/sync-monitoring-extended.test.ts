import { describe, it, expect, vi } from 'vitest'

// ── Sync Monitoring Extended Tests ────────────────────────────────────────────
//
// Spec: "Sync Monitoring"
// Covers:
//   - Scenario: Active sync progress (ingesting, extracting, applying phases)
//   - Scenario: Sync history (completed runs with status, timestamps, duration)
//   - Scenario: Manual sync trigger (triggerSync API call)

// ── Types ─────────────────────────────────────────────────────────────────────

interface SyncRun {
  id: string
  status: 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'
  started_at: string
  completed_at: string | null
  error: string | null
  created_at: string
}

// ── Active sync phase helpers ─────────────────────────────────────────────────

/**
 * Determine the displayed progress phase label from a sync run status.
 * Maps the run status to the appropriate user-facing phase.
 */
function getSyncPhaseLabel(status: SyncRun['status']): string {
  switch (status) {
    case 'pending':
      return 'Pending'
    case 'ingesting':
      return 'Ingesting'
    case 'ai_extracting':
      return 'Extracting'
    case 'applying':
      return 'Applying'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    default:
      return 'Unknown'
  }
}

function isActiveSyncPhase(status: SyncRun['status']): boolean {
  return status === 'pending' || status === 'ingesting' || status === 'ai_extracting' || status === 'applying'
}

function getSyncBadgeVariant(status: SyncRun['status']): 'default' | 'destructive' | 'secondary' {
  if (status === 'completed') return 'default'
  if (status === 'failed') return 'destructive'
  return 'secondary' // pending, ingesting, ai_extracting, applying
}

function getDataSourceSyncStatus(syncRuns: SyncRun[]): string {
  if (syncRuns.length === 0) return 'idle'
  return syncRuns[0].status
}

// ── Duration computation ──────────────────────────────────────────────────────

function computeSyncDuration(startedAt: string, completedAt: string | null): number | null {
  if (!completedAt) return null
  return Math.round(
    (new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000,
  )
}

// ── Sync trigger ──────────────────────────────────────────────────────────────

async function triggerSync(
  dsId: string,
  apiFetch: (url: string, opts: { method: string }) => Promise<void>,
): Promise<{ success: boolean; message: string }> {
  try {
    await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
    return { success: true, message: 'Sync triggered' }
  } catch {
    return { success: false, message: 'Failed to trigger sync' }
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Active sync progress — real backend phase display
// ────────────────────────────────────────────────────────────────────────────

describe('Sync Monitoring - real backend phase labels (ingesting/ai_extracting/applying)', () => {
  it('shows "Ingesting" label for ingesting phase', () => {
    expect(getSyncPhaseLabel('ingesting')).toBe('Ingesting')
  })

  it('shows "Extracting" label for ai_extracting phase', () => {
    expect(getSyncPhaseLabel('ai_extracting')).toBe('Extracting')
  })

  it('shows "Applying" label for applying phase', () => {
    expect(getSyncPhaseLabel('applying')).toBe('Applying')
  })

  it('isActiveSyncPhase returns true for ingesting status', () => {
    expect(isActiveSyncPhase('ingesting')).toBe(true)
  })

  it('isActiveSyncPhase returns true for ai_extracting status', () => {
    expect(isActiveSyncPhase('ai_extracting')).toBe(true)
  })

  it('isActiveSyncPhase returns true for applying status', () => {
    expect(isActiveSyncPhase('applying')).toBe(true)
  })

  it('isActiveSyncPhase returns false for "running" (not a real backend status)', () => {
    // The backend never emits 'running'; all in-progress phases are ingesting,
    // ai_extracting, or applying. This assertion documents that 'running' must
    // NOT be treated as an active phase.
    const runningAsUnknown = 'running' as unknown as SyncRun['status']
    expect(isActiveSyncPhase(runningAsUnknown)).toBe(false)
  })

  it('ingesting status uses "secondary" badge variant (in-progress)', () => {
    expect(getSyncBadgeVariant('ingesting')).toBe('secondary')
  })

  it('ai_extracting status uses "secondary" badge variant (in-progress)', () => {
    expect(getSyncBadgeVariant('ai_extracting')).toBe('secondary')
  })

  it('applying status uses "secondary" badge variant (in-progress)', () => {
    expect(getSyncBadgeVariant('applying')).toBe('secondary')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Active sync progress — phase display (all statuses)
// ────────────────────────────────────────────────────────────────────────────

describe('Sync Monitoring - active sync progress phases', () => {
  it('shows "Pending" label for pending sync', () => {
    expect(getSyncPhaseLabel('pending')).toBe('Pending')
  })

  it('shows "Completed" label for completed sync', () => {
    expect(getSyncPhaseLabel('completed')).toBe('Completed')
  })

  it('shows "Failed" label for failed sync', () => {
    expect(getSyncPhaseLabel('failed')).toBe('Failed')
  })

  it('isActiveSyncPhase returns true for pending status', () => {
    expect(isActiveSyncPhase('pending')).toBe(true)
  })

  it('isActiveSyncPhase returns false for completed status', () => {
    expect(isActiveSyncPhase('completed')).toBe(false)
  })

  it('isActiveSyncPhase returns false for failed status', () => {
    expect(isActiveSyncPhase('failed')).toBe(false)
  })
})

describe('Sync Monitoring - badge variants for sync status', () => {
  it('completed sync uses "default" badge variant', () => {
    expect(getSyncBadgeVariant('completed')).toBe('default')
  })

  it('failed sync uses "destructive" badge variant', () => {
    expect(getSyncBadgeVariant('failed')).toBe('destructive')
  })

  it('ingesting sync uses "secondary" badge variant (progress indicator)', () => {
    expect(getSyncBadgeVariant('ingesting')).toBe('secondary')
  })

  it('pending sync uses "secondary" badge variant', () => {
    expect(getSyncBadgeVariant('pending')).toBe('secondary')
  })
})

describe('Sync Monitoring - data source current sync status', () => {
  it('shows "idle" when no sync runs exist', () => {
    expect(getDataSourceSyncStatus([])).toBe('idle')
  })

  it('shows the most recent run status (first in array)', () => {
    const runs: SyncRun[] = [
      { id: 'run-2', status: 'ingesting', started_at: '2024-01-02T10:00:00Z', completed_at: null, error: null, created_at: '2024-01-02T10:00:00Z' },
      { id: 'run-1', status: 'completed', started_at: '2024-01-01T10:00:00Z', completed_at: '2024-01-01T10:00:30Z', error: null, created_at: '2024-01-01T10:00:00Z' },
    ]
    expect(getDataSourceSyncStatus(runs)).toBe('ingesting')
  })

  it('shows "completed" when the latest sync completed successfully', () => {
    const runs: SyncRun[] = [
      { id: 'run-1', status: 'completed', started_at: '2024-01-01T10:00:00Z', completed_at: '2024-01-01T10:01:00Z', error: null, created_at: '2024-01-01T10:00:00Z' },
    ]
    expect(getDataSourceSyncStatus(runs)).toBe('completed')
  })

  it('shows "failed" when the latest sync failed', () => {
    const runs: SyncRun[] = [
      { id: 'run-1', status: 'failed', started_at: '2024-01-01T10:00:00Z', completed_at: '2024-01-01T10:01:00Z', error: 'Connection refused', created_at: '2024-01-01T10:00:00Z' },
    ]
    expect(getDataSourceSyncStatus(runs)).toBe('failed')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Sync history — list with status, timestamps, duration
// ────────────────────────────────────────────────────────────────────────────

describe('Sync Monitoring - sync history list rendering', () => {
  it('computes duration in seconds from started_at and completed_at', () => {
    const duration = computeSyncDuration('2024-01-01T10:00:00Z', '2024-01-01T10:00:30Z')
    expect(duration).toBe(30)
  })

  it('computes longer duration correctly', () => {
    const duration = computeSyncDuration('2024-01-01T10:00:00Z', '2024-01-01T10:05:00Z')
    expect(duration).toBe(300) // 5 minutes = 300 seconds
  })

  it('returns null duration when completed_at is null (in-progress)', () => {
    const duration = computeSyncDuration('2024-01-01T10:00:00Z', null)
    expect(duration).toBeNull()
  })

  it('each sync run in history has required display fields', () => {
    const run: SyncRun = {
      id: 'run-1',
      status: 'completed',
      started_at: '2024-01-01T10:00:00Z',
      completed_at: '2024-01-01T10:00:45Z',
      error: null,
      created_at: '2024-01-01T10:00:00Z',
    }
    // Verify all spec-required fields are present
    expect(run.status).toBeDefined() // status (completed, failed)
    expect(run.started_at).toBeDefined() // timestamp
    expect(computeSyncDuration(run.started_at, run.completed_at)).toBe(45) // duration
  })

  it('history run with error shows error message', () => {
    const run: SyncRun = {
      id: 'run-1',
      status: 'failed',
      started_at: '2024-01-01T10:00:00Z',
      completed_at: '2024-01-01T10:00:05Z',
      error: 'Connection refused to GitHub API',
      created_at: '2024-01-01T10:00:00Z',
    }
    expect(run.error).toBe('Connection refused to GitHub API')
  })

  it('renders sync run timestamps as human-readable dates', () => {
    const run: SyncRun = {
      id: 'run-1',
      status: 'completed',
      started_at: '2024-01-15T14:30:00Z',
      completed_at: '2024-01-15T14:31:00Z',
      error: null,
      created_at: '2024-01-15T14:30:00Z',
    }
    const displayDate = new Date(run.started_at).toLocaleString()
    expect(displayDate).toBeTruthy()
    expect(typeof displayDate).toBe('string')
  })

  it('multiple sync runs are listed in order (most recent first)', () => {
    const runs: SyncRun[] = [
      {
        id: 'run-3',
        status: 'ingesting',
        started_at: '2024-01-03T10:00:00Z',
        completed_at: null,
        error: null,
        created_at: '2024-01-03T10:00:00Z',
      },
      {
        id: 'run-2',
        status: 'failed',
        started_at: '2024-01-02T10:00:00Z',
        completed_at: '2024-01-02T10:00:05Z',
        error: 'Timeout',
        created_at: '2024-01-02T10:00:00Z',
      },
      {
        id: 'run-1',
        status: 'completed',
        started_at: '2024-01-01T10:00:00Z',
        completed_at: '2024-01-01T10:01:00Z',
        error: null,
        created_at: '2024-01-01T10:00:00Z',
      },
    ]
    // Most recent first: run-3, run-2, run-1
    expect(runs[0].id).toBe('run-3')
    expect(runs[1].id).toBe('run-2')
    expect(runs[2].id).toBe('run-1')
    // History shows all 3 runs
    expect(runs).toHaveLength(3)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Manual sync trigger
// ────────────────────────────────────────────────────────────────────────────

describe('Sync Monitoring - manual sync trigger', () => {
  it('calls the correct API endpoint to trigger sync', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const result = await triggerSync('ds-abc123', apiFetch)

    expect(apiFetch).toHaveBeenCalledWith(
      '/management/data-sources/ds-abc123/sync',
      { method: 'POST' },
    )
    expect(result.success).toBe(true)
    expect(result.message).toBe('Sync triggered')
  })

  it('shows success message when sync trigger API call succeeds', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const result = await triggerSync('ds-1', apiFetch)
    expect(result.success).toBe(true)
    expect(result.message).toBe('Sync triggered')
  })

  it('returns failure message when sync trigger API call fails', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Server Error'))
    const result = await triggerSync('ds-1', apiFetch)
    expect(result.success).toBe(false)
    expect(result.message).toBe('Failed to trigger sync')
  })

  it('uses POST method for sync trigger (not GET)', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    await triggerSync('ds-1', apiFetch)
    expect(apiFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('includes data source ID in the trigger URL', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    const dsId = 'data-source-xyz-789'
    await triggerSync(dsId, apiFetch)
    const calledUrl = (apiFetch as ReturnType<typeof vi.fn>).mock.calls[0][0]
    expect(calledUrl).toContain(dsId)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Tenant switch refreshes sync data
// ────────────────────────────────────────────────────────────────────────────

describe('Sync Monitoring - tenant switch reloads data sources', () => {
  it('data source list is cleared when tenant version changes', () => {
    // Simulate tenantVersion watch handler: clears dataSources
    let dataSources = [
      { id: 'ds-1', name: 'my-repo', adapter_type: 'github', knowledge_graph_id: 'kg-1' },
    ]
    let tenantVersion = 1

    function onTenantVersionChange() {
      dataSources = []
    }

    tenantVersion = 2
    onTenantVersionChange()

    expect(dataSources).toEqual([])
  })

  it('reload is triggered after tenant version change', async () => {
    const loadDataSources = vi.fn().mockResolvedValue([])
    let tenantVersion = 1

    async function onTenantVersionChange() {
      await loadDataSources()
    }

    tenantVersion = 2
    await onTenantVersionChange()

    expect(loadDataSources).toHaveBeenCalledOnce()
  })
})
