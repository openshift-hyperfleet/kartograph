<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  ArrowLeft,
  ArrowRight,
  Box,
  CheckCircle2,
  ChevronLeft,
  Coins,
  Database,
  DollarSign,
  FileText,
  GitBranch,
  Link2,
  Loader2,
  Lock,
  MessageSquare,
  PencilRuler,
  PlayCircle,
  ScrollText,
  ShieldAlert,
  Trash2,
  Wrench,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import SharedConversationPanel from '@/components/extraction/SharedConversationPanel.vue'
import {
  GRAPH_MANAGEMENT_INPUT_PLACEHOLDERS,
  GRAPH_MANAGEMENT_MODE_LABELS,
  GRAPH_MANAGEMENT_MODE_ORDER,
  buildGraphManagementRailItems,
  buildGraphManagementStepUrl,
  filterRailItemsForMode,
  graphManagementModeLockReason,
  isGraphManagementModeUnlocked,
  parseGraphManagementModeQuery,
  resolveEffectiveGraphManagementMode,
  resolveSharedSessionMode,
  type GraphManagementMode,
  type GraphManagementModeGateInput,
  type GraphManagementRailItemId,
} from '@/utils/kgGraphManagement'
import {
  filterSchemaRailItems,
  graphManagementArtifactHint,
  graphManagementArtifactRowClass,
  graphManagementRailItemDone,
  resolveSchemaRailSelection,
} from '@/utils/kgGraphManagementArtifacts'
import {
  buildManageStepUrl,
  parseManageStepQuery,
} from '@/utils/kgManageWorkspace'
import {
  buildWorkspaceHubNextStep,
  buildWorkspaceHubTiles,
  resolveWorkspaceHubPhaseBadge,
  workspaceHubDescription,
  workspaceHubStepBadgeClass,
  workspaceHubTileClasses,
  type WorkspaceHubOverview,
  type WorkspaceHubSourceRow,
} from '@/utils/kgManageWorkspaceHub'
import { isIngestionPreparedAtHead, resolvePrepStatusLabel, resolveRepoUrl } from '@/utils/kgDataSourcesCommits'
import { latestSyncRun } from '@/utils/kgDataSourcesSync'
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
import { streamExtractionChatTurn, streamRuntimeWarmup } from '@/utils/kgExtractionChat'
import { applyThinkingRecentUpdate } from '@/utils/thinkingActivityLines'
import { useGraphApi } from '@/composables/api/useGraphApi'

const runtimeConfig = useRuntimeConfig()
const { accessToken } = useAuth()

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
  connection_config?: Record<string, string>
  last_extraction_baseline_commit?: string | null
  tracked_branch_head_commit?: string | null
  clone_head_commit?: string | null
  last_prepared_commit?: string | null
  ingested_head_commit?: string | null
  newest_unpulled_commit?: string | null
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
const { apiFetch, currentTenantId } = useApiClient()
const graphApi = useGraphApi()
const kgId = computed(() => String(route.params.kgId ?? ''))
const kgIdentity = ref<KnowledgeGraphIdentity | null>(null)
const dataSourceCount = ref(0)
const preparedSourceCount = ref(0)
const maintenanceReadyCount = ref(0)
const overviewSourceRows = ref<WorkspaceHubSourceRow[]>([])
const entityTypeLabels = ref<string[]>([])
const relationshipTypeLabels = ref<string[]>([])
const deleteKgDialogOpen = ref(false)
const deletingKg = ref(false)
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
const runtimeWarming = ref(false)
const runtimeReady = ref(false)
const runtimeWarmupError = ref<string | null>(null)
let runtimeWarmupGeneration = 0
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

const workspaceHubOverview = computed((): WorkspaceHubOverview => ({
  ...workspaceOverviewInput.value,
  preparedSourceCount: preparedSourceCount.value,
  entityTypeLabels: entityTypeLabels.value,
  relationshipTypeLabels: relationshipTypeLabels.value,
}))

const workspaceHubTiles = computed(() => buildWorkspaceHubTiles(workspaceHubOverview.value))
const workspaceHubNextStep = computed(() => buildWorkspaceHubNextStep(workspaceHubOverview.value))
const workspaceHubPhaseBadge = computed(() => resolveWorkspaceHubPhaseBadge(workspaceHubOverview.value))
const workspaceHubDescriptionText = computed(() => workspaceHubDescription(workspaceHubOverview.value))

const workspaceHubTileIcons = {
  'data-sources': GitBranch,
  'graph-management': MessageSquare,
  'mutation-logs': ScrollText,
  maintain: Wrench,
} as const

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

const conversationSessionForPanel = computed<ExtractionSessionResponse | null>(() => {
  if (!extractionSession.value) return null
  if (!runtimeReady.value) {
    return {
      ...extractionSession.value,
      message_history: [],
    }
  }
  return extractionSession.value
})

const sessionStatusLabel = computed(() => {
  const latestActivity = sessionActivityLines.value.filter(Boolean).at(-1)
  if (runtimeWarming.value) {
    return latestActivity ?? 'Starting assistant'
  }
  if (!runtimeReady.value && latestActivity) {
    return latestActivity
  }
  if (!runtimeReady.value && runtimeWarmupError.value) {
    return runtimeWarmupError.value
  }
  if (sessionLoading.value) return 'Loading session'
  if (clearingChat.value) return 'Resetting chat'
  if (extractionSession.value?.id) {
    return `Active · ${extractionSession.value.id.slice(0, 8)}`
  }
  return 'No active session'
})

