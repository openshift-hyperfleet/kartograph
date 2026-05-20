import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const manageWorkspaceVue = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/[kgId]/manage.vue'),
  'utf-8',
)

describe('Knowledge Graph Manage Workspace - mode-aware controls', () => {
  it('loads workspace status projection from management API', () => {
    expect(manageWorkspaceVue).toContain('/workspace-status')
    expect(manageWorkspaceVue).toContain('loadWorkspaceStatus')
  })

  it('exposes Validate action calling workspace validate endpoint', () => {
    expect(manageWorkspaceVue).toContain('validateWorkspace')
    expect(manageWorkspaceVue).toContain('/workspace/validate')
    expect(manageWorkspaceVue).toContain('Validate')
  })

  it('exposes Go to Extraction/Mutations action calling transition endpoint', () => {
    expect(manageWorkspaceVue).toContain('transitionToExtraction')
    expect(manageWorkspaceVue).toContain('/workspace/transition-to-extraction')
    expect(manageWorkspaceVue).toContain('Go to Extraction/Mutations')
  })

  it('renders readiness result blocks and blocking reasons list', () => {
    expect(manageWorkspaceVue).toContain('Readiness Results')
    expect(manageWorkspaceVue).toContain('blocking_reasons')
    expect(manageWorkspaceVue).toContain('prepopulated_types_ready')
  })

  it('renders session pointer references for bootstrap and extraction modes', () => {
    expect(manageWorkspaceVue).toContain('Session Pointers')
    expect(manageWorkspaceVue).toContain('active_schema_bootstrap_session_id')
    expect(manageWorkspaceVue).toContain('active_extraction_operations_session_id')
  })
})

describe('Knowledge Graph Manage Workspace - mutation log browser', () => {
  it('renders mutation log browser card and scoped run listing', () => {
    expect(manageWorkspaceVue).toContain('MutationLog Browser')
    expect(manageWorkspaceVue).toContain('loadMutationLogRuns')
    expect(manageWorkspaceVue).toContain('/management/knowledge-graphs/${kgId.value}/data-sources')
  })

  it('loads sync runs per data source and filters to mutation-log runs', () => {
    expect(manageWorkspaceVue).toContain('/management/data-sources/${ds.id}/sync-runs')
    expect(manageWorkspaceVue).toContain('if (!run.mutation_log_id) continue')
  })

  it('renders run detail summary with token and cost metrics', () => {
    expect(manageWorkspaceVue).toContain('Token usage')
    expect(manageWorkspaceVue).toContain('Cost (USD)')
    expect(manageWorkspaceVue).toContain('token_usage_total')
    expect(manageWorkspaceVue).toContain('cost_total_usd')
  })

  it('renders per-entry operation preview rows from operation_counts', () => {
    expect(manageWorkspaceVue).toContain('Per-entry operation previews')
    expect(manageWorkspaceVue).toContain('operation_counts')
    expect(manageWorkspaceVue).toContain('Object.entries(selectedMutationLogRun.operation_counts)')
  })
})
