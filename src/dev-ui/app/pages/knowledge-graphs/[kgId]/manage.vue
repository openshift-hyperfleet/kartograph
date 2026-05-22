<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ArrowLeft, CheckCircle2, Coins, DollarSign, Loader2, PlayCircle, ShieldAlert } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import SharedConversationPanel from '@/components/extraction/SharedConversationPanel.vue'
import {
  GRAPH_MANAGEMENT_INPUT_PLACEHOLDERS,
  GRAPH_MANAGEMENT_MODE_LABELS,
  GRAPH_MANAGEMENT_MODE_ORDER,
  buildGraphManagementRailItems,
  buildGraphManagementStepUrl,
  filterRailItemsForMode,
  parseGraphManagementModeQuery,
  resolveDefaultGraphManagementMode,
  resolveRailSelectionForMode,
  resolveSharedSessionMode,
  type GraphManagementMode,
  type GraphManagementRailItemId,
} from '@/utils/kgGraphManagement'
import {
  buildManageStepUrl,
  buildSuggestedNextStep,
  buildWorkspaceStepCards,
  parseManageStepQuery,
  resolveStepDestination,
  stepStatusTintClass,
  type WorkspaceStepId,
} from '@/utils/kgManageWorkspace'
import {
  appendLocalChatMessage,
  buildTransitionRestrictionReason,
  handleActivatableKeydown,
  isForbiddenHttpError,
  resolveForbiddenReason,
  resolveSectionState,
  shouldApplyMutationResult,
} from '@/utils/kgManageState'
import {
  buildMutationLogEntryPreviewUrl,
  collectScopedMutationLogRuns,
  hasMutationLogEntryPreviewPage,
  MUTATION_LOG_ENTRY_PREVIEW_PAGE_SIZE,
  MUTATION_LOG_NO_PREVIEW_MESSAGE,
  resolveDefaultSelectedMutationLogRunId,
  type MutationLogEntryPreviewPage,
  type MutationLogRunRecord,
} from '@/utils/kgMutationLogs'
import { useGraphApi } from '@/composables/api/useGraphApi'

interface WorkspaceReadinessStatus {
  has_minimum_entity_types: boolean
  has_minimum_relationship_types: boolean
  prepopulated_types_ready: boolean
  prepopulated_types_without_instances: string[]
  blocking_reasons: string[]
}

interface WorkspaceSessionPointers {
  active_schema_bootstrap_session_id: string | null
  active_extraction_operations_session_id: string | null
  most_recent_completed_session_id: string | null
}

interface WorkspaceStatusResponse {
  knowledge_graph_id: string
  workspace_mode: 'schema_bootstrap' | 'extraction_operations'
  readiness: WorkspaceReadinessStatus
  transition_eligible: boolean
  session_pointers: WorkspaceSessionPointers
}

interface KnowledgeGraphIdentity {
  id: string
  name: string
  description?: string | null
}

interface DataSourceRef {
  id: string
  name: string
  last_extraction_baseline_commit?: string | null
  tracked_branch_head_commit?: string | null
}

interface MutationLogRunView extends MutationLogRunRecord {
  data_source_name: string
}

interface InlineSyncRun {
  id: string
  status: string
  started_at: string
  completed_at: string | null
}

interface ExtractionSessionResponse {
  id: string
  message_history: Array<{ role?: string; content?: string; message?: string }>
  runtime_context: Record<string, unknown>
  updated_at: string
}

interface SessionRunMetricView {
  sync_run_id: string
  mutation_log_id: string | null
  status: string
  started_at: string
  completed_at: string | null
  token_usage_total: number | null
  cost_total_usd: number | null
  operation_counts: Record<string, number>
}

interface ExtractionSessionHistoryItem {
  id: string
  created_at: string
  updated_at: string
  archived_at: string | null
  is_active: boolean
  message_count: number
  run_metrics: SessionRunMetricView[]
}

const route = useRoute()
const { hasTenant, tenantVersion } = useTenant()
const { extractErrorMessage } = useErrorHandler()
const { apiFetch } = useApiClient()
const graphApi = useGraphApi()
const kgId = computed(() => String(route.params.kgId ?? ''))
const kgIdentity = ref<KnowledgeGraphIdentity | null>(null)
const dataSourceCount = ref(0)
const maintenanceReadyCount = ref(0)
const loading = ref(false)
const workspaceLoadError = ref<string | null>(null)
const workspaceForbidden = ref(false)
const workspaceForbiddenReason = ref<string | null>(null)
const validating = ref(false)
const transitioning = ref(false)
const sessionLoading = ref(false)
const sessionHistoryLoading = ref(false)
const sessionLoadError = ref<string | null>(null)
const sessionForbidden = ref(false)
const sessionForbiddenReason = ref<string | null>(null)
const clearingChat = ref(false)
const sendingChat = ref(false)
const extractionSession = ref<ExtractionSessionResponse | null>(null)
const sessionHistory = ref<ExtractionSessionHistoryItem[]>([])
const draftMessage = ref('')
const statusProjection = ref<WorkspaceStatusResponse | null>(null)
const mutationLogLoading = ref(false)
const mutationLogLoadError = ref<string | null>(null)
const mutationLogRuns = ref<MutationLogRunView[]>([])
const selectedMutationLogRunId = ref<string | null>(null)
const graphManagementMode = ref<GraphManagementMode>('initial-schema-design')
const selectedRailItemId = ref<GraphManagementRailItemId | null>(null)
const mutationLogEntryPreviewLoading = ref(false)
const mutationLogEntryPreviewPage = ref<MutationLogEntryPreviewPage | null>(null)
const mutationLogEntryPreviewOffset = ref(0)
const graphManagementDataSources = ref<DataSourceRef[]>([])
const graphManagementDataSourcesLoading = ref(false)
const graphManagementDataSourcesError = ref<string | null>(null)
const selectedOpsDataSourceId = ref<string | null>(null)
const inlineSyncRuns = ref<InlineSyncRun[]>([])
const inlineSyncRunsLoading = ref(false)
const inlineSyncRunsError = ref<string | null>(null)
const inlineSyncTriggering = ref(false)
const selectedInlineRunId = ref<string | null>(null)
const inlineRunLogs = ref<string[]>([])
const inlineRunLogsLoading = ref(false)
const inlineRunLogsError = ref<string | null>(null)
const inlineMutationJsonl = ref('')
const inlineMutationApplying = ref(false)
const inlineMutationApplyError = ref<string | null>(null)

const activeStep = computed(() => parseManageStepQuery(route.query.step))
const showOverview = computed(() => activeStep.value === null)

const workspaceOverviewInput = computed(() => ({
  kgId: kgId.value,
  dataSourceCount: dataSourceCount.value,
  maintenanceReadyCount: maintenanceReadyCount.value,
  mutationLogRunCount: mutationLogRuns.value.length,
  workspaceStatus: statusProjection.value,
}))

const workspaceStepCards = computed(() => buildWorkspaceStepCards(workspaceOverviewInput.value))
const suggestedNextStep = computed(() => buildSuggestedNextStep(workspaceOverviewInput.value))

const graphHeaderTitle = computed(() =>
  kgIdentity.value?.name ?? 'Knowledge Graph Manage Workspace',
)

