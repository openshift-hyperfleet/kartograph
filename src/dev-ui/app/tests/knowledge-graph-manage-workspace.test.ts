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
const manageWorkspaceHubTs = readFileSync(
  resolve(__dirname, '../utils/kgManageWorkspaceHub.ts'),
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

  it('loads scoped session history with run metrics after clear chat', () => {
    expect(manageWorkspaceVue).toContain('loadSessionHistory')
    expect(manageWorkspaceVue).toContain('/sessions/${sharedSessionMode.value}/history')
    expect(manageWorkspaceVue).toContain('sessionHistory')
    expect(manageWorkspaceVue).toContain('run_metrics')
    expect(manageWorkspaceVue).toContain('Session History')
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
    expect(manageWorkspaceVue).toContain('collectScopedMutationLogRuns')
  })

  it('renders run detail summary with token and cost metrics', () => {
    expect(manageWorkspaceVue).toContain('Token usage')
    expect(manageWorkspaceVue).toContain('Cost (USD)')
    expect(manageWorkspaceVue).toContain('token_usage_total')
    expect(manageWorkspaceVue).toContain('cost_total_usd')
  })

  it('separates operation class counts from per-entry previews', () => {
    expect(manageWorkspaceVue).toContain('Operation class counts')
    expect(manageWorkspaceVue).toContain('Per-entry operation previews')
    expect(manageWorkspaceVue).toContain('Object.entries(selectedMutationLogRun.operation_counts)')
    expect(manageWorkspaceVue).toContain('loadMutationLogEntryPreviews')
  })
})

describe('KG-MANAGE-012 - graph-scoped mutation run list', () => {
  it('loads runs only from graph-scoped data sources with KG metadata filtering', () => {
    expect(manageWorkspaceVue).toContain('collectScopedMutationLogRuns')
    expect(manageWorkspaceVue).toContain('knowledge_graph_id')
  })

  it('defaults run list ordering to newest-first', () => {
    expect(manageWorkspaceVue).toContain('collectScopedMutationLogRuns')
    expect(manageWorkspaceVue).toContain('resolveDefaultSelectedMutationLogRunId')
  })

  it('shows status, timestamp, source, and run identifier in run list items', () => {
    expect(manageWorkspaceVue).toContain('run.data_source_name')
    expect(manageWorkspaceVue).toContain('run.started_at')
    expect(manageWorkspaceVue).toContain('run.status')
    expect(manageWorkspaceVue).toContain('run.mutation_log_id')
  })
})

describe('KG-MANAGE-013 - run detail richness', () => {
  it('renders run summary, session reference, token/cost metrics, and operation counts', () => {
    expect(manageWorkspaceVue).toContain('Run summary')
    expect(manageWorkspaceVue).toContain('Session')
    expect(manageWorkspaceVue).toContain('Token usage')
    expect(manageWorkspaceVue).toContain('Cost (USD)')
    expect(manageWorkspaceVue).toContain('Operation class counts')
  })

  it('loads paginated per-entry previews from mutation-log-entries API', () => {
    expect(manageWorkspaceVue).toContain('buildMutationLogEntryPreviewUrl')
    expect(manageWorkspaceVue).toContain('loadMutationLogEntryPreviews')
    expect(manageWorkspaceVue).toContain('mutationLogEntryPreviewPage')
  })
})

