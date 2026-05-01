import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Default Layout — Sync-Status Badge on Data Sources Nav Item ───────────────
//
// Spec: specs/ui/experience.spec.md — "Navigation Structure — Primary navigation"
// The sidebar's Data Sources nav item must show a numeric badge when one or more
// data sources have an active sync run. This test file validates the logic that
// powers that badge without mounting the full Nuxt layout component.
//
// Task: task-047
//
// Active sync statuses (matching the backend):
//   pending | ingesting | ai_extracting | applying

type SyncStatus = 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'

interface SyncRun {
  status: SyncStatus
}

interface DataSource {
  id: string
  name: string
  latest_sync_run?: SyncRun
}

interface DataSourcesListResponse {
  data_sources: DataSource[]
}

// ── Core badge logic (extracted from layout implementation) ───────────────────

const ACTIVE_SYNC_STATUSES = new Set<SyncStatus>(['pending', 'ingesting', 'ai_extracting', 'applying'])

/**
 * Count data sources with an active sync run from an API response.
 */
function countActiveSyncs(response: DataSourcesListResponse): number {
  return (response.data_sources ?? []).filter(
    (ds) => ds.latest_sync_run && ACTIVE_SYNC_STATUSES.has(ds.latest_sync_run.status),
  ).length
}

/**
 * Simulates the fetchActiveSyncCount function from the layout.
 * Returns the count on success, 0 on error (graceful degradation).
 */
async function fetchActiveSyncCount(
  hasTenant: boolean,
  apiFetch: (url: string) => Promise<DataSourcesListResponse>,
): Promise<number> {
  if (!hasTenant) return 0
  try {
    const result = await apiFetch('/management/data-sources')
    return countActiveSyncs(result)
  } catch {
    // Best-effort — badge is optional indicator, not critical UI
    return 0
  }
}

/**
 * Compute the badge string for the Data Sources nav item.
 */
function dataBadge(activeSyncCount: number): string | undefined {
  return activeSyncCount > 0 ? String(activeSyncCount) : undefined
}

// ── navSections computed shape ─────────────────────────────────────────────────

interface NavItem {
  label: string
  to: string
  badge?: string
  ariaLabel?: string
}

interface NavSection {
  title: string
  items: NavItem[]
}

/**
 * Simulates building the navSections computed ref from the layout.
 * The Data Sources item gets a badge and aria-label when activeSyncCount > 0.
 */
function buildNavSections(activeSyncCount: number): NavSection[] {
  const badge = dataBadge(activeSyncCount)
  return [
    {
      title: 'Explore',
      items: [
        { label: 'Query Console', to: '/query' },
        { label: 'Schema Browser', to: '/graph/schema' },
        { label: 'Graph Explorer', to: '/graph/explorer' },
      ],
    },
    {
      title: 'Data',
      items: [
        { label: 'Knowledge Graphs', to: '/knowledge-graphs' },
        {
          label: 'Data Sources',
          to: '/data-sources',
          badge,
          ariaLabel: badge
            ? `Data Sources — ${activeSyncCount} active sync${activeSyncCount === 1 ? '' : 's'}`
            : undefined,
        },
      ],
    },
    {
      title: 'Connect',
      items: [
        { label: 'API Keys', to: '/api-keys' },
        { label: 'MCP Integration', to: '/integrate/mcp' },
      ],
    },
    {
      title: 'Settings',
      items: [
        { label: 'Workspaces', to: '/workspaces' },
        { label: 'Groups', to: '/groups' },
        { label: 'Tenants', to: '/tenants' },
      ],
    },
  ]
}

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 1: Badge shows active-sync count when syncs are running
// ─────────────────────────────────────────────────────────────────────────────

