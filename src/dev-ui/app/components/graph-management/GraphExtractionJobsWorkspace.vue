<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Loader2,
  RefreshCw,
  Play,
  Settings,
  ClipboardList,
  AlertCircle,
  Eye,
  XCircle,
} from 'lucide-vue-next'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import GraphExtractionJobSetsPanel from '@/components/graph-management/GraphExtractionJobSetsPanel.vue'
import GraphDesignEntitiesPanel from '@/components/graph-management/GraphDesignEntitiesPanel.vue'
import GraphDesignRelationshipsPanel from '@/components/graph-management/GraphDesignRelationshipsPanel.vue'
import GraphExtractionJobWatchDialog from '@/components/graph-management/GraphExtractionJobWatchDialog.vue'

const props = defineProps<{
  kgId: string
  reloadNonce?: number
}>()

const { apiFetch } = useApiClient()

type OntologyTab = 'entities' | 'relationships'

interface DbStatus {
  jobsByStatus: Record<string, number>
  jobsBySet?: Record<string, { pending: number; in_progress: number; completed: number; failed: number; total: number }>
  avgCompletedJobSeconds?: number | null
  totalInputTokens: number
  totalOutputTokens: number
  totalCacheReadTokens: number
  totalCacheCreationTokens: number
  totalCostUsd: number
  recentJobs: Array<{
    jobId: string
    jobSet: string
    status: string
    workerId: string | null
    startedAt: string | null
    completedAt: string | null
    inputTokens: number
    outputTokens: number
    writeOps: number
    entitiesCreated?: number
    entitiesModified?: number
    relationshipsCreated?: number
    instanceCount?: number
    errorMessage?: string | null
    assistantPreview: string | null
  }>
  activeWorkers?: Array<{
    workerId: string
    jobId: string
    jobSet: string
    strategy: string
    instanceCount: number
    startedAt: string | null
  }>
}

type RecentJobEvent = DbStatus['recentJobs'][number] & {
  eventKey: string
  seenAtMs: number
}

interface ExtractionRunState {
  live: boolean
  status: string
  workerCount: number
  pauseRequested: boolean
}

interface PlanSummary {
  job_sets: Array<{
    name: string
    strategy: string
    enabled?: boolean
    entity_type?: string
    instances_per_job?: number
    projected_jobs?: number | null
  }>
}

const selectedOntologyTab = ref<OntologyTab>('entities')
const jobSetsReloadNonce = ref(0)
const dbStatus = ref<DbStatus | null>(null)
const dbLoading = ref(true)
const dbRefreshing = ref(false)
const dbError = ref<string | null>(null)
const extractionRunState = ref<ExtractionRunState | null>(null)
const planSummary = ref<PlanSummary | null>(null)
const workers = ref(2)
const startingExtraction = ref(false)
const pausingExtraction = ref(false)
const killingExtraction = ref(false)
const regeneratingJobs = ref(false)
const resettingRunning = ref(false)
const resettingCompleted = ref(false)
const resettingFailed = ref(false)
const resettingAll = ref(false)
const optimisticLiveUntilMs = ref<number | null>(null)
const nowMs = ref(Date.now())
const lastStatusRefreshMs = ref<number | null>(null)
const recentJobEvents = ref<RecentJobEvent[]>([])
const watchJobId = ref<string | null>(null)
const watchDialogOpen = ref(false)
const cancellingJobId = ref<string | null>(null)

function resolveApiErrorDescription(e: unknown): string {
  const err = e as { data?: { detail?: unknown }; message?: string }
  const detail = err.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: string }).message)
  }
  if (err.message) return err.message
  return 'Request failed'
}

