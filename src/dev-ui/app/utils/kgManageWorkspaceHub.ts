import { cn } from '@/lib/utils'
import {
  buildManageStepUrl,
  buildSuggestedNextStep,
  buildWorkspaceStepCards,
  resolveStepDestination,
  type SuggestedNextStepView,
  type WorkspaceOverviewInputs,
  type WorkspaceStepId,
} from '@/utils/kgManageWorkspace'

export type WorkspaceHubTone = 'success' | 'warning' | 'primary' | 'muted'

export interface WorkspaceHubTile {
  step: number
  key: WorkspaceStepId
  title: string
  subtitle: string
  to: string
  enabled: boolean
  lockedReason: string | null
  highlight: boolean
  tone: WorkspaceHubTone
  linkLabel: string
  done: boolean
}

export interface WorkspaceHubPhaseBadge {
  label: string
  variant: 'default' | 'secondary' | 'success' | 'warning'
}

export interface WorkspaceHubOverview extends WorkspaceOverviewInputs {
  preparedSourceCount: number
  entityTypeLabels: string[]
  relationshipTypeLabels: string[]
}

export interface WorkspaceHubSourceRow {
  id: string
  name: string
  url: string
  status: string
  statusVariant: 'success' | 'secondary' | 'outline'
}

function sourcesPhaseComplete(input: WorkspaceHubOverview): boolean {
  return input.dataSourceCount > 0 && input.preparedSourceCount === input.dataSourceCount
}

function designPhaseComplete(input: WorkspaceHubOverview): boolean {
  return (
    input.workspaceStatus?.workspace_mode === 'extraction_operations'
    || input.workspaceStatus?.transition_eligible === true
  )
}

export function resolveWorkspaceHubPhaseBadge(input: WorkspaceHubOverview): WorkspaceHubPhaseBadge {
  if (designPhaseComplete(input)) {
    return { label: 'Operations', variant: 'success' }
  }
  if (sourcesPhaseComplete(input)) {
    return { label: 'Design', variant: 'warning' }
  }
  return { label: 'Data sources', variant: 'secondary' }
}

export function resolveSuggestedWorkspaceKey(input: WorkspaceHubOverview): WorkspaceStepId {
  if (!sourcesPhaseComplete(input)) return 'data-sources'
  if (!designPhaseComplete(input)) return 'graph-management'
  if (input.maintenanceReadyCount > 0) return 'maintain'
  if (input.mutationLogRunCount === 0) return 'graph-management'
  return 'mutation-logs'
}

export function buildWorkspaceHubTiles(input: WorkspaceHubOverview): WorkspaceHubTile[] {
  const cards = buildWorkspaceStepCards(input)
  const cardById = Object.fromEntries(cards.map((c) => [c.id, c])) as Record<
    WorkspaceStepId,
    (typeof cards)[number]
  >
  const highlightKey = resolveSuggestedWorkspaceKey(input)
  const sourcesDone = sourcesPhaseComplete(input)
  const designDone = designPhaseComplete(input)

  const dsCard = cardById['data-sources']
  const gmCard = cardById['graph-management']
  const mlCard = cardById['mutation-logs']
  const maintainCard = cardById.maintain

  const toneFor = (
    step: number,
    done: boolean,
    enabled: boolean,
    cardStatus: (typeof cards)[number]['status'],
  ): WorkspaceHubTone => {
    if (done) return 'success'
    if (!enabled) return 'muted'
    if (cardStatus === 'needs_attention') return 'warning'
    if (highlightKey === (['data-sources', 'graph-management', 'mutation-logs', 'maintain'] as const)[step - 1]) {
      return 'primary'
    }
    return 'muted'
  }

  const linkLabelFor = (action: (typeof cards)[number]['actionLabel'], done: boolean) =>
    action === 'Revisit' || done ? 'Revisit →' : action === 'Run' ? 'Run →' : 'Open →'

  return [
    {
      step: 1,
      key: 'data-sources',
      title: 'Data sources',
      subtitle: sourcesDone
        ? `${input.dataSourceCount} source${input.dataSourceCount === 1 ? '' : 's'} · ingestion ready`
        : input.dataSourceCount > 0
          ? `${input.preparedSourceCount}/${input.dataSourceCount} prepared · finish ingestion`
          : 'Connect repositories and prepare ingestion context',
      to: resolveStepDestination(input.kgId, 'data-sources', {
        dataSourceCount: input.dataSourceCount,
      }),
      enabled: true,
      lockedReason: null,
      highlight: highlightKey === 'data-sources',
      tone: toneFor(1, sourcesDone, true, dsCard.status),
      linkLabel: linkLabelFor(dsCard.actionLabel, sourcesDone),
      done: sourcesDone,
    },
    {
      step: 2,
      key: 'graph-management',
      title: 'Design',
      subtitle: designDone
        ? 'Schema validated · extraction operations available'
        : sourcesDone
          ? 'Design assistant, schema bootstrap, and validation'
          : 'Open anytime; prepare data sources to clear later gates',
      to: resolveStepDestination(input.kgId, 'graph-management'),
      enabled: true,
      lockedReason: null,
      highlight: highlightKey === 'graph-management',
      tone: toneFor(2, designDone, true, gmCard.status),
      linkLabel: linkLabelFor(gmCard.actionLabel, designDone),
      done: designDone,
    },
    {
      step: 3,
      key: 'mutation-logs',
      title: 'Mutation logs',
      subtitle: input.mutationLogRunCount > 0
        ? `${input.mutationLogRunCount} run${input.mutationLogRunCount === 1 ? '' : 's'} recorded`
        : 'Review extraction and apply runs',
      to: resolveStepDestination(input.kgId, 'mutation-logs'),
      enabled: input.dataSourceCount > 0,
      lockedReason: input.dataSourceCount > 0 ? null : 'Connect a data source before reviewing runs.',
      highlight: highlightKey === 'mutation-logs',
      tone: toneFor(3, input.mutationLogRunCount > 0, input.dataSourceCount > 0, mlCard.status),
      linkLabel: linkLabelFor(mlCard.actionLabel, input.mutationLogRunCount > 0),
      done: input.mutationLogRunCount > 0,
    },
    {
      step: 4,
      key: 'maintain',
      title: 'Maintain',
      subtitle: input.maintenanceReadyCount > 0
        ? `${input.maintenanceReadyCount} source${input.maintenanceReadyCount === 1 ? '' : 's'} need maintenance`
        : 'Incremental graph updates from new commits',
      to: resolveStepDestination(input.kgId, 'maintain'),
      enabled: designDone,
      lockedReason: designDone ? null : 'Complete design validation before maintenance.',
      highlight: highlightKey === 'maintain',
      tone: toneFor(4, maintainCard.status === 'ready' && input.maintenanceReadyCount === 0, designDone, maintainCard.status),
      linkLabel: linkLabelFor(maintainCard.actionLabel, maintainCard.status === 'ready' && input.maintenanceReadyCount === 0),
      done: maintainCard.status === 'ready' && input.maintenanceReadyCount === 0 && input.dataSourceCount > 0,
    },
  ]
}

