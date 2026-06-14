import type { StepStatusLabel } from './kgManageWorkspace'

export type GraphManagementMode =
  | 'initial-schema-design'
  | 'extraction-jobs'
  | 'one-off-mutations'

export type GraphManagementRailItemId =
  | 'schema-entities'
  | 'schema-relationships'
  | 'schema-readiness'
  | 'validation-diagnostics'
  | 'session-pointers'
  | 'extraction-jobs-setup'
  | 'mutation-authoring'

export const GRAPH_MANAGEMENT_MODE_ORDER: GraphManagementMode[] = [
  'initial-schema-design',
  'extraction-jobs',
  'one-off-mutations',
]

export const GRAPH_MANAGEMENT_MODE_LABELS: Record<GraphManagementMode, string> = {
  'initial-schema-design': 'Initial Schema Design',
  'extraction-jobs': 'Extraction Jobs',
  'one-off-mutations': 'One-off Mutations',
}

export const GRAPH_MANAGEMENT_INPUT_PLACEHOLDERS: Record<GraphManagementMode, string> = {
  'initial-schema-design':
    'Describe schema goals, entity types, or relationship constraints for this knowledge graph…',
  'extraction-jobs':
    'Ask about extraction job sets, per-instance descriptions, or running extraction workers…',
  'one-off-mutations':
    'Ask for a schema or instance change — the assistant will validate and apply it…',
}

export interface GraphManagementRailItem {
  id: GraphManagementRailItemId
  label: string
  status: StepStatusLabel
  lastUpdated: string
  detailHint: string
  modes: GraphManagementMode[]
}

export interface GraphManagementRailInputs {
  workspaceMode: 'schema_bootstrap' | 'extraction_operations'
  transitionEligible: boolean
  blockingReasonCount: number
  prepopulatedGapCount: number
  hasMinimumEntityTypes: boolean
  hasMinimumRelationshipTypes: boolean
  sessionUpdatedAt: string | null
  hasActiveSession: boolean
}

export function parseGraphManagementModeQuery(mode: unknown): GraphManagementMode | null {
  if (
    mode === 'initial-schema-design'
    || mode === 'extraction-jobs'
    || mode === 'one-off-mutations'
  ) {
    return mode
  }
  return null
}

export function resolveDefaultGraphManagementMode(
  workspaceMode: 'schema_bootstrap' | 'extraction_operations',
): GraphManagementMode {
  return workspaceMode === 'extraction_operations' ? 'extraction-jobs' : 'initial-schema-design'
}

export function resolveSharedSessionMode(
  workspaceMode: 'schema_bootstrap' | 'extraction_operations',
): 'schema_bootstrap' | 'extraction_operations' {
  return workspaceMode === 'extraction_operations' ? 'extraction_operations' : 'schema_bootstrap'
}