function resolveRegenerateFailureMessage(description: string): { title: string; hint?: string } {
  const lower = description.toLowerCase()
  if (lower.includes('in progress') || lower.includes('still running')) {
    return {
      title: 'Cannot refresh jobs for that set yet',
      hint: 'Wait for running jobs to finish, use Cancel on individual jobs, or use Kill extraction to stop all workers — then Regenerate jobs again.',
    }
  }
  if (lower.includes('description') || lower.includes('entity type')) {
    return {
      title: 'Job set configuration is invalid',
      hint: 'Fix the errors shown in the Job Sets panel, then Save job sets or Regenerate jobs.',
    }
  }
  return { title: 'Regenerate failed', hint: description }
}

let autoRefreshInterval: ReturnType<typeof setInterval> | null = null
let clockInterval: ReturnType<typeof setInterval> | null = null

const basePath = computed(() => `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs`)

async function loadDatabaseStatus(options?: { background?: boolean }) {
  const background = options?.background ?? false
  const hasExistingData = dbStatus.value !== null

  if (background && hasExistingData) {
    dbRefreshing.value = true
  } else {
    dbLoading.value = true
  }
  if (!background) {
    dbError.value = null
  }
  try {
    const status = await apiFetch<DbStatus>(`${basePath.value}/database-status`)
    dbStatus.value = status
    mergeRecentJobEvents(status.recentJobs || [])
    lastStatusRefreshMs.value = Date.now()
    dbError.value = null
  } catch (e: unknown) {
    if (!background || !hasExistingData) {
      dbError.value = e instanceof Error ? e.message : 'Failed to load status'
    }
  } finally {
    dbLoading.value = false
    dbRefreshing.value = false
  }
}

async function loadExtractionRunState() {
  try {
    extractionRunState.value = await apiFetch<ExtractionRunState>(`${basePath.value}/run-state`)
  } catch {
    // Keep prior run state during background refresh failures.
  }
}

async function loadPlanSummary() {
  try {
    planSummary.value = await apiFetch<PlanSummary>(`${basePath.value}/plan-summary`)
  } catch {
    // Keep prior plan summary during background refresh failures.
  }
}

async function refreshAll(options?: { background?: boolean }) {
  const background = options?.background ?? dbStatus.value !== null
  await Promise.all([
    loadDatabaseStatus({ background }),
    loadExtractionRunState(),
    loadPlanSummary(),
  ])
}

const workerCount = computed(() => Math.max(1, Math.floor(Number(workers.value) || 1)))
const pendingJobsCount = computed(() => Number(dbStatus.value?.jobsByStatus?.pending || 0))
const inProgressJobsCount = computed(() => Number(dbStatus.value?.jobsByStatus?.in_progress || 0))
const completedJobsCount = computed(() => Number(dbStatus.value?.jobsByStatus?.completed || 0))
const failedJobsCount = computed(() => Number(dbStatus.value?.jobsByStatus?.failed || 0))
const remainingJobsCount = computed(() => pendingJobsCount.value + inProgressJobsCount.value)
const materializedJobsTotal = computed(
  () => pendingJobsCount.value + inProgressJobsCount.value + failedJobsCount.value + completedJobsCount.value,
)
const extractionRunLive = computed(() => {
  if (optimisticLiveUntilMs.value && nowMs.value < optimisticLiveUntilMs.value) return true
  return Boolean(extractionRunState.value?.live)
})
const hasRunningJobs = computed(() => inProgressJobsCount.value > 0)
const extractionProgressPercent = computed(() => {
  const total = materializedJobsTotal.value
  if (total <= 0) return 0
  return Math.round(((completedJobsCount.value + failedJobsCount.value) / total) * 100)
})
const plannedKnownTotalJobs = computed(() => {
  const sets = planSummary.value?.job_sets || []
  return sets.reduce((sum, set) => sum + (Number(set.projected_jobs) || 0), 0)
})
const plannedVsMaterializedMismatch = computed(() => {
  const planned = plannedKnownTotalJobs.value
  if (planned <= 0) return false
  return planned !== materializedJobsTotal.value
})
const recentJobs = computed(() => recentJobEvents.value)
const activeWorkerCount = computed(() => dbStatus.value?.activeWorkers?.length || 0)
const idleWorkerCount = computed(() => Math.max(0, workerCount.value - activeWorkerCount.value))
const statusAgeSeconds = computed(() => {
  if (!lastStatusRefreshMs.value) return null
  return Math.max(0, Math.floor((nowMs.value - lastStatusRefreshMs.value) / 1000))
})
const showOptimisticLiveActivity = computed(
  () => Boolean(optimisticLiveUntilMs.value && nowMs.value < optimisticLiveUntilMs.value),
)

