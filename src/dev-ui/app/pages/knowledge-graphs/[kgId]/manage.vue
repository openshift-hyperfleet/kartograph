<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  captureScrollPositions,
  restoreScrollPositions,
  withPreservedScrollPositions,
  type ScrollSnapshot,
} from '@/composables/useScrollPositionPreserve'
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
import GraphDesignEntitiesPanel from '@/components/graph-management/GraphDesignEntitiesPanel.vue'
import GraphDesignRelationshipsPanel from '@/components/graph-management/GraphDesignRelationshipsPanel.vue'
import GraphExtractionJobsWorkspace from '@/components/graph-management/GraphExtractionJobsWorkspace.vue'
import GraphExtractionArchivedHistory from '@/components/graph-management/GraphExtractionArchivedHistory.vue'
import GraphMaintenanceWorkspace from '@/components/graph-management/GraphMaintenanceWorkspace.vue'
import GraphManagementMutationAuthoringPanel from '@/components/graph-management/GraphManagementMutationAuthoringPanel.vue'
import GraphSchemaExplorer from '@/components/graph-management/GraphSchemaExplorer.vue'
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
  resolveSessionModeForGraphManagementMode,
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
  buildDataSourcesStepUrl,
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
import { hasIngestionContextPrepared, resolvePrepStatusLabel, resolveRepoUrl } from '@/utils/kgDataSourcesCommits'
import { latestSyncRun } from '@/utils/kgDataSourcesSync'
import {
  appendLocalChatMessage,
  buildTransitionRestrictionReason,
  handleActivatableKeydown,
  isForbiddenHttpError,
  isNotFoundHttpError,
  resolveForbiddenReason,
  resolveSectionState,
  shouldApplyMutationResult,
} from '@/utils/kgManageState'
import { streamExtractionChatTurn, streamRuntimeWarmup } from '@/utils/kgExtractionChat'
import { applyThinkingRecentUpdate } from '@/utils/thinkingActivityLines'
import type { DesignArtifactsResponse } from '@/utils/kgDesignArtifacts'
import { primaryRelationshipTypeLabels, DEFAULT_DESIGN_ARTIFACTS_INSTANCES_PER_TYPE } from '@/utils/kgDesignArtifacts'

const runtimeConfig = useRuntimeConfig()
const { accessToken } = useAuth()

