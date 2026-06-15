<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { toast } from 'vue-sonner'
import {
  Calendar,
  GitBranch,
  Loader2,
  Play,
  RefreshCw,
  Settings,
  ArrowRight,
} from 'lucide-vue-next'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { isMaintenanceReady } from '@/utils/kgManageWorkspace'
import { buildGraphManagementStepUrl } from '@/utils/kgGraphManagement'
import {
  commitStatusClass,
  formatFilesOnDisk,
  hasUnpulledCommits,
  needsIngestionPrepare,
  resolveIngestedHeadCommit,
  resolveRepoUrl,
  resolveTrackedBranch,
  shortCommitHash,
  unpulledCommitStatusLabel,
} from '@/utils/kgDataSourcesCommits'
import {
  cronToDailyTime,
  dailyTimeToCron,
  formatMaintenanceRunOutcome,
  maintenanceRunOutcomeVariant,
  MAINTENANCE_TIMEZONE_OPTIONS,
} from '@/utils/kgMaintenanceSchedule'

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

interface ExtractionJobSet {
  name: string
  strategy: string
  enabled?: boolean
  files_per_job?: number
  file_patterns?: string[]
  description?: string
  entity_type?: string
  instances_per_job?: number
}

interface MaintenanceSchedule {
  enabled: boolean
  cron_expression: string
  timezone_name: string
  next_run_at: string | null
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
}

const loading = ref(true)
const refreshing = ref(false)
const dataSources = ref<DataSourceRow[]>([])
const schedule = ref<MaintenanceSchedule | null>(null)
const runHistory = ref<MaintenanceRun[]>([])
const extractionRunState = ref<ExtractionRunState | null>(null)
const dbStatus = ref<DbStatus | null>(null)

const scheduleEnabled = ref(false)
const scheduleTime = ref('02:00')
const scheduleTimezone = ref('UTC')
const scheduleSaving = ref(false)

const workers = ref(8)
const filesPerJob = ref(2)
const checkingCommits = ref(false)
const updatingLocalCommits = ref(false)
const runningMaintenance = ref(false)
const startingExtraction = ref(false)

let refreshInterval: ReturnType<typeof setInterval> | null = null

const maintenanceReadySources = computed(() =>
  dataSources.value.filter((ds) => isMaintenanceReady(ds)),
)