const showRuntimeWarmupProgress = computed(
  () =>
    runtimeWarming.value
    || (!runtimeReady.value && sessionActivityLines.value.some((line) => line.trim().length > 0)),
)

const conversationPanelLoading = computed(
  () => sessionLoading.value && !showRuntimeWarmupProgress.value,
)

const chatInputDisabled = computed(
  () => workspaceForbidden.value || runtimeWarming.value || !runtimeReady.value,
)

const chatInputDisabledReason = computed(() => {
  if (workspaceForbidden.value) return workspaceForbiddenReason.value
  if (runtimeWarming.value) return 'Starting Graph Management Assistant…'
  if (!runtimeReady.value) {
    return runtimeWarmupError.value ?? 'Assistant runtime is not ready yet.'
  }
  return null
})

const graphManagementRailItems = computed(() => {
  if (!statusProjection.value) return []
  return buildGraphManagementRailItems({
    workspaceMode: statusProjection.value.workspace_mode,
    transitionEligible: statusProjection.value.transition_eligible,
    blockingReasonCount: statusProjection.value.readiness.blocking_reasons.length,
    prepopulatedGapCount: statusProjection.value.readiness.prepopulated_types_without_instances.length,
    hasMinimumEntityTypes: statusProjection.value.readiness.has_minimum_entity_types,
    hasMinimumRelationshipTypes: statusProjection.value.readiness.has_minimum_relationship_types,
    sessionUpdatedAt: extractionSession.value?.updated_at ?? null,
    hasActiveSession: Boolean(extractionSession.value?.id),
  })
})

const visibleRailItems = computed(() =>
  filterRailItemsForMode(graphManagementRailItems.value, graphManagementMode.value),
)

const schemaRailItems = computed(() => filterSchemaRailItems(visibleRailItems.value))

const graphManagementModeGate = computed((): GraphManagementModeGateInput => ({
  workspaceMode: statusProjection.value?.workspace_mode ?? 'schema_bootstrap',
  transitionEligible: statusProjection.value?.transition_eligible === true,
}))

const graphManagementChatDescription = computed(() => {
  if (graphManagementMode.value === 'extraction-jobs') {
    return 'Coordinate extraction job setup, sync runs, and maintenance for this knowledge graph. Use the assistant below to drive operational changes.'
  }
  if (graphManagementMode.value === 'one-off-mutations') {
    return 'Author and apply one-off graph mutations scoped to this knowledge graph. Use the assistant below for mutation guidance and workspace context.'
  }
  return 'Design and refine schema readiness, validation, and bootstrap transition for this knowledge graph. Use the assistant below to prepare workspace artifacts.'
})

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

const sessionActivityLines = ref<string[]>([])

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

    let prepared = 0
    const rows: WorkspaceHubSourceRow[] = []
    for (const ds of dataSources) {
      let status = 'not prepared'
      let statusVariant: WorkspaceHubSourceRow['statusVariant'] = 'secondary'
      try {
        const runs = await apiFetch<Array<{ status: string }>>(
          `/management/data-sources/${ds.id}/sync-runs`,
        )
        const latest = latestSyncRun(runs)
        if (latest) {
          status = resolvePrepStatusLabel(latest.status).toLowerCase()
          if (latest.status === 'ingested' || latest.status === 'completed') {
            statusVariant = 'success'
          }
        }
      } catch {
        // keep default status
      }
      if (isIngestionPreparedAtHead(ds)) {
        prepared += 1
        if (status === 'not prepared') {
          status = 'prepared'
          statusVariant = 'success'
        }
      }
      rows.push({
        id: ds.id,
        name: ds.name,
        url: resolveRepoUrl(ds.connection_config),
        status,
        statusVariant,
      })
    }
    preparedSourceCount.value = prepared
    overviewSourceRows.value = rows

    try {
      const ontology = await apiFetch<{
        node_types?: Array<{ label: string }>
        edge_types?: Array<{ label: string }>
      }>(`/management/knowledge-graphs/${kgId.value}/ontology`)
      entityTypeLabels.value = (ontology.node_types ?? []).map((t) => t.label)
      relationshipTypeLabels.value = (ontology.edge_types ?? []).map((t) => t.label)
    } catch {
      entityTypeLabels.value = []
      relationshipTypeLabels.value = []
    }
  } catch {
    dataSourceCount.value = 0
    preparedSourceCount.value = 0
    maintenanceReadyCount.value = 0
    overviewSourceRows.value = []
    entityTypeLabels.value = []
    relationshipTypeLabels.value = []
  }
}

