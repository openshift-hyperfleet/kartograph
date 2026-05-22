<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ArrowLeft, CheckCircle2, Coins, DollarSign, Loader2, PlayCircle, ShieldAlert } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import SharedConversationPanel from '@/components/extraction/SharedConversationPanel.vue'
import {
  buildDataSourcesStepUrl,
  buildMaintainStepUrl,
  buildManageStepUrl,
  buildSuggestedNextStep,
  buildWorkspaceStepCards,
  parseManageStepQuery,
  resolveStepDestination,
  stepStatusTintClass,
  type WorkspaceStepId,
} from '@/utils/kgManageWorkspace'

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

interface MutationLogRunView {
  id: string
  data_source_id: string
  data_source_name: string
  status: string
  started_at: string
  completed_at: string | null
  mutation_log_id: string | null
  session_id: string | null
  actor_id: string | null
  operation_counts: Record<string, number>
  token_usage_total: number | null
  cost_total_usd: number | null
  error: string | null
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
const kgId = computed(() => String(route.params.kgId ?? ''))
const kgIdentity = ref<KnowledgeGraphIdentity | null>(null)
const dataSourceCount = ref(0)
const maintenanceReadyCount = ref(0)
const loading = ref(false)
const validating = ref(false)
const transitioning = ref(false)
const sessionLoading = ref(false)
const sessionHistoryLoading = ref(false)
const clearingChat = ref(false)
const extractionSession = ref<ExtractionSessionResponse | null>(null)
const sessionHistory = ref<ExtractionSessionHistoryItem[]>([])
const extractionTab = ref('extraction-jobs')
const draftMessage = ref('')
const statusProjection = ref<WorkspaceStatusResponse | null>(null)
const mutationLogLoading = ref(false)
const mutationLogRuns = ref<MutationLogRunView[]>([])
const selectedMutationLogRunId = ref<string | null>(null)

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

const sessionMode = computed<'schema_bootstrap' | 'extraction_operations'>(() =>
  statusProjection.value?.workspace_mode === 'extraction_operations'
    ? 'extraction_operations'
    : 'schema_bootstrap',
)

const canTransition = computed(() =>
  statusProjection.value?.workspace_mode === 'schema_bootstrap'
  && statusProjection.value?.transition_eligible === true,
)

const selectedMutationLogRun = computed(() =>
  mutationLogRuns.value.find((run) => run.id === selectedMutationLogRunId.value) ?? null,
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

function openWorkspaceStep(stepId: WorkspaceStepId) {
  navigateTo(resolveStepDestination(kgId.value, stepId))
}

function returnToWorkspaceOverview() {
  navigateTo(buildManageStepUrl(kgId.value))
}

async function loadWorkspaceStatus() {
  if (!hasTenant.value || !kgId.value) return
  loading.value = true
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace-status`,
    )
  } catch (err) {
    statusProjection.value = null
    toast.error('Failed to load knowledge graph workspace', {
      description: extractErrorMessage(err),
    })
  } finally {
    loading.value = false
  }
}

async function loadMutationLogRuns() {
  if (!hasTenant.value || !kgId.value) return
  mutationLogLoading.value = true
  try {
    const dataSources = await apiFetch<DataSourceRef[]>(
      `/management/knowledge-graphs/${kgId.value}/data-sources`,
    )

    const collected: MutationLogRunView[] = []
    for (const ds of dataSources) {
      try {
        const runs = await apiFetch<MutationLogRunView[]>(
          `/management/data-sources/${ds.id}/sync-runs`,
        )
        for (const run of runs) {
          if (!run.mutation_log_id) continue
          collected.push({
            ...run,
            data_source_name: ds.name,
          })
        }
      } catch {
        // Keep page resilient when one data source run list fails.
      }
    }

    collected.sort(
      (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
    )
    mutationLogRuns.value = collected
    if (
      !selectedMutationLogRunId.value
      || !collected.some((run) => run.id === selectedMutationLogRunId.value)
    ) {
      selectedMutationLogRunId.value = collected[0]?.id ?? null
    }
  } catch (err) {
    mutationLogRuns.value = []
    selectedMutationLogRunId.value = null
    toast.error('Failed to load mutation log runs', {
      description: extractErrorMessage(err),
    })
  } finally {
    mutationLogLoading.value = false
  }
}

async function loadExtractionSession() {
  if (!kgId.value) return
  sessionLoading.value = true
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${sessionMode.value}/active`,
    )
  } catch (err) {
    extractionSession.value = null
    toast.error('Failed to load extraction conversation', {
      description: extractErrorMessage(err),
    })
  } finally {
    sessionLoading.value = false
  }
}

