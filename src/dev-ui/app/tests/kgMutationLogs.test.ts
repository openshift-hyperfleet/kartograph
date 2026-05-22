import { describe, expect, it } from 'vitest'
import {
  MUTATION_LOG_NO_PREVIEW_MESSAGE,
  buildMutationLogEntryPreviewUrl,
  collectScopedMutationLogRuns,
  hasMutationLogEntryPreviewPage,
  isMutationLogRunForKnowledgeGraph,
  resolveDefaultSelectedMutationLogRunId,
  sortMutationLogRunsNewestFirst,
} from '../utils/kgMutationLogs'

const kgId = 'kg-target'

function makeRun(overrides: Partial<ReturnType<typeof baseRun>> = {}) {
  return { ...baseRun(), ...overrides }
}

function baseRun() {
  return {
    id: 'run-1',
    data_source_id: 'ds-1',
    status: 'completed',
    started_at: '2026-05-20T10:00:00Z',
    completed_at: '2026-05-20T10:05:00Z',
    mutation_log_id: 'mlog-1',
    knowledge_graph_id: kgId,
    session_id: 'sess-1',
    actor_id: 'actor-1',
    operation_counts: { create_node: 2 },
    token_usage_total: 100,
    cost_total_usd: 0.5,
    error: null,
  }
}

describe('KG-MANAGE-012 - graph-scoped mutation run list', () => {
  it('includes only runs with mutation logs scoped to the selected knowledge graph', () => {
    const runs = collectScopedMutationLogRuns(
      kgId,
      [{ id: 'ds-1', name: 'Source A' }],
      {
        'ds-1': [
          makeRun({ id: 'run-a', mutation_log_id: 'mlog-a' }),
          makeRun({ id: 'run-b', mutation_log_id: 'mlog-b', knowledge_graph_id: 'kg-other' }),
          makeRun({ id: 'run-c', mutation_log_id: null }),
        ],
      },
    )

    expect(runs.map((run) => run.id)).toEqual(['run-a'])
    expect(runs[0]?.data_source_name).toBe('Source A')
  })

  it('orders runs newest-first by started_at', () => {
    const runs = sortMutationLogRunsNewestFirst([
      makeRun({ id: 'older', started_at: '2026-05-01T10:00:00Z' }),
      makeRun({ id: 'newer', started_at: '2026-05-22T10:00:00Z' }),
    ])

    expect(runs.map((run) => run.id)).toEqual(['newer', 'older'])
  })

  it('keeps current selection when still present otherwise selects newest run', () => {
    const runs = [
      makeRun({ id: 'newest', started_at: '2026-05-22T10:00:00Z' }),
      makeRun({ id: 'selected', started_at: '2026-05-21T10:00:00Z' }),
    ]

    expect(resolveDefaultSelectedMutationLogRunId(runs, 'selected')).toBe('selected')
    expect(resolveDefaultSelectedMutationLogRunId(runs, 'missing')).toBe('newest')
  })

  it('allows legacy runs without knowledge_graph_id when loaded from graph data sources', () => {
    expect(
      isMutationLogRunForKnowledgeGraph(
        { mutation_log_id: 'mlog-legacy', knowledge_graph_id: null },
        kgId,
      ),
    ).toBe(true)
  })
})

describe('KG-MANAGE-013 - run detail richness helpers', () => {
  it('builds paginated mutation-log entry preview URLs', () => {
    expect(buildMutationLogEntryPreviewUrl('ds-1', 'run-1')).toBe(
      '/management/data-sources/ds-1/sync-runs/run-1/mutation-log-entries?offset=0&limit=20',
    )
    expect(buildMutationLogEntryPreviewUrl('ds-1', 'run-1', 20, 10)).toBe(
      '/management/data-sources/ds-1/sync-runs/run-1/mutation-log-entries?offset=20&limit=10',
    )
  })
})

describe('KG-MANAGE-014 - no-preview fallback helpers', () => {
  it('uses explicit no-preview messaging constant', () => {
    expect(MUTATION_LOG_NO_PREVIEW_MESSAGE).toContain('not available')
  })

  it('detects when entry preview pages are unavailable', () => {
    expect(hasMutationLogEntryPreviewPage(null)).toBe(false)
    expect(
      hasMutationLogEntryPreviewPage({
        entries: [],
        total: 0,
        offset: 0,
        limit: 20,
        preview_available: false,
      }),
    ).toBe(false)
    expect(
      hasMutationLogEntryPreviewPage({
        entries: [{ line_number: 1, operation_class: 'create_node', summary: 'Create Person' }],
        total: 1,
        offset: 0,
        limit: 20,
        preview_available: true,
      }),
    ).toBe(true)
  })
})