interface WorkspaceReadinessStatus {
  has_minimum_entity_types: boolean
  has_minimum_relationship_types: boolean
  prepopulated_types_ready: boolean
  prepopulated_types_without_instances: string[]
  prepopulated_relationship_types_without_instances: string[]
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

interface ArchivedHistorySummary {
  archivedJobCount: number
}

const route = useRoute()
const { hasTenant, tenantVersion } = useTenant()
const { extractErrorMessage } = useErrorHandler()
const { apiFetch, currentTenantId } = useApiClient()
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
const sessionLoadError = ref<string | null>(null)
const sessionForbidden = ref(false)
const sessionForbiddenReason = ref<string | null>(null)
const clearingChat = ref(false)
const togglingSession = ref(false)
const sendingChat = ref(false)
const runtimeWarming = ref(false)
const runtimeReady = ref(false)
const runtimeWarmupError = ref<string | null>(null)
let runtimeWarmupGeneration = 0
const extractionSession = ref<ExtractionSessionResponse | null>(null)
const draftMessage = ref('')
const statusProjection = ref<WorkspaceStatusResponse | null>(null)
const archivedWriteCount = ref(0)
const graphManagementMode = ref<GraphManagementMode>('initial-schema-design')
const selectedRailItemId = ref<GraphManagementRailItemId | null>(null)
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
const designArtifactsReloadNonce = ref(0)
const designArtifactsRefreshing = ref(false)

type ModeConversationState = {
  session: ExtractionSessionResponse | null
  runtimeReady: boolean
  runtimeWarmupError: string | null
  sessionActivityLines: string[]
  draftMessage: string
}

function emptyModeConversationState(): ModeConversationState {
  return {
    session: null,
    runtimeReady: false,
    runtimeWarmupError: null,
    sessionActivityLines: [],
    draftMessage: '',
  }
}

const modeConversationState = ref<Record<GraphManagementMode, ModeConversationState>>({
  'initial-schema-design': emptyModeConversationState(),
  'extraction-jobs': emptyModeConversationState(),
  'one-off-mutations': emptyModeConversationState(),
})

const activeStep = computed(() => parseManageStepQuery(route.query.step))
const showOverview = computed(() => activeStep.value === null)

const dataSourcesDetailUrl = computed(() =>
  buildDataSourcesStepUrl(kgId.value, dataSourceCount.value),
)

const workspaceOverviewInput = computed(() => ({
  kgId: kgId.value,
  dataSourceCount: dataSourceCount.value,
  maintenanceReadyCount: maintenanceReadyCount.value,
  mutationLogRunCount: archivedWriteCount.value,
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
  if (activeStep.value === 'maintain') {
    return 'Maintain'
  }
  if (activeStep.value === 'mutation-logs') {
    return 'Graph Writes History'
  }
  return modeLabel.value
})

const graphManagementSessionMode = computed<'schema_bootstrap' | 'extraction_operations'>(() =>
  resolveSessionModeForGraphManagementMode(graphManagementMode.value),
)

const graphManagementSessionActive = computed(
  () => Boolean(extractionSession.value?.id && !extractionSession.value.archived_at),
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
  if (togglingSession.value) return 'Updating session'
  if (!graphManagementSessionActive.value) return 'No active session'
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
  () =>
    workspaceForbidden.value
    || !graphManagementSessionActive.value
    || runtimeWarming.value
    || !runtimeReady.value,
)

const chatInputDisabledReason = computed(() => {
  if (workspaceForbidden.value) return workspaceForbiddenReason.value
  if (!graphManagementSessionActive.value) {
    return 'Start a session to chat with the Graph Management Assistant.'
  }
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
    prepopulatedGapCount:
      statusProjection.value.readiness.prepopulated_types_without_instances.length
      + statusProjection.value.readiness.prepopulated_relationship_types_without_instances.length,
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
    return 'Define extraction job sets with per-instance descriptions, review ontology schema, and run parallel extraction workers for this knowledge graph.'
  }
  if (graphManagementMode.value === 'one-off-mutations') {
    return 'Ask the assistant to change schema types or specific instances — it validates and applies mutations directly. Use manual JSONL below only for power-user overrides.'
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

const graphManagementSectionState = computed(() =>
  resolveSectionState({
    section: 'graph-management',
    loading: sessionLoading.value,
    error: sessionLoadError.value,
    forbidden: sessionForbidden.value,
    forbiddenReason: sessionForbiddenReason.value,
  }),
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
const graphManagementDetailRef = ref<HTMLElement | null>(null)
let graphManagementScrollSnapshot: ScrollSnapshot | null = null

function graphManagementScrollTargets(): HTMLElement[] {
  const elements: HTMLElement[] = []
  const main = document.querySelector('main')
  if (main instanceof HTMLElement) elements.push(main)
  if (graphManagementDetailRef.value) elements.push(graphManagementDetailRef.value)
  return elements
}

function captureGraphManagementScroll(): void {
  if (activeStep.value !== 'graph-management') return
  graphManagementScrollSnapshot = captureScrollPositions(graphManagementScrollTargets())
}

function restoreGraphManagementScroll(): void {
  if (!graphManagementScrollSnapshot) return
  restoreScrollPositions(graphManagementScrollSnapshot)
  graphManagementScrollSnapshot = null
}

async function refreshDesignArtifacts(options: { silent?: boolean } = {}) {
  if (!hasTenant.value || !kgId.value) return
  designArtifactsRefreshing.value = true
  try {
    const artifacts = await apiFetch<DesignArtifactsResponse>(
      `/management/knowledge-graphs/${kgId.value}/design-artifacts`,
      { query: { limit: DEFAULT_DESIGN_ARTIFACTS_INSTANCES_PER_TYPE } },
    )
    const applyArtifactRefresh = () => {
      entityTypeLabels.value = Object.keys(artifacts.entities ?? {}).sort()
      relationshipTypeLabels.value = (artifacts.relationships ?? []).map((rel) => rel.relationship_type)
      designArtifactsReloadNonce.value += 1
    }
    if (activeStep.value === 'graph-management') {
      await withPreservedScrollPositions(graphManagementScrollTargets(), async () => {
        applyArtifactRefresh()
        await nextTick()
      })
    } else {
      applyArtifactRefresh()
    }
    if (!options.silent) {
      toast.success('Design artifacts refreshed')
    }
  } catch (err) {
    if (!options.silent) {
      toast.error('Failed to refresh design artifacts', {
        description: extractErrorMessage(err),
      })
    }
  } finally {
    designArtifactsRefreshing.value = false
  }
}

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
      if (hasIngestionContextPrepared(ds)) {
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
        edge_types?: Array<{
          label: string
          auto_generated?: boolean
          inverse_of?: string | null
        }>
      }>(`/management/knowledge-graphs/${kgId.value}/ontology`)
      entityTypeLabels.value = (ontology.node_types ?? []).map((t) => t.label)
      relationshipTypeLabels.value = primaryRelationshipTypeLabels(ontology.edge_types ?? [])
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

function returnToWorkspaceOverview() {
  navigateTo(buildManageStepUrl(kgId.value))
}

async function loadWorkspaceStatus() {
  if (!hasTenant.value || !kgId.value) return
  loading.value = true
  workspaceLoadError.value = null
  const preserveScroll =
    activeStep.value === 'graph-management' && statusProjection.value !== null
  const fetchStatus = async () => {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace-status`,
    )
  }
  try {
    if (preserveScroll) {
      await withPreservedScrollPositions(graphManagementScrollTargets(), fetchStatus)
    } else {
      await fetchStatus()
    }
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

async function loadArchivedWriteCount() {
  if (!hasTenant.value || !kgId.value) return
  try {
    const payload = await apiFetch<ArchivedHistorySummary>(
      `/management/knowledge-graphs/${kgId.value}/extraction-jobs/archived-history`,
    )
    archivedWriteCount.value = payload.archivedJobCount
  } catch {
    archivedWriteCount.value = 0
  }
}

async function clearChat() {
  if (!kgId.value || sessionForbidden.value) return
  clearingChat.value = true
  runtimeWarmupGeneration += 1
  runtimeWarming.value = false
  runtimeReady.value = false
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${graphManagementSessionMode.value}/clear-chat`,
      {
        method: 'POST',
        body: { graph_management_ui_mode: graphManagementMode.value },
      },
    )
    snapshotCurrentModeConversation()
    await warmupAssistantRuntime()
    toast.success('Extraction chat cleared')
    void loadArchivedWriteCount()
  } catch (err) {
    toast.error('Failed to clear chat', {
      description: extractErrorMessage(err),
    })
  } finally {
    clearingChat.value = false
  }
}

function snapshotCurrentModeConversation() {
  const mode = graphManagementMode.value
  modeConversationState.value[mode] = {
    session: extractionSession.value,
    runtimeReady: runtimeReady.value,
    runtimeWarmupError: runtimeWarmupError.value,
    sessionActivityLines: [...sessionActivityLines.value],
    draftMessage: draftMessage.value,
  }
}

function restoreModeConversation(mode: GraphManagementMode) {
  const cached = modeConversationState.value[mode] ?? emptyModeConversationState()
  extractionSession.value = cached.session
  runtimeReady.value = cached.runtimeReady
  runtimeWarmupError.value = cached.runtimeWarmupError
  sessionActivityLines.value = [...cached.sessionActivityLines]
  draftMessage.value = cached.draftMessage
}

function syncRuntimeReadyFromSession() {
  if (runtimeWarming.value) return
  const sticky = extractionSession.value?.runtime_context?.sticky_runtime
  runtimeReady.value = Boolean(
    sticky
    && typeof sticky === 'object'
    && (sticky as { phase?: string }).phase === 'ready',
  )
}

async function loadExtractionSession() {
  if (!kgId.value || activeStep.value !== 'graph-management') return
  sessionLoading.value = true
  sessionLoadError.value = null
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${graphManagementSessionMode.value}/active`
        + `?graph_management_ui_mode=${encodeURIComponent(graphManagementMode.value)}`,
    )
    syncActivityLinesFromSession()
    syncRuntimeReadyFromSession()
    sessionForbidden.value = false
    sessionForbiddenReason.value = null
  } catch (err) {
    extractionSession.value = null
    runtimeReady.value = false
    if (isForbiddenHttpError(err)) {
      sessionForbidden.value = true
      sessionForbiddenReason.value = resolveForbiddenReason(
        err,
        'You do not have permission to manage this knowledge graph.',
      )
    } else if (isNotFoundHttpError(err)) {
      sessionForbidden.value = false
      sessionForbiddenReason.value = null
      sessionLoadError.value = null
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
    snapshotCurrentModeConversation()
  }
}

async function startGraphManagementSession() {
  if (!kgId.value || sessionForbidden.value) return
  togglingSession.value = true
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${graphManagementSessionMode.value}/start-session`,
      {
        method: 'POST',
        body: { graph_management_ui_mode: graphManagementMode.value },
      },
    )
    snapshotCurrentModeConversation()
    await warmupAssistantRuntime()
    toast.success('Graph Management Assistant session started')
  } catch (err) {
    toast.error('Failed to start session', {
      description: extractErrorMessage(err),
    })
  } finally {
    togglingSession.value = false
  }
}

async function endGraphManagementSession() {
  if (!kgId.value || sessionForbidden.value || !graphManagementSessionActive.value) return
  togglingSession.value = true
  runtimeWarmupGeneration += 1
  runtimeWarming.value = false
  runtimeReady.value = false
  try {
    await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${graphManagementSessionMode.value}/end-session`,
      {
        method: 'POST',
        body: { graph_management_ui_mode: graphManagementMode.value },
      },
    )
    extractionSession.value = null
    runtimeWarmupError.value = null
    sessionActivityLines.value = []
    snapshotCurrentModeConversation()
    void loadArchivedWriteCount()
    toast.success('Graph Management Assistant session ended')
  } catch (err) {
    toast.error('Failed to end session', {
      description: extractErrorMessage(err),
    })
  } finally {
    togglingSession.value = false
  }
}

async function toggleGraphManagementSession() {
  if (graphManagementSessionActive.value) {
    await endGraphManagementSession()
    return
  }
  await startGraphManagementSession()
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
  snapshotCurrentModeConversation()
  graphManagementMode.value = mode
  restoreModeConversation(mode)
  selectedRailItemId.value = resolveSchemaRailSelection(
    selectedRailItemId.value,
    mode,
    graphManagementRailItems.value,
  )
  navigateTo(buildGraphManagementStepUrl(kgId.value, mode), { replace: true })
  void loadExtractionSession()
}

function selectSchemaRailItem(itemId: GraphManagementRailItemId) {
  selectedRailItemId.value = itemId
  void nextTick(() => {
    document.querySelector<HTMLElement>('.graph-management-detail')?.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  })
}

function onSchemaRailKeydown(event: KeyboardEvent, itemId: GraphManagementRailItemId) {
  handleActivatableKeydown(event, () => selectSchemaRailItem(itemId))
}

function onModeSwitchKeydown(event: KeyboardEvent, mode: GraphManagementMode) {
  handleActivatableKeydown(event, () => setGraphManagementMode(mode))
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
      sessionMode: graphManagementSessionMode.value,
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
      syncRuntimeReadyFromSession()
      snapshotCurrentModeConversation()
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
      sessionMode: graphManagementSessionMode.value,
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
      await refreshDesignArtifacts({ silent: true })
      await loadWorkspaceStatus()
    }
  }
}

async function validateWorkspace() {
  if (!kgId.value || workspaceForbidden.value) return
  validating.value = true
  try {
    const validate = async () => {
      statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
        `/management/knowledge-graphs/${kgId.value}/workspace/validate`,
        { method: 'POST' },
      )
    }
    if (activeStep.value === 'graph-management') {
      await withPreservedScrollPositions(graphManagementScrollTargets(), validate)
    } else {
      await validate()
    }
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
    const transition = async () => {
      statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
        `/management/knowledge-graphs/${kgId.value}/workspace/transition-to-extraction`,
        { method: 'POST' },
      )
    }
    if (activeStep.value === 'graph-management') {
      await withPreservedScrollPositions(graphManagementScrollTargets(), transition)
    } else {
      await transition()
    }
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

onMounted(() => {
  loadKgIdentity()
  loadWorkspaceStatus()
  loadOverviewMetrics()
  loadArchivedWriteCount()
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
  archivedWriteCount.value = 0
  workspaceLoadError.value = null
  workspaceForbidden.value = false
  workspaceForbiddenReason.value = null
  sessionLoadError.value = null
  sessionForbidden.value = false
  sessionForbiddenReason.value = null
  loadKgIdentity()
  loadWorkspaceStatus()
  loadOverviewMetrics()
  loadArchivedWriteCount()
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
  () => [activeStep.value, route.query.gm_mode] as const,
  async ([step]) => {
    if (step === 'graph-management') {
      syncGraphManagementState()
      restoreModeConversation(graphManagementMode.value)
      await Promise.all([
        loadExtractionSession(),
        loadGraphManagementDataSources(),
        refreshDesignArtifacts({ silent: true }),
      ])
    } else {
      snapshotCurrentModeConversation()
      runtimeWarmupGeneration += 1
      runtimeWarming.value = false
      runtimeReady.value = false
      runtimeWarmupError.value = null
    }
  },
)

watch(selectedOpsDataSourceId, () => {
  inlineRunLogs.value = []
  inlineRunLogsError.value = null
  selectedInlineRunId.value = null
  loadInlineSyncRuns()
})

watch(
  () => {
    if (activeStep.value !== 'graph-management') return null
    return [
      statusProjection.value,
      designArtifactsReloadNonce.value,
      progressChecklist.value,
      graphManagementRailItems.value,
    ] as const
  },
  () => {
    captureGraphManagementScroll()
  },
  { flush: 'sync', deep: true },
)

watch(
  () => {
    if (activeStep.value !== 'graph-management') return null
    return [
      statusProjection.value,
      designArtifactsReloadNonce.value,
      progressChecklist.value,
      graphManagementRailItems.value,
    ] as const
  },
  () => {
    restoreGraphManagementScroll()
  },
  { flush: 'post', deep: true },
)
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
            <template v-else-if="activeStep === 'maintain'">
              Schedule and run incremental maintenance extraction jobs when tracked sources have new commits.
            </template>
            <template v-else-if="activeStep === 'mutation-logs'">
              Knowledge-graph scoped mutation run visibility and run metrics.
            </template>
            <template v-else>
              Knowledge-graph scoped workspace overview.
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
                <div class="text-2xl font-bold">{{ archivedWriteCount }}</div>
                <p class="text-xs text-muted-foreground">Archived writes</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader class="flex flex-row items-start justify-between gap-3 space-y-0">
            <div class="space-y-1">
              <CardTitle class="text-base">Data Sources</CardTitle>
              <CardDescription>Configured repositories for this knowledge graph</CardDescription>
            </div>
            <Button as-child variant="outline" size="sm" class="shrink-0">
              <NuxtLink :to="dataSourcesDetailUrl" class="inline-flex items-center">
                More Detail
                <ArrowRight class="ml-1.5 size-3.5" />
              </NuxtLink>
            </Button>
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

        <GraphSchemaExplorer :kg-id="kgId" :reload-nonce="designArtifactsReloadNonce" />
      </section>

      <section v-else-if="activeStep === 'mutation-logs'" class="space-y-4">
        <GraphExtractionArchivedHistory :kg-id="kgId" />
      </section>

      <section v-else-if="activeStep === 'maintain'" class="space-y-4">
        <GraphMaintenanceWorkspace :kg-id="kgId" />
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
          <CardHeader class="gap-2 space-y-2 px-4 py-3">
            <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
              <div class="flex min-w-0 items-center gap-2">
                <div
                  class="flex size-8 shrink-0 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary"
                >
                  <PencilRuler class="size-4 shrink-0" aria-hidden="true" />
                </div>
                <CardTitle class="text-base leading-none">Graph Management</CardTitle>
              </div>
              <span class="text-xs font-medium text-muted-foreground">Mode</span>
              <div
                class="flex min-w-0 flex-1 flex-wrap gap-1.5"
                role="tablist"
                aria-label="Graph management modes"
              >
                <template v-for="mode in GRAPH_MANAGEMENT_MODE_ORDER" :key="mode">
                  <Button
                    v-if="isGraphManagementModeUnlocked(mode, graphManagementModeGate)"
                    size="sm"
                    variant="outline"
                    class="h-8 shrink-0 px-2.5 text-xs shadow-none transition-colors"
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
                    class="inline-flex h-8 max-w-full items-center gap-1.5 rounded-md border border-dashed border-rose-200/80 bg-rose-500/[0.04] px-2 text-xs text-muted-foreground dark:border-rose-900/40 dark:bg-rose-950/20"
                    role="tab"
                    :aria-selected="false"
                    :aria-disabled="true"
                    :aria-label="`${GRAPH_MANAGEMENT_MODE_LABELS[mode]} locked: ${graphManagementModeLockReason(mode, graphManagementModeGate) ?? ''}`"
                    :title="graphManagementModeLockReason(mode, graphManagementModeGate) ?? undefined"
                  >
                    <Lock class="size-3 shrink-0 text-rose-700/80 dark:text-rose-400/90" aria-hidden="true" />
                    <span class="truncate font-medium text-foreground/80">
                      {{ GRAPH_MANAGEMENT_MODE_LABELS[mode] }}
                    </span>
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
          :session-active="graphManagementSessionActive"
          :loading="conversationPanelLoading"
          :clearing="clearingChat"
          :toggling-session="togglingSession"
          :sending="sendingChat"
          :preparing-runtime="runtimeWarming"
          :activity-lines="sessionActivityLines"
          :forbidden="sessionForbidden"
          :forbidden-reason="sessionForbiddenReason"
          :input-disabled="chatInputDisabled"
          :input-disabled-reason="chatInputDisabledReason"
          @toggle-session="toggleGraphManagementSession"
          @clear-chat="clearChat"
          @send-message="sendChatMessage"
        />

        <GraphExtractionJobsWorkspace
          v-if="graphManagementMode === 'extraction-jobs'"
          :kg-id="kgId"
          :reload-nonce="designArtifactsReloadNonce"
        />

        <div
          v-else
          class="graph-management-artifacts grid gap-6 lg:grid-cols-[minmax(0,15.5rem)_minmax(0,1fr)] lg:items-start"
        >
          <Card
            id="graph-management-schema-artifacts"
            class="graph-management-schema-panel lg:sticky lg:top-4 lg:self-start"
          >
            <CardHeader class="pb-2">
              <CardTitle class="text-sm font-semibold">Design Artifacts</CardTitle>
              <CardDescription class="text-xs">
                Live schema and instances from the platform database for
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

          <div
            id="graph-management-artifact-detail"
            ref="graphManagementDetailRef"
            class="graph-management-detail min-h-0 min-w-0 max-h-[min(70dvh,calc(100dvh-12rem))] space-y-6 overflow-y-auto overscroll-contain"
          >
            <div v-if="selectedRailItemId === 'schema-entities'" class="min-w-0 space-y-2">
              <GraphDesignEntitiesPanel
                :kg-id="kgId"
                :reload-nonce="designArtifactsReloadNonce"
                embedded
              />
            </div>

            <div v-else-if="selectedRailItemId === 'schema-relationships'" class="min-w-0 space-y-2">
              <GraphDesignRelationshipsPanel
                :kg-id="kgId"
                :reload-nonce="designArtifactsReloadNonce"
                embedded
              />
            </div>

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
                      Prepopulated entity types missing instances
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
                    v-if="
                      statusProjection.readiness.prepopulated_relationship_types_without_instances
                        .length > 0
                    "
                    class="rounded-lg border border-amber-400/60 bg-amber-50/60 p-3 text-xs dark:border-amber-800 dark:bg-amber-950/20"
                  >
                    <p class="font-medium text-amber-800 dark:text-amber-300">
                      Prepopulated relationship types missing instances
                    </p>
                    <ul class="mt-1 list-disc space-y-1 pl-4 text-muted-foreground">
                      <li
                        v-for="relKey in statusProjection.readiness
                          .prepopulated_relationship_types_without_instances"
                        :key="relKey"
                      >
                        {{ relKey }}
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
                    v-else-if="
                      statusProjection.readiness.prepopulated_types_without_instances.length === 0
                        && statusProjection.readiness.prepopulated_relationship_types_without_instances
                          .length === 0
                        && statusProjection.readiness.blocking_reasons.length === 0
                    "
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

            <GraphManagementMutationAuthoringPanel
              v-else-if="selectedRailItemId === 'mutation-authoring'"
              :kg-id="kgId"
              @applied="refreshDesignArtifacts"
            />

            <Card v-else>
              <CardHeader>
                <CardTitle class="text-base">Schema &amp; artifacts</CardTitle>
                <CardDescription>
                  Select a schema artifact from the list to inspect mode-specific workspace content.
                </CardDescription>
              </CardHeader>
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
