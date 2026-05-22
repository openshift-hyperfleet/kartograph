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
import {
  GRAPH_MANAGEMENT_MODE_LABELS,
  GRAPH_MANAGEMENT_MODE_ORDER,
  buildGraphManagementRailItems,
  buildGraphManagementStepUrl,
  filterRailItemsForMode,
  isRailItemValidInMode,
  parseGraphManagementModeQuery,
  resolveDefaultGraphManagementMode,
  resolveRailSelectionForMode,
  resolveSharedSessionMode,
} from '../utils/kgGraphManagement'

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

describe('Knowledge Graph Manage Workspace - graph management controls', () => {
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
})

describe('Knowledge Graph Manage Workspace - mutation log browser', () => {
  it('renders mutation log step with scoped run listing', () => {
    expect(manageWorkspaceVue).toContain('MutationLogs')
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

  it('accepts mode-aware input placeholder and session status props', () => {
    expect(sharedConversationPanelVue).toContain('inputPlaceholder')
    expect(sharedConversationPanelVue).toContain('sessionStatusLabel')
  })
})

describe('KG-MANAGE-006 - graph management conversation-first layout', () => {
  it('renders graph management step with shared conversation panel', () => {
    expect(manageWorkspaceVue).toContain("activeStep === 'graph-management'")
    expect(manageWorkspaceVue).toContain('SharedConversationPanel')
    expect(manageWorkspaceVue).toContain('graph-management-controls')
  })

  it('uses one shared session endpoint across UI mode changes', () => {
    expect(manageWorkspaceVue).toContain('sharedSessionMode')
    expect(manageWorkspaceVue).toContain('/sessions/${sharedSessionMode.value}/active')
    expect(manageWorkspaceVue).not.toContain('watch(graphManagementMode')
  })
})

describe('KG-MANAGE-007 - graph management modes', () => {
  it('supports the three canonical graph management modes', () => {
    for (const mode of GRAPH_MANAGEMENT_MODE_ORDER) {
      expect(GRAPH_MANAGEMENT_MODE_LABELS[mode]).toBeTruthy()
      expect(manageWorkspaceVue).toContain(mode)
    }
    expect(manageWorkspaceVue).toContain('graphManagementMode')
    expect(manageWorkspaceVue).toContain('parseGraphManagementModeQuery')
  })

  it('defaults mode from workspace lifecycle state', () => {
    expect(resolveDefaultGraphManagementMode('schema_bootstrap')).toBe('initial-schema-design')
    expect(resolveDefaultGraphManagementMode('extraction_operations')).toBe('extraction-jobs')
  })

  it('updates chat placeholder by mode without changing session scope', () => {
    expect(manageWorkspaceVue).toContain('graphManagementInputPlaceholder')
    expect(manageWorkspaceVue).toContain('GRAPH_MANAGEMENT_INPUT_PLACEHOLDERS')
  })
})

describe('KG-MANAGE-008 - hybrid lower panel shared rail', () => {
  it('renders persistent status and artifact rail with keyboard selection', () => {
    expect(manageWorkspaceVue).toContain('graph-management-rail')
    expect(manageWorkspaceVue).toContain('buildGraphManagementRailItems')
    expect(manageWorkspaceVue).toContain('role="listbox"')
    expect(manageWorkspaceVue).toContain('@keydown')
  })

  it('builds rail items with status and last-updated metadata', () => {
    const items = buildGraphManagementRailItems({
      workspaceMode: 'schema_bootstrap',
      transitionEligible: false,
      blockingReasonCount: 1,
      prepopulatedGapCount: 0,
      sessionUpdatedAt: '2026-05-22T12:00:00Z',
      hasActiveSession: true,
    })

    expect(items.every((item) => item.status && item.lastUpdated && item.label)).toBe(true)
    expect(items.find((item) => item.id === 'session-pointers')?.modes).toEqual(
      GRAPH_MANAGEMENT_MODE_ORDER,
    )
  })
})

describe('KG-MANAGE-009 - hybrid lower panel mode-specific detail', () => {
  it('renders mode-specific detail panel content regions', () => {
    expect(manageWorkspaceVue).toContain('graph-management-detail')
    expect(manageWorkspaceVue).toContain('selectedRailItemId')
    expect(manageWorkspaceVue).toContain("selectedRailItemId === 'schema-readiness'")
    expect(manageWorkspaceVue).toContain("graphManagementMode === 'extraction-jobs'")
    expect(manageWorkspaceVue).toContain("graphManagementMode === 'one-off-mutations'")
  })

  it('filters rail items to the active mode', () => {
    const items = buildGraphManagementRailItems({
      workspaceMode: 'extraction_operations',
      transitionEligible: true,
      blockingReasonCount: 0,
      prepopulatedGapCount: 0,
      sessionUpdatedAt: null,
      hasActiveSession: true,
    })

    expect(filterRailItemsForMode(items, 'extraction-jobs').map((item) => item.id)).toContain(
      'extraction-jobs-setup',
    )
    expect(filterRailItemsForMode(items, 'one-off-mutations').map((item) => item.id)).toContain(
      'mutation-authoring',
    )
  })
})

describe('KG-MANAGE-010 - schema design parity behavior', () => {
  it('exposes schema readiness and validation detail in initial schema design mode', () => {
    expect(manageWorkspaceVue).toContain('progressChecklist')
    expect(manageWorkspaceVue).toContain('Bootstrap Progress Checklist')
    expect(manageWorkspaceVue).toContain('blocking_reasons')
    expect(manageWorkspaceVue).toContain('prepopulated_types_without_instances')
  })

  it('keeps validate and transition controls available for schema design work', () => {
    expect(manageWorkspaceVue).toContain('validateWorkspace')
    expect(manageWorkspaceVue).toContain('transitionToExtraction')
    expect(manageWorkspaceVue).toContain('canTransition')
  })
})

describe('KG-MANAGE-011 - session reset behavior', () => {
  it('supports explicit clear chat reset on the shared session', () => {
    expect(manageWorkspaceVue).toContain('clearChat')
    expect(manageWorkspaceVue).toContain('/sessions/${sharedSessionMode.value}/clear-chat')
    expect(sharedConversationPanelVue).toContain('Clear chat')
  })

  it('keeps graph management mode unchanged after clear chat', () => {
    const clearChatBlock = manageWorkspaceVue.match(
      /async function clearChat\(\) \{[\s\S]*?\n\}/,
    )?.[0] ?? ''
    expect(clearChatBlock).toContain('clearChat')
    expect(clearChatBlock).not.toContain('graphManagementMode')
  })
})

describe('KG-MANAGE-016 - graph management top controls', () => {
  it('renders mode switcher, session status, and validation affordance without scrolling', () => {
    expect(manageWorkspaceVue).toContain('graph-management-controls')
    expect(manageWorkspaceVue).toContain('graphManagementModeLabel')
    expect(manageWorkspaceVue).toContain('sessionStatusLabel')
    expect(manageWorkspaceVue).toContain('validateWorkspace')
    expect(manageWorkspaceVue).toContain('Clear chat')
  })

  it('maps shared session mode from workspace lifecycle without UI mode coupling', () => {
    expect(resolveSharedSessionMode('schema_bootstrap')).toBe('schema_bootstrap')
    expect(resolveSharedSessionMode('extraction_operations')).toBe('extraction_operations')
  })

  it('preserves rail selection across mode changes when still valid', () => {
    const items = buildGraphManagementRailItems({
      workspaceMode: 'extraction_operations',
      transitionEligible: true,
      blockingReasonCount: 0,
      prepopulatedGapCount: 0,
      sessionUpdatedAt: '2026-05-22T12:00:00Z',
      hasActiveSession: true,
    })

    expect(
      resolveRailSelectionForMode('session-pointers', 'extraction-jobs', items),
    ).toBe('session-pointers')
    expect(
      isRailItemValidInMode('schema-readiness', 'extraction-jobs', items),
    ).toBe(false)
    expect(
      resolveRailSelectionForMode('schema-readiness', 'extraction-jobs', items),
    ).toBe('session-pointers')
  })

  it('builds graph management URLs with mode query for keyboard navigation', () => {
    expect(buildGraphManagementStepUrl('kg-abc', 'one-off-mutations')).toBe(
      '/knowledge-graphs/kg-abc/manage?step=graph-management&gm_mode=one-off-mutations',
    )
    expect(parseGraphManagementModeQuery('initial-schema-design')).toBe('initial-schema-design')
  })
})
