import { describe, expect, it } from 'vitest'
import {
  buildWorkspaceHubNextStep,
  buildWorkspaceHubTiles,
  resolveWorkspaceHubPhaseBadge,
  workspaceHubDescription,
  workspaceHubStepBadgeClass,
  workspaceHubTileClasses,
} from '../utils/kgManageWorkspaceHub'

const baseStatus = {
  workspace_mode: 'schema_bootstrap' as const,
  transition_eligible: false,
  readiness: {
    has_minimum_entity_types: false,
    has_minimum_relationship_types: false,
    prepopulated_types_ready: false,
    blocking_reasons: ['Missing entity types'],
  },
}

const baseInput = {
  kgId: 'kg-1',
  dataSourceCount: 0,
  preparedSourceCount: 0,
  maintenanceReadyCount: 0,
  mutationLogRunCount: 0,
  entityTypeLabels: [] as string[],
  relationshipTypeLabels: [] as string[],
  workspaceStatus: baseStatus,
}

describe('kgManageWorkspaceHub', () => {
  it('returns four numbered hub tiles in workspace order', () => {
    const tiles = buildWorkspaceHubTiles(baseInput)
    expect(tiles).toHaveLength(4)
    expect(tiles.map((tile) => tile.step)).toEqual([1, 2, 3, 4])
    expect(tiles.map((tile) => tile.key)).toEqual([
      'data-sources',
      'graph-management',
      'mutation-logs',
      'maintain',
    ])
  })

  it('locks mutation logs and maintain when prerequisites are missing', () => {
    const tiles = buildWorkspaceHubTiles(baseInput)
    expect(tiles.find((tile) => tile.key === 'mutation-logs')?.enabled).toBe(false)
    expect(tiles.find((tile) => tile.key === 'maintain')?.enabled).toBe(false)
  })

  it('labels the graph-management hub tile as Graph Management', () => {
    const tiles = buildWorkspaceHubTiles(baseInput)
    expect(tiles.find((tile) => tile.key === 'graph-management')?.title).toBe('Graph Management')
  })

  it('marks sources phase complete when all sources are prepared', () => {
    const tiles = buildWorkspaceHubTiles({
      ...baseInput,
      dataSourceCount: 2,
      preparedSourceCount: 2,
    })
    const sourcesTile = tiles.find((tile) => tile.key === 'data-sources')
    expect(sourcesTile?.done).toBe(true)
    expect(sourcesTile?.tone).toBe('success')
    expect(resolveWorkspaceHubPhaseBadge({
      ...baseInput,
      dataSourceCount: 2,
      preparedSourceCount: 2,
    }).label).toBe('Graph Management')
  })

  it('builds a primary next-step CTA while sources phase is incomplete', () => {
    const next = buildWorkspaceHubNextStep(baseInput)
    expect(next.primaryPhase).toBe(true)
    expect(next.title).toBe('Data Sources')
    expect(next.label).toContain('Open')
  })

  it('maps tile tones to k-extract style surface classes', () => {
    expect(workspaceHubTileClasses({ enabled: true, highlight: false, tone: 'success' })).toContain('green')
    expect(workspaceHubTileClasses({ enabled: true, highlight: true, tone: 'primary' })).toContain('primary')
    expect(workspaceHubStepBadgeClass({ enabled: true, done: true, tone: 'success' })).toContain('green-500')
  })

  it('describes workspace guidance by phase', () => {
    expect(workspaceHubDescription(baseInput)).toContain('Data sources')
    expect(workspaceHubDescription({
      ...baseInput,
      dataSourceCount: 1,
      preparedSourceCount: 1,
    })).toContain('Graph Management')
  })
})