describe('KG-MANAGE-014 - no-preview fallback state', () => {
  it('shows explicit fallback when entry previews are unavailable', () => {
    expect(manageWorkspaceVue).toContain('MUTATION_LOG_NO_PREVIEW_MESSAGE')
    expect(manageWorkspaceVue).toContain('hasMutationLogEntryPreviewPage')
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

describe('KG-MANAGE-002 - workspace hub tile set', () => {
  it('renders Project workspace section with hub tiles and stats', () => {
    expect(manageWorkspaceVue).toContain('Project workspace')
    expect(manageWorkspaceVue).toContain('workspaceHubTiles')
    expect(manageWorkspaceVue).toContain('workspaceHubTileClasses')
    expect(manageWorkspaceVue).toContain('Entity Types')
    expect(manageWorkspaceVue).toContain('Relationship Types')
    expect(manageWorkspaceVue).toContain('Mutation Runs')
    expect(manageWorkspaceHubTs).toContain('Data sources')
    expect(manageWorkspaceHubTs).toContain('Design')
    expect(manageWorkspaceHubTs).toContain('Mutation logs')
    expect(manageWorkspaceHubTs).toContain('Maintain')
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
  it('renders next-step callout in the workspace hub card', () => {
    expect(manageWorkspaceVue).toContain('Suggested next step')
    expect(manageWorkspaceVue).toContain('workspaceHubNextStep')
    expect(manageWorkspaceVue).toContain('Next step')
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

describe('KG-MANAGE-004 - workspace hub tile semantics', () => {
  it('renders hub tile classes, badges, subtitles, and link labels', () => {
    expect(manageWorkspaceVue).toContain('workspaceHubTileClasses')
    expect(manageWorkspaceVue).toContain('workspaceHubStepBadgeClass')
    expect(manageWorkspaceVue).toContain('item.subtitle')
    expect(manageWorkspaceVue).toContain('item.linkLabel')
    expect(manageWorkspaceVue).toContain('item.lockedReason')
  })

  it('maps each status label to a tint class in graph-management rail', () => {
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
  it('keeps data-sources route utility for workspace cards but not graph-management redirects', () => {
    expect(manageWorkspaceVue).not.toContain('navigateTo(buildDataSourcesStepUrl(kgId))')
    expect(buildDataSourcesStepUrl('kg-abc', 0)).toBe('/knowledge-graphs/kg-abc/data-sources/new')
    expect(buildDataSourcesStepUrl('kg-abc', 2)).toBe('/knowledge-graphs/kg-abc/data-sources')
  })

  it('manage workspace passes data source count when opening data-sources step', () => {
    expect(manageWorkspaceVue).toContain('dataSourceCount: dataSourceCount.value')
  })

  it('kg-scoped data sources pages preserve manage return path', () => {
    const kgDataSourcesIndex = readFileSync(
      resolve(__dirname, '../pages/knowledge-graphs/[kgId]/data-sources/index.vue'),
      'utf-8',
    )
    expect(kgDataSourcesIndex).toContain('Back to workspace overview')
    expect(kgDataSourcesIndex).toContain('buildKgManageUrl')
    expect(kgDataSourcesIndex).toContain('Data sources overview')
    expect(kgDataSourcesIndex).toContain('max-w-7xl')
  })
})

describe('KG-MANAGE-015 - graph-scoped maintain step and round trip', () => {
  it('keeps maintain route utility for workspace cards but not graph-management redirects', () => {
    expect(manageWorkspaceVue).not.toContain('navigateTo(buildMaintainStepUrl(kgId))')
    expect(buildMaintainStepUrl('kg-abc')).toBe(
      '/knowledge-graphs/kg-abc/data-sources?focus=maintain',
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
  it('renders phase-2 style conversational intelligence header and resume action', () => {
    expect(sharedConversationPanelVue).toContain('Graph Management Assistant')
    expect(sharedConversationPanelVue).toContain('Resume session')
    expect(sharedConversationPanelVue).toContain('Sparkles')
  })

  it('renders clear-chat confirmation dialog before emitting clear action', () => {
    expect(sharedConversationPanelVue).toContain('Clear conversation?')
    expect(sharedConversationPanelVue).toContain('confirmClearChat')
    expect(sharedConversationPanelVue).toContain("emit('clearChat')")
  })

  it('renders bubble chat, thinking state, and auto-scroll', () => {
    expect(sharedConversationPanelVue).toContain('thinkingDisplaySlots')
    expect(sharedConversationPanelVue).toContain('chatScrollRef')
    expect(sharedConversationPanelVue).toContain('renderAssistantHtml')
    expect(sharedConversationPanelVue).toContain('scrollToBottom')
    expect(sharedConversationPanelVue).toContain('el.scrollTop = el.scrollHeight')
  })

  it('accepts mode-aware input placeholder and session status props', () => {
    expect(sharedConversationPanelVue).toContain('inputPlaceholder')
    expect(sharedConversationPanelVue).toContain('sessionStatusLabel')
    expect(sharedConversationPanelVue).toContain('footerHint')
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
    expect(manageWorkspaceVue).toContain('isGraphManagementModeUnlocked')
    expect(manageWorkspaceVue).toContain('graphManagementModeLockReason')
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
  it('renders side-by-side schema artifacts and session pointers panels', () => {
    expect(manageWorkspaceVue).toContain('graph-management-artifacts')
    expect(manageWorkspaceVue).toContain('Schema &amp; artifacts')
    expect(manageWorkspaceVue).toContain('graph-management-session-pointers')
    expect(manageWorkspaceVue).toContain('graphManagementArtifactRowClass')
    expect(manageWorkspaceVue).toContain('schemaRailItems')
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
    expect(manageWorkspaceVue).toContain("selectedRailItemId === 'extraction-jobs-setup'")
    expect(manageWorkspaceVue).toContain("selectedRailItemId === 'mutation-authoring'")
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

describe('KG-MANAGE-017 - chat input keyboard contract', () => {
  it('wires Enter-to-send and Shift+Enter newline handling in shared conversation panel', () => {
    expect(sharedConversationPanelVue).toContain('handleComposerEnter')
    expect(sharedConversationPanelVue).toContain('@keydown.enter="handleComposerEnter"')
    expect(sharedConversationPanelVue).toContain('Shift+Enter for a new line')
    expect(sharedConversationPanelVue).toContain("emit('sendMessage'")
    expect(manageWorkspaceVue).toContain('@send-message="sendChatMessage"')
  })
})

describe('KG-MANAGE-018 - keyboard operable step and rail actions', () => {
  it('uses native links for workspace hub tiles', () => {
    expect(manageWorkspaceVue).toContain('workspaceHubTiles')
    expect(manageWorkspaceVue).toContain('<NuxtLink')
    expect(manageWorkspaceVue).toContain('focus-visible:ring-2 focus-visible:ring-ring')
  })

  it('supports keyboard activation for schema artifact navigation', () => {
    expect(manageWorkspaceVue).toContain('onSchemaRailKeydown')
    expect(manageWorkspaceVue).toContain('@keydown="onSchemaRailKeydown($event, item.id)"')
  })

  it('exposes keyboard-reachable graph management mode switch tabs', () => {
    expect(manageWorkspaceVue).toContain('role="tablist"')
    expect(manageWorkspaceVue).toContain('onModeSwitchKeydown')
    expect(manageWorkspaceVue).toContain('@keydown="onModeSwitchKeydown($event, mode)"')
  })
})

describe('KG-MANAGE-019 - section-specific loading, empty, and error states', () => {
  it('uses section state contracts for workspace, graph management, and mutation logs', () => {
    expect(manageWorkspaceVue).toContain('resolveSectionState')
    expect(manageWorkspaceVue).toContain('workspaceOverviewState')
    expect(manageWorkspaceVue).toContain('graphManagementSectionState')
    expect(manageWorkspaceVue).toContain('mutationLogsSectionState')
    expect(manageWorkspaceVue).toContain('Retry workspace load')
    expect(manageWorkspaceVue).toContain('Retry mutation log load')
    expect(manageWorkspaceVue).toContain('Retry session load')
  })

  it('renders actionable empty states for mutation log runs', () => {
    expect(manageWorkspaceVue).toContain('mutationLogsSectionState.actionLabel')
    expect(manageWorkspaceVue).toContain('Refresh runs')
  })
})

describe('KG-MANAGE-020 - forbidden and disabled action restrictions', () => {
  it('detects forbidden responses and surfaces explicit restriction messaging', () => {
    expect(manageWorkspaceVue).toContain('isForbiddenHttpError')
    expect(manageWorkspaceVue).toContain('workspaceForbiddenReason')
    expect(manageWorkspaceVue).toContain('sessionForbiddenReason')
    expect(manageWorkspaceVue).toContain('role="alert"')
    expect(manageWorkspaceVue).toContain(':forbidden="sessionForbidden"')
    expect(sharedConversationPanelVue).toContain('forbidden?: boolean')
    expect(sharedConversationPanelVue).toContain('v-if="forbidden"')
  })

  it('explains disabled transition actions and avoids partial updates on forbidden', () => {
    expect(manageWorkspaceVue).toContain('transitionRestrictionReason')
    expect(manageWorkspaceVue).toContain('buildTransitionRestrictionReason')
    expect(manageWorkspaceVue).toContain('shouldApplyMutationResult')
    expect(manageWorkspaceVue).toContain('statusProjection.value = previousStatus')
  })
})

describe('KG-MANAGE-021 - unified in-place graph operations', () => {
  it('runs extraction jobs and logs directly in graph-management without data-sources redirect', () => {
    expect(manageWorkspaceVue).toContain('triggerInlineSync')
    expect(manageWorkspaceVue).toContain('loadInlineSyncRuns')
    expect(manageWorkspaceVue).toContain('loadInlineRunLogs')
    expect(manageWorkspaceVue).toContain('Run logs')
    expect(manageWorkspaceVue).not.toContain('Open Data Source Operations')
    expect(manageWorkspaceVue).not.toContain('Open Maintain Step')
  })

  it('applies one-off mutations directly in graph-management without mutations-console redirect', () => {
    expect(manageWorkspaceVue).toContain('inlineMutationJsonl')
    expect(manageWorkspaceVue).toContain('applyInlineMutations')
    expect(manageWorkspaceVue).toContain('graphApi.applyMutations')
    expect(manageWorkspaceVue).not.toContain('navigateTo(`/graph/mutations?kg_id=${kgId}&view=editor`)')
  })
})
