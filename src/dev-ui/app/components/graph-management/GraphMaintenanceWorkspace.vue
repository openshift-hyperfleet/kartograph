<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Archive,
  Calendar,
  CircleAlert,
  ClipboardList,
  Eye,
  GitBranch,
  Loader2,
  Play,
  RefreshCw,
  Settings,
  XCircle,
} from 'lucide-vue-next'
import GraphExtractionJobWatchDialog from '@/components/graph-management/GraphExtractionJobWatchDialog.vue'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'
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
import { isMaintenanceReady } from '@/utils/kgManageWorkspace'
import {
  commitStatusClass,
  resolveRepoUrl,
  resolveTrackedBranch,
  shortCommitHash,
} from '@/utils/kgDataSourcesCommits'
import {
  cronToDailyTime,
  dailyTimeToCron,
  formatMaintenanceRunOutcome,
  MAINTENANCE_TIMEZONE_OPTIONS,
} from '@/utils/kgMaintenanceSchedule'

const MAINTENANCE_JOB_SET = 'maintenance'

type RecentJobStatusFilter = 'all' | 'pending' | 'in_progress' | 'archived' | 'failed'

const RECENT_JOB_STATUS_FILTERS: Array<{ value: RecentJobStatusFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'archived', label: 'Archived' },
  { value: 'failed', label: 'Failed' },
]

const props = defineProps<{
  kgId: string
}>()

const { apiFetch } = useApiClient()

interface DiffSummary {
  total_changed_files: number
  added_count: number
  modified_count: number
  removed_count: number
  renamed_count: number
}

interface DataSourceRow {
  id: string
  name: string
  connection_config?: Record<string, string>
  last_extraction_baseline_commit?: string | null
  tracked_branch_head_commit?: string | null
  newest_unpulled_commit?: string | null
  clone_head_commit?: string | null
  last_prepared_commit?: string | null
  last_prepared_file_count?: number | null
  ingested_head_commit?: string | null
  job_package_available?: boolean | null
  diff_summary?: DiffSummary | null
}

interface MaintenanceSchedule {
  enabled: boolean
  cron_expression: string
  timezone_name: string
  next_run_at: string | null
  files_per_job?: number
  worker_count?: number
}

interface MaintenanceRun {
  run_id: string
  triggered_at: string
  outcome: string
  message: string | null
  target_data_source_ids: string[]
}

interface ExtractionRunState {
  live: boolean
  status: string
  workerCount: number
  pauseRequested: boolean
}

