import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const manageWorkspaceVue = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/[kgId]/manage.vue'),
  'utf-8',
)
const sharedConversationPanelVue = readFileSync(
  resolve(__dirname, '../components/extraction/SharedConversationPanel.vue'),
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

  it('loads scoped session history with run metrics after clear chat', () => {
    expect(manageWorkspaceVue).toContain('loadSessionHistory')
    expect(manageWorkspaceVue).toContain('/sessions/${sessionMode.value}/history')
    expect(manageWorkspaceVue).toContain('sessionHistory')
    expect(manageWorkspaceVue).toContain('run_metrics')
    expect(manageWorkspaceVue).toContain('Session History')
  })


  it('uses shared conversation panel for bootstrap and extraction sessions', () => {
    expect(manageWorkspaceVue).toContain('SharedConversationPanel')
    expect(manageWorkspaceVue).toContain('sessionMode')
    expect(manageWorkspaceVue).toContain('/sessions/${sessionMode.value}/active')
  })

  it('supports explicit Clear chat reset for extraction session', () => {
    expect(manageWorkspaceVue).toContain('clearChat')
    expect(manageWorkspaceVue).toContain('/sessions/${sessionMode.value}/clear-chat')
    expect(sharedConversationPanelVue).toContain('Clear chat')
  })

  it('provides tabbed lower operations area for extraction workflows', () => {
    expect(manageWorkspaceVue).toContain('Operations Workspace')
    expect(manageWorkspaceVue).toContain('TabsTrigger value="extraction-jobs"')
    expect(manageWorkspaceVue).toContain('TabsTrigger value="manual-mutations"')
    expect(manageWorkspaceVue).toContain('TabsTrigger value="run-logs"')
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

describe('Knowledge Graph Manage Workspace - bootstrap readiness guidance', () => {
  it('renders a bootstrap progress checklist section with explicit checks', () => {
    expect(manageWorkspaceVue).toContain('Bootstrap Progress Checklist')
    expect(manageWorkspaceVue).toContain('progressChecklist')
    expect(manageWorkspaceVue).toContain('Minimum entity types')
    expect(manageWorkspaceVue).toContain('Minimum relationship types')
    expect(manageWorkspaceVue).toContain('Prepopulated instance coverage')
  })

  it('renders diagnostics panel with prepopulated type failures and blocking reasons', () => {
    expect(manageWorkspaceVue).toContain('Validation Diagnostics')
    expect(manageWorkspaceVue).toContain('prepopulated_types_without_instances')
    expect(manageWorkspaceVue).toContain('blocking_reasons')
  })

  it('renders explicit next steps guidance for transition readiness', () => {
    expect(manageWorkspaceVue).toContain('Next Steps')
    expect(manageWorkspaceVue).toContain('Run Validate to refresh readiness signals')
    expect(manageWorkspaceVue).toContain('Transition is enabled')
  })
})

describe('Shared conversation panel - extraction UX contract', () => {
  it('renders resume-session action and explicit server-side persistence note', () => {
    expect(sharedConversationPanelVue).toContain('Resume session')
    expect(sharedConversationPanelVue).toContain('No local cache: conversation state is server-side only.')
  })

  it('renders clear-chat confirmation dialog before emitting clear action', () => {
    expect(sharedConversationPanelVue).toContain('Clear conversation?')
    expect(sharedConversationPanelVue).toContain('confirmClearChat')
    expect(sharedConversationPanelVue).toContain("emit('clearChat')")
  })

  it('renders activity/thinking timeline lines and auto-scrolls timeline updates', () => {
    expect(sharedConversationPanelVue).toContain('activityTimeline')
    expect(sharedConversationPanelVue).toContain('timelineRef')
    expect(sharedConversationPanelVue).toContain('scrollTop = timelineRef.value.scrollHeight')
  })
})