const modeLabel = computed(() =>
  statusProjection.value?.workspace_mode === 'extraction_operations'
    ? 'Extraction Operations'
    : 'Schema Bootstrap',
)

const stepBadgeLabel = computed(() => {
  if (activeStep.value === 'graph-management') {
    return graphManagementModeLabel.value
  }
  return modeLabel.value
})

const sharedSessionMode = computed<'schema_bootstrap' | 'extraction_operations'>(() =>
  resolveSharedSessionMode(
    statusProjection.value?.workspace_mode ?? 'schema_bootstrap',
  ),
)

const graphManagementModeLabel = computed(
  () => GRAPH_MANAGEMENT_MODE_LABELS[graphManagementMode.value],
)

const graphManagementInputPlaceholder = computed(
  () => GRAPH_MANAGEMENT_INPUT_PLACEHOLDERS[graphManagementMode.value],
)

const sessionStatusLabel = computed(() => {
  if (sessionLoading.value) return 'Loading session'
  if (clearingChat.value) return 'Resetting chat'
  if (extractionSession.value?.id) {
    return `Active · ${extractionSession.value.id.slice(0, 8)}`
  }
  return 'No active session'
})

const graphManagementRailItems = computed(() => {
  if (!statusProjection.value) return []
  return buildGraphManagementRailItems({
    workspaceMode: statusProjection.value.workspace_mode,
    transitionEligible: statusProjection.value.transition_eligible,
    blockingReasonCount: statusProjection.value.readiness.blocking_reasons.length,
    prepopulatedGapCount: statusProjection.value.readiness.prepopulated_types_without_instances.length,
    sessionUpdatedAt: extractionSession.value?.updated_at ?? null,
    hasActiveSession: Boolean(extractionSession.value?.id),
  })
})

const visibleRailItems = computed(() =>
  filterRailItemsForMode(graphManagementRailItems.value, graphManagementMode.value),
)

const selectedRailItem = computed(() =>
  visibleRailItems.value.find((item) => item.id === selectedRailItemId.value) ?? null,
)

const canTransition = computed(() =>
  statusProjection.value?.workspace_mode === 'schema_bootstrap'
  && statusProjection.value?.transition_eligible === true,
)

const transitionRestrictionReason = computed(() =>
  buildTransitionRestrictionReason(
    canTransition.value,
    statusProjection.value?.readiness.blocking_reasons ?? [],
  ),
)

const workspaceOverviewState = computed(() =>
  resolveSectionState({
    section: 'workspace-overview',
    loading: loading.value,
    error: workspaceLoadError.value,
    forbidden: workspaceForbidden.value,
    forbiddenReason: workspaceForbiddenReason.value,
  }),
)

const mutationLogsSectionState = computed(() =>
  resolveSectionState({
    section: 'mutation-logs',
    loading: mutationLogLoading.value,
    error: mutationLogLoadError.value,
    forbidden: workspaceForbidden.value,
    forbiddenReason: workspaceForbiddenReason.value,
    empty: !mutationLogLoading.value
      && !mutationLogLoadError.value
      && mutationLogRuns.value.length === 0,
    emptyActionLabel: 'Refresh runs',
  }),
)

const graphManagementSectionState = computed(() =>
  resolveSectionState({
    section: 'graph-management',
    loading: sessionLoading.value,
    error: sessionLoadError.value,
    forbidden: sessionForbidden.value,
    forbiddenReason: sessionForbiddenReason.value,
  }),
)

const selectedMutationLogRun = computed(() =>
  mutationLogRuns.value.find((run) => run.id === selectedMutationLogRunId.value) ?? null,
)

const selectedOpsDataSource = computed(() =>
  graphManagementDataSources.value.find((ds) => ds.id === selectedOpsDataSourceId.value) ?? null,
)

const progressChecklist = computed(() => {
  const readiness = statusProjection.value?.readiness
  if (!readiness) return []
  return [
    {
      id: 'entity-types',
      label: 'Minimum entity types',
      passed: readiness.has_minimum_entity_types,
      passDetail: 'At least one entity type defined.',
      failDetail: 'Add at least one entity type before transition.',
    },
    {
      id: 'relationship-types',
      label: 'Minimum relationship types',
      passed: readiness.has_minimum_relationship_types,
      passDetail: 'At least one relationship type defined.',
      failDetail: 'Add at least one relationship type before transition.',
    },
    {
      id: 'prepopulated-types',
      label: 'Prepopulated instance coverage',
      passed: readiness.prepopulated_types_ready,
      passDetail: 'All prepopulated types have at least one instance.',
      failDetail: 'Create instances for all prepopulated types listed below.',
    },
  ]
})

const nextSteps = computed(() => {
  if (!statusProjection.value) return []
  const steps = ['Run Validate to refresh readiness signals after schema changes.']
  if (!statusProjection.value.readiness.has_minimum_entity_types) {
    steps.push('Define at least one entity type in schema bootstrap mode.')
  }
  if (!statusProjection.value.readiness.has_minimum_relationship_types) {
    steps.push('Define at least one relationship type linked to your entity types.')
  }
  if (!statusProjection.value.readiness.prepopulated_types_ready) {
    steps.push('Populate missing prepopulated types with at least one instance each.')
  }
  if (statusProjection.value.transition_eligible) {
    steps.push('Transition is enabled. Use Go to Extraction/Mutations when ready.')
  }
  return steps
})

const sessionActivityLines = computed(() => {
  const context = extractionSession.value?.runtime_context ?? {}
  const candidate = context.activity_lines ?? context.ndjson_activity_lines ?? context.thinking_lines
  if (!Array.isArray(candidate)) return []
  return candidate.filter((line): line is string => typeof line === 'string' && line.trim().length > 0)
})

async function loadKgIdentity() {
  if (!hasTenant.value || !kgId.value) return
  try {
    kgIdentity.value = await apiFetch<KnowledgeGraphIdentity>(
      `/management/knowledge-graphs/${kgId.value}`,
    )
  } catch (err) {
    kgIdentity.value = { id: kgId.value, name: kgId.value }
    toast.error('Failed to load knowledge graph identity', {
      description: extractErrorMessage(err),
    })
  }
}

async function loadOverviewMetrics() {
  if (!hasTenant.value || !kgId.value) return
  try {
    const dataSources = await apiFetch<DataSourceRef[]>(
      `/management/knowledge-graphs/${kgId.value}/data-sources`,
    )
    dataSourceCount.value = dataSources.length
    maintenanceReadyCount.value = dataSources.filter((ds) => {
      if (!ds.last_extraction_baseline_commit || !ds.tracked_branch_head_commit) return false
      return ds.last_extraction_baseline_commit !== ds.tracked_branch_head_commit
    }).length
  } catch {
    dataSourceCount.value = 0
    maintenanceReadyCount.value = 0
  }
}

async function loadGraphManagementDataSources() {
  if (!hasTenant.value || !kgId.value || activeStep.value !== 'graph-management') return
  graphManagementDataSourcesLoading.value = true
  graphManagementDataSourcesError.value = null
  try {
    const dataSources = await apiFetch<DataSourceRef[]>(
      `/management/knowledge-graphs/${kgId.value}/data-sources`,
    )
    graphManagementDataSources.value = dataSources
    if (
      !selectedOpsDataSourceId.value
      || !dataSources.some((ds) => ds.id === selectedOpsDataSourceId.value)
    ) {
      selectedOpsDataSourceId.value = dataSources[0]?.id ?? null
    }
  } catch (err) {
    graphManagementDataSources.value = []
    selectedOpsDataSourceId.value = null
    graphManagementDataSourcesError.value = extractErrorMessage(err)
  } finally {
    graphManagementDataSourcesLoading.value = false
  }
}