interface DbStatus {
  jobsByStatus: Record<string, number>
  jobsBySet?: Record<string, {
    pending: number
    in_progress: number
    completed: number
    failed: number
    archived?: number
    total: number
  }>
  recentJobs: Array<{
    jobId: string
    jobSet: string
    status: string
    workerId: string | null
    startedAt: string | null
    completedAt: string | null
    inputTokens: number
    outputTokens: number
    costUsd?: number
    writeOps: number
    entitiesCreated?: number
    entitiesModified?: number
    relationshipsCreated?: number
    errorMessage?: string | null
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

const loading = ref(true)
const refreshing = ref(false)
const dataSources = ref<DataSourceRow[]>([])
const schedule = ref<MaintenanceSchedule | null>(null)
const extractionRunState = ref<ExtractionRunState | null>(null)
const dbStatus = ref<DbStatus | null>(null)
const dbError = ref<string | null>(null)
const pausingExtraction = ref(false)
const killingExtraction = ref(false)
const resettingRunning = ref(false)
const resettingCompleted = ref(false)
const resettingFailed = ref(false)
const resettingAll = ref(false)
const archivingCompleted = ref(false)
const regeneratingJobs = ref(false)
const regenerateConfirmOpen = ref(false)
const optimisticLiveUntilMs = ref<number | null>(null)
const nowMs = ref(Date.now())
const lastStatusRefreshMs = ref<number | null>(null)
const recentJobEvents = ref<RecentJobEvent[]>([])
const recentJobStatusFilter = ref<RecentJobStatusFilter>('all')
const watchJobId = ref<string | null>(null)
const watchDialogOpen = ref(false)
const cancellingJobId = ref<string | null>(null)

const scheduleEnabled = ref(false)
const scheduleTime = ref('02:00')
const scheduleTimezone = ref('UTC')
const scheduleSaving = ref(false)

const MAX_MAINTENANCE_WORKERS = 50

const workers = ref(8)
const filesPerJob = ref(2)
const runControlsInitialized = ref(false)
const checkingCommits = ref(false)
const runningMaintenance = ref(false)

let refreshInterval: ReturnType<typeof setInterval> | null = null
let clockInterval: ReturnType<typeof setInterval> | null = null

const extractionJobsBasePath = computed(
  () => `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs`,
)

const maintenanceReadySources = computed(() =>
  dataSources.value.filter((ds) => isMaintenanceReady(ds)),
)

const totalChangedFiles = computed(() =>
  dataSources.value.reduce((sum, ds) => sum + (ds.diff_summary?.total_changed_files || 0), 0),
)

const normalizedFilesPerJob = computed(() =>
  Math.max(1, Math.floor(Number(filesPerJob.value || 1))),
)

const estimatedJobsFromFiles = computed(() => {
  const total = totalChangedFiles.value
  if (total <= 0) return 0
  return Math.ceil(total / normalizedFilesPerJob.value)
})

const workerCount = computed(() =>
  Math.min(MAX_MAINTENANCE_WORKERS, Math.max(1, Math.floor(Number(workers.value) || 1))),
)
const maintenanceSetStats = computed(
  () => dbStatus.value?.jobsBySet?.[MAINTENANCE_JOB_SET] ?? {
    pending: 0,
    in_progress: 0,
    completed: 0,
    failed: 0,
    archived: 0,
    total: 0,
  },
)
const pendingJobsCount = computed(() => maintenanceSetStats.value.pending)
const inProgressJobsCount = computed(() => maintenanceSetStats.value.in_progress)
const completedJobsCount = computed(() => maintenanceSetStats.value.completed)
const failedJobsCount = computed(() => maintenanceSetStats.value.failed)
const archivedJobsCount = computed(() => Number(maintenanceSetStats.value.archived || 0))
const readyJobsCount = computed(() => {
  if (pendingJobsCount.value > 0) return pendingJobsCount.value
  if (totalChangedFiles.value > 0 && estimatedJobsFromFiles.value > 0) {
    return estimatedJobsFromFiles.value
  }
  return 0
})
const readyJobsAreEstimated = computed(
  () => pendingJobsCount.value === 0 && readyJobsCount.value > 0,
)
const canRunReadyMaintenanceJobs = computed(
  () => pendingJobsCount.value > 0 || (inProgressJobsCount.value > 0 && !extractionRunLive.value),
)
const canQueueMaintenanceJobs = computed(
  () => maintenanceReadySources.value.length > 0 && inProgressJobsCount.value === 0,
)
const remainingJobsCount = computed(() => {
  const queued = pendingJobsCount.value + inProgressJobsCount.value
  if (queued > 0) return queued
  if (totalChangedFiles.value > 0 && estimatedJobsFromFiles.value > 0) {
    return estimatedJobsFromFiles.value
  }
  return 0
})
const activeQueueJobsTotal = computed(
  () => pendingJobsCount.value + inProgressJobsCount.value + failedJobsCount.value + completedJobsCount.value,
)
const showExtractionBaselineNotice = computed(
  () => maintenanceReadySources.value.length > 0 || activeQueueJobsTotal.value > 0,
)
const extractionBaselineNoticeDetail = computed(() => {
  const queued = pendingJobsCount.value + inProgressJobsCount.value + failedJobsCount.value
  if (queued > 0) {
    return (
      `${queued} job${queued === 1 ? '' : 's'} still need to finish `
      + '(ready, running, or failed). Resolve failures or reset them, then run ready jobs. '
      + 'Job Status tracks the queue; Regenerate jobs refreshes pending work from the table below.'
    )
  }
  if (completedJobsCount.value > 0 && maintenanceReadySources.value.length > 0) {
    return (
      `${completedJobsCount.value} job${completedJobsCount.value === 1 ? '' : 's'} completed but the baseline `
      + 'has not advanced yet — wait for reconciliation after the queue drains.'
    )
  }
  return (
    'After you queue maintenance, that column stays fixed until every job in the run succeeds. '
    + 'Use Check for new commits to refresh branch tips from GitHub before queueing or regenerating.'
  )
})
const extractionRunLive = computed(() => {
  if (optimisticLiveUntilMs.value && nowMs.value < optimisticLiveUntilMs.value) return true
  return Boolean(extractionRunState.value?.live)
})
const hasRunningJobs = computed(() => inProgressJobsCount.value > 0)
const extractionLive = computed(() => extractionRunLive.value || hasRunningJobs.value)
const maintenanceProgressPercent = computed(() => {
  const total = activeQueueJobsTotal.value
  if (total <= 0) return 0
  return Math.round(((completedJobsCount.value + failedJobsCount.value) / total) * 100)
})
const maintenanceRecentJobs = computed(() => {
  const maintenanceOnly = recentJobEvents.value.filter((event) => event.jobSet === MAINTENANCE_JOB_SET)
  if (recentJobStatusFilter.value === 'all') return maintenanceOnly
  return maintenanceOnly.filter((event) => event.status === recentJobStatusFilter.value)
})
const activeWorkerCount = computed(
  () => (dbStatus.value?.activeWorkers || []).filter((worker) => worker.jobSet === MAINTENANCE_JOB_SET).length,
)
const idleWorkerCount = computed(() => Math.max(0, workerCount.value - activeWorkerCount.value))
const statusAgeSeconds = computed(() => {
  if (!lastStatusRefreshMs.value) return null
  return Math.max(0, Math.floor((nowMs.value - lastStatusRefreshMs.value) / 1000))
})
const showOptimisticLiveActivity = computed(
  () => Boolean(optimisticLiveUntilMs.value && nowMs.value < optimisticLiveUntilMs.value),
)
const recentJobsEmptyMessage = computed(() => {
  if (runningMaintenance.value || showOptimisticLiveActivity.value) {
    return 'Starting maintenance workers. Job events will appear as jobs are claimed and completed.'
  }
  if (recentJobEvents.value.filter((event) => event.jobSet === MAINTENANCE_JOB_SET).length === 0) {
    return 'No maintenance job events yet. Queue maintenance jobs from changed sources, then run ready jobs to start workers.'
  }
  const filterLabel = RECENT_JOB_STATUS_FILTERS.find(
    (option) => option.value === recentJobStatusFilter.value,
  )?.label
  if (recentJobStatusFilter.value === 'all') return 'No maintenance job events yet.'
  return `No ${filterLabel?.toLowerCase() ?? recentJobStatusFilter.value} maintenance job events in the recent window.`
})
const maintenanceRunTotals = computed(() => {
  const jobs = (dbStatus.value?.recentJobs || []).filter((job) => job.jobSet === MAINTENANCE_JOB_SET)
  return {
    inputTokens: jobs.reduce((sum, job) => sum + Number(job.inputTokens || 0), 0),
    outputTokens: jobs.reduce((sum, job) => sum + Number(job.outputTokens || 0), 0),
    costUsd: jobs.reduce((sum, job) => sum + Number(job.costUsd || 0), 0),
  }
})

function resolveApiError(e: unknown): string {
  const err = e as { data?: { detail?: unknown }; message?: string }
  const detail = err.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  return err.message || 'Request failed'
}

function resolveRegenerateFailureMessage(description: string): { title: string; hint?: string } {
  const lower = description.toLowerCase()
  if (lower.includes('in progress') || lower.includes('still running') || lower.includes('running')) {
    return {
      title: 'Cannot regenerate maintenance jobs yet',
      hint: 'Wait for running jobs to finish, cancel them, or reset running jobs — then regenerate again.',
    }
  }
  if (lower.includes('ingest prepare')) {
    return {
      title: 'Sources need ingest prepare first',
      hint: 'Queue maintenance jobs to refresh JobPackages, then regenerate pending jobs.',
    }
  }
  return { title: 'Regenerate failed', hint: description }
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

async function loadDiffSummary(ds: DataSourceRow) {
  try {
    ds.diff_summary = await apiFetch<DiffSummary>(
      `/management/data-sources/${ds.id}/diff-summary`,
    )
  } catch {
    ds.diff_summary = null
  }
}

async function loadDataSources() {
  const sources = await apiFetch<DataSourceRow[]>(
    `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/data-sources`,
  )
  await Promise.all(sources.map((ds) => loadDiffSummary(ds)))
  dataSources.value = sources
}

async function loadSchedule() {
  const payload = await apiFetch<MaintenanceSchedule>(
    `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/maintenance-schedule`,
  )
  schedule.value = payload
  if (!runControlsInitialized.value) {
    scheduleEnabled.value = payload.enabled
    scheduleTimezone.value = payload.timezone_name || 'UTC'
    scheduleTime.value = cronToDailyTime(payload.cron_expression) || '02:00'
    if (payload.files_per_job) filesPerJob.value = payload.files_per_job
    if (payload.worker_count) workers.value = payload.worker_count
    runControlsInitialized.value = true
  }
}

async function loadExtractionState() {
  const base = extractionJobsBasePath.value
  try {
    extractionRunState.value = await apiFetch<ExtractionRunState>(`${base}/run-state`)
  } catch {
    extractionRunState.value = null
  }
  try {
    const status = await apiFetch<DbStatus>(`${base}/database-status`)
    dbStatus.value = status
    mergeRecentJobEvents(status)
    lastStatusRefreshMs.value = Date.now()
    dbError.value = null
  } catch (e: unknown) {
    dbStatus.value = null
    dbError.value = resolveApiError(e)
  }
}

function mergeRecentJobEvents(status: DbStatus) {
  const incoming = (status.recentJobs || []).filter((job) => job.jobSet === MAINTENANCE_JOB_SET)
  const now = Date.now()
  const activeWorkerJobIds = new Set(
    (status.activeWorkers || [])
      .filter((worker) => worker.jobSet === MAINTENANCE_JOB_SET)
      .map((worker) => worker.jobId),
  )
  const inProgressCount = Number(status.jobsBySet?.[MAINTENANCE_JOB_SET]?.in_progress || 0)
  const existingByJobId = new Map(
    recentJobEvents.value.map((event) => [event.jobId, event] as const),
  )
  for (const job of incoming) {
    existingByJobId.set(job.jobId, { ...job, eventKey: job.jobId, seenAtMs: now })
  }
  const maxAgeMs = 15 * 60 * 1000
  let merged = Array.from(existingByJobId.values()).filter((event) => now - event.seenAtMs <= maxAgeMs)
  if (inProgressCount === 0) {
    merged = merged.filter(
      (event) => event.status !== 'in_progress' || activeWorkerJobIds.has(event.jobId),
    )
  }
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
  if (status === 'archived') return 'secondary'
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

function canCancelJob(status: string): boolean {
  return status === 'pending' || status === 'in_progress'
}

async function pauseExtractionWorkers() {
  pausingExtraction.value = true
  try {
    const res = await apiFetch<{ message?: string }>(`${extractionJobsBasePath.value}/pause`, {
      method: 'POST',
    })
    toast.success('Pause requested', { description: res.message })
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Failed to pause workers', { description: resolveApiError(e) })
  } finally {
    pausingExtraction.value = false
  }
}

async function killExtractionWorkers() {
  killingExtraction.value = true
  try {
    const res = await apiFetch<{ message?: string }>(`${extractionJobsBasePath.value}/halt`, {
      method: 'POST',
    })
    toast.success('Workers stopped', { description: res.message })
    optimisticLiveUntilMs.value = null
    stopFastAutoRefresh()
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Failed to stop workers', { description: resolveApiError(e) })
  } finally {
    killingExtraction.value = false
  }
}

async function cancelJob(jobId: string) {
  cancellingJobId.value = jobId
  try {
    const res = await apiFetch<{ message?: string }>(
      `${extractionJobsBasePath.value}/jobs/${encodeURIComponent(jobId)}/cancel`,
      { method: 'POST' },
    )
    toast.success('Job cancelled', { description: res.message })
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Cancel failed', { description: resolveApiError(e) })
  } finally {
    cancellingJobId.value = null
  }
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
    const res = await apiFetch<{ message?: string; reset_count?: number; containers_stopped?: number }>(
      `${extractionJobsBasePath.value}/${map[kind].path}`,
      { method: 'POST' },
    )
    toast.success(kind === 'stale' ? 'Running jobs reset' : 'Jobs reset', {
      description: res.message || (res.reset_count !== undefined ? `${res.reset_count} job(s) reset` : undefined),
    })
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Reset failed', { description: resolveApiError(e) })
  } finally {
    map[kind].ref.value = false
  }
}

async function archiveCompletedJobs() {
  archivingCompleted.value = true
  try {
    const res = await apiFetch<{ message?: string; archived_count?: number }>(
      `${extractionJobsBasePath.value}/archive-completed`,
      { method: 'POST' },
    )
    toast.success('Completed jobs archived', {
      description: res.message || (res.archived_count !== undefined ? `${res.archived_count} job(s) archived` : undefined),
    })
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Archive failed', { description: resolveApiError(e) })
  } finally {
    archivingCompleted.value = false
  }
}

async function regenerateMaintenanceJobs() {
  regeneratingJobs.value = true
  try {
    const res = await apiFetch<{ generated_jobs?: number; message?: string }>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/maintenance-runs/regenerate-jobs`,
      {
        method: 'POST',
        body: { files_per_job: normalizedFilesPerJob.value },
      },
    )
    toast.success('Maintenance jobs synced', {
      description: res.message || `Synced ${res.generated_jobs ?? 0} pending job(s).`,
    })
    await refreshAll({ background: true })
  } catch (e: unknown) {
    const description = resolveApiError(e)
    const failure = resolveRegenerateFailureMessage(description)
    toast.error(failure.title, {
      description: failure.hint || description,
      duration: 10000,
    })
  } finally {
    regeneratingJobs.value = false
  }
}

async function refreshAll(options?: { background?: boolean }) {
  const background = options?.background ?? false
  if (background) refreshing.value = true
  else loading.value = true
  try {
    await Promise.all([
      loadDataSources(),
      loadSchedule(),
      loadExtractionState(),
    ])
  } catch (e: unknown) {
    if (!background) {
      toast.error('Failed to load maintenance workspace', { description: resolveApiError(e) })
    }
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function checkForNewCommits() {
  if (dataSources.value.length === 0) return
  checkingCommits.value = true
  try {
    await Promise.allSettled(
      dataSources.value.map((ds) =>
        apiFetch(`/management/data-sources/${ds.id}/commit-refs/refresh`, { method: 'POST' }),
      ),
    )
    await loadDataSources()
    const ready = maintenanceReadySources.value.length
    if (ready === 0) {
      toast.success('Branch tips refreshed', {
        description: 'No sources have commits ahead of the last extraction baseline.',
      })
    } else {
      toast.success(
        `${ready} source${ready === 1 ? '' : 's'} have new commits vs baseline`,
        { description: 'Queue or regenerate maintenance jobs when ready to process them.' },
      )
    }
  } catch (e: unknown) {
    toast.error('Failed to check for new commits', { description: resolveApiError(e) })
  } finally {
    checkingCommits.value = false
  }
}

async function saveSchedule() {
  const cron = dailyTimeToCron(scheduleTime.value)
  if (!cron) {
    toast.error('Invalid schedule time', { description: 'Use HH:MM in 24-hour format.' })
    return
  }
  scheduleSaving.value = true
  try {
    schedule.value = await apiFetch<MaintenanceSchedule>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/maintenance-schedule`,
      {
        method: 'PUT',
        body: {
          enabled: scheduleEnabled.value,
          cron_expression: cron,
          timezone_name: scheduleTimezone.value,
          files_per_job: normalizedFilesPerJob.value,
          worker_count: Math.min(
            MAX_MAINTENANCE_WORKERS,
            Math.max(1, Math.floor(Number(workers.value) || 1)),
          ),
        },
      },
    )
    toast.success('Maintenance schedule saved')
  } catch (e: unknown) {
    toast.error('Failed to save schedule', { description: resolveApiError(e) })
  } finally {
    scheduleSaving.value = false
  }
}

async function queueMaintenanceJobs() {
  optimisticLiveUntilMs.value = Date.now() + 30000
  await runMaintenanceNow({ startExtraction: true })
  startFastAutoRefresh()
}

async function runReadyMaintenanceJobs() {
  runningMaintenance.value = true
  const workerTotal = Math.min(
    MAX_MAINTENANCE_WORKERS,
    Math.max(1, Math.floor(Number(workers.value) || 1)),
  )
  try {
    const result = await apiFetch<{
      success: boolean
      message: string
      pending_jobs: number
      in_progress_jobs: number
      worker_count: number
    }>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/maintenance-runs/start-ready`,
      {
        method: 'POST',
        body: { worker_count: workerTotal },
      },
    )
    optimisticLiveUntilMs.value = Date.now() + 30000
    toast.success('Ready maintenance jobs started', { description: result.message })
    startFastAutoRefresh()
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Failed to run ready maintenance jobs', { description: resolveApiError(e) })
  } finally {
    runningMaintenance.value = false
  }
}

async function runMaintenanceNow(options?: { startExtraction?: boolean }) {
  runningMaintenance.value = true
  const workerTotal = Math.min(
    MAX_MAINTENANCE_WORKERS,
    Math.max(1, Math.floor(Number(workers.value) || 1)),
  )
  try {
    const run = await apiFetch<MaintenanceRun>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/maintenance-runs/trigger`,
      {
        method: 'POST',
        body: {
          files_per_job: normalizedFilesPerJob.value,
          worker_count: workerTotal,
          start_extraction: options?.startExtraction ?? false,
        },
      },
    )
    const description = run.message || formatMaintenanceRunOutcome(run.outcome)
    if (run.outcome === 'extraction-started') {
      toast.success('Maintenance started', { description })
    } else if (
      run.outcome === 'ingest-failed'
      || run.outcome === 'launch-failed'
      || run.outcome === 'preflight-failed'
    ) {
      toast.error('Maintenance failed', { description })
    } else if (run.outcome === 'no-changes') {
      toast.message('No maintenance work', { description })
    } else {
      toast.success('Maintenance run recorded', { description })
    }
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Maintenance run failed', { description: resolveApiError(e) })
  } finally {
    runningMaintenance.value = false
  }
}
function startAutoRefresh() {
  if (refreshInterval) return
  refreshInterval = setInterval(() => { void refreshAll({ background: true }) }, 3000)
}

function startFastAutoRefresh() {
  stopAutoRefresh()
  refreshInterval = setInterval(() => { void refreshAll({ background: true }) }, 1500)
}

function stopAutoRefresh() {
  if (!refreshInterval) return
  clearInterval(refreshInterval)
  refreshInterval = null
}

function stopFastAutoRefresh() {
  stopAutoRefresh()
  startAutoRefresh()
}

onMounted(async () => {
  await refreshAll()
  startAutoRefresh()
  clockInterval = setInterval(() => { nowMs.value = Date.now() }, 1000)
})

watch(
  () => extractionRunLive.value || hasRunningJobs.value,
  (active) => {
    if (active) startFastAutoRefresh()
    else if (!optimisticLiveUntilMs.value) stopFastAutoRefresh()
  },
  { immediate: true },
)

onUnmounted(() => {
  stopAutoRefresh()
  if (clockInterval) clearInterval(clockInterval)
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="max-w-3xl space-y-2">
        <p class="text-sm text-muted-foreground">
          Maintenance jobs keep your knowledge graph aligned with upstream repository changes.
          Each job is <span class="font-medium text-foreground">by-file</span>: changed files since
          the last extraction baseline are batched and processed so the graph reflects what is on
          disk for those paths.
        </p>
        <p class="text-sm text-muted-foreground">
          Run maintenance manually below when you are ready, or schedule recurring maintenance jobs
          to sync and extract on a daily cadence. Completed runs appear in Graph Writes History.
        </p>
      </div>
      <Button variant="outline" size="sm" :disabled="refreshing || loading" @click="refreshAll({ background: true })">
        <Loader2 v-if="refreshing" class="mr-2 size-4 animate-spin" />
        <RefreshCw v-else class="mr-2 size-4" />
        Refresh
      </Button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-16">
      <Loader2 class="size-8 animate-spin text-muted-foreground" />
    </div>

    <template v-else>
      <Card>
        <CardHeader class="pb-2">
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle class="flex items-center gap-2 text-base">
                <GitBranch class="size-4 text-primary" />
                New Files to Process
              </CardTitle>
              <CardDescription class="mt-1">
                Compare commit during last extraction to branch HEAD. Check for new commits refreshes
                tips from GitHub; queue and regenerate use these stored refs and prepare sources as needed.
              </CardDescription>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                :disabled="checkingCommits || dataSources.length === 0"
                @click="checkForNewCommits"
              >
                <Loader2 v-if="checkingCommits" class="mr-2 size-4 animate-spin" />
                <RefreshCw v-else class="mr-2 size-4" />
                Check for new commits
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Alert
            v-if="showExtractionBaselineNotice"
            variant="warning"
            class="mb-4"
          >
            <CircleAlert class="size-4" />
            <AlertDescription>
              <span class="font-medium">Commit during last extraction</span>
              does not update until every maintenance job in the current run completes successfully
              with no failed jobs remaining.
              {{ extractionBaselineNoticeDetail }}
            </AlertDescription>
          </Alert>
          <div
            v-if="dataSources.length === 0"
            class="rounded-md border border-dashed px-4 py-8 text-center text-sm text-muted-foreground"
          >
            Connect a data source before scheduling maintenance.
          </div>
          <div v-else class="overflow-x-auto rounded-md border">
            <table class="w-full min-w-[900px] text-sm">
              <thead>
                <tr class="border-b bg-muted/50 text-left">
                  <th class="px-3 py-2 font-medium">Source</th>
                  <th class="px-3 py-2 font-medium">Branch</th>
                  <th class="px-3 py-2 font-medium">Branch HEAD</th>
                  <th class="px-3 py-2 font-medium">Commit during last extraction</th>
                  <th class="px-3 py-2 text-right font-medium">Changed files</th>
                  <th class="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="ds in dataSources"
                  :key="ds.id"
                  class="border-b border-border/60 align-top last:border-0"
                  :class="isMaintenanceReady(ds) ? 'bg-amber-50/40 dark:bg-amber-950/10' : ''"
                >
                  <td class="px-3 py-2">
                    <p class="font-medium">{{ ds.name }}</p>
                    <p class="mt-0.5 max-w-[18rem] truncate font-mono text-xs text-muted-foreground">
                      {{ resolveRepoUrl(ds.connection_config) }}
                    </p>
                  </td>
                  <td class="px-3 py-2 font-mono text-xs">{{ resolveTrackedBranch(ds.connection_config) }}</td>
                  <td class="px-3 py-2 font-mono text-xs">
                    <span
                      :class="commitStatusClass(ds.tracked_branch_head_commit, ds.last_extraction_baseline_commit)"
                      :title="ds.tracked_branch_head_commit || ''"
                    >
                      {{ shortCommitHash(ds.tracked_branch_head_commit) }}
                    </span>
                  </td>
                  <td class="px-3 py-2 font-mono text-xs">
                    <span
                      :class="commitStatusClass(ds.last_extraction_baseline_commit, ds.tracked_branch_head_commit)"
                      :title="ds.last_extraction_baseline_commit || ''"
                    >
                      {{ shortCommitHash(ds.last_extraction_baseline_commit) }}
                    </span>
                  </td>
                  <td class="px-3 py-2 text-right tabular-nums">
                    {{ ds.diff_summary?.total_changed_files ?? '—' }}
                  </td>
                  <td class="px-3 py-2">
                    <Badge
                      :variant="isMaintenanceReady(ds) ? 'default' : 'secondary'"
                      class="text-xs"
                    >
                      {{ isMaintenanceReady(ds) ? 'New commits vs baseline' : 'Up to date' }}
                    </Badge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="mt-3 text-xs text-muted-foreground">
            {{ maintenanceReadySources.length }} source(s) have commits ahead of the last job baseline ·
            {{ totalChangedFiles }} changed file(s) detected
          </p>
        </CardContent>
      </Card>

      <div class="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle class="flex items-center gap-2 text-base">
              <Play class="size-4 text-primary" />
              Maintenance jobs
            </CardTitle>
            <CardDescription>
              Queue by-file jobs from changed sources, then run ready jobs to start workers.
              Per-job results appear in Graph Writes History.
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1.5">
                <label for="maintain-files-per-job" class="text-sm font-medium">Files per job</label>
                <Input
                  id="maintain-files-per-job"
                  v-model.number="filesPerJob"
                  type="number"
                  min="1"
                />
              </div>
              <div class="space-y-1.5">
                <label for="maintain-workers" class="text-sm font-medium">Worker concurrency</label>
                <Input
                  id="maintain-workers"
                  v-model.number="workers"
                  type="number"
                  min="1"
                />
              </div>
            </div>

            <div class="rounded-lg border bg-muted/20 p-3">
              <p class="text-xs font-medium text-foreground/90">Run preview</p>
              <div class="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <div class="rounded-md border bg-background px-3 py-2">
                  <p class="text-[11px] uppercase tracking-wide text-muted-foreground">Changed files</p>
                  <p class="text-lg font-semibold tabular-nums">{{ totalChangedFiles }}</p>
                </div>
                <div class="rounded-md border bg-background px-3 py-2">
                  <p class="text-[11px] uppercase tracking-wide text-muted-foreground">Estimated jobs</p>
                  <p class="text-lg font-semibold tabular-nums">{{ estimatedJobsFromFiles }}</p>
                </div>
                <div class="rounded-md border bg-background px-3 py-2">
                  <p class="text-[11px] uppercase tracking-wide text-muted-foreground">Remaining jobs</p>
                  <p class="text-lg font-semibold tabular-nums">{{ remainingJobsCount }}</p>
                </div>
              </div>
              <p class="mt-2 text-xs text-muted-foreground">
                Maintenance queue: {{ readyJobsCount }} ready
                <span v-if="readyJobsAreEstimated"> (estimated)</span>
                · {{ inProgressJobsCount }} running
                <span v-if="extractionLive"> · live</span>
              </p>
            </div>

            <div class="flex flex-wrap items-end gap-2">
              <Button
                variant="outline"
                :disabled="runningMaintenance || !canQueueMaintenanceJobs"
                @click="queueMaintenanceJobs"
              >
                <Loader2 v-if="runningMaintenance" class="mr-2 size-4 animate-spin" />
                Queue maintenance jobs
              </Button>
              <Button
                :disabled="runningMaintenance || !canRunReadyMaintenanceJobs"
                @click="runReadyMaintenanceJobs"
              >
                Run ready maintenance jobs
              </Button>
              <Button size="sm" variant="outline" :disabled="pausingExtraction" @click="pauseExtractionWorkers">
                Pause
              </Button>
              <Button size="sm" variant="destructive" :disabled="killingExtraction" @click="killExtractionWorkers">
                Kill
              </Button>
            </div>

            <div class="grid gap-3 sm:grid-cols-2 text-sm">
              <div class="rounded-lg border bg-muted/30 p-3">
                <p class="text-xs text-muted-foreground">Remaining maintenance jobs</p>
                <p class="text-lg font-semibold">{{ remainingJobsCount }}</p>
              </div>
              <div class="rounded-lg border bg-muted/30 p-3">
                <p class="text-xs text-muted-foreground">Progress</p>
                <p class="text-lg font-semibold">{{ maintenanceProgressPercent }}%</p>
              </div>
            </div>

            <div class="rounded-lg border bg-card p-3">
              <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p class="text-xs font-medium text-foreground/90">Live maintenance activity</p>
                <div class="flex flex-wrap items-center gap-1.5">
                  <Badge variant="outline" class="font-mono text-[11px]">
                    {{ completedJobsCount }} completed · {{ inProgressJobsCount }} running · {{ readyJobsCount }} ready
                    <span v-if="readyJobsAreEstimated"> (est.)</span>
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
                  :style="{ width: `${maintenanceProgressPercent}%` }"
                />
              </div>
              <div class="space-y-2">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-xs font-medium text-foreground/90">Recent maintenance jobs</p>
                    <div class="flex flex-wrap gap-1">
                      <Button
                        v-for="option in RECENT_JOB_STATUS_FILTERS"
                        :key="option.value"
                        variant="ghost"
                        size="sm"
                        class="h-7 px-2 text-[11px]"
                        :class="recentJobStatusFilter === option.value ? 'bg-muted text-foreground' : 'text-muted-foreground'"
                        @click="recentJobStatusFilter = option.value"
                      >
                        {{ option.label }}
                      </Button>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-7 px-2 text-[11px]"
                    :disabled="maintenanceRecentJobs.length === 0"
                    @click="clearRecentJobEvents"
                  >
                    Clear events
                  </Button>
                </div>
                <div v-if="maintenanceRecentJobs.length === 0" class="text-xs text-muted-foreground">
                  {{ recentJobsEmptyMessage }}
                </div>
                <div v-else class="max-h-64 space-y-1 overflow-y-auto pr-1">
                  <div
                    v-for="job in maintenanceRecentJobs"
                    :key="`recent-${job.jobId}`"
                    class="rounded-md border bg-muted/10 px-2 py-1.5"
                  >
                    <div class="flex flex-wrap items-center justify-between gap-2 text-[11px]">
                      <div class="flex flex-wrap items-center gap-2">
                        <Badge :variant="recentJobBadgeVariant(job.status)" class="font-mono">{{ job.status }}</Badge>
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
                      <span class="font-mono">writes {{ job.writeOps }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle class="flex items-center gap-2 text-base">
              <Calendar class="size-4 text-primary" />
              Schedule recurring maintenance jobs
            </CardTitle>
            <CardDescription>
              Each scheduled run checks for new commits, rebuilds the pending maintenance job set,
              and starts workers on ready jobs. Failed jobs in Job Status block scheduled runs
              until you reset or fix them manually.
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <label class="flex items-center gap-2 text-sm">
              <input v-model="scheduleEnabled" type="checkbox" class="size-4 rounded border" />
              Enable recurring maintenance schedule
            </label>

            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1.5">
                <label for="schedule-time" class="text-sm font-medium">Daily time (HH:MM)</label>
                <Input id="schedule-time" v-model="scheduleTime" placeholder="02:00" />
              </div>
              <div class="space-y-1.5">
                <label for="schedule-tz" class="text-sm font-medium">Timezone</label>
                <select
                  id="schedule-tz"
                  v-model="scheduleTimezone"
                  class="flex h-9 w-full rounded-md border bg-background px-3 text-sm"
                >
                  <option
                    v-for="tz in MAINTENANCE_TIMEZONE_OPTIONS"
                    :key="tz.value"
                    :value="tz.value"
                  >
                    {{ tz.label }}
                  </option>
                </select>
              </div>
            </div>

            <div class="rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
              <p v-if="failedJobsCount > 0" class="mb-2 font-medium text-destructive">
                Scheduled maintenance is blocked while {{ failedJobsCount }} failed job(s) remain.
                Reset failed jobs in Job Status before the next run can proceed.
              </p>
              <p v-if="schedule?.next_run_at">
                Next scheduled run: {{ formatWhen(schedule.next_run_at) }}
              </p>
              <p v-else-if="scheduleEnabled">Next run will be computed after saving.</p>
              <p v-else>Scheduling is disabled.</p>
            </div>

            <Button variant="outline" class="w-full" :disabled="scheduleSaving" @click="saveSchedule">
              <Loader2 v-if="scheduleSaving" class="mr-2 size-4 animate-spin" />
              <Settings v-else class="mr-2 size-4" />
              Save maintenance schedule
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <ClipboardList class="size-4" />
            Job Status
            <Loader2 v-if="refreshing" class="size-3.5 animate-spin text-muted-foreground" />
          </CardTitle>
          <CardDescription>Maintenance job metrics and queue maintenance actions.</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div v-if="loading && !dbStatus" class="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />
            Loading job status...
          </div>
          <div v-else-if="dbError && !dbStatus" class="text-sm text-destructive">{{ dbError }}</div>
          <template v-else-if="dbStatus">
            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <div class="rounded-lg border p-3 text-center">
                <p class="text-xs text-muted-foreground">
                  Ready
                  <span v-if="readyJobsAreEstimated" class="block text-[10px] normal-case">(estimated)</span>
                </p>
                <p class="text-xl font-semibold">{{ readyJobsCount }}</p>
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
                <p class="text-xs text-muted-foreground">Archived</p>
                <p class="text-xl font-semibold">{{ archivedJobsCount }}</p>
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
              <Button
                size="sm"
                variant="outline"
                :disabled="archivingCompleted || completedJobsCount === 0"
                @click="archiveCompletedJobs"
              >
                <Archive class="mr-1.5 size-3.5" />
                Archive Completed
              </Button>
              <Button size="sm" variant="outline" :disabled="resettingFailed" @click="resetByKind('failed')">
                Reset Failed
              </Button>
              <Button size="sm" variant="outline" :disabled="resettingAll" @click="resetByKind('all')">
                Reset All Jobs
              </Button>
              <Button
                size="sm"
                variant="destructive"
                :disabled="regeneratingJobs"
                @click="regenerateConfirmOpen = true"
              >
                <Settings class="mr-1.5 size-3.5" />
                Regenerate jobs
              </Button>
            </div>

            <div class="rounded-lg border bg-muted/20 p-3 text-xs">
              <p class="font-medium">{{ MAINTENANCE_JOB_SET }}</p>
              <p class="text-muted-foreground">
                ready {{ readyJobsCount }}<span v-if="readyJobsAreEstimated"> (estimated)</span>
                · running {{ inProgressJobsCount }} · done {{ completedJobsCount }} · failed {{ failedJobsCount }} · archived {{ archivedJobsCount }}
              </p>
            </div>

            <div class="rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
              Run totals (recent maintenance jobs) —
              input {{ maintenanceRunTotals.inputTokens.toLocaleString() }} ·
              output {{ maintenanceRunTotals.outputTokens.toLocaleString() }} ·
              cost ${{ maintenanceRunTotals.costUsd.toFixed(4) }}
            </div>
          </template>
        </CardContent>
      </Card>

      <GraphExtractionJobWatchDialog
        v-model:open="watchDialogOpen"
        :kg-id="kgId"
        :job-id="watchJobId"
      />

      <AlertDialog v-model:open="regenerateConfirmOpen">
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Regenerate maintenance jobs?</AlertDialogTitle>
            <AlertDialogDescription class="space-y-2 text-left">
              <p>
                This replaces the entire <span class="font-medium text-foreground">Ready</span>
                queue with a freshly materialized maintenance job set from the current diffs.
              </p>
              <p>
                All pending jobs are wiped. Running jobs must finish or be reset first — regenerate
                is blocked while workers are active.
              </p>
              <p>
                If some jobs already completed, regenerating can create
                <span class="font-medium text-destructive">duplicate work</span>
                on the same files until you archive completed jobs and the extraction baseline advances.
              </p>
              <p class="font-medium text-destructive">
                Only continue when you intend to discard the current pending queue and start over.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              class="bg-destructive text-white hover:bg-destructive/90"
              :disabled="regeneratingJobs"
              @click="regenerateMaintenanceJobs"
            >
              <Loader2 v-if="regeneratingJobs" class="mr-2 size-4 animate-spin" />
              Regenerate jobs
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </template>
  </div>
</template>