async function handleDeleteKnowledgeGraph() {
  deletingKg.value = true
  try {
    await apiFetch(`/management/knowledge-graphs/${kgId.value}`, { method: 'DELETE' })
    toast.success(`Knowledge graph "${kgIdentity.value?.name ?? kgId.value}" deleted`)
    deleteKgDialogOpen.value = false
    await navigateTo('/knowledge-graphs')
  } catch (err) {
    toast.error('Failed to delete knowledge graph', {
      description: extractErrorMessage(err),
    })
  } finally {
    deletingKg.value = false
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

async function refreshGraphManagementSession() {
  await loadExtractionSession()
  await warmupAssistantRuntime()
}

async function loadExtractionSession() {
  if (!kgId.value || activeStep.value !== 'graph-management') return
  sessionLoading.value = true
  sessionLoadError.value = null
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${sharedSessionMode.value}/active`,
    )
    syncActivityLinesFromSession()
    const stickyPhase = extractionSession.value?.runtime_context?.sticky_runtime
    if (
      stickyPhase
      && typeof stickyPhase === 'object'
      && (stickyPhase as { phase?: string }).phase === 'ready'
      && !runtimeWarming.value
    ) {
      runtimeReady.value = true
    }
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
  const effectiveMode = resolveEffectiveGraphManagementMode(
    fromQuery,
    graphManagementModeGate.value,
  )
  graphManagementMode.value = effectiveMode
  if (fromQuery && fromQuery !== effectiveMode) {
    navigateTo(buildGraphManagementStepUrl(kgId.value, effectiveMode), { replace: true })
  }
  selectedRailItemId.value = resolveSchemaRailSelection(
    selectedRailItemId.value,
    graphManagementMode.value,
    graphManagementRailItems.value,
  )
}

function setGraphManagementMode(mode: GraphManagementMode) {
  if (!isGraphManagementModeUnlocked(mode, graphManagementModeGate.value)) {
    const reason = graphManagementModeLockReason(mode, graphManagementModeGate.value)
    toast.message('Mode locked', { description: reason ?? 'Finish schema design first.' })
    return
  }
  graphManagementMode.value = mode
  selectedRailItemId.value = resolveSchemaRailSelection(
    selectedRailItemId.value,
    mode,
    graphManagementRailItems.value,
  )
  navigateTo(buildGraphManagementStepUrl(kgId.value, mode), { replace: true })
}

function selectSchemaRailItem(itemId: GraphManagementRailItemId) {
  selectedRailItemId.value = itemId
  void nextTick(() => {
    document.getElementById('graph-management-artifact-detail')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  })
}

function onSchemaRailKeydown(event: KeyboardEvent, itemId: GraphManagementRailItemId) {
  handleActivatableKeydown(event, () => selectSchemaRailItem(itemId))
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

function applySessionThinkingRecent(recent: string[]) {
  sessionActivityLines.value = applyThinkingRecentUpdate(sessionActivityLines.value, recent)
}

function syncActivityLinesFromSession() {
  if (runtimeWarming.value || showRuntimeWarmupProgress.value) return
  const context = extractionSession.value?.runtime_context ?? {}
  const candidate = context.activity_lines ?? context.ndjson_activity_lines ?? context.thinking_lines
  if (Array.isArray(candidate)) {
    sessionActivityLines.value = applyThinkingRecentUpdate(
      [],
      candidate.filter(
        (line): line is string => typeof line === 'string' && line.trim().length > 0,
      ),
    )
  } else if (!runtimeWarming.value) {
    sessionActivityLines.value = []
  }
}

async function warmupAssistantRuntime() {
  if (!kgId.value || activeStep.value !== 'graph-management') return
  if (sessionForbidden.value || workspaceForbidden.value) {
    runtimeReady.value = false
    return
  }

  const generation = ++runtimeWarmupGeneration
  runtimeWarming.value = true
  runtimeReady.value = false
  runtimeWarmupError.value = null
  sessionActivityLines.value = ['Preparing Graph Management Assistant runtime…']

  try {
    for await (const event of streamRuntimeWarmup({
      apiBaseUrl: String(runtimeConfig.public.apiBaseUrl ?? ''),
      accessToken: accessToken.value,
      tenantId: currentTenantId.value,
      kgId: kgId.value,
      sessionMode: sharedSessionMode.value,
      uiMode: graphManagementMode.value,
    })) {
      if (generation !== runtimeWarmupGeneration) return
      if (event.type === 'thinking' && Array.isArray(event.recent)) {
        applySessionThinkingRecent(event.recent)
      }
      if (event.type === 'wait' && event.message) {
        applySessionThinkingRecent([event.message])
      }
      if (event.type === 'ready') {
        applySessionThinkingRecent(['Assistant container ready'])
      }
      if (event.type === 'done') {
        if (event.ok !== true) {
          throw new Error(
            event.error?.message
              ?? 'Runtime warmup failed before the assistant container was ready.',
          )
        }
        runtimeReady.value = event.ready === true || event.wait === true
      }
    }
    await loadExtractionSession()
  } catch (err) {
    runtimeWarmupError.value = extractErrorMessage(err)
    runtimeReady.value = false
    const lines = sessionActivityLines.value.filter(Boolean)
    sessionActivityLines.value = [
      ...lines,
      `Runtime startup failed: ${runtimeWarmupError.value}`,
    ]
    toast.error('Failed to start Graph Management Assistant', {
      description: runtimeWarmupError.value,
    })
  } finally {
    if (generation === runtimeWarmupGeneration) {
      runtimeWarming.value = false
    }
  }
}

async function sendChatMessage(message: string) {
  if (sessionForbidden.value || !shouldApplyMutationResult(sessionForbidden.value)) {
    toast.error('Chat unavailable', {
      description: sessionForbiddenReason.value
        ?? 'You do not have permission to send messages for this knowledge graph.',
    })
    return
  }

  const trimmed = message.trim()
  if (!trimmed || !kgId.value) return

  sendingChat.value = true
  sessionActivityLines.value = ['Contacting Graph Management Assistant…']
  draftMessage.value = ''

  const optimisticHistory = appendLocalChatMessage(extractionSession.value, trimmed)
  extractionSession.value = {
    ...(extractionSession.value ?? {
      id: 'pending-session',
      runtime_context: {},
      updated_at: new Date().toISOString(),
    }),
    message_history: optimisticHistory,
    updated_at: new Date().toISOString(),
  }

  let chatSucceeded = false
  try {
    for await (const event of streamExtractionChatTurn({
      apiBaseUrl: String(runtimeConfig.public.apiBaseUrl ?? ''),
      accessToken: accessToken.value,
      tenantId: currentTenantId.value,
      kgId: kgId.value,
      sessionMode: sharedSessionMode.value,
      uiMode: graphManagementMode.value,
      message: trimmed,
    })) {
      if (event.type === 'thinking' && Array.isArray(event.recent)) {
        applySessionThinkingRecent(event.recent)
      }
      if (event.type === 'wait') {
        sessionActivityLines.value = applyThinkingRecentUpdate(
          [],
          event.message ? [event.message] : ['Waiting for JobPackage ingestion context…'],
        )
      }
      if (event.type === 'done' && event.ok !== true) {
        throw new Error(event.error?.message ?? 'Graph Management Assistant returned an error.')
      }
    }
    chatSucceeded = true
    await loadExtractionSession()
  } catch (err) {
    const message = extractErrorMessage(err)
    applySessionThinkingRecent([`Error: ${message}`])
    toast.error('Failed to send message', {
      description: message,
    })
    await loadExtractionSession()
  } finally {
    sendingChat.value = false
    if (chatSucceeded) {
      syncActivityLinesFromSession()
    }
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
  preparedSourceCount.value = 0
  maintenanceReadyCount.value = 0
  overviewSourceRows.value = []
  entityTypeLabels.value = []
  relationshipTypeLabels.value = []
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
  async () => {
    if (activeStep.value === 'graph-management') {
      syncGraphManagementState()
      await loadExtractionSession()
    }
  },
)

watch(
  () => [activeStep.value, route.query.gm_mode, sharedSessionMode.value] as const,
  async () => {
    if (activeStep.value === 'graph-management') {
      syncGraphManagementState()
      await Promise.all([
        loadExtractionSession(),
        loadSessionHistory(),
        loadGraphManagementDataSources(),
      ])
      await warmupAssistantRuntime()
    } else {
      runtimeWarmupGeneration += 1
      runtimeWarming.value = false
      runtimeReady.value = false
      runtimeWarmupError.value = null
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
  <div class="mx-auto max-w-7xl space-y-6">
    <template v-if="showOverview">
      <NuxtLink
        to="/knowledge-graphs"
        class="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft class="mr-1 size-4" />
        Back to Knowledge Graphs
      </NuxtLink>
    </template>

    <template v-else>
      <div class="flex items-center justify-between">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <h1 class="text-2xl font-semibold tracking-tight">{{ graphHeaderTitle }}</h1>
            <Badge variant="secondary">{{ stepBadgeLabel }}</Badge>
          </div>
          <p class="text-sm text-muted-foreground">
            <template v-if="activeStep === 'graph-management'">
              Conversation-first graph management with shared session and mode-specific workspace panels.
            </template>
            <template v-else>
              Knowledge-graph scoped mutation run visibility and run metrics.
            </template>
          </p>
        </div>
        <Button variant="outline" size="sm" @click="returnToWorkspaceOverview()">
          <ArrowLeft class="mr-1.5 size-3.5" />
          Back to workspace overview
        </Button>
      </div>
      <Separator />
    </template>

    <div v-if="!hasTenant" class="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
      Select a tenant to manage this workspace.
    </div>

    <div
      v-else-if="workspaceOverviewState.phase === 'loading'"
      class="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"
      role="status"
    >
      <Loader2 class="size-8 animate-spin" />
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
        <div class="flex items-start justify-between gap-4">
          <div class="flex min-w-0 items-center gap-3">
            <Database class="size-8 shrink-0 text-primary" />
            <div class="min-w-0">
              <h2 class="text-2xl font-bold tracking-tight">{{ graphHeaderTitle }}</h2>
              <p class="truncate font-mono text-sm text-muted-foreground">{{ kgId }}</p>
              <p
                v-if="kgIdentity?.description"
                class="mt-0.5 text-sm text-muted-foreground"
              >
                {{ kgIdentity.description }}
              </p>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <Button variant="destructive" size="sm" class="gap-1.5" @click="deleteKgDialogOpen = true">
              <Trash2 class="size-4" />
              Delete
            </Button>
            <Badge :variant="workspaceHubPhaseBadge.variant" class="text-sm">
              {{ workspaceHubPhaseBadge.label }}
            </Badge>
          </div>
        </div>

        <Separator />

        <Card class="border-border">
          <CardHeader class="pb-3">
            <CardTitle class="text-base">Project workspace</CardTitle>
            <CardDescription>{{ workspaceHubDescriptionText }}</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div
              class="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between"
              :class="
                workspaceHubNextStep.primaryPhase
                  ? 'border-primary/25 bg-primary/5'
                  : 'border-border bg-muted/40'
              "
            >
              <div class="min-w-0 space-y-1">
                <p
                  class="text-xs font-semibold uppercase tracking-wide"
                  :class="workspaceHubNextStep.primaryPhase ? 'text-primary' : 'text-muted-foreground'"
                >
                  {{ workspaceHubNextStep.primaryPhase ? 'Next step' : 'Suggested next step' }}
                </p>
                <p class="text-sm font-medium leading-snug">{{ workspaceHubNextStep.title }}</p>
                <p class="text-sm leading-snug text-muted-foreground">{{ workspaceHubNextStep.description }}</p>
              </div>
              <Button
                as-child
                :variant="workspaceHubNextStep.primaryPhase ? 'default' : 'secondary'"
                class="w-full shrink-0 sm:w-auto"
              >
                <NuxtLink :to="workspaceHubNextStep.to" class="inline-flex items-center justify-center gap-2">
                  {{ workspaceHubNextStep.label }}
                  <ArrowRight class="size-4" />
                </NuxtLink>
              </Button>
            </div>

            <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <template v-for="item in workspaceHubTiles" :key="item.key">
                <NuxtLink
                  v-if="item.enabled"
                  :to="item.to"
                  class="flex flex-col gap-2 rounded-lg border p-4 text-left transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  :class="[
                    workspaceHubTileClasses(item),
                    item.tone === 'success'
                      ? 'hover:bg-green-500/10 dark:hover:bg-green-950/30'
                      : 'hover:bg-muted/60',
                  ]"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex min-w-0 flex-1 items-center gap-2">
                      <component
                        :is="workspaceHubTileIcons[item.key]"
                        class="size-4 shrink-0"
                        :class="
                          item.tone === 'success'
                            ? 'text-green-600 dark:text-green-400'
                            : 'text-primary'
                        "
                      />
                      <span class="text-sm font-semibold leading-tight">{{ item.title }}</span>
                    </div>
                    <div :class="workspaceHubStepBadgeClass(item)">
                      <CheckCircle2 v-if="item.done" class="size-4" />
                      <span v-else class="text-xs font-bold leading-none">{{ item.step }}</span>
                    </div>
                  </div>
                  <p class="text-xs leading-snug text-muted-foreground">{{ item.subtitle }}</p>
                  <span
                    class="text-xs font-medium"
                    :class="
                      item.tone === 'success'
                        ? 'text-green-700 dark:text-green-400'
                        : 'text-primary'
                    "
                  >
                    {{ item.linkLabel }}
                  </span>
                </NuxtLink>
                <div
                  v-else
                  class="flex flex-col gap-2 rounded-lg border border-dashed border-rose-200/80 bg-rose-500/[0.04] p-4 text-left text-muted-foreground dark:border-rose-900/40 dark:bg-rose-950/20"
                  :title="item.lockedReason || 'Locked'"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex min-w-0 flex-1 items-center gap-2">
                      <Lock class="size-4 shrink-0 text-rose-700/70 dark:text-rose-400/80" />
                      <span class="text-sm font-semibold leading-tight text-foreground/80">{{ item.title }}</span>
                    </div>
                    <div :class="workspaceHubStepBadgeClass(item)">
                      <span class="text-xs font-bold leading-none">{{ item.step }}</span>
                    </div>
                  </div>
                  <p class="text-xs leading-snug">{{ item.subtitle }}</p>
                  <p class="text-xs text-rose-800/90 dark:text-rose-300/90">{{ item.lockedReason }}</p>
                </div>
              </template>
            </div>
          </CardContent>
        </Card>

        <div class="grid gap-4 md:grid-cols-4">
          <Card>
            <CardContent class="flex items-center gap-3 p-4">
              <div class="rounded-md bg-muted p-2">
                <GitBranch class="size-4 text-muted-foreground" />
              </div>
              <div>
                <div class="text-2xl font-bold">{{ dataSourceCount }}</div>
                <p class="text-xs text-muted-foreground">Data Sources</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="flex items-center gap-3 p-4">
              <div class="rounded-md bg-muted p-2">
                <Box class="size-4 text-muted-foreground" />
              </div>
              <div>
                <div class="text-2xl font-bold">{{ entityTypeLabels.length }}</div>
                <p class="text-xs text-muted-foreground">Entity Types</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="flex items-center gap-3 p-4">
              <div class="rounded-md bg-muted p-2">
                <Link2 class="size-4 text-muted-foreground" />
              </div>
              <div>
                <div class="text-2xl font-bold">{{ relationshipTypeLabels.length }}</div>
                <p class="text-xs text-muted-foreground">Relationship Types</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="flex items-center gap-3 p-4">
              <div class="rounded-md bg-muted p-2">
                <FileText class="size-4 text-muted-foreground" />
              </div>
              <div>
                <div class="text-2xl font-bold">{{ mutationLogRuns.length }}</div>
                <p class="text-xs text-muted-foreground">Mutation Runs</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle class="text-base">Data Sources</CardTitle>
            <CardDescription>Configured repositories for this knowledge graph</CardDescription>
          </CardHeader>
          <CardContent>
            <div v-if="overviewSourceRows.length === 0" class="text-sm text-muted-foreground">
              No data sources configured yet.
            </div>
            <div v-else class="space-y-3">
              <div
                v-for="source in overviewSourceRows"
                :key="source.id"
                class="flex items-center justify-between rounded-lg border p-3"
              >
                <div class="flex min-w-0 items-center gap-3">
                  <GitBranch class="size-4 shrink-0 text-muted-foreground" />
                  <div class="min-w-0">
                    <p class="font-medium">{{ source.name }}</p>
                    <p class="truncate font-mono text-xs text-muted-foreground">{{ source.url }}</p>
                  </div>
                </div>
                <Badge :variant="source.statusVariant">{{ source.status }}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <div class="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle class="text-base">Entity Types</CardTitle>
              <CardDescription>Node types in the knowledge graph ontology</CardDescription>
            </CardHeader>
            <CardContent>
              <div v-if="entityTypeLabels.length === 0" class="text-sm text-muted-foreground">
                No entity types defined yet.
              </div>
              <div v-else class="flex flex-wrap gap-2">
                <Badge v-for="label in entityTypeLabels" :key="label" variant="outline">
                  {{ label }}
                </Badge>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle class="text-base">Relationship Types</CardTitle>
              <CardDescription>Edge types connecting entities</CardDescription>
            </CardHeader>
            <CardContent>
              <div v-if="relationshipTypeLabels.length === 0" class="text-sm text-muted-foreground">
                No relationship types defined yet.
              </div>
              <div v-else class="flex flex-wrap gap-2">
                <Badge v-for="label in relationshipTypeLabels" :key="label" variant="outline">
                  {{ label }}
                </Badge>
              </div>
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

        <Card class="graph-management-controls overflow-hidden">
          <CardHeader class="space-y-4 pb-4">
            <div class="flex flex-wrap items-start gap-3">
              <div
                class="flex size-10 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary"
              >
                <PencilRuler class="size-5 shrink-0" aria-hidden="true" />
              </div>
              <div class="min-w-0 flex-1 space-y-1">
                <CardTitle class="text-xl leading-tight">Graph Management</CardTitle>
                <CardDescription>
                  Shared chat session with mode-specific assistant framing and workspace panels.
                </CardDescription>
              </div>
            </div>

            <div class="space-y-2">
              <p class="text-sm font-medium text-muted-foreground">Mode:</p>
              <div
                class="grid gap-2 sm:grid-cols-3"
                role="tablist"
                aria-label="Graph management modes"
              >
                <template v-for="mode in GRAPH_MANAGEMENT_MODE_ORDER" :key="mode">
                  <Button
                    v-if="isGraphManagementModeUnlocked(mode, graphManagementModeGate)"
                    size="sm"
                    variant="outline"
                    class="h-auto min-h-9 justify-center border py-2 shadow-none transition-colors"
                    :class="
                      graphManagementMode === mode
                        ? 'border-primary/70 bg-muted/50 font-medium text-foreground ring-1 ring-primary/25'
                        : 'border-border bg-card text-muted-foreground hover:border-muted-foreground/30 hover:bg-muted/40 hover:text-foreground'
                    "
                    role="tab"
                    :aria-selected="graphManagementMode === mode"
                    tabindex="0"
                    @click="setGraphManagementMode(mode)"
                    @keydown="onModeSwitchKeydown($event, mode)"
                  >
                    {{ GRAPH_MANAGEMENT_MODE_LABELS[mode] }}
                  </Button>
                  <div
                    v-else
                    class="flex flex-col gap-1.5 rounded-lg border border-dashed border-rose-200/80 bg-rose-500/[0.04] px-3 py-2.5 text-left text-muted-foreground dark:border-rose-900/40 dark:bg-rose-950/20"
                    role="tab"
                    :aria-selected="false"
                    :aria-disabled="true"
                    :title="graphManagementModeLockReason(mode, graphManagementModeGate) ?? undefined"
                  >
                    <div class="flex items-center gap-2">
                      <Lock class="size-3.5 shrink-0 text-rose-700/80 dark:text-rose-400/90" />
                      <span class="text-sm font-medium leading-tight text-foreground/80">
                        {{ GRAPH_MANAGEMENT_MODE_LABELS[mode] }}
                      </span>
                    </div>
                    <p class="text-[11px] leading-snug text-rose-800/90 dark:text-rose-300/90">
                      {{ graphManagementModeLockReason(mode, graphManagementModeGate) }}
                    </p>
                  </div>
                </template>
              </div>
            </div>
          </CardHeader>
        </Card>

        <SharedConversationPanel
          v-model:draft-message="draftMessage"
          :mode-label="graphManagementModeLabel"
          :description="graphManagementChatDescription"
          :input-placeholder="graphManagementInputPlaceholder"
          :session-status-label="sessionStatusLabel"
          :session="conversationSessionForPanel"
          :loading="conversationPanelLoading"
          :clearing="clearingChat"
          :sending="sendingChat"
          :preparing-runtime="runtimeWarming"
          :activity-lines="sessionActivityLines"
          :forbidden="sessionForbidden"
          :forbidden-reason="sessionForbiddenReason"
          :input-disabled="chatInputDisabled"
          :input-disabled-reason="chatInputDisabledReason"
          @refresh="refreshGraphManagementSession"
          @clear-chat="clearChat"
          @send-message="sendChatMessage"
        />

        <div class="graph-management-artifacts grid gap-6 lg:grid-cols-[minmax(0,15.5rem)_minmax(0,1fr)] lg:items-start">
          <Card
            id="graph-management-schema-artifacts"
            class="graph-management-schema-panel lg:sticky lg:top-4 lg:self-start"
          >
            <CardHeader class="pb-2">
              <CardTitle class="text-sm font-semibold">Schema &amp; artifacts</CardTitle>
              <CardDescription class="text-xs">
                Workspace signals for
                <span class="font-medium text-foreground">{{ graphManagementModeLabel }}</span>.
                Select an artifact to open it in the detail panel to the right.
              </CardDescription>
            </CardHeader>
            <CardContent class="space-y-1.5 p-3 pt-0">
              <template v-if="schemaRailItems.length > 0">
                <button
                  v-for="item in schemaRailItems"
                  :key="item.id"
                  type="button"
                  :class="graphManagementArtifactRowClass(
                    selectedRailItemId === item.id,
                    graphManagementRailItemDone(item.status),
                  )"
                  @click="selectSchemaRailItem(item.id)"
                  @keydown="onSchemaRailKeydown($event, item.id)"
                >
                  <span class="font-medium leading-tight">{{ item.label }}</span>
                  <span class="text-xs text-muted-foreground">{{ graphManagementArtifactHint(item) }}</span>
                </button>
              </template>
              <p
                v-else
                class="rounded-lg border border-dashed p-3 text-xs text-muted-foreground"
              >
                No schema artifacts for this mode.
              </p>
            </CardContent>
          </Card>

          <div id="graph-management-artifact-detail" class="graph-management-detail scroll-mt-6 space-y-6">
            <Card v-if="selectedRailItemId === 'schema-entities'">
              <CardHeader>
                <CardTitle class="text-base flex items-center gap-2">
                  <Box class="size-4" />
                  Schema: Entities
                </CardTitle>
                <CardDescription>
                  Entity type coverage snapshot for
                  <span class="font-medium text-foreground">{{ graphManagementModeLabel }}</span>.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-3 text-sm">
                <div class="flex flex-wrap justify-end gap-2">
                  <Button variant="outline" size="sm" as-child>
                    <NuxtLink to="/graph/schema">Open schema browser</NuxtLink>
                  </Button>
                </div>
                <div class="rounded-lg border bg-muted/30 p-3">
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Entity type inventory
                    </p>
                    <Badge :variant="entityTypeLabels.length > 0 ? 'default' : 'secondary'">
                      {{ entityTypeLabels.length }} type(s)
                    </Badge>
                  </div>
                  <p
                    v-if="entityTypeLabels.length === 0"
                    class="mt-2 text-xs text-muted-foreground"
                  >
                    No entity types defined yet. Add at least one type to satisfy schema readiness.
                  </p>
                  <div v-else class="mt-2 flex flex-wrap gap-2">
                    <Badge v-for="label in entityTypeLabels" :key="label" variant="outline">
                      {{ label }}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card v-else-if="selectedRailItemId === 'schema-relationships'">
              <CardHeader>
                <CardTitle class="text-base flex items-center gap-2">
                  <Link2 class="size-4" />
                  Schema: Relationships
                </CardTitle>
                <CardDescription>
                  Relationship type coverage snapshot for
                  <span class="font-medium text-foreground">{{ graphManagementModeLabel }}</span>.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-3 text-sm">
                <div class="flex flex-wrap justify-end gap-2">
                  <Button variant="outline" size="sm" as-child>
                    <NuxtLink to="/graph/schema">Open schema browser</NuxtLink>
                  </Button>
                </div>
                <div class="rounded-lg border bg-muted/30 p-3">
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Relationship type inventory
                    </p>
                    <Badge :variant="relationshipTypeLabels.length > 0 ? 'default' : 'secondary'">
                      {{ relationshipTypeLabels.length }} type(s)
                    </Badge>
                  </div>
                  <p
                    v-if="relationshipTypeLabels.length === 0"
                    class="mt-2 text-xs text-muted-foreground"
                  >
                    No relationship types defined yet. Add at least one type to satisfy schema readiness.
                  </p>
                  <div v-else class="mt-2 flex flex-wrap gap-2">
                    <Badge v-for="label in relationshipTypeLabels" :key="label" variant="outline">
                      {{ label }}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card v-else-if="selectedRailItemId === 'schema-readiness'">
              <CardHeader>
                <CardTitle class="text-base flex items-center gap-2">
                  <CheckCircle2 class="size-4" />
                  Schema readiness
                </CardTitle>
                <CardDescription>
                  Bootstrap checklist, validate, and transition controls for
                  <span class="font-medium text-foreground">{{ graphManagementModeLabel }}</span>.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-4 text-sm">
                <div class="space-y-2 rounded-lg border bg-muted/30 p-3">
                  <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Bootstrap progress checklist
                  </p>
                  <div class="space-y-2">
                    <div
                      v-for="item in progressChecklist"
                      :key="item.id"
                      class="rounded-lg border bg-card px-3 py-2"
                    >
                      <div class="flex items-center justify-between gap-2">
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
              </CardContent>
            </Card>

            <Card v-else-if="selectedRailItemId === 'validation-diagnostics'">
              <CardHeader>
                <CardTitle class="text-base flex items-center gap-2">
                  <ShieldAlert class="size-4" />
                  Validation diagnostics
                </CardTitle>
                <CardDescription>
                  Blocking reasons and prepopulated type gaps before transitioning to extraction.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-4 text-sm">
                <div class="space-y-3 rounded-lg border bg-muted/30 p-3">
                  <div
                    v-if="statusProjection.readiness.prepopulated_types_without_instances.length > 0"
                    class="rounded-lg border border-amber-400/60 bg-amber-50/60 p-3 text-xs dark:border-amber-800 dark:bg-amber-950/20"
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
                    class="rounded-lg border border-destructive/50 bg-card p-3"
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
                <div class="rounded-lg border bg-muted/30 p-3">
                  <p class="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Next steps
                  </p>
                  <ul class="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                    <li v-for="step in nextSteps" :key="step">{{ step }}</li>
                  </ul>
                </div>
              </CardContent>
            </Card>

            <Card v-else-if="selectedRailItemId === 'extraction-jobs-setup'">
              <CardHeader>
                <CardTitle class="text-base flex items-center gap-2">
                  <Wrench class="size-4" />
                  Extraction jobs setup
                </CardTitle>
                <CardDescription>
                  Trigger extraction jobs, inspect run history, and view run logs without leaving this workspace.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-4 text-sm">
                <div class="space-y-3 rounded-lg border bg-muted/30 p-3">
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
                  <div class="rounded-lg border bg-card">
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
                        class="w-full rounded-lg border px-2 py-1.5 text-left text-xs transition-colors"
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
                  <div class="rounded-lg border bg-muted/30 p-3">
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
                      class="max-h-72 overflow-auto rounded-lg border bg-background p-2 text-[11px]"
                    >{{ inlineRunLogs.join('\n') }}</pre>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card v-else-if="selectedRailItemId === 'mutation-authoring'">
              <CardHeader>
                <CardTitle class="text-base flex items-center gap-2">
                  <PencilRuler class="size-4" />
                  Mutation authoring
                </CardTitle>
                <CardDescription>
                  Author and apply one-off JSONL mutations directly in this workspace.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-3 text-sm">
                <div class="space-y-3 rounded-lg border bg-muted/30 p-3">
                  <p class="text-xs font-medium text-muted-foreground">Mutation payload (JSONL)</p>
                  <textarea
                    v-model="inlineMutationJsonl"
                    class="min-h-44 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    placeholder='{"op":"CREATE","type":"node","label":"repo","id":"repo:example","set_properties":{"name":"example"}}'
                  />
                  <div class="flex flex-wrap items-center gap-2">
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
              </CardContent>
            </Card>

            <Card v-else>
              <CardHeader>
                <CardTitle class="text-base">Schema &amp; artifacts</CardTitle>
                <CardDescription>
                  Select a schema artifact from the list to inspect mode-specific workspace content.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card id="graph-management-session-pointers" class="graph-management-session-pointers">
              <CardHeader>
                <CardTitle class="text-base flex items-center gap-2">
                  <ScrollText class="size-4" />
                  Session pointers
                </CardTitle>
                <CardDescription>
                  Active bootstrap and extraction sessions, plus archived history for this knowledge graph.
                </CardDescription>
              </CardHeader>
              <CardContent class="space-y-4 text-sm">
                <div class="grid gap-2 md:grid-cols-3 text-xs">
                  <div class="rounded-lg border bg-muted/30 px-3 py-2">
                    <p class="text-muted-foreground">Active schema bootstrap session</p>
                    <p class="mt-1 break-all font-mono">
                      {{ statusProjection.session_pointers.active_schema_bootstrap_session_id ?? 'None' }}
                    </p>
                  </div>
                  <div class="rounded-lg border bg-muted/30 px-3 py-2">
                    <p class="text-muted-foreground">Active extraction operations session</p>
                    <p class="mt-1 break-all font-mono">
                      {{ statusProjection.session_pointers.active_extraction_operations_session_id ?? 'None' }}
                    </p>
                  </div>
                  <div class="rounded-lg border bg-muted/30 px-3 py-2">
                    <p class="text-muted-foreground">Most recent completed session</p>
                    <p class="mt-1 break-all font-mono">
                      {{ statusProjection.session_pointers.most_recent_completed_session_id ?? 'None' }}
                    </p>
                  </div>
                </div>
                <div class="space-y-3 border-t pt-3">
                  <div class="flex items-center justify-between">
                    <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Session history
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
                    class="rounded-lg border border-dashed px-3 py-4 text-xs text-muted-foreground"
                  >
                    No archived or active sessions found for this scope yet.
                  </div>
                  <div v-else class="space-y-2">
                    <div
                      v-for="entry in sessionHistory"
                      :key="entry.id"
                      class="rounded-lg border bg-card px-3 py-2 text-xs"
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
                        class="mt-2 space-y-1.5 rounded-lg border bg-muted/20 p-2"
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
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </template>

    <AlertDialog v-model:open="deleteKgDialogOpen">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this knowledge graph?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently deletes
            <span class="font-medium text-foreground">{{ kgIdentity?.name ?? kgId }}</span>
            and its configuration. Data sources and sync history for this graph will be removed.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel :disabled="deletingKg">Cancel</AlertDialogCancel>
          <AlertDialogAction :disabled="deletingKg" @click="handleDeleteKnowledgeGraph">
            <Loader2 v-if="deletingKg" class="mr-2 size-4 animate-spin" />
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