async function loadInlineSyncRuns() {
  if (!selectedOpsDataSourceId.value) {
    inlineSyncRuns.value = []
    return
  }
  inlineSyncRunsLoading.value = true
  inlineSyncRunsError.value = null
  try {
    const runs = await apiFetch<InlineSyncRun[]>(
      `/management/data-sources/${selectedOpsDataSourceId.value}/sync-runs`,
    )
    inlineSyncRuns.value = runs
    selectedInlineRunId.value = runs[0]?.id ?? null
  } catch (err) {
    inlineSyncRuns.value = []
    selectedInlineRunId.value = null
    inlineSyncRunsError.value = extractErrorMessage(err)
  } finally {
    inlineSyncRunsLoading.value = false
  }
}

async function triggerInlineSync() {
  if (!selectedOpsDataSourceId.value) return
  inlineSyncTriggering.value = true
  try {
    await apiFetch(`/management/data-sources/${selectedOpsDataSourceId.value}/sync`, { method: 'POST' })
    toast.success('Sync triggered')
    await loadInlineSyncRuns()
  } catch (err) {
    toast.error('Failed to trigger sync', { description: extractErrorMessage(err) })
  } finally {
    inlineSyncTriggering.value = false
  }
}

async function loadInlineRunLogs(runId: string) {
  if (!selectedOpsDataSourceId.value) return
  selectedInlineRunId.value = runId
  inlineRunLogsLoading.value = true
  inlineRunLogsError.value = null
  try {
    const result = await apiFetch<{ logs: string[] }>(
      `/management/data-sources/${selectedOpsDataSourceId.value}/sync-runs/${runId}/logs`,
    )
    inlineRunLogs.value = result.logs ?? []
  } catch (err) {
    inlineRunLogs.value = []
    inlineRunLogsError.value = extractErrorMessage(err)
  } finally {
    inlineRunLogsLoading.value = false
  }
}

async function applyInlineMutations() {
  if (!kgId.value || inlineMutationJsonl.value.trim().length === 0) {
    inlineMutationApplyError.value = 'Add one or more JSONL mutation operations first.'
    return
  }
  inlineMutationApplying.value = true
  inlineMutationApplyError.value = null
  try {
    await graphApi.applyMutations(kgId.value, inlineMutationJsonl.value.trim())
    toast.success('Mutations applied')
    inlineMutationJsonl.value = ''
    await loadMutationLogRuns()
  } catch (err) {
    inlineMutationApplyError.value = extractErrorMessage(err)
    toast.error('Failed to apply mutations', { description: inlineMutationApplyError.value })
  } finally {
    inlineMutationApplying.value = false
  }
}

function openWorkspaceStep(stepId: WorkspaceStepId) {
  navigateTo(resolveStepDestination(kgId.value, stepId))
}

function returnToWorkspaceOverview() {
  navigateTo(buildManageStepUrl(kgId.value))
}

async function loadWorkspaceStatus() {
  if (!hasTenant.value || !kgId.value) return
  loading.value = true
  workspaceLoadError.value = null
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace-status`,
    )
    workspaceForbidden.value = false
    workspaceForbiddenReason.value = null
  } catch (err) {
    if (isForbiddenHttpError(err)) {
      workspaceForbidden.value = true
      workspaceForbiddenReason.value = resolveForbiddenReason(
        err,
        'You do not have permission to view this knowledge graph workspace.',
      )
      statusProjection.value = null
    } else {
      workspaceForbidden.value = false
      workspaceForbiddenReason.value = null
      statusProjection.value = null
      workspaceLoadError.value = extractErrorMessage(err)
      toast.error('Failed to load knowledge graph workspace', {
        description: workspaceLoadError.value,
      })
    }
  } finally {
    loading.value = false
  }
}

async function loadMutationLogRuns() {
  if (!hasTenant.value || !kgId.value) return
  mutationLogLoading.value = true
  mutationLogLoadError.value = null
  try {
    const dataSources = await apiFetch<DataSourceRef[]>(
      `/management/knowledge-graphs/${kgId.value}/data-sources`,
    )

    const runsByDataSourceId: Record<string, MutationLogRunRecord[]> = {}
    for (const ds of dataSources) {
      try {
        runsByDataSourceId[ds.id] = await apiFetch<MutationLogRunRecord[]>(
          `/management/data-sources/${ds.id}/sync-runs`,
        )
      } catch {
        runsByDataSourceId[ds.id] = []
      }
    }

    const collected = collectScopedMutationLogRuns(
      kgId.value,
      dataSources,
      runsByDataSourceId,
    ) as MutationLogRunView[]

    mutationLogRuns.value = collected
    selectedMutationLogRunId.value = resolveDefaultSelectedMutationLogRunId(
      collected,
      selectedMutationLogRunId.value,
    )
  } catch (err) {
    if (isForbiddenHttpError(err)) {
      mutationLogLoadError.value = resolveForbiddenReason(
        err,
        'You do not have permission to view mutation logs for this graph.',
      )
    } else {
      mutationLogLoadError.value = extractErrorMessage(err)
      toast.error('Failed to load mutation log runs', {
        description: mutationLogLoadError.value,
      })
    }
    mutationLogRuns.value = []
    selectedMutationLogRunId.value = null
    mutationLogEntryPreviewPage.value = null
  } finally {
    mutationLogLoading.value = false
  }
}

async function loadMutationLogEntryPreviews(offset = 0) {
  const run = selectedMutationLogRun.value
  if (!run) {
    mutationLogEntryPreviewPage.value = null
    mutationLogEntryPreviewOffset.value = 0
    return
  }

  mutationLogEntryPreviewLoading.value = true
  try {
    mutationLogEntryPreviewPage.value = await apiFetch<MutationLogEntryPreviewPage>(
      buildMutationLogEntryPreviewUrl(
        run.data_source_id,
        run.id,
        offset,
        MUTATION_LOG_ENTRY_PREVIEW_PAGE_SIZE,
      ),
    )
    mutationLogEntryPreviewOffset.value = offset
  } catch (err) {
    mutationLogEntryPreviewPage.value = {
      entries: [],
      total: 0,
      offset,
      limit: MUTATION_LOG_ENTRY_PREVIEW_PAGE_SIZE,
      preview_available: false,
    }
    mutationLogEntryPreviewOffset.value = offset
    toast.error('Failed to load mutation log entry previews', {
      description: extractErrorMessage(err),
    })
  } finally {
    mutationLogEntryPreviewLoading.value = false
  }
}

async function loadExtractionSession() {
  if (!kgId.value || activeStep.value !== 'graph-management') return
  sessionLoading.value = true
  sessionLoadError.value = null
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${sharedSessionMode.value}/active`,
    )
    sessionForbidden.value = false
    sessionForbiddenReason.value = null
  } catch (err) {
    extractionSession.value = null
    if (isForbiddenHttpError(err)) {
      sessionForbidden.value = true
      sessionForbiddenReason.value = resolveForbiddenReason(
        err,
        'You do not have permission to manage this knowledge graph.',
      )
    } else {
      sessionForbidden.value = false
      sessionForbiddenReason.value = null
      sessionLoadError.value = extractErrorMessage(err)
      toast.error('Failed to load extraction conversation', {
        description: sessionLoadError.value,
      })
    }
  } finally {
    sessionLoading.value = false
  }
}