const sourcesNeedingPrepare = computed(() =>
  dataSources.value.filter((ds) => needsIngestionPrepare(ds)),
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

const pendingJobsCount = computed(() => Number(dbStatus.value?.jobsByStatus?.pending || 0))
const inProgressJobsCount = computed(() => Number(dbStatus.value?.jobsByStatus?.in_progress || 0))
const extractionLive = computed(() =>
  Boolean(extractionRunState.value?.live || inProgressJobsCount.value > 0),
)

const extractionJobsUrl = computed(() =>
  buildGraphManagementStepUrl(props.kgId, 'extraction-jobs'),
)

function resolveApiError(e: unknown): string {
  const err = e as { data?: { detail?: unknown }; message?: string }
  const detail = err.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  return err.message || 'Request failed'
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
  scheduleEnabled.value = payload.enabled
  scheduleTimezone.value = payload.timezone_name || 'UTC'
  scheduleTime.value = cronToDailyTime(payload.cron_expression) || '02:00'
}

async function loadRunHistory() {
  const payload = await apiFetch<{ runs: MaintenanceRun[] }>(
    `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/maintenance-runs?limit=20`,
  )
  runHistory.value = payload.runs || []
}

async function loadExtractionState() {
  const base = `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs`
  try {
    extractionRunState.value = await apiFetch<ExtractionRunState>(`${base}/run-state`)
  } catch {
    extractionRunState.value = null
  }
  try {
    dbStatus.value = await apiFetch<DbStatus>(`${base}/database-status`)
  } catch {
    dbStatus.value = null
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
      loadRunHistory(),
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
    const unpulled = dataSources.value.filter((ds) => hasUnpulledCommits(ds))
    if (unpulled.length === 0) {
      toast.success('Up to date with remote branches')
    } else {
      toast.success(
        `${unpulled.length} source${unpulled.length === 1 ? '' : 's'} have unpulled commits`,
        { description: 'Compare baseline vs branch head in the table below.' },
      )
    }
  } catch (e: unknown) {
    toast.error('Failed to check for new commits', { description: resolveApiError(e) })
  } finally {
    checkingCommits.value = false
  }
}

async function getLatestCommitLocally() {
  const queue = sourcesNeedingPrepare.value
  if (queue.length === 0) {
    toast.message('Already up to date locally', {
      description: 'No sources need ingestion prepare. Run check for new commits first if unsure.',
    })
    return
  }
  updatingLocalCommits.value = true
  try {
    const results = await Promise.allSettled(
      queue.map((ds) =>
        apiFetch(`/management/data-sources/${ds.id}/sync`, {
          method: 'POST',
          body: { mode: 'ingest_only' },
        }),
      ),
    )
    const failures = results.filter((result) => result.status === 'rejected')
    await loadDataSources()
    if (failures.length === queue.length) {
      toast.error('Failed to update local commits', {
        description: resolveApiError(failures[0]?.status === 'rejected' ? failures[0].reason : null),
      })
      return
    }
    if (failures.length > 0) {
      toast.warning(
        `Started ${queue.length - failures.length} of ${queue.length} preparations`,
        { description: 'Some sources could not be queued.' },
      )
      return
    }
    toast.success(`Preparing ${queue.length} data source${queue.length === 1 ? '' : 's'}`)
  } catch (e: unknown) {
    toast.error('Failed to get latest commit locally', { description: resolveApiError(e) })
  } finally {
    updatingLocalCommits.value = false
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

async function applyFilesPerJobToJobSets() {
  const perJob = normalizedFilesPerJob.value
  const doc = await apiFetch<{ version?: string; job_sets: ExtractionJobSet[] }>(
    `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs`,
  )
  const hasByFiles = doc.job_sets.some((js) => js.strategy === 'by_files' && js.enabled !== false)
  if (!hasByFiles) return
  await apiFetch(
    `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs`,
    {
      method: 'PUT',
      body: {
        version: doc.version || '1.0',
        job_sets: doc.job_sets.map((js) =>
          js.strategy === 'by_files'
            ? { ...js, files_per_job: perJob }
            : js,
        ),
      },
    },
  )
}

async function runMaintenanceNow() {
  runningMaintenance.value = true
  try {
    const run = await apiFetch<MaintenanceRun>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/maintenance-runs/trigger`,
      { method: 'POST' },
    )
    toast.success('Maintenance run recorded', {
      description: run.message || formatMaintenanceRunOutcome(run.outcome),
    })
    await refreshAll({ background: true })
  } catch (e: unknown) {
    toast.error('Maintenance run failed', { description: resolveApiError(e) })
  } finally {
    runningMaintenance.value = false
  }
}

async function startExtractionJobs() {
  startingExtraction.value = true
  try {
    try {
      await applyFilesPerJobToJobSets()
    } catch (e: unknown) {
      toast.warning('Could not update files-per-job on job sets', {
        description: resolveApiError(e),
      })
    }
    const res = await apiFetch<{ message?: string }>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs/start`,
      {
        method: 'POST',
        body: { workers: Math.max(1, Math.floor(workers.value)) },
      },
    )
    toast.success('Extraction started', { description: res.message })
    await loadExtractionState()
  } catch (e: unknown) {
    toast.error('Failed to start extraction', { description: resolveApiError(e) })
  } finally {
    startingExtraction.value = false
  }
}

async function runMaintenancePipeline() {
  await runMaintenanceNow()
  if (maintenanceReadySources.value.length > 0) {
    await startExtractionJobs()
  }
}

function startAutoRefresh() {
  if (refreshInterval) return
  refreshInterval = setInterval(() => { void refreshAll({ background: true }) }, 3000)
}

function stopAutoRefresh() {
  if (!refreshInterval) return
  clearInterval(refreshInterval)
  refreshInterval = null
}

onMounted(async () => {
  await refreshAll()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <p class="text-sm text-muted-foreground">
          Schedule and run incremental maintenance: sync changed sources, then execute extraction jobs.
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
                Compare the last job baseline to the remote branch tip and review changed files since extraction.
              </CardDescription>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                :disabled="checkingCommits || updatingLocalCommits || dataSources.length === 0"
                @click="checkForNewCommits"
              >
                <Loader2 v-if="checkingCommits" class="mr-2 size-4 animate-spin" />
                <RefreshCw v-else class="mr-2 size-4" />
                Check for new commits
              </Button>
              <Button
                variant="outline"
                size="sm"
                :disabled="checkingCommits || updatingLocalCommits || dataSources.length === 0"
                @click="getLatestCommitLocally"
              >
                <Loader2 v-if="updatingLocalCommits" class="mr-2 size-4 animate-spin" />
                Get latest commit locally
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div
            v-if="dataSources.length === 0"
            class="rounded-md border border-dashed px-4 py-8 text-center text-sm text-muted-foreground"
          >
            Connect a data source before scheduling maintenance.
          </div>
          <div v-else class="overflow-x-auto rounded-md border">
            <table class="w-full min-w-[1100px] text-sm">
              <thead>
                <tr class="border-b bg-muted/50 text-left">
                  <th class="px-3 py-2 font-medium">Source</th>
                  <th class="px-3 py-2 font-medium">Branch</th>
                  <th class="px-3 py-2 font-medium">Branch HEAD</th>
                  <th class="px-3 py-2 text-right font-medium">Files on disk</th>
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
                  :class="isMaintenanceReady(ds) || hasUnpulledCommits(ds) ? 'bg-amber-50/40 dark:bg-amber-950/10' : ''"
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
                      :class="commitStatusClass(ds.tracked_branch_head_commit, resolveIngestedHeadCommit(ds))"
                      :title="ds.tracked_branch_head_commit || ''"
                    >
                      {{ shortCommitHash(ds.tracked_branch_head_commit) }}
                    </span>
                    <p class="mt-0.5 text-[10px] text-muted-foreground">
                      {{
                        unpulledCommitStatusLabel(
                          ds.newest_unpulled_commit,
                          ds.tracked_branch_head_commit,
                        )
                      }}
                    </p>
                  </td>
                  <td class="px-3 py-2 text-right tabular-nums text-muted-foreground">
                    {{ formatFilesOnDisk(ds) }}
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
                      :variant="isMaintenanceReady(ds) ? 'default' : hasUnpulledCommits(ds) ? 'outline' : 'secondary'"
                      class="text-xs"
                    >
                      {{
                        isMaintenanceReady(ds)
                          ? 'New files vs baseline'
                          : hasUnpulledCommits(ds)
                            ? 'Unpulled commits'
                            : 'Up to date'
                      }}
                    </Badge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="mt-3 text-xs text-muted-foreground">
            {{ maintenanceReadySources.length }} source(s) have commits ahead of the last job baseline ·
            {{ totalChangedFiles }} changed file(s) detected ·
            {{ sourcesNeedingPrepare.length }} need local prepare
          </p>
        </CardContent>
      </Card>

      <div class="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle class="flex items-center gap-2 text-base">
              <Play class="size-4 text-primary" />
              Run maintenance jobs
            </CardTitle>
            <CardDescription>
              Set files per job and worker concurrency, then run maintenance across all data sources.
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
                <label for="maintain-workers" class="text-sm font-medium">Parallel workers</label>
                <Input
                  id="maintain-workers"
                  v-model.number="workers"
                  type="number"
                  min="1"
                  max="32"
                />
              </div>
            </div>

            <div class="rounded-lg border bg-muted/20 p-3">
              <p class="text-xs font-medium text-foreground/90">Maintain run preview</p>
              <div class="mt-2 grid gap-2 sm:grid-cols-3">
                <div class="rounded-md border bg-background px-3 py-2">
                  <p class="text-[11px] uppercase tracking-wide text-muted-foreground">Changed files</p>
                  <p class="text-lg font-semibold tabular-nums">{{ totalChangedFiles }}</p>
                </div>
                <div class="rounded-md border bg-background px-3 py-2">
                  <p class="text-[11px] uppercase tracking-wide text-muted-foreground">Files per job</p>
                  <p class="text-lg font-semibold tabular-nums">{{ normalizedFilesPerJob }}</p>
                </div>
                <div class="rounded-md border bg-background px-3 py-2">
                  <p class="text-[11px] uppercase tracking-wide text-muted-foreground">Estimated jobs</p>
                  <p class="text-lg font-semibold tabular-nums">{{ estimatedJobsFromFiles }}</p>
                </div>
              </div>
              <p class="mt-2 text-xs text-muted-foreground">
                Extraction queue: {{ pendingJobsCount }} ready · {{ inProgressJobsCount }} running
                <span v-if="extractionLive"> · live</span>
              </p>
            </div>

            <div class="flex flex-wrap gap-2">
              <Button :disabled="runningMaintenance" @click="runMaintenanceNow">
                <Loader2 v-if="runningMaintenance" class="mr-2 size-4 animate-spin" />
                Sync changed sources
              </Button>
              <Button variant="secondary" :disabled="startingExtraction" @click="startExtractionJobs">
                <Loader2 v-if="startingExtraction" class="mr-2 size-4 animate-spin" />
                Start extraction jobs
              </Button>
              <Button
                variant="outline"
                :disabled="runningMaintenance || startingExtraction || maintenanceReadySources.length === 0"
                @click="runMaintenancePipeline"
              >
                Run full pipeline
              </Button>
            </div>

            <Button as-child variant="link" class="h-auto px-0 text-xs">
              <NuxtLink :to="extractionJobsUrl" class="inline-flex items-center gap-1">
                Configure job sets and monitor workers
                <ArrowRight class="size-3.5" />
              </NuxtLink>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle class="flex items-center gap-2 text-base">
              <Calendar class="size-4 text-primary" />
              Scheduled maintenance
            </CardTitle>
            <CardDescription>
              Daily cron schedule for automatic maintenance orchestration (sync changed sources).
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <label class="flex items-center gap-2 text-sm">
              <input v-model="scheduleEnabled" type="checkbox" class="size-4 rounded border" />
              Enable scheduled maintenance
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
          <CardTitle class="text-base">Maintenance run history</CardTitle>
          <CardDescription>Recent manual and scheduled maintenance orchestration attempts.</CardDescription>
        </CardHeader>
        <CardContent>
          <div v-if="runHistory.length === 0" class="text-sm text-muted-foreground">
            No maintenance runs recorded yet.
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="run in runHistory"
              :key="run.run_id"
              class="rounded-lg border p-3 text-sm"
            >
              <div class="flex flex-wrap items-center gap-2">
                <Badge :variant="maintenanceRunOutcomeVariant(run.outcome)" class="font-mono text-[11px]">
                  {{ formatMaintenanceRunOutcome(run.outcome) }}
                </Badge>
                <span class="font-mono text-xs text-muted-foreground">{{ formatWhen(run.triggered_at) }}</span>
                <span v-if="run.target_data_source_ids.length" class="text-xs text-muted-foreground">
                  · {{ run.target_data_source_ids.length }} source(s)
                </span>
              </div>
              <p v-if="run.message" class="mt-1 text-xs text-muted-foreground">{{ run.message }}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </template>
  </div>
</template>
