import {
  buildKgDataSourcesUrl,
  resolveKgDataSourcesEntryUrl,
} from '@/utils/kgDataSourcesNavigation'

export type WorkspaceStepId = 'data-sources' | 'graph-management' | 'mutation-logs' | 'maintain'

export interface StepDestinationContext {
  dataSourceCount: number
}

export type StepStatusLabel = 'ready' | 'in_progress' | 'needs_attention' | 'blocked'

export type StepActionLabel = 'Open' | 'Revisit' | 'Run'

export const WORKSPACE_STEP_TITLES: Record<WorkspaceStepId, string> = {
  'data-sources': 'Data Sources',
  'graph-management': 'Graph Management',
  'mutation-logs': 'Graph Writes History',
  maintain: 'Maintain',
}

export const WORKSPACE_STEP_ORDER: WorkspaceStepId[] = [
  'data-sources',
  'graph-management',
  'maintain',
  'mutation-logs',
]

export interface WorkspaceReadinessSnapshot {
  has_minimum_entity_types: boolean
  has_minimum_relationship_types: boolean
  prepopulated_types_ready: boolean
  blocking_reasons: string[]
}

export interface WorkspaceStatusSnapshot {
  workspace_mode: 'schema_bootstrap' | 'extraction_operations'
  transition_eligible: boolean
  readiness: WorkspaceReadinessSnapshot
}

export interface WorkspaceOverviewInputs {
  kgId: string
  dataSourceCount: number
  maintenanceReadyCount: number
  mutationLogRunCount: number
  workspaceStatus: WorkspaceStatusSnapshot | null
}

export interface WorkspaceStepCardView {
  id: WorkspaceStepId
  title: string
  status: StepStatusLabel
  statusDetail: string
  actionLabel: StepActionLabel
}

export interface SuggestedNextStepView {
  stepId: WorkspaceStepId
  title: string
  description: string
  actionLabel: StepActionLabel
}

export function isMaintenanceReady(ds: {
  last_extraction_baseline_commit?: string | null
  tracked_branch_head_commit?: string | null
}): boolean {
  if (!ds.last_extraction_baseline_commit || !ds.tracked_branch_head_commit) return false
  return ds.last_extraction_baseline_commit !== ds.tracked_branch_head_commit
}

export function buildDataSourcesStepUrl(kgId: string, dataSourceCount = 0): string {
  return resolveKgDataSourcesEntryUrl(kgId, dataSourceCount)
}

export function buildMaintainStepUrl(kgId: string): string {
  return buildManageStepUrl(kgId, 'maintain')
}

export function buildManageStepUrl(kgId: string, step?: WorkspaceStepId): string {
  if (!step) {
    return `/knowledge-graphs/${encodeURIComponent(kgId)}/manage`
  }
  return `/knowledge-graphs/${encodeURIComponent(kgId)}/manage?step=${step}`
}

export function parseManageStepQuery(step: unknown): WorkspaceStepId | null {
  if (
    step === 'graph-management'
    || step === 'mutation-logs'
    || step === 'maintain'
  ) {
    return step
  }
  return null
}

export function stepStatusTintClass(status: StepStatusLabel): string {
  switch (status) {
    case 'ready':
      return 'border-emerald-500/40 bg-emerald-50/30 dark:bg-emerald-950/20'
    case 'in_progress':
      return 'border-blue-500/40 bg-blue-50/30 dark:bg-blue-950/20'
    case 'needs_attention':
      return 'border-amber-500/40 bg-amber-50/30 dark:bg-amber-950/20'
    case 'blocked':
      return 'border-destructive/50 bg-destructive/5'
  }
}

function buildDataSourcesCard(input: WorkspaceOverviewInputs): WorkspaceStepCardView {
  if (input.dataSourceCount === 0) {
    return {
      id: 'data-sources',
      title: WORKSPACE_STEP_TITLES['data-sources'],
      status: 'needs_attention',
      statusDetail: 'No data sources connected yet.',
      actionLabel: 'Open',
    }
  }

  return {
    id: 'data-sources',
    title: WORKSPACE_STEP_TITLES['data-sources'],
    status: 'ready',
    statusDetail: `${input.dataSourceCount} data source${input.dataSourceCount === 1 ? '' : 's'} connected.`,
    actionLabel: 'Revisit',
  }
}

function buildGraphManagementCard(input: WorkspaceOverviewInputs): WorkspaceStepCardView {
  const status = input.workspaceStatus

  if (!status) {
    return {
      id: 'graph-management',
      title: WORKSPACE_STEP_TITLES['graph-management'],
      status: 'in_progress',
      statusDetail: 'Loading workspace readiness signals.',
      actionLabel: 'Open',
    }
  }

  if (status.workspace_mode === 'schema_bootstrap') {
    if (status.readiness.blocking_reasons.length > 0) {
      return {
        id: 'graph-management',
        title: WORKSPACE_STEP_TITLES['graph-management'],
        status: 'needs_attention',
        statusDetail: `${status.readiness.blocking_reasons.length} blocking reason${status.readiness.blocking_reasons.length === 1 ? '' : 's'} before extraction.`,
        actionLabel: 'Open',
      }
    }

    if (status.transition_eligible) {
      return {
        id: 'graph-management',
        title: WORKSPACE_STEP_TITLES['graph-management'],
        status: 'ready',
        statusDetail: 'Schema bootstrap is ready to transition to extraction.',
        actionLabel: 'Run',
      }
    }

    return {
      id: 'graph-management',
      title: WORKSPACE_STEP_TITLES['graph-management'],
      status: 'in_progress',
      statusDetail: 'Continue schema bootstrap and validation work.',
      actionLabel: 'Open',
    }
  }

  return {
    id: 'graph-management',
    title: WORKSPACE_STEP_TITLES['graph-management'],
    status: 'ready',
    statusDetail: 'Extraction operations mode is active.',
    actionLabel: 'Revisit',
  }
}