async function loadSessionHistory() {
  if (!kgId.value) return
  sessionHistoryLoading.value = true
  try {
    const response = await apiFetch<{ sessions: ExtractionSessionHistoryItem[] }>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${sharedSessionMode.value}/history`,
    )
    sessionHistory.value = response.sessions
  } catch (err) {
    sessionHistory.value = []
    toast.error('Failed to load session history', {
      description: extractErrorMessage(err),
    })
  } finally {
    sessionHistoryLoading.value = false
  }
}

function syncGraphManagementState() {
  if (activeStep.value !== 'graph-management') return
  const fromQuery = parseGraphManagementModeQuery(route.query.gm_mode)
  graphManagementMode.value = fromQuery
    ?? resolveDefaultGraphManagementMode(
      statusProjection.value?.workspace_mode ?? 'schema_bootstrap',
    )
  selectedRailItemId.value = resolveRailSelectionForMode(
    selectedRailItemId.value,
    graphManagementMode.value,
    graphManagementRailItems.value,
  )
}

function setGraphManagementMode(mode: GraphManagementMode) {
  graphManagementMode.value = mode
  selectedRailItemId.value = resolveRailSelectionForMode(
    selectedRailItemId.value,
    mode,
    graphManagementRailItems.value,
  )
  navigateTo(buildGraphManagementStepUrl(kgId.value, mode), { replace: true })
}

function selectRailItem(itemId: GraphManagementRailItemId) {
  selectedRailItemId.value = itemId
}

function onRailKeydown(event: KeyboardEvent, itemId: GraphManagementRailItemId) {
  handleActivatableKeydown(event, () => selectRailItem(itemId))
}

function onStepActionKeydown(event: KeyboardEvent, stepId: WorkspaceStepId) {
  handleActivatableKeydown(event, () => openWorkspaceStep(stepId))
}

function onModeSwitchKeydown(event: KeyboardEvent, mode: GraphManagementMode) {
  handleActivatableKeydown(event, () => setGraphManagementMode(mode))
}

function selectMutationLogRun(runId: string) {
  selectedMutationLogRunId.value = runId
}

function onMutationRunKeydown(event: KeyboardEvent, runId: string) {
  handleActivatableKeydown(event, () => selectMutationLogRun(runId))
}

function sendChatMessage(message: string) {
  if (sessionForbidden.value || !shouldApplyMutationResult(sessionForbidden.value)) {
    toast.error('Chat unavailable', {
      description: sessionForbiddenReason.value
        ?? 'You do not have permission to send messages for this knowledge graph.',
    })
    return
  }

  sendingChat.value = true
  try {
    const nextHistory = appendLocalChatMessage(extractionSession.value, message)
    extractionSession.value = {
      ...(extractionSession.value ?? {
        id: 'local-session',
        runtime_context: {},
        updated_at: new Date().toISOString(),
      }),
      message_history: nextHistory,
      updated_at: new Date().toISOString(),
    }
    draftMessage.value = ''
  } finally {
    sendingChat.value = false
  }
}

async function validateWorkspace() {
  if (!kgId.value || workspaceForbidden.value) return
  validating.value = true
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace/validate`,
      { method: 'POST' },
    )
    toast.success('Workspace validation complete')
  } catch (err) {
    if (isForbiddenHttpError(err)) {
      workspaceForbidden.value = true
      workspaceForbiddenReason.value = resolveForbiddenReason(
        err,
        'You do not have permission to validate this workspace.',
      )
    } else {
      toast.error('Validation failed', {
        description: extractErrorMessage(err),
      })
    }
  } finally {
    validating.value = false
  }
}

async function transitionToExtraction() {
  if (!kgId.value || !canTransition.value || workspaceForbidden.value) return
  transitioning.value = true
  const previousStatus = statusProjection.value
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace/transition-to-extraction`,
      { method: 'POST' },
    )
    toast.success('Workspace transitioned to extraction operations')
    await loadExtractionSession()
  } catch (err) {
    statusProjection.value = previousStatus
    if (isForbiddenHttpError(err)) {
      workspaceForbidden.value = true
      workspaceForbiddenReason.value = resolveForbiddenReason(
        err,
        'You do not have permission to transition this workspace.',
      )
    } else {
      toast.error('Transition failed', {
        description: extractErrorMessage(err),
      })
    }
  } finally {
    transitioning.value = false
  }
}

async function clearChat() {
  // Clear chat resets the active extraction session for this knowledge graph.
  if (!kgId.value || sessionForbidden.value) return
  clearingChat.value = true
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${sharedSessionMode.value}/clear-chat`,
      { method: 'POST' },
    )
    toast.success('Extraction chat cleared')
    await loadSessionHistory()
  } catch (err) {
    toast.error('Failed to clear chat', {
      description: extractErrorMessage(err),
    })
  } finally {
    clearingChat.value = false
  }
}

onMounted(() => {
  loadKgIdentity()
  loadWorkspaceStatus()
  loadOverviewMetrics()
  loadMutationLogRuns()
})

watch(tenantVersion, () => {
  kgIdentity.value = null
  statusProjection.value = null
  extractionSession.value = null
  dataSourceCount.value = 0
  maintenanceReadyCount.value = 0
  workspaceLoadError.value = null
  workspaceForbidden.value = false
  workspaceForbiddenReason.value = null
  mutationLogLoadError.value = null
  sessionLoadError.value = null
  sessionForbidden.value = false
  sessionForbiddenReason.value = null
  loadKgIdentity()
  loadWorkspaceStatus()
  loadOverviewMetrics()
  loadMutationLogRuns()
})

watch(
  () => statusProjection.value?.workspace_mode,
  () => {
    if (activeStep.value === 'graph-management') {
      syncGraphManagementState()
      loadExtractionSession()
    }
  },
)

watch(
  () => [activeStep.value, route.query.gm_mode] as const,
  () => {
    if (activeStep.value === 'graph-management') {
      syncGraphManagementState()
      loadExtractionSession()
      loadSessionHistory()
      loadGraphManagementDataSources()
    }
  },
)

watch(selectedMutationLogRunId, () => {
  loadMutationLogEntryPreviews(0)
})