export function buildWorkspaceHubNextStep(input: WorkspaceHubOverview): {
  to: string
  title: string
  description: string
  label: string
  primaryPhase: boolean
} {
  const next = buildSuggestedNextStep(input)
  const actionWord =
    next.actionLabel === 'Run'
      ? 'Run'
      : next.actionLabel === 'Revisit'
        ? 'Revisit'
        : 'Open'
  return {
    to: resolveStepDestination(input.kgId, next.stepId, {
      dataSourceCount: input.dataSourceCount,
    }),
    title: next.title,
    description: next.description,
    label: `${actionWord} ${next.title}`,
    primaryPhase: !sourcesPhaseComplete(input),
  }
}

export function workspaceHubTileClasses(item: {
  enabled: boolean
  highlight: boolean
  tone: WorkspaceHubTone
}): string {
  if (!item.enabled) return ''
  const { tone, highlight } = item
  if (tone === 'success') {
    return cn(
      'border-green-500/35 bg-green-500/5 dark:border-green-500/25 dark:bg-green-950/20',
      highlight && 'ring-1 ring-green-500/30',
    )
  }
  if (tone === 'warning') {
    return cn(
      'border-amber-500/40 bg-amber-500/5 dark:border-amber-500/30 dark:bg-amber-950/25',
      highlight && 'ring-1 ring-amber-500/25',
    )
  }
  if (tone === 'primary') {
    return cn(
      'border-primary/45 bg-primary/10 ring-1 ring-primary/20',
      highlight && 'ring-2 ring-primary/35',
    )
  }
  return cn(
    'border-border bg-card',
    highlight && 'border-primary/50 bg-primary/10 ring-1 ring-primary/20',
  )
}

export function workspaceHubStepBadgeClass(item: {
  enabled: boolean
  done: boolean
  tone: WorkspaceHubTone
}): string {
  if (!item.enabled) {
    return 'flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold text-muted-foreground'
  }
  if (item.done) {
    return 'flex size-7 shrink-0 items-center justify-center rounded-full bg-green-500 text-white'
  }
  if (item.tone === 'warning') {
    return 'flex size-7 shrink-0 items-center justify-center rounded-full bg-amber-600 text-white dark:bg-amber-500'
  }
  if (item.tone === 'primary') {
    return 'flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground'
  }
  return 'flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold text-muted-foreground'
}

export function workspaceHubDescription(input: WorkspaceHubOverview): string {
  if (!sourcesPhaseComplete(input)) {
    return 'Finish ingestion under Data sources, then continue through Design. Green tiles mark completed gates; the highlighted tile is your current focus.'
  }
  if (!designPhaseComplete(input)) {
    return 'Use Design for the assistant and schema bootstrap. Green tiles use Revisit; the highlighted tile is your suggested next step.'
  }
  return 'Continue with mutation logs or maintenance, or Revisit any completed step below.'
}

export function buildManageOverviewUrl(kgId: string): string {
  return buildManageStepUrl(kgId)
}