function buildMutationLogsCard(input: WorkspaceOverviewInputs): WorkspaceStepCardView {
  if (input.dataSourceCount === 0) {
    return {
      id: 'mutation-logs',
      title: WORKSPACE_STEP_TITLES['mutation-logs'],
      status: 'blocked',
      statusDetail: 'Connect a data source before reviewing mutation runs.',
      actionLabel: 'Open',
    }
  }

  if (input.mutationLogRunCount === 0) {
    return {
      id: 'mutation-logs',
      title: WORKSPACE_STEP_TITLES['mutation-logs'],
      status: input.workspaceStatus?.workspace_mode === 'extraction_operations'
        ? 'needs_attention'
        : 'ready',
      statusDetail: 'No archived graph writes recorded for this graph yet.',
      actionLabel: 'Open',
    }
  }

  return {
    id: 'mutation-logs',
    title: WORKSPACE_STEP_TITLES['mutation-logs'],
    status: 'ready',
    statusDetail: `${input.mutationLogRunCount} archived write entr${input.mutationLogRunCount === 1 ? 'y' : 'ies'} available.`,
    actionLabel: 'Revisit',
  }
}

function buildMaintainCard(input: WorkspaceOverviewInputs): WorkspaceStepCardView {
  if (input.dataSourceCount === 0) {
    return {
      id: 'maintain',
      title: WORKSPACE_STEP_TITLES.maintain,
      status: 'blocked',
      statusDetail: 'Add a data source before maintenance can run.',
      actionLabel: 'Open',
    }
  }

  if (input.maintenanceReadyCount > 0) {
    return {
      id: 'maintain',
      title: WORKSPACE_STEP_TITLES.maintain,
      status: 'needs_attention',
      statusDetail: `${input.maintenanceReadyCount} source${input.maintenanceReadyCount === 1 ? '' : 's'} have new commits ready for maintenance.`,
      actionLabel: 'Run',
    }
  }

  return {
    id: 'maintain',
    title: WORKSPACE_STEP_TITLES.maintain,
    status: 'ready',
    statusDetail: 'All tracked sources are up to date.',
    actionLabel: 'Revisit',
  }
}

export function buildWorkspaceStepCards(input: WorkspaceOverviewInputs): WorkspaceStepCardView[] {
  return [
    buildDataSourcesCard(input),
    buildGraphManagementCard(input),
    buildMaintainCard(input),
    buildMutationLogsCard(input),
  ]
}

export function buildSuggestedNextStep(input: WorkspaceOverviewInputs): SuggestedNextStepView {
  const cards = buildWorkspaceStepCards(input)

  if (input.dataSourceCount === 0) {
    const card = cards.find((item) => item.id === 'data-sources')!
    return {
      stepId: 'data-sources',
      title: card.title,
      description: 'Connect a data source to start schema bootstrap and extraction.',
      actionLabel: card.actionLabel,
    }
  }

  const maintainCard = cards.find((item) => item.id === 'maintain')!
  if (maintainCard.status === 'needs_attention' && maintainCard.actionLabel === 'Run') {
    return {
      stepId: 'maintain',
      title: maintainCard.title,
      description: maintainCard.statusDetail,
      actionLabel: 'Run',
    }
  }

  const graphCard = cards.find((item) => item.id === 'graph-management')!
  if (
    input.workspaceStatus?.workspace_mode === 'schema_bootstrap'
    && input.workspaceStatus.transition_eligible
  ) {
    return {
      stepId: 'graph-management',
      title: graphCard.title,
      description: 'Validate readiness and transition into extraction operations.',
      actionLabel: 'Run',
    }
  }

  if (
    graphCard.status === 'needs_attention'
    || graphCard.status === 'in_progress'
  ) {
    return {
      stepId: 'graph-management',
      title: graphCard.title,
      description: graphCard.statusDetail,
      actionLabel: graphCard.actionLabel,
    }
  }

  const mutationCard = cards.find((item) => item.id === 'mutation-logs')!
  if (mutationCard.status === 'needs_attention') {
    return {
      stepId: 'mutation-logs',
      title: mutationCard.title,
      description: mutationCard.statusDetail,
      actionLabel: mutationCard.actionLabel,
    }
  }

  return {
    stepId: 'graph-management',
    title: graphCard.title,
    description: graphCard.statusDetail,
    actionLabel: 'Revisit',
  }
}

export function resolveStepDestination(
  kgId: string,
  stepId: WorkspaceStepId,
  context?: StepDestinationContext,
): string {
  const dataSourceCount = context?.dataSourceCount ?? 0
  switch (stepId) {
    case 'data-sources':
      return buildDataSourcesStepUrl(kgId, dataSourceCount)
    case 'maintain':
      return buildMaintainStepUrl(kgId)
    case 'graph-management':
    case 'mutation-logs':
      return buildManageStepUrl(kgId, stepId)
  }
}