watch(selectedOpsDataSourceId, () => {
  inlineRunLogs.value = []
  inlineRunLogsError.value = null
  selectedInlineRunId.value = null
  loadInlineSyncRuns()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-semibold tracking-tight">{{ graphHeaderTitle }}</h1>
          <Badge v-if="!showOverview" variant="secondary">{{ stepBadgeLabel }}</Badge>
        </div>
        <p class="text-sm text-muted-foreground">
          <template v-if="showOverview">
            Project workspace for knowledge graph {{ kgId }}.
          </template>
          <template v-else-if="activeStep === 'graph-management'">
            Conversation-first graph management with shared session and mode-specific workspace panels.
          </template>
          <template v-else>
            Knowledge-graph scoped mutation run visibility and run metrics.
          </template>
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        @click="showOverview ? navigateTo('/knowledge-graphs') : returnToWorkspaceOverview()"
      >
        <ArrowLeft class="mr-1.5 size-3.5" />
        {{ showOverview ? 'Back to Knowledge Graphs' : 'Back to workspace overview' }}
      </Button>
    </div>

    <Separator />

    <div v-if="!hasTenant" class="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
      Select a tenant to manage this workspace.
    </div>

    <div
      v-else-if="workspaceOverviewState.phase === 'loading'"
      class="flex items-center gap-2 text-sm text-muted-foreground"
      role="status"
    >
      <Loader2 class="size-4 animate-spin" />
      {{ workspaceOverviewState.message }}
    </div>

    <div
      v-else-if="workspaceOverviewState.phase === 'forbidden'"
      class="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-sm"
      role="alert"
    >
      <p class="font-medium text-destructive">{{ workspaceOverviewState.title }}</p>
      <p class="mt-1 text-muted-foreground">{{ workspaceOverviewState.message }}</p>
    </div>

    <div
      v-else-if="workspaceOverviewState.phase === 'error'"
      class="rounded-lg border border-dashed p-6 text-sm"
      role="alert"
    >
      <p class="font-medium">{{ workspaceOverviewState.title }}</p>
      <p class="mt-1 text-muted-foreground">{{ workspaceOverviewState.message }}</p>
      <Button class="mt-3" size="sm" variant="outline" @click="loadWorkspaceStatus">
        Retry workspace load
      </Button>
    </div>

    <template v-else-if="statusProjection">
      <section v-if="showOverview" class="space-y-6">
        <div>
          <h2 class="text-lg font-semibold tracking-tight">Project workspace</h2>
          <p class="text-sm text-muted-foreground">
            Choose a step to continue work on this knowledge graph without re-selecting context.
          </p>
        </div>

        <Card class="border-primary/30 bg-primary/5">
          <CardHeader class="pb-3">
            <CardTitle class="text-base">Suggested next step</CardTitle>
            <CardDescription>{{ suggestedNextStep.description }}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button @click="openWorkspaceStep(suggestedNextStep.stepId)">
              {{ suggestedNextStep.actionLabel }} {{ suggestedNextStep.title }}
            </Button>
          </CardContent>
        </Card>

        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <!-- Step cards: Data Sources, Graph Management, MutationLogs, Maintain -->
          <Card
            v-for="card in workspaceStepCards"
            :key="card.id"
            class="flex flex-col"
            :class="stepStatusTintClass(card.status)"
          >
            <CardHeader class="pb-3">
              <div class="flex items-center justify-between gap-2">
                <CardTitle class="text-base">{{ card.title }}</CardTitle>
                <Badge variant="outline">{{ card.status }}</Badge>
              </div>
              <CardDescription>{{ card.statusDetail }}</CardDescription>
            </CardHeader>
            <CardContent class="mt-auto">
              <Button
                class="w-full"
                variant="outline"
                tabindex="0"
                @click="openWorkspaceStep(card.id)"
                @keydown="onStepActionKeydown($event, card.id)"
              >
                {{ card.actionLabel }}
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      <section v-else-if="activeStep === 'mutation-logs'" class="space-y-4">
        <div
          v-if="mutationLogsSectionState.phase === 'forbidden'"
          class="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm"
          role="alert"
        >
          <p class="font-medium text-destructive">{{ mutationLogsSectionState.title }}</p>
          <p class="mt-1 text-muted-foreground">{{ mutationLogsSectionState.message }}</p>
        </div>
        <div
          v-else-if="mutationLogsSectionState.phase === 'error'"
          class="rounded-lg border border-dashed p-4 text-sm"
          role="alert"
        >
          <p class="font-medium">{{ mutationLogsSectionState.title }}</p>
          <p class="mt-1 text-muted-foreground">{{ mutationLogsSectionState.message }}</p>
          <Button class="mt-3" size="sm" variant="outline" @click="loadMutationLogRuns">
            Retry mutation log load
          </Button>
        </div>
        <Card v-else>
          <CardHeader>
            <CardTitle class="text-base">MutationLogs</CardTitle>
            <CardDescription>
              Knowledge-graph scoped mutation runs with per-entry operation previews and run metrics.
            </CardDescription>
          </CardHeader>
          <CardContent class="grid gap-3 xl:grid-cols-[280px_1fr]">
            <div class="rounded border">
              <div class="flex items-center justify-between border-b px-3 py-2">
                <p class="text-xs font-medium text-muted-foreground">Runs</p>
                <Button size="sm" variant="ghost" class="h-6 px-2 text-[10px]" @click="loadMutationLogRuns">
                  Refresh
                </Button>
              </div>
              <div v-if="mutationLogLoading" class="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground" role="status">
                <Loader2 class="size-3.5 animate-spin" />
                {{ mutationLogsSectionState.message }}
              </div>
              <div
                v-else-if="mutationLogRuns.length === 0"
                class="space-y-2 px-3 py-4 text-xs text-muted-foreground"
              >
                <p>{{ mutationLogsSectionState.message }}</p>
                <Button size="sm" variant="outline" @click="loadMutationLogRuns">
                  {{ mutationLogsSectionState.actionLabel ?? 'Refresh runs' }}
                </Button>
              </div>
              <div v-else class="max-h-64 overflow-auto p-2 space-y-1.5">
                <button
                  v-for="run in mutationLogRuns"
                  :key="run.id"
                  type="button"
                  tabindex="0"
                  class="w-full rounded border px-2 py-1.5 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  :class="selectedMutationLogRunId === run.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/40'"
                  @click="selectMutationLogRun(run.id)"
                  @keydown="onMutationRunKeydown($event, run.id)"
                >
                  <p class="font-medium truncate">{{ run.data_source_name }}</p>
                  <p class="text-muted-foreground truncate">{{ new Date(run.started_at).toLocaleString() }}</p>
                  <div class="mt-1 flex items-center justify-between">
                    <Badge variant="outline" class="text-[10px]">{{ run.status }}</Badge>
                    <span class="font-mono text-[10px] text-muted-foreground">{{ run.mutation_log_id }}</span>
                  </div>
                </button>
              </div>
            </div>

            <div v-if="selectedMutationLogRun" class="space-y-3 rounded border p-3">
              <p class="text-xs font-medium text-muted-foreground">Run summary</p>
              <div class="flex flex-wrap items-center gap-2">
                <Badge>{{ selectedMutationLogRun.status }}</Badge>
                <p class="text-xs text-muted-foreground">
                  Data source:
                  <span class="font-medium text-foreground">{{ selectedMutationLogRun.data_source_name }}</span>
                </p>
              </div>
              <div class="grid gap-2 sm:grid-cols-2">
                <div class="rounded border px-3 py-2 text-xs">
                  <p class="text-muted-foreground">MutationLog</p>
                  <p class="mt-1 font-mono break-all">{{ selectedMutationLogRun.mutation_log_id }}</p>
                </div>
                <div class="rounded border px-3 py-2 text-xs">
                  <p class="text-muted-foreground">Session</p>
                  <p class="mt-1 font-mono break-all">{{ selectedMutationLogRun.session_id ?? 'None' }}</p>
                </div>
                <div class="rounded border px-3 py-2 text-xs">
                  <p class="text-muted-foreground">Started</p>
                  <p class="mt-1">{{ new Date(selectedMutationLogRun.started_at).toLocaleString() }}</p>
                </div>
                <div class="rounded border px-3 py-2 text-xs">
                  <p class="text-muted-foreground">Completed</p>
                  <p class="mt-1">
                    {{ selectedMutationLogRun.completed_at ? new Date(selectedMutationLogRun.completed_at).toLocaleString() : 'In progress' }}
                  </p>
                </div>
              </div>
              <div class="grid gap-2 sm:grid-cols-2">
                <div class="rounded border px-3 py-2 text-xs">
                  <p class="text-muted-foreground flex items-center gap-1.5">
                    <Coins class="size-3.5" />
                    Token usage
                  </p>
                  <p class="mt-1 font-medium">{{ (selectedMutationLogRun.token_usage_total ?? 0).toLocaleString() }}</p>
                </div>
                <div class="rounded border px-3 py-2 text-xs">
                  <p class="text-muted-foreground flex items-center gap-1.5">
                    <DollarSign class="size-3.5" />
                    Cost (USD)
                  </p>
                  <p class="mt-1 font-medium">${{ (selectedMutationLogRun.cost_total_usd ?? 0).toFixed(2) }}</p>
                </div>
              </div>
              <div class="rounded border p-3">
                <p class="mb-2 text-xs font-medium text-muted-foreground">Operation class counts</p>
                <div v-if="Object.keys(selectedMutationLogRun.operation_counts).length === 0" class="text-xs text-muted-foreground">
                  No operation class counts recorded for this run.
                </div>
                <div v-else class="space-y-1.5">
                  <div
                    v-for="([opClass, count]) in Object.entries(selectedMutationLogRun.operation_counts)"
                    :key="opClass"
                    class="flex items-center justify-between rounded border px-2 py-1.5 text-xs"
                  >
                    <span class="font-mono">{{ opClass }}</span>
                    <Badge variant="secondary">{{ count }}</Badge>
                  </div>
                </div>
              </div>
              <div class="rounded border p-3">
                <div class="mb-2 flex items-center justify-between gap-2">
                  <p class="text-xs font-medium text-muted-foreground">Per-entry operation previews</p>
                  <div
                    v-if="hasMutationLogEntryPreviewPage(mutationLogEntryPreviewPage)"
                    class="flex items-center gap-1"
                  >
                    <Button
                      size="sm"
                      variant="ghost"
                      class="h-6 px-2 text-[10px]"
                      :disabled="mutationLogEntryPreviewLoading || mutationLogEntryPreviewOffset === 0"
                      @click="loadMutationLogEntryPreviews(mutationLogEntryPreviewOffset - MUTATION_LOG_ENTRY_PREVIEW_PAGE_SIZE)"
                    >
                      Previous
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      class="h-6 px-2 text-[10px]"
                      :disabled="mutationLogEntryPreviewLoading || (mutationLogEntryPreviewPage?.offset ?? 0) + (mutationLogEntryPreviewPage?.entries.length ?? 0) >= (mutationLogEntryPreviewPage?.total ?? 0)"
                      @click="loadMutationLogEntryPreviews(mutationLogEntryPreviewOffset + MUTATION_LOG_ENTRY_PREVIEW_PAGE_SIZE)"
                    >
                      Next
                    </Button>
                  </div>
                </div>
                <div v-if="mutationLogEntryPreviewLoading" class="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 class="size-3.5 animate-spin" />
                  Loading entry previews...
                </div>
                <div
                  v-else-if="!hasMutationLogEntryPreviewPage(mutationLogEntryPreviewPage)"
                  class="rounded border border-dashed px-3 py-4 text-xs text-muted-foreground"
                >
                  {{ MUTATION_LOG_NO_PREVIEW_MESSAGE }}
                </div>
                <div v-else class="space-y-1.5">
                  <div
                    v-for="entry in mutationLogEntryPreviewPage?.entries ?? []"
                    :key="`${entry.line_number}-${entry.operation_class}`"
                    class="rounded border px-2 py-1.5 text-xs"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-mono">{{ entry.operation_class }}</span>
                      <span class="text-[10px] text-muted-foreground">Line {{ entry.line_number }}</span>
                    </div>
                    <p class="mt-1 text-muted-foreground">{{ entry.summary }}</p>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="rounded border border-dashed p-6 text-sm text-muted-foreground">
              Select a mutation run to view summary and per-entry previews.
            </div>
          </CardContent>
        </Card>
      </section>

      <section v-else-if="activeStep === 'graph-management'" class="space-y-4">
        <div
          v-if="graphManagementSectionState.phase === 'error'"
          class="rounded-lg border border-dashed p-4 text-sm"
          role="alert"
        >
          <p class="font-medium">{{ graphManagementSectionState.title }}</p>
          <p class="mt-1 text-muted-foreground">{{ graphManagementSectionState.message }}</p>
          <Button class="mt-3" size="sm" variant="outline" @click="loadExtractionSession">
            Retry session load
          </Button>
        </div>

        <Card class="graph-management-controls">
          <CardHeader class="pb-3">
            <CardTitle class="text-base">Graph Management</CardTitle>
            <CardDescription>
              Shared chat session with mode-specific assistant framing and workspace panels.
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-3">
            <div
              class="flex flex-wrap gap-2"
              role="tablist"
              aria-label="Graph management modes"
            >
              <Button
                v-for="mode in GRAPH_MANAGEMENT_MODE_ORDER"
                :key="mode"
                size="sm"
                role="tab"
                :aria-selected="graphManagementMode === mode"
                tabindex="0"
                :variant="graphManagementMode === mode ? 'default' : 'outline'"
                @click="setGraphManagementMode(mode)"
                @keydown="onModeSwitchKeydown($event, mode)"
              >
                {{ GRAPH_MANAGEMENT_MODE_LABELS[mode] }}
              </Button>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{{ sessionStatusLabel }}</Badge>
              <Button
                variant="outline"
                size="sm"
                :disabled="validating || transitioning || workspaceForbidden"
                :title="workspaceForbiddenReason ?? undefined"
                @click="validateWorkspace"
              >
                <Loader2 v-if="validating" class="mr-1.5 size-3.5 animate-spin" />
                <CheckCircle2 v-else class="mr-1.5 size-3.5" />
                Validate
              </Button>
              <Badge :variant="canTransition ? 'default' : 'secondary'">
                {{ canTransition ? 'Transition eligible' : 'Transition blocked' }}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <SharedConversationPanel
          v-model:draft-message="draftMessage"
          :mode-label="graphManagementModeLabel"
          :input-placeholder="graphManagementInputPlaceholder"
          :session-status-label="sessionStatusLabel"
          :session="extractionSession"
          :loading="sessionLoading"
          :clearing="clearingChat"
          :sending="sendingChat"
          :activity-lines="sessionActivityLines"
          :forbidden="sessionForbidden"
          :forbidden-reason="sessionForbiddenReason"
          :input-disabled="workspaceForbidden"
          :input-disabled-reason="workspaceForbiddenReason"
          @refresh="loadExtractionSession"
          @clear-chat="clearChat"
          @send-message="sendChatMessage"
        />

        <div class="grid gap-4 xl:grid-cols-[280px_1fr]">
          <div
            class="graph-management-rail rounded border"
            role="listbox"
            aria-label="Graph management status and artifacts"
          >
            <div class="border-b px-3 py-2">
              <p class="text-xs font-medium text-muted-foreground">Status &amp; artifacts</p>
            </div>
            <div class="space-y-1.5 p-2">
              <button
                v-for="item in visibleRailItems"
                :key="item.id"
                type="button"
                role="option"
                :aria-selected="selectedRailItemId === item.id"
                tabindex="0"
                class="w-full rounded border px-2 py-2 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                :class="[
                  stepStatusTintClass(item.status),
                  selectedRailItemId === item.id ? 'border-primary ring-1 ring-primary/30' : 'hover:bg-muted/40',
                ]"
                @click="selectRailItem(item.id)"
                @keydown="onRailKeydown($event, item.id)"
              >
                <div class="flex items-center justify-between gap-2">
                  <p class="font-medium">{{ item.label }}</p>
                  <Badge variant="outline" class="text-[10px]">{{ item.status }}</Badge>
                </div>
                <p class="mt-1 text-muted-foreground">{{ item.detailHint }}</p>
                <p class="mt-1 text-[10px] text-muted-foreground">Updated {{ item.lastUpdated }}</p>
              </button>
            </div>
          </div>

          <Card class="graph-management-detail">
            <CardHeader class="pb-3">
              <CardTitle class="text-base">
                {{ selectedRailItem?.label ?? 'Workspace detail' }}
              </CardTitle>
              <CardDescription>
                Mode:
                <span class="font-medium text-foreground">{{ graphManagementModeLabel }}</span>
              </CardDescription>
            </CardHeader>
            <CardContent class="space-y-4 text-sm">
              <template v-if="selectedRailItemId === 'schema-readiness'">
                <div class="rounded border p-3">
                  <p class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Bootstrap Progress Checklist
                  </p>
                  <div class="space-y-2">
                    <div
                      v-for="item in progressChecklist"
                      :key="item.id"
                      class="rounded border px-3 py-2"
                    >
                      <div class="flex items-center justify-between">
                        <p class="font-medium">{{ item.label }}</p>
                        <Badge :variant="item.passed ? 'default' : 'destructive'">
                          {{ item.passed ? 'Pass' : 'Fail' }}
                        </Badge>
                      </div>
                      <p class="mt-1 text-xs text-muted-foreground">
                        {{ item.passed ? item.passDetail : item.failDetail }}
                      </p>
                    </div>
                  </div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <Button variant="outline" :disabled="validating || transitioning || workspaceForbidden" @click="validateWorkspace">
                    <Loader2 v-if="validating" class="mr-1.5 size-3.5 animate-spin" />
                    <CheckCircle2 v-else class="mr-1.5 size-3.5" />
                    Validate
                  </Button>
                  <Button
                    :disabled="!canTransition || transitioning || validating || workspaceForbidden"
                    :title="transitionRestrictionReason ?? undefined"
                    @click="transitionToExtraction"
                  >
                    <Loader2 v-if="transitioning" class="mr-1.5 size-3.5 animate-spin" />
                    <PlayCircle v-else class="mr-1.5 size-3.5" />
                    Go to Extraction/Mutations
                  </Button>
                </div>
              </template>

              <template v-else-if="selectedRailItemId === 'validation-diagnostics'">
                <div class="rounded border p-3">
                  <p class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Validation Diagnostics
                  </p>
                  <div
                    v-if="statusProjection.readiness.prepopulated_types_without_instances.length > 0"
                    class="rounded border border-amber-400/60 bg-amber-50/60 p-2 text-xs dark:border-amber-800 dark:bg-amber-950/20"
                  >
                    <p class="font-medium text-amber-800 dark:text-amber-300">
                      Prepopulated types missing instances
                    </p>
                    <ul class="mt-1 list-disc space-y-1 pl-4 text-muted-foreground">
                      <li
                        v-for="typeLabel in statusProjection.readiness.prepopulated_types_without_instances"
                        :key="typeLabel"
                      >
                        {{ typeLabel }}
                      </li>
                    </ul>
                  </div>
                  <div
                    v-if="statusProjection.readiness.blocking_reasons.length > 0"
                    class="mt-2 rounded border border-destructive/50 p-3"
                  >
                    <p class="mb-1 flex items-center gap-1.5 text-xs font-medium text-destructive">
                      <ShieldAlert class="size-3.5" />
                      Blocking reasons
                    </p>
                    <ul class="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                      <li v-for="reason in statusProjection.readiness.blocking_reasons" :key="reason">
                        {{ reason }}
                      </li>
                    </ul>
                  </div>
                  <p
                    v-else-if="statusProjection.readiness.prepopulated_types_without_instances.length === 0"
                    class="text-xs text-muted-foreground"
                  >
                    No validation diagnostics are currently blocking transition.
                  </p>
                </div>
                <div class="rounded border p-3">
                  <p class="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Next Steps
                  </p>
                  <ul class="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                    <li v-for="step in nextSteps" :key="step">{{ step }}</li>
                  </ul>
                </div>
              </template>

              <template v-else-if="selectedRailItemId === 'session-pointers'">
                <div class="grid gap-2 md:grid-cols-3 text-xs">
                  <div class="rounded border px-3 py-2">
                    <p class="text-muted-foreground">Active schema bootstrap session</p>
                    <p class="mt-1 break-all font-mono">
                      {{ statusProjection.session_pointers.active_schema_bootstrap_session_id ?? 'None' }}
                    </p>
                  </div>
                  <div class="rounded border px-3 py-2">
                    <p class="text-muted-foreground">Active extraction operations session</p>
                    <p class="mt-1 break-all font-mono">
                      {{ statusProjection.session_pointers.active_extraction_operations_session_id ?? 'None' }}
                    </p>
                  </div>
                  <div class="rounded border px-3 py-2">
                    <p class="text-muted-foreground">Most recent completed session</p>
                    <p class="mt-1 break-all font-mono">
                      {{ statusProjection.session_pointers.most_recent_completed_session_id ?? 'None' }}
                    </p>
                  </div>
                </div>
                <div class="space-y-3 border-t pt-3">
                  <div class="flex items-center justify-between">
                    <p class="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Session History
                    </p>
                    <Button
                      size="sm"
                      variant="ghost"
                      class="h-6 px-2 text-[10px]"
                      :disabled="sessionHistoryLoading"
                      @click="loadSessionHistory"
                    >
                      Refresh
                    </Button>
                  </div>
                  <div
                    v-if="sessionHistoryLoading"
                    class="flex items-center gap-2 text-xs text-muted-foreground"
                  >
                    <Loader2 class="size-3.5 animate-spin" />
                    Loading session history...
                  </div>
                  <div
                    v-else-if="sessionHistory.length === 0"
                    class="rounded border border-dashed px-3 py-4 text-xs text-muted-foreground"
                  >
                    No archived or active sessions found for this scope yet.
                  </div>
                  <div v-else class="space-y-2">
                    <div
                      v-for="entry in sessionHistory"
                      :key="entry.id"
                      class="rounded border px-3 py-2 text-xs"
                    >
                      <div class="flex flex-wrap items-center justify-between gap-2">
                        <p class="font-mono break-all">{{ entry.id }}</p>
                        <Badge :variant="entry.is_active ? 'default' : 'secondary'">
                          {{ entry.is_active ? 'Active' : 'Archived' }}
                        </Badge>
                      </div>
                      <p class="mt-1 text-muted-foreground">
                        Updated {{ new Date(entry.updated_at).toLocaleString() }}
                        <span v-if="entry.archived_at">
                          · Archived {{ new Date(entry.archived_at).toLocaleString() }}
                        </span>
                      </p>
                      <p class="mt-1 text-muted-foreground">
                        {{ entry.message_count }} message(s)
                        · {{ entry.run_metrics.length }} linked run(s)
                      </p>
                      <div
                        v-if="entry.run_metrics.length > 0"
                        class="mt-2 space-y-1.5 rounded border bg-muted/20 p-2"
                      >
                        <div
                          v-for="metric in entry.run_metrics"
                          :key="metric.sync_run_id"
                          class="flex flex-wrap items-center justify-between gap-2"
                        >
                          <span class="font-mono">{{ metric.mutation_log_id ?? metric.sync_run_id }}</span>
                          <span class="text-muted-foreground">
                            {{ metric.token_usage_total ?? 0 }} tokens ·
                            ${{ (metric.cost_total_usd ?? 0).toFixed(2) }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <template v-else-if="graphManagementMode === 'extraction-jobs'">
                <p class="text-muted-foreground">
                  Trigger extraction jobs, inspect run history, and view run logs without leaving this workspace.
                </p>
                <div class="space-y-3 rounded border p-3">
                  <p class="text-xs font-medium text-muted-foreground">Data source</p>
                  <div
                    v-if="graphManagementDataSourcesLoading"
                    class="flex items-center gap-2 text-xs text-muted-foreground"
                  >
                    <Loader2 class="size-3.5 animate-spin" />
                    Loading data sources...
                  </div>
                  <div v-else-if="graphManagementDataSourcesError" class="text-xs text-destructive">
                    {{ graphManagementDataSourcesError }}
                  </div>
                  <div
                    v-else-if="graphManagementDataSources.length === 0"
                    class="text-xs text-muted-foreground"
                  >
                    No data sources are connected to this knowledge graph yet.
                  </div>
                  <div v-else class="flex flex-wrap gap-2">
                    <Button
                      v-for="ds in graphManagementDataSources"
                      :key="ds.id"
                      size="sm"
                      :variant="selectedOpsDataSourceId === ds.id ? 'default' : 'outline'"
                      @click="selectedOpsDataSourceId = ds.id"
                    >
                      {{ ds.name }}
                    </Button>
                  </div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    :disabled="!selectedOpsDataSourceId || inlineSyncTriggering"
                    @click="triggerInlineSync"
                  >
                    <Loader2 v-if="inlineSyncTriggering" class="mr-1.5 size-3.5 animate-spin" />
                    Trigger Sync
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    :disabled="!selectedOpsDataSourceId || inlineSyncRunsLoading"
                    @click="loadInlineSyncRuns"
                  >
                    Refresh Runs
                  </Button>
                </div>
                <div class="grid gap-3 xl:grid-cols-[300px_1fr]">
                  <div class="rounded border">
                    <div class="border-b px-3 py-2 text-xs font-medium text-muted-foreground">Sync runs</div>
                    <div
                      v-if="inlineSyncRunsLoading"
                      class="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground"
                    >
                      <Loader2 class="size-3.5 animate-spin" />
                      Loading sync runs...
                    </div>
                    <div v-else-if="inlineSyncRunsError" class="px-3 py-4 text-xs text-destructive">
                      {{ inlineSyncRunsError }}
                    </div>
                    <div v-else-if="inlineSyncRuns.length === 0" class="px-3 py-4 text-xs text-muted-foreground">
                      No sync runs found for this data source.
                    </div>
                    <div v-else class="max-h-72 space-y-1.5 overflow-auto p-2">
                      <button
                        v-for="run in inlineSyncRuns"
                        :key="run.id"
                        class="w-full rounded border px-2 py-1.5 text-left text-xs transition-colors"
                        :class="selectedInlineRunId === run.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/40'"
                        @click="loadInlineRunLogs(run.id)"
                      >
                        <div class="flex items-center justify-between gap-2">
                          <span class="font-mono">{{ run.id }}</span>
                          <Badge variant="outline" class="text-[10px]">{{ run.status }}</Badge>
                        </div>
                        <p class="mt-1 text-muted-foreground">
                          {{ new Date(run.started_at).toLocaleString() }}
                        </p>
                      </button>
                    </div>
                  </div>
                  <div class="rounded border p-3">
                    <p class="mb-2 text-xs font-medium text-muted-foreground">
                      Run logs
                      <span v-if="selectedOpsDataSource" class="font-normal text-muted-foreground/80">
                        · {{ selectedOpsDataSource.name }}
                      </span>
                    </p>
                    <div v-if="inlineRunLogsLoading" class="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 class="size-3.5 animate-spin" />
                      Loading logs...
                    </div>
                    <div v-else-if="inlineRunLogsError" class="text-xs text-destructive">
                      {{ inlineRunLogsError }}
                    </div>
                    <div v-else-if="inlineRunLogs.length === 0" class="text-xs text-muted-foreground">
                      Select a sync run to view logs.
                    </div>
                    <pre
                      v-else
                      class="max-h-72 overflow-auto rounded border bg-muted/20 p-2 text-[11px]"
                    >{{ inlineRunLogs.join('\n') }}</pre>
                  </div>
                </div>
              </template>

              <template v-else-if="graphManagementMode === 'one-off-mutations'">
                <p class="text-muted-foreground">
                  Author and apply one-off JSONL mutations directly in this workspace.
                </p>
                <div class="space-y-3 rounded border p-3">
                  <p class="text-xs font-medium text-muted-foreground">Mutation payload (JSONL)</p>
                  <textarea
                    v-model="inlineMutationJsonl"
                    class="min-h-44 w-full rounded border bg-background px-3 py-2 font-mono text-xs"
                    placeholder='{"op":"CREATE","type":"node","label":"repo","id":"repo:example","set_properties":{"name":"example"}}'
                  />
                  <div class="flex items-center gap-2">
                    <Button size="sm" :disabled="inlineMutationApplying" @click="applyInlineMutations">
                      <Loader2 v-if="inlineMutationApplying" class="mr-1.5 size-3.5 animate-spin" />
                      Apply Mutations
                    </Button>
                    <span class="text-xs text-muted-foreground">
                      Applies directly to this knowledge graph without page navigation.
                    </span>
                  </div>
                  <p v-if="inlineMutationApplyError" class="text-xs text-destructive">
                    {{ inlineMutationApplyError }}
                  </p>
                </div>
              </template>

              <template v-else>
                <p class="text-xs text-muted-foreground">
                  Select a status or artifact item to inspect mode-specific workspace content.
                </p>
              </template>
            </CardContent>
          </Card>
        </div>
      </section>
    </template>
  </div>
</template>