async function loadSessionHistory() {
  if (!kgId.value) return
  sessionHistoryLoading.value = true
  try {
    const response = await apiFetch<{ sessions: ExtractionSessionHistoryItem[] }>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${sessionMode.value}/history`,
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

async function validateWorkspace() {
  if (!kgId.value) return
  validating.value = true
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace/validate`,
      { method: 'POST' },
    )
    toast.success('Workspace validation complete')
  } catch (err) {
    toast.error('Validation failed', {
      description: extractErrorMessage(err),
    })
  } finally {
    validating.value = false
  }
}

async function transitionToExtraction() {
  if (!kgId.value || !canTransition.value) return
  transitioning.value = true
  try {
    statusProjection.value = await apiFetch<WorkspaceStatusResponse>(
      `/management/knowledge-graphs/${kgId.value}/workspace/transition-to-extraction`,
      { method: 'POST' },
    )
    toast.success('Workspace transitioned to extraction operations')
    await loadExtractionSession()
  } catch (err) {
    toast.error('Transition failed', {
      description: extractErrorMessage(err),
    })
  } finally {
    transitioning.value = false
  }
}

async function clearChat() {
  // Clear chat resets the active extraction session for this knowledge graph.
  if (!kgId.value) return
  clearingChat.value = true
  try {
    extractionSession.value = await apiFetch<ExtractionSessionResponse>(
      `/extraction/knowledge-graphs/${kgId.value}/sessions/${sessionMode.value}/clear-chat`,
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
  loadKgIdentity()
  loadWorkspaceStatus()
  loadOverviewMetrics()
  loadMutationLogRuns()
})

watch(
  () => statusProjection.value?.workspace_mode,
  (mode) => {
    if (mode) {
      loadExtractionSession()
      loadSessionHistory()
    }
  },
)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-semibold tracking-tight">{{ graphHeaderTitle }}</h1>
          <Badge v-if="!showOverview" variant="secondary">{{ modeLabel }}</Badge>
        </div>
        <p class="text-sm text-muted-foreground">
          <template v-if="showOverview">
            Project workspace for knowledge graph {{ kgId }}.
          </template>
          <template v-else>
            Validate readiness and move from schema bootstrap to extraction operations.
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

    <div v-else-if="loading" class="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 class="size-4 animate-spin" />
      Loading workspace status...
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
                @click="openWorkspaceStep(card.id)"
              >
                {{ card.actionLabel }}
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      <section v-else-if="activeStep === 'mutation-logs'" class="space-y-4">
        <Card>
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
              <div v-if="mutationLogLoading" class="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground">
                <Loader2 class="size-3.5 animate-spin" />
                Loading mutation runs...
              </div>
              <div v-else-if="mutationLogRuns.length === 0" class="px-3 py-4 text-xs text-muted-foreground">
                No mutation log runs found for this knowledge graph yet.
              </div>
              <div v-else class="max-h-64 overflow-auto p-2 space-y-1.5">
                <button
                  v-for="run in mutationLogRuns"
                  :key="run.id"
                  class="w-full rounded border px-2 py-1.5 text-left text-xs transition-colors"
                  :class="selectedMutationLogRunId === run.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/40'"
                  @click="selectedMutationLogRunId = run.id"
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
                <p class="mb-2 text-xs font-medium text-muted-foreground">Per-entry operation previews</p>
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
            </div>
            <div v-else class="rounded border border-dashed p-6 text-sm text-muted-foreground">
              Select a mutation run to view summary and per-entry previews.
            </div>
          </CardContent>
        </Card>
      </section>

      <section v-else class="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle class="text-base">Mode & Transition Controls</CardTitle>
          <CardDescription>
            Validate current readiness and transition when eligible.
          </CardDescription>
        </CardHeader>
        <CardContent class="flex flex-wrap gap-2">
          <Button variant="outline" :disabled="validating || transitioning" @click="validateWorkspace">
            <Loader2 v-if="validating" class="mr-1.5 size-3.5 animate-spin" />
            <CheckCircle2 v-else class="mr-1.5 size-3.5" />
            Validate
          </Button>
          <Button
            :disabled="!canTransition || transitioning || validating"
            @click="transitionToExtraction"
          >
            <Loader2 v-if="transitioning" class="mr-1.5 size-3.5 animate-spin" />
            <PlayCircle v-else class="mr-1.5 size-3.5" />
            Go to Extraction/Mutations
          </Button>
          <Badge :variant="canTransition ? 'default' : 'secondary'">
            {{ canTransition ? 'Transition eligible' : 'Transition blocked' }}
          </Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle class="text-base">Readiness Results</CardTitle>
          <CardDescription>
            Bootstrap readiness requirements from workspace validation.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4 text-sm">
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

          <div class="flex items-center justify-between rounded border px-3 py-2">
            <span>Has minimum entity types</span>
            <Badge :variant="statusProjection.readiness.has_minimum_entity_types ? 'default' : 'destructive'">
              {{ statusProjection.readiness.has_minimum_entity_types ? 'Yes' : 'No' }}
            </Badge>
          </div>
          <div class="flex items-center justify-between rounded border px-3 py-2">
            <span>Has minimum relationship types</span>
            <Badge :variant="statusProjection.readiness.has_minimum_relationship_types ? 'default' : 'destructive'">
              {{ statusProjection.readiness.has_minimum_relationship_types ? 'Yes' : 'No' }}
            </Badge>
          </div>
          <div class="flex items-center justify-between rounded border px-3 py-2">
            <span>Prepopulated types ready</span>
            <Badge :variant="statusProjection.readiness.prepopulated_types_ready ? 'default' : 'destructive'">
              {{ statusProjection.readiness.prepopulated_types_ready ? 'Yes' : 'No' }}
            </Badge>
          </div>

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

            <div v-if="statusProjection.readiness.blocking_reasons.length > 0" class="mt-2 rounded border border-destructive/50 p-3">
              <p class="mb-1 text-xs font-medium text-destructive flex items-center gap-1.5">
                <ShieldAlert class="size-3.5" />
                Blocking reasons
              </p>
              <ul class="list-disc pl-4 text-xs text-muted-foreground space-y-1">
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
            <ul class="list-disc pl-4 text-xs text-muted-foreground space-y-1">
              <li v-for="step in nextSteps" :key="step">{{ step }}</li>
            </ul>
          </div>

        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle class="text-base">Session Pointers</CardTitle>
          <CardDescription>
            Active and recent extraction session references for this knowledge graph.
          </CardDescription>
        </CardHeader>
        <CardContent class="grid gap-2 md:grid-cols-3 text-xs">
          <div class="rounded border px-3 py-2">
            <p class="text-muted-foreground">Active schema bootstrap session</p>
            <p class="font-mono break-all mt-1">
              {{ statusProjection.session_pointers.active_schema_bootstrap_session_id ?? 'None' }}
            </p>
          </div>
          <div class="rounded border px-3 py-2">
            <p class="text-muted-foreground">Active extraction operations session</p>
            <p class="font-mono break-all mt-1">
              {{ statusProjection.session_pointers.active_extraction_operations_session_id ?? 'None' }}
            </p>
          </div>
          <div class="rounded border px-3 py-2">
            <p class="text-muted-foreground">Most recent completed session</p>
            <p class="font-mono break-all mt-1">
              {{ statusProjection.session_pointers.most_recent_completed_session_id ?? 'None' }}
            </p>
          </div>
        </CardContent>
        <CardContent class="space-y-3 border-t pt-4">
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
        </CardContent>
      </Card>

      <div class="space-y-4">
        <SharedConversationPanel
          v-model:draft-message="draftMessage"
          :mode-label="modeLabel"
          :session="extractionSession"
          :loading="sessionLoading"
          :clearing="clearingChat"
          :activity-lines="sessionActivityLines"
          @refresh="loadExtractionSession"
          @clear-chat="clearChat"
        />

        <Card v-if="statusProjection.workspace_mode === 'extraction_operations'">
          <CardHeader>
            <CardTitle class="text-base">Operations Workspace</CardTitle>
            <CardDescription>
              Tabbed controls for extraction jobs, manual mutations, and run/log visibility.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs v-model="extractionTab" class="w-full">
              <TabsList class="grid w-full grid-cols-3">
                <TabsTrigger value="extraction-jobs">Extraction Jobs</TabsTrigger>
                <TabsTrigger value="manual-mutations">Manual Mutations</TabsTrigger>
                <TabsTrigger value="run-logs">Run/Logs</TabsTrigger>
              </TabsList>
              <TabsContent value="extraction-jobs" class="mt-3 space-y-2 text-sm">
                <p class="text-muted-foreground">
                  Trigger extraction and maintenance controls from the data sources operations panel.
                </p>
                <Button size="sm" variant="outline" @click="navigateTo('/data-sources')">
                  Open Data Source Operations
                </Button>
              </TabsContent>
              <TabsContent value="manual-mutations" class="mt-3 space-y-2 text-sm">
                <p class="text-muted-foreground">
                  Open the mutation editor scoped to this knowledge graph for minor direct edits.
                </p>
                <Button size="sm" @click="navigateTo(`/graph/mutations?kg_id=${kgId}&view=editor`)">
                  Open Manual Mutations
                </Button>
              </TabsContent>
              <TabsContent value="run-logs" class="mt-3 space-y-2 text-sm">
                <p class="text-muted-foreground">
                  Review sync run history, maintenance outcomes, and operational logs.
                </p>
                <Button size="sm" variant="outline" @click="navigateTo('/data-sources')">
                  Open Run and Log Views
                </Button>
                <Card class="mt-2">
                  <CardHeader>
                    <CardTitle class="text-sm">MutationLog Browser</CardTitle>
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
                      <div v-if="mutationLogLoading" class="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground">
                        <Loader2 class="size-3.5 animate-spin" />
                        Loading mutation runs...
                      </div>
                      <div v-else-if="mutationLogRuns.length === 0" class="px-3 py-4 text-xs text-muted-foreground">
                        No mutation log runs found for this knowledge graph yet.
                      </div>
                      <div v-else class="max-h-64 overflow-auto p-2 space-y-1.5">
                        <button
                          v-for="run in mutationLogRuns"
                          :key="run.id"
                          class="w-full rounded border px-2 py-1.5 text-left text-xs transition-colors"
                          :class="selectedMutationLogRunId === run.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/40'"
                          @click="selectedMutationLogRunId = run.id"
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
                        <p class="mb-2 text-xs font-medium text-muted-foreground">Per-entry operation previews</p>
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
                    </div>
                    <div v-else class="rounded border border-dashed p-6 text-sm text-muted-foreground">
                      Select a mutation run to view summary and per-entry previews.
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
      </section>
    </template>
  </div>
</template>