export function buildGraphManagementRailItems(
  input: GraphManagementRailInputs,
): GraphManagementRailItem[] {
  const sessionStamp = input.sessionUpdatedAt ?? 'Not loaded'
  const readinessStatus: StepStatusLabel = input.blockingReasonCount > 0
    ? 'needs_attention'
    : input.transitionEligible
      ? 'ready'
      : 'in_progress'

  return [
    {
      id: 'schema-entities',
      label: 'Schema: Entities',
      status: input.hasMinimumEntityTypes ? 'ready' : 'in_progress',
      lastUpdated: sessionStamp,
      detailHint: 'Entity type definitions and instance inventory.',
      modes: ['initial-schema-design', 'one-off-mutations'],
    },
    {
      id: 'schema-relationships',
      label: 'Schema: Relationships',
      status: input.hasMinimumRelationshipTypes ? 'ready' : 'in_progress',
      lastUpdated: sessionStamp,
      detailHint: 'Relationship type definitions and edge inventory.',
      modes: ['initial-schema-design', 'one-off-mutations'],
    },
    {
      id: 'schema-readiness',
      label: 'Schema readiness',
      status: readinessStatus,
      lastUpdated: sessionStamp,
      detailHint: 'Bootstrap checklist, validate, and transition controls.',
      modes: ['initial-schema-design'],
    },
    {
      id: 'validation-diagnostics',
      label: 'Validation diagnostics',
      status: input.prepopulatedGapCount > 0 || input.blockingReasonCount > 0
        ? 'needs_attention'
        : 'ready',
      lastUpdated: sessionStamp,
      detailHint: 'Blocking reasons and prepopulated type gaps.',
      modes: ['initial-schema-design'],
    },
    {
      id: 'session-pointers',
      label: 'Session pointers',
      status: input.hasActiveSession ? 'ready' : 'in_progress',
      lastUpdated: sessionStamp,
      detailHint: 'Active bootstrap, extraction, and completed session references.',
      modes: GRAPH_MANAGEMENT_MODE_ORDER,
    },
    {
      id: 'extraction-jobs-setup',
      label: 'Extraction jobs setup',
      status: input.workspaceMode === 'extraction_operations' ? 'ready' : 'blocked',
      lastUpdated: sessionStamp,
      detailHint: 'Job setup, execution controls, and run context.',
      modes: ['extraction-jobs'],
    },
    {
      id: 'mutation-authoring',
      label: 'Mutation Authoring',
      status: input.workspaceMode === 'extraction_operations' ? 'ready' : 'blocked',
      lastUpdated: sessionStamp,
      detailHint: 'Manual JSONL editor with templates — independent from the assistant.',
      modes: ['one-off-mutations'],
    },
  ]
}

export function filterRailItemsForMode(
  items: GraphManagementRailItem[],
  mode: GraphManagementMode,
): GraphManagementRailItem[] {
  return items.filter((item) => item.modes.includes(mode))
}

export function isRailItemValidInMode(
  itemId: GraphManagementRailItemId,
  mode: GraphManagementMode,
  items: GraphManagementRailItem[],
): boolean {
  const item = items.find((candidate) => candidate.id === itemId)
  return item?.modes.includes(mode) ?? false
}

export function resolveRailSelectionForMode(
  selectedId: GraphManagementRailItemId | null,
  mode: GraphManagementMode,
  items: GraphManagementRailItem[],
): GraphManagementRailItemId | null {
  const modeItems = filterRailItemsForMode(items, mode)
  if (modeItems.length === 0) return null
  if (selectedId && isRailItemValidInMode(selectedId, mode, items)) {
    return selectedId
  }
  return modeItems[0]?.id ?? null
}

export function buildGraphManagementStepUrl(
  kgId: string,
  mode: GraphManagementMode,
): string {
  return `/knowledge-graphs/${encodeURIComponent(kgId)}/manage?step=graph-management&gm_mode=${mode}`
}

export interface GraphManagementModeGateInput {
  workspaceMode: 'schema_bootstrap' | 'extraction_operations'
  transitionEligible: boolean
}

export function isGraphManagementModeUnlocked(
  mode: GraphManagementMode,
  input: GraphManagementModeGateInput,
): boolean {
  if (mode === 'initial-schema-design') return true
  return input.workspaceMode === 'extraction_operations'
}

export function graphManagementModeLockReason(
  mode: GraphManagementMode,
  input: GraphManagementModeGateInput,
): string | null {
  if (isGraphManagementModeUnlocked(mode, input)) return null
  if (input.transitionEligible) {
    return 'Schema validated — use Go to Extraction/Mutations in Schema readiness to unlock.'
  }
  return 'Complete schema design and pass validation to unlock.'
}

export function resolveEffectiveGraphManagementMode(
  requested: GraphManagementMode | null,
  input: GraphManagementModeGateInput,
): GraphManagementMode {
  const fallback = resolveDefaultGraphManagementMode(input.workspaceMode)
  if (!requested) return fallback
  if (isGraphManagementModeUnlocked(requested, input)) return requested
  return 'initial-schema-design'
}
