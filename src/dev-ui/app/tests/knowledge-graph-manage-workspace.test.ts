import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import {
  WORKSPACE_STEP_ORDER,
  WORKSPACE_STEP_TITLES,
  buildDataSourcesStepUrl,
  buildMaintainStepUrl,
  buildManageStepUrl,
  buildSuggestedNextStep,
  buildWorkspaceStepCards,
  isMaintenanceReady,
  resolveStepDestination,
  stepStatusTintClass,
} from '../utils/kgManageWorkspace'

const manageWorkspaceVue = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/[kgId]/manage.vue'),
  'utf-8',
)
const kgIndexVue = readFileSync(
  resolve(__dirname, '../pages/knowledge-graphs/index.vue'),
  'utf-8',
)
const dataSourcesVue = readFileSync(
  resolve(__dirname, '../pages/data-sources/index.vue'),
  'utf-8',
)
const sharedConversationPanelVue = readFileSync(
  resolve(__dirname, '../components/extraction/SharedConversationPanel.vue'),
  'utf-8',
)

const baseWorkspaceStatus = {
  workspace_mode: 'schema_bootstrap' as const,
  transition_eligible: false,
  readiness: {
    has_minimum_entity_types: false,
    has_minimum_relationship_types: false,
    prepopulated_types_ready: false,
    blocking_reasons: ['Missing entity types'],
  },
}

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

describe('KG-MANAGE-001 - manage entry navigation', () => {
  it('routes Manage action to graph-scoped manage workspace', () => {
    expect(kgIndexVue).toContain('navigateTo(`/knowledge-graphs/${kg.id}/manage`)')
  })

  it('loads graph identity for manage header and back action', () => {
    expect(manageWorkspaceVue).toContain('/management/knowledge-graphs/${kgId.value}')
    expect(manageWorkspaceVue).toContain('loadKgIdentity')
    expect(manageWorkspaceVue).toContain('Back to Knowledge Graphs')
  })
})

describe('KG-MANAGE-002 - workspace step card set', () => {
  it('renders Project workspace section with exactly four step cards', () => {
    expect(manageWorkspaceVue).toContain('Project workspace')
    expect(manageWorkspaceVue).toContain('workspaceStepCards')
    for (const stepId of WORKSPACE_STEP_ORDER) {
      expect(manageWorkspaceVue).toContain(WORKSPACE_STEP_TITLES[stepId])
    }
  })

  it('buildWorkspaceStepCards returns the canonical four-card set', () => {
    const cards = buildWorkspaceStepCards({
      kgId: 'kg-1',
      dataSourceCount: 1,
      maintenanceReadyCount: 0,
      mutationLogRunCount: 0,
      workspaceStatus: baseWorkspaceStatus,
    })

    expect(cards.map((card) => card.title)).toEqual([
      'Data Sources',
      'Graph Management',
      'MutationLogs',
      'Maintain',
    ])
  })
})

describe('KG-MANAGE-003 - suggested next step callout', () => {
  it('renders Suggested next step callout above the card grid', () => {
    expect(manageWorkspaceVue).toContain('Suggested next step')
    expect(manageWorkspaceVue).toContain('suggestedNextStep')
    expect(manageWorkspaceVue).toContain('openWorkspaceStep')
  })

  it('prioritizes data sources when no sources are connected', () => {
    const next = buildSuggestedNextStep({
      kgId: 'kg-1',
      dataSourceCount: 0,
      maintenanceReadyCount: 0,
      mutationLogRunCount: 0,
      workspaceStatus: baseWorkspaceStatus,
    })

    expect(next.stepId).toBe('data-sources')
    expect(next.actionLabel).toBe('Open')
  })

  it('uses Run action when maintenance is ready', () => {
    const next = buildSuggestedNextStep({
      kgId: 'kg-1',
      dataSourceCount: 2,
      maintenanceReadyCount: 1,
      mutationLogRunCount: 3,
      workspaceStatus: {
        workspace_mode: 'extraction_operations',
        transition_eligible: true,
        readiness: {
          has_minimum_entity_types: true,
          has_minimum_relationship_types: true,
          prepopulated_types_ready: true,
          blocking_reasons: [],
        },
      },
    })

    expect(next.stepId).toBe('maintain')
    expect(next.actionLabel).toBe('Run')
  })
})

describe('KG-MANAGE-004 - step card status semantics', () => {
  it('renders status label, tint, detail text, and primary action per card', () => {
    expect(manageWorkspaceVue).toContain('stepStatusTintClass')
    expect(manageWorkspaceVue).toContain('card.status')
    expect(manageWorkspaceVue).toContain('card.statusDetail')
    expect(manageWorkspaceVue).toContain('card.actionLabel')
  })

  it('maps each status label to a tint class', () => {
    expect(stepStatusTintClass('ready')).toContain('emerald')
    expect(stepStatusTintClass('in_progress')).toContain('blue')
    expect(stepStatusTintClass('needs_attention')).toContain('amber')
    expect(stepStatusTintClass('blocked')).toContain('destructive')
  })

  it('uses Open, Revisit, or Run action labels on cards', () => {
    const cards = buildWorkspaceStepCards({
      kgId: 'kg-1',
      dataSourceCount: 2,
      maintenanceReadyCount: 1,
      mutationLogRunCount: 4,
      workspaceStatus: {
        workspace_mode: 'extraction_operations',
        transition_eligible: true,
        readiness: {
          has_minimum_entity_types: true,
          has_minimum_relationship_types: true,
          prepopulated_types_ready: true,
          blocking_reasons: [],
        },
      },
    })

    expect(cards.every((card) => ['Open', 'Revisit', 'Run'].includes(card.actionLabel))).toBe(true)
    expect(cards.find((card) => card.id === 'maintain')?.actionLabel).toBe('Run')
  })
})

describe('KG-MANAGE-005 - graph-scoped data sources step', () => {
  it('routes Data Sources step with kg_id and manage return context', () => {
    expect(manageWorkspaceVue).toContain('buildDataSourcesStepUrl')
    expect(buildDataSourcesStepUrl('kg-abc')).toBe('/data-sources?kg_id=kg-abc&from=manage')
  })

  it('data-sources page preserves manage return path without auto-opening wizard', () => {
    expect(dataSourcesVue).toContain('from=manage')
    expect(dataSourcesVue).toContain('scopedKnowledgeGraphId')
    expect(dataSourcesVue).toContain('Back to workspace overview')
  })
})

describe('KG-MANAGE-015 - graph-scoped maintain step and round trip', () => {
  it('routes Maintain step with graph scope and maintenance focus', () => {
    expect(manageWorkspaceVue).toContain('buildMaintainStepUrl')
    expect(buildMaintainStepUrl('kg-abc')).toBe(
      '/data-sources?kg_id=kg-abc&from=manage&focus=maintain',
    )
  })

  it('returns to manage overview from in-page steps', () => {
    expect(manageWorkspaceVue).toContain('returnToWorkspaceOverview')
    expect(buildManageStepUrl('kg-abc')).toBe('/knowledge-graphs/kg-abc/manage')
    expect(resolveStepDestination('kg-abc', 'graph-management')).toBe(
      '/knowledge-graphs/kg-abc/manage?step=graph-management',
    )
  })

  it('detects maintenance readiness from commit diff semantics', () => {
    expect(isMaintenanceReady({
      last_extraction_baseline_commit: 'abc',
      tracked_branch_head_commit: 'def',
    })).toBe(true)
    expect(isMaintenanceReady({
      last_extraction_baseline_commit: 'abc',
      tracked_branch_head_commit: 'abc',
    })).toBe(false)
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