function mergeRecentJobEvents(incoming: DbStatus['recentJobs']) {
  const now = Date.now()
  const existingByJobId = new Map(recentJobEvents.value.map((event) => [event.jobId, event] as const))
  for (const job of incoming) {
    existingByJobId.set(job.jobId, { ...job, eventKey: job.jobId, seenAtMs: now })
  }
  const maxAgeMs = 15 * 60 * 1000
  const merged = Array.from(existingByJobId.values()).filter((event) => now - event.seenAtMs <= maxAgeMs)
  merged.sort((a, b) => {
    const aTs = Date.parse(a.completedAt || a.startedAt || '') || a.seenAtMs
    const bTs = Date.parse(b.completedAt || b.startedAt || '') || b.seenAtMs
    return bTs - aTs
  })
  recentJobEvents.value = merged.slice(0, 80)
}

function clearRecentJobEvents() {
  recentJobEvents.value = []
}

function openWatch(jobId: string) {
  watchJobId.value = jobId
  watchDialogOpen.value = true
}

function recentJobBadgeVariant(status: string): 'default' | 'outline' | 'secondary' | 'destructive' | 'success' {
  if (status === 'in_progress') return 'default'
  if (status === 'failed') return 'destructive'
  if (status === 'completed') return 'success'
  return 'outline'
}