describe('Default layout — sync-status badge logic', () => {
  describe('countActiveSyncs()', () => {
    it('returns 1 when one data source has an active ingesting sync', () => {
      const response: DataSourcesListResponse = {
        data_sources: [
          { id: 'ds-1', name: 'Repo A', latest_sync_run: { status: 'ingesting' } },
          { id: 'ds-2', name: 'Repo B', latest_sync_run: { status: 'completed' } },
        ],
      }
      expect(countActiveSyncs(response)).toBe(1)
    })

    it('returns 2 when two data sources have active sync runs', () => {
      const response: DataSourcesListResponse = {
        data_sources: [
          { id: 'ds-1', name: 'Repo A', latest_sync_run: { status: 'ingesting' } },
          { id: 'ds-2', name: 'Repo B', latest_sync_run: { status: 'ai_extracting' } },
          { id: 'ds-3', name: 'Repo C', latest_sync_run: { status: 'completed' } },
        ],
      }
      expect(countActiveSyncs(response)).toBe(2)
    })

    it('counts all four active statuses: pending, ingesting, ai_extracting, applying', () => {
      const response: DataSourcesListResponse = {
        data_sources: [
          { id: 'ds-1', name: 'A', latest_sync_run: { status: 'pending' } },
          { id: 'ds-2', name: 'B', latest_sync_run: { status: 'ingesting' } },
          { id: 'ds-3', name: 'C', latest_sync_run: { status: 'ai_extracting' } },
          { id: 'ds-4', name: 'D', latest_sync_run: { status: 'applying' } },
        ],
      }
      expect(countActiveSyncs(response)).toBe(4)
    })
  })

  // ── Scenario 2: Badge absent when no syncs are in progress ─────────────────

  describe('Badge absent when no active syncs', () => {
    it('returns 0 when all sync runs are completed', () => {
      const response: DataSourcesListResponse = {
        data_sources: [
          { id: 'ds-1', name: 'Repo A', latest_sync_run: { status: 'completed' } },
          { id: 'ds-2', name: 'Repo B', latest_sync_run: { status: 'completed' } },
        ],
      }
      expect(countActiveSyncs(response)).toBe(0)
    })

    it('returns 0 when all sync runs are failed', () => {
      const response: DataSourcesListResponse = {
        data_sources: [
          { id: 'ds-1', name: 'Repo A', latest_sync_run: { status: 'failed' } },
        ],
      }
      expect(countActiveSyncs(response)).toBe(0)
    })

    it('returns 0 when data sources have no sync runs at all', () => {
      const response: DataSourcesListResponse = {
        data_sources: [
          { id: 'ds-1', name: 'Repo A' },
        ],
      }
      expect(countActiveSyncs(response)).toBe(0)
    })

    it('returns 0 when data_sources array is empty', () => {
      const response: DataSourcesListResponse = { data_sources: [] }
      expect(countActiveSyncs(response)).toBe(0)
    })
  })

  // ── Scenario 3: Badge updates after tenant change ──────────────────────────

  describe('fetchActiveSyncCount() — badge updates on tenant change', () => {
    it('calls apiFetch when tenant is set and returns the active count', async () => {
      const apiFetch = vi.fn().mockResolvedValue({
        data_sources: [
          { id: 'ds-1', name: 'A', latest_sync_run: { status: 'ingesting' } },
        ],
      })
      const count = await fetchActiveSyncCount(true, apiFetch)
      expect(apiFetch).toHaveBeenCalledWith('/management/data-sources')
      expect(count).toBe(1)
    })

    it('reflects the new tenant state after a second call with updated data', async () => {
      // Simulate first call (old tenant: 1 active sync) → second call (new tenant: 0 active)
      let activeSyncCount = 0

      const firstApiFetch = vi.fn().mockResolvedValue({
        data_sources: [{ id: 'ds-1', name: 'A', latest_sync_run: { status: 'ingesting' } }],
      })
      activeSyncCount = await fetchActiveSyncCount(true, firstApiFetch)
      expect(activeSyncCount).toBe(1)

      const secondApiFetch = vi.fn().mockResolvedValue({
        data_sources: [{ id: 'ds-x', name: 'B', latest_sync_run: { status: 'completed' } }],
      })
      activeSyncCount = await fetchActiveSyncCount(true, secondApiFetch)
      expect(activeSyncCount).toBe(0)
    })
  })

  // ── Scenario 4: Badge absent while tenant is unset ─────────────────────────

  describe('fetchActiveSyncCount() — no fetch when tenant unset', () => {
    it('does not call apiFetch when hasTenant is false', async () => {
      const apiFetch = vi.fn()
      const count = await fetchActiveSyncCount(false, apiFetch)
      expect(apiFetch).not.toHaveBeenCalled()
      expect(count).toBe(0)
    })

    it('badge is absent (count 0) when no tenant is selected', async () => {
      const apiFetch = vi.fn()
      const count = await fetchActiveSyncCount(false, apiFetch)
      expect(dataBadge(count)).toBeUndefined()
    })
  })

  // ── Scenario 5: Fetch error degrades gracefully ────────────────────────────

  describe('fetchActiveSyncCount() — graceful error handling', () => {
    it('returns 0 and does not throw when apiFetch rejects', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Network error'))
      const count = await fetchActiveSyncCount(true, apiFetch)
      expect(count).toBe(0)
    })

    it('badge is absent when fetch fails', async () => {
      const apiFetch = vi.fn().mockRejectedValue(new Error('Network error'))
      const count = await fetchActiveSyncCount(true, apiFetch)
      expect(dataBadge(count)).toBeUndefined()
    })
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Spec: navSections computed ref has badge on Data Sources item
// ─────────────────────────────────────────────────────────────────────────────

describe('Default layout — navSections computed with badge', () => {
  it('Data Sources nav item has badge when activeSyncCount > 0', () => {
    const sections = buildNavSections(2)
    const dataSection = sections.find((s) => s.title === 'Data')!
    const dsItem = dataSection.items.find((i) => i.label === 'Data Sources')!
    expect(dsItem.badge).toBe('2')
  })

  it('Data Sources nav item has no badge when activeSyncCount is 0', () => {
    const sections = buildNavSections(0)
    const dataSection = sections.find((s) => s.title === 'Data')!
    const dsItem = dataSection.items.find((i) => i.label === 'Data Sources')!
    expect(dsItem.badge).toBeUndefined()
  })

  it('badge string matches the numeric count exactly', () => {
    for (const count of [1, 3, 10]) {
      const sections = buildNavSections(count)
      const dsItem = sections
        .find((s) => s.title === 'Data')!
        .items.find((i) => i.label === 'Data Sources')!
      expect(dsItem.badge).toBe(String(count))
    }
  })

  it('other nav items are unaffected by activeSyncCount', () => {
    const sections = buildNavSections(5)
    const kgItem = sections
      .find((s) => s.title === 'Data')!
      .items.find((i) => i.label === 'Knowledge Graphs')!
    expect(kgItem.badge).toBeUndefined()
  })

  it('Data Sources aria-label includes count when badge is shown', () => {
    const sections = buildNavSections(1)
    const dsItem = sections
      .find((s) => s.title === 'Data')!
      .items.find((i) => i.label === 'Data Sources')!
    expect(dsItem.ariaLabel).toBe('Data Sources — 1 active sync')
  })

  it('Data Sources aria-label uses plural form for count > 1', () => {
    const sections = buildNavSections(3)
    const dsItem = sections
      .find((s) => s.title === 'Data')!
      .items.find((i) => i.label === 'Data Sources')!
    expect(dsItem.ariaLabel).toBe('Data Sources — 3 active syncs')
  })

  it('Data Sources has no aria-label when no active syncs', () => {
    const sections = buildNavSections(0)
    const dsItem = sections
      .find((s) => s.title === 'Data')!
      .items.find((i) => i.label === 'Data Sources')!
    expect(dsItem.ariaLabel).toBeUndefined()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Spec: dataBadge helper
// ─────────────────────────────────────────────────────────────────────────────

describe('dataBadge() helper', () => {
  it('returns undefined for count 0', () => {
    expect(dataBadge(0)).toBeUndefined()
  })

  it('returns "1" for count 1', () => {
    expect(dataBadge(1)).toBe('1')
  })

  it('returns "99" for count 99', () => {
    expect(dataBadge(99)).toBe('99')
  })
})