function formatRecentWhen(startedAt: string | null, completedAt: string | null): string {
  if (completedAt && startedAt) {
    const startMs = Date.parse(startedAt)
    const endMs = Date.parse(completedAt)
    if (Number.isFinite(startMs) && Number.isFinite(endMs) && endMs >= startMs) {
      const deltaSec = Math.max(0, Math.floor((endMs - startMs) / 1000))
      if (deltaSec < 60) return `${deltaSec}s`
      const mins = Math.floor(deltaSec / 60)
      const secs = deltaSec % 60
      if (mins < 60) return `${mins}m ${secs}s`
      const hours = Math.floor(mins / 60)
      return `${hours}h ${mins % 60}m`
    }
  }
  return completedAt || startedAt || '—'
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

async function startExtraction() {
  startingExtraction.value = true
  optimisticLiveUntilMs.value = Date.now() + 30000
  try {
    const res = await apiFetch<{ message?: string }>(`${basePath.value}/start`, {
      method: 'POST',
      body: { workers: workerCount.value },
    })
    toast.success('Extraction started', { description: res.message })
    startAutoRefresh()
    await refreshAll()
  } catch (e: unknown) {
    optimisticLiveUntilMs.value = null
    toast.error('Failed to start extraction', {
      description: e instanceof Error ? e.message : 'Request failed',
    })
  } finally {
    startingExtraction.value = false
  }
}

async function pauseExtraction() {
  pausingExtraction.value = true
  try {
    const res = await apiFetch<{ message?: string }>(`${basePath.value}/pause`, { method: 'POST' })
    toast.success('Pause requested', { description: res.message })
    await refreshAll()
  } catch (e: unknown) {
    toast.error('Failed to pause extraction', {
      description: e instanceof Error ? e.message : 'Request failed',
    })
  } finally {
    pausingExtraction.value = false
  }
}

async function killExtraction() {
  killingExtraction.value = true
  try {
    const res = await apiFetch<{ message?: string }>(`${basePath.value}/halt`, { method: 'POST' })
    toast.success('Extraction killed', { description: res.message })
    optimisticLiveUntilMs.value = null
    stopAutoRefresh()
    await refreshAll()
  } catch (e: unknown) {
    toast.error('Failed to kill extraction', {
      description: e instanceof Error ? e.message : 'Request failed',
    })
  } finally {
    killingExtraction.value = false
  }
}

async function regenerateJobs() {
  regeneratingJobs.value = true
  try {
    const res = await apiFetch<{ generated_jobs?: number; message?: string; warnings?: string[] }>(
      `${basePath.value}/regenerate`,
      { method: 'POST' },
    )
    toast.success('Jobs synced', {
      description: res.message || `Synced ${res.generated_jobs ?? 0} pending job(s).`,
    })
    if (Array.isArray(res.warnings) && res.warnings.length > 0) {
      toast.warning('Some job sets were skipped', {
        description: `${res.warnings.join(' ')} Save job sets after those jobs finish, or cancel them first.`,
        duration: 10000,
      })
    }
    await refreshAll()
  } catch (e: unknown) {
    const description = resolveApiErrorDescription(e)
    const failure = resolveRegenerateFailureMessage(description)
    toast.error(failure.title, {
      description: failure.hint || description,
      duration: 10000,
    })
  } finally {
    regeneratingJobs.value = false
  }
}

async function cancelJob(jobId: string) {
  cancellingJobId.value = jobId
  try {
    const res = await apiFetch<{ message?: string }>(
      `${basePath.value}/jobs/${encodeURIComponent(jobId)}/cancel`,
      { method: 'POST' },
    )
    toast.success('Job cancelled', { description: res.message })
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Cancel failed', { description: resolveApiErrorDescription(e) })
  } finally {
    cancellingJobId.value = null
  }
}

function canCancelJob(status: string): boolean {
  return status === 'pending' || status === 'in_progress'
}

async function resetByKind(kind: 'stale' | 'completed' | 'failed' | 'all') {
  const map = {
    stale: { ref: resettingRunning, path: 'reset-stale' },
    completed: { ref: resettingCompleted, path: 'reset-completed' },
    failed: { ref: resettingFailed, path: 'reset-failed' },
    all: { ref: resettingAll, path: 'reset' },
  } as const
  map[kind].ref.value = true
  try {
    await apiFetch(`${basePath.value}/${map[kind].path}`, { method: 'POST' })
    toast.success('Jobs reset')
    await refreshAll()
  } catch (e: unknown) {
    toast.error('Reset failed', { description: e instanceof Error ? e.message : 'Request failed' })
  } finally {
    map[kind].ref.value = false
  }
}

function startAutoRefresh() {
  if (autoRefreshInterval) return
  autoRefreshInterval = setInterval(() => { void refreshAll({ background: true }) }, 1500)
}

function stopAutoRefresh() {
  if (!autoRefreshInterval) return
  clearInterval(autoRefreshInterval)
  autoRefreshInterval = null
}

function onJobSetsSaved() {
  jobSetsReloadNonce.value += 1
  void refreshAll({ background: dbStatus.value !== null })
}

watch(
  () => extractionRunLive.value || hasRunningJobs.value,
  (active) => {
    if (active) startAutoRefresh()
    else if (!optimisticLiveUntilMs.value) stopAutoRefresh()
  },
  { immediate: true },
)

watch(
  () => props.reloadNonce,
  () => { void refreshAll({ background: dbStatus.value !== null }) },
)

onMounted(() => {
  void refreshAll()
  clockInterval = setInterval(() => { nowMs.value = Date.now() }, 1000)
})

onUnmounted(() => {
  stopAutoRefresh()
  if (clockInterval) clearInterval(clockInterval)
})
</script>

<template>
  <div class="space-y-6">
    <div class="grid gap-6 lg:grid-cols-2 lg:items-start">
      <Card>
        <CardContent class="p-4">
          <GraphExtractionJobSetsPanel
            :kg-id="kgId"
            :reload-nonce="jobSetsReloadNonce + (reloadNonce ?? 0)"
            embedded
            @saved="onJobSetsSaved"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader class="pb-2">
          <CardTitle class="text-base">Ontology Schema</CardTitle>
          <CardDescription>Live entity and relationship types with expandable instances.</CardDescription>
          <div class="flex gap-2 pt-2">
            <Button
              size="sm"
              :variant="selectedOntologyTab === 'entities' ? 'default' : 'outline'"
              @click="selectedOntologyTab = 'entities'"
            >
              Entities
            </Button>
            <Button
              size="sm"
              :variant="selectedOntologyTab === 'relationships' ? 'default' : 'outline'"
              @click="selectedOntologyTab = 'relationships'"
            >
              Relationships
            </Button>
          </div>
        </CardHeader>
        <CardContent class="max-h-[min(70dvh,720px)] overflow-y-auto">
          <GraphDesignEntitiesPanel
            v-if="selectedOntologyTab === 'entities'"
            :kg-id="kgId"
            :reload-nonce="reloadNonce ?? 0"
            embedded
          />
          <GraphDesignRelationshipsPanel
            v-else
            :kg-id="kgId"
            :reload-nonce="reloadNonce ?? 0"
            embedded
          />
        </CardContent>
      </Card>
    </div>

    <Card>
      <CardHeader>
        <CardTitle class="flex items-center gap-2 text-base">
          <Play class="size-4" />
          Run extraction
        </CardTitle>
        <CardDescription>
          Launch parallel extraction workers. Each worker processes one pending job at a time using the job set description.
        </CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="flex flex-wrap items-end gap-4">
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">Worker concurrency</label>
            <input
              v-model.number="workers"
              type="number"
              min="1"
              max="32"
              class="h-10 w-24 rounded-lg border bg-background px-3 text-sm"
            />
          </div>
          <div class="flex flex-wrap gap-2">
            <Button size="sm" :disabled="startingExtraction" @click="startExtraction">
              <Loader2 v-if="startingExtraction" class="mr-1.5 size-3.5 animate-spin" />
              Start
            </Button>
            <Button size="sm" variant="outline" :disabled="pausingExtraction" @click="pauseExtraction">
              Pause
            </Button>
            <Button size="sm" variant="destructive" :disabled="killingExtraction" @click="killExtraction">
              Kill
            </Button>
            <Button size="sm" variant="ghost" @click="refreshAll">
              <RefreshCw class="mr-1.5 size-3.5" />
              Refresh
            </Button>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <div class="rounded-lg border bg-muted/30 p-3">
            <p class="text-xs text-muted-foreground">Remaining jobs</p>
            <p class="text-lg font-semibold">{{ remainingJobsCount }}</p>
          </div>
          <div class="rounded-lg border bg-muted/30 p-3">
            <p class="text-xs text-muted-foreground">Materialized jobs</p>
            <p class="text-lg font-semibold">{{ materializedJobsTotal }}</p>
          </div>
          <div class="rounded-lg border bg-muted/30 p-3">
            <p class="text-xs text-muted-foreground">Planned (from job sets)</p>
            <p class="text-lg font-semibold">{{ plannedKnownTotalJobs || '—' }}</p>
          </div>
          <div class="rounded-lg border bg-muted/30 p-3">
            <p class="text-xs text-muted-foreground">Progress</p>
            <p class="text-lg font-semibold">{{ extractionProgressPercent }}%</p>
          </div>
        </div>

        <div v-if="plannedVsMaterializedMismatch" class="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-xs">
          <AlertCircle class="mt-0.5 size-4 shrink-0 text-amber-600" />
          <div>
            Planned job count ({{ plannedKnownTotalJobs }}) differs from materialized total ({{ materializedJobsTotal }}).
            Regenerate syncs pending jobs for enabled sets only; running jobs are left untouched.
            <Button size="sm" variant="link" class="h-auto p-0 text-xs" :disabled="regeneratingJobs" @click="regenerateJobs">
              Regenerate jobs
            </Button>
          </div>
        </div>

        <div class="rounded-lg border bg-card p-3">
          <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p class="text-xs font-medium text-foreground/90">Live extraction activity</p>
            <div class="flex flex-wrap items-center gap-1.5">
              <Badge variant="outline" class="font-mono text-[11px]">
                {{ completedJobsCount }} completed · {{ inProgressJobsCount }} running · {{ pendingJobsCount }} ready
              </Badge>
              <Badge variant="outline" class="font-mono text-[11px]">
                workers: {{ activeWorkerCount }}/{{ workerCount }}
              </Badge>
              <Badge v-if="idleWorkerCount > 0" variant="outline" class="font-mono text-[11px]">
                {{ idleWorkerCount }} idle
              </Badge>
              <Badge v-if="statusAgeSeconds !== null" variant="outline" class="font-mono text-[11px]">
                updated {{ statusAgeSeconds }}s ago
              </Badge>
            </div>
          </div>
          <div class="mb-3 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              class="h-full bg-primary/80 transition-all"
              :style="{ width: `${extractionProgressPercent}%` }"
            />
          </div>
          <div class="space-y-2">
            <div class="flex items-center justify-between gap-2">
              <p class="text-xs font-medium text-foreground/90">Recent job events</p>
              <Button
                variant="ghost"
                size="sm"
                class="h-7 px-2 text-[11px]"
                :disabled="recentJobs.length === 0"
                @click="clearRecentJobEvents"
              >
                Clear events
              </Button>
            </div>
            <div v-if="recentJobs.length === 0" class="text-xs text-muted-foreground">
              {{
                startingExtraction || showOptimisticLiveActivity
                  ? 'Starting extraction workers. Job events will appear as jobs are claimed and completed.'
                  : 'No job events yet.'
              }}
            </div>
            <div v-else class="max-h-80 space-y-1 overflow-y-auto pr-1">
              <div
                v-for="job in recentJobs"
                :key="`recent-${job.jobId}`"
                class="rounded-md border bg-muted/10 px-2 py-1.5"
              >
                <div class="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                  <div class="flex flex-wrap items-center gap-2">
                    <Badge :variant="recentJobBadgeVariant(job.status)" class="font-mono">{{ job.status }}</Badge>
                    <span class="font-medium text-foreground">{{ job.jobSet }}</span>
                    <span class="font-mono text-muted-foreground">{{ job.jobId }}</span>
                  </div>
                  <div class="flex flex-wrap items-center gap-2 text-muted-foreground">
                    <span v-if="job.workerId" class="font-mono">{{ job.workerId }}</span>
                    <span>{{ formatRecentWhen(job.startedAt, job.completedAt) }}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      class="h-6 px-2 text-[10px]"
                      @click="openWatch(job.jobId)"
                    >
                      <Eye class="mr-1 size-3" />
                      Watch
                    </Button>
                    <Button
                      v-if="canCancelJob(job.status)"
                      variant="ghost"
                      size="sm"
                      class="h-6 px-2 text-[10px] text-destructive hover:text-destructive"
                      :disabled="cancellingJobId === job.jobId"
                      @click="cancelJob(job.jobId)"
                    >
                      <Loader2 v-if="cancellingJobId === job.jobId" class="mr-1 size-3 animate-spin" />
                      <XCircle v-else class="mr-1 size-3" />
                      Cancel
                    </Button>
                  </div>
                </div>
                <div class="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                  <span class="font-mono">
                    tokens {{ formatCompactNumber(job.inputTokens) }} in / {{ formatCompactNumber(job.outputTokens) }} out
                  </span>
                  <span class="font-mono">
                    writes {{ job.writeOps }}
                    <template v-if="job.entitiesCreated || job.entitiesModified || job.relationshipsCreated">
                      ({{ job.entitiesCreated || 0 }}+{{ job.entitiesModified || 0 }}e / {{ job.relationshipsCreated || 0 }}r)
                    </template>
                  </span>
                  <span v-if="job.instanceCount" class="font-mono">{{ job.instanceCount }} instances</span>
                </div>
                <p
                  v-if="job.assistantPreview"
                  class="line-clamp-1 text-[10px] leading-snug text-muted-foreground"
                >
                  {{ job.assistantPreview }}
                </p>
                <p v-if="job.errorMessage" class="line-clamp-1 text-[10px] text-destructive">
                  {{ job.errorMessage }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    <GraphExtractionJobWatchDialog
      v-model:open="watchDialogOpen"
      :kg-id="kgId"
      :job-id="watchJobId"
    />

    <Card>
      <CardHeader>
        <CardTitle class="flex items-center gap-2 text-base">
          <ClipboardList class="size-4" />
          Job Status
          <Loader2 v-if="dbRefreshing" class="size-3.5 animate-spin text-muted-foreground" />
        </CardTitle>
        <CardDescription>Aggregate job metrics and maintenance actions.</CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <div v-if="dbLoading && !dbStatus" class="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading job status...
        </div>
        <div v-else-if="dbError && !dbStatus" class="text-sm text-destructive">{{ dbError }}</div>
        <template v-else-if="dbStatus">
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div class="rounded-lg border p-3 text-center">
              <p class="text-xs text-muted-foreground">Ready</p>
              <p class="text-xl font-semibold">{{ pendingJobsCount }}</p>
            </div>
            <div class="rounded-lg border p-3 text-center">
              <p class="text-xs text-muted-foreground">Running</p>
              <p class="text-xl font-semibold">{{ inProgressJobsCount }}</p>
            </div>
            <div class="rounded-lg border p-3 text-center">
              <p class="text-xs text-muted-foreground">Completed</p>
              <p class="text-xl font-semibold">{{ completedJobsCount }}</p>
            </div>
            <div class="rounded-lg border p-3 text-center">
              <p class="text-xs text-muted-foreground">Failed</p>
              <p class="text-xl font-semibold">{{ failedJobsCount }}</p>
            </div>
            <div class="rounded-lg border p-3 text-center">
              <p class="text-xs text-muted-foreground">Stale candidates</p>
              <p class="text-xl font-semibold">
                {{ extractionRunLive ? 0 : inProgressJobsCount }}
              </p>
            </div>
          </div>

          <Separator />

          <div class="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" :disabled="resettingRunning" @click="resetByKind('stale')">
              Reset Running
            </Button>
            <Button size="sm" variant="outline" :disabled="resettingCompleted" @click="resetByKind('completed')">
              Reset Completed
            </Button>
            <Button size="sm" variant="outline" :disabled="resettingFailed" @click="resetByKind('failed')">
              Reset Failed
            </Button>
            <Button size="sm" variant="outline" :disabled="resettingAll" @click="resetByKind('all')">
              Reset All Jobs
            </Button>
            <Button size="sm" variant="outline" :disabled="regeneratingJobs" @click="regenerateJobs">
              <Settings class="mr-1.5 size-3.5" />
              Regenerate jobs
            </Button>
          </div>

          <div v-if="dbStatus.jobsBySet && Object.keys(dbStatus.jobsBySet).length" class="space-y-2">
            <p class="text-xs font-medium text-muted-foreground">Per job set</p>
            <div class="grid gap-2 md:grid-cols-2">
              <div
                v-for="(stats, setName) in dbStatus.jobsBySet"
                :key="setName"
                class="rounded-lg border bg-muted/20 p-3 text-xs"
              >
                <p class="font-medium">{{ setName }}</p>
                <p class="text-muted-foreground">
                  ready {{ stats.pending }} · running {{ stats.in_progress }} · done {{ stats.completed }} · failed {{ stats.failed }}
                </p>
              </div>
            </div>
          </div>

          <div class="rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
            Run totals —
            input {{ dbStatus.totalInputTokens.toLocaleString() }} ·
            output {{ dbStatus.totalOutputTokens.toLocaleString() }} ·
            cost ${{ dbStatus.totalCostUsd.toFixed(4) }}
          </div>
        </template>
      </CardContent>
    </Card>
  </div>
</template>
