<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import {
  Cable,
  ChevronLeft,
  GitBranch,
  Plus,
  Trash2,
  Loader2,
  Check,
  ArrowRight,
  Settings,
  RefreshCw,
  ScrollText,
  Building2,
  LayoutDashboard,
} from 'lucide-vue-next'
import {
  buildKgDataSourcesNewUrl,
  buildKgManageUrl,
  parseKgDataSourcesFocusQuery,
} from '@/utils/kgDataSourcesNavigation'
import { isMaintenanceReady } from '@/utils/kgManageWorkspace'
import {
  hasAnyActiveSync,
  isActiveSyncStatus,
  isSyncTerminal,
  latestSyncRun,
  type SyncRunStatus,
} from '@/utils/kgDataSourcesSync'
import {
  formatPreparedFileCount,
  commitStatusClass,
  commitStatusLabel,
  hasUnpulledCommits,
  isIngestionPreparedAtHead,
  needsIngestionPrepare,
  resolveBranchTipCommit,
  resolveIngestedHeadCommit,
  resolveNewestUnpulledCommit,
  unpulledCommitStatusLabel,
  prepStatusBadgeVariant,
  resolvePrepStatusLabel,
  resolveRepoUrl,
  resolveTrackedBranch,
  shortCommitHash,
} from '@/utils/kgDataSourcesCommits'
import {
  buildDataSourceCreationBody,
  buildDataSourceCreationUrl,
  detectAdapterFromUrl,
  inferNameFromRepoUrl,
} from '@/utils/dataSourceWizard'
import SyncPhaseIndicator from '@/components/graph/SyncPhaseIndicator.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
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

interface SyncRun {
  id: string
  status: SyncRunStatus
  started_at: string
  completed_at: string | null
  error: string | null
}

interface DiffChangedFile {
  path: string
  status: string
}

interface DataSourceDiffSummary {
  total_changed_files: number
  added_count: number
  modified_count: number
  removed_count: number
  renamed_count: number
  files_truncated: boolean
  changed_files: DiffChangedFile[]
}

interface DataSourceItem {
  id: string
  name: string
  adapter_type: string
  knowledge_graph_id: string
  connection_config?: Record<string, string>
  last_extraction_baseline_commit?: string | null
  tracked_branch_head_commit?: string | null
  last_prepared_commit?: string | null
  last_prepared_file_count?: number | null
  ingested_head_commit?: string | null
  newest_unpulled_commit?: string | null
  clone_head_commit?: string | null
  sync_runs?: SyncRun[]
  diff_summary?: DataSourceDiffSummary | null
}

const route = useRoute()
const kgId = computed(() => route.params.kgId as string)
const maintainFocus = computed(() => parseKgDataSourcesFocusQuery(route.query.focus) === 'maintain')

const { hasTenant, tenantVersion } = useTenant()
const { apiFetch } = useApiClient()

const kgName = ref('')
const dataSources = ref<DataSourceItem[]>([])
const loading = ref(false)
const expandedDiffLists = ref<Record<string, boolean>>({})
const checkingAllCommits = ref(false)
const preparingAll = ref(false)

const newUrls = ref<string[]>([''])
const addToken = ref('')
const addingUrls = ref(false)

const manageUrl = computed(() => buildKgManageUrl(kgId.value))
const newSourceUrl = computed(() => buildKgDataSourcesNewUrl(kgId.value))
const graphManagementUrl = computed(
  () => `${buildKgManageUrl(kgId.value)}?step=graph-management`,
)

const visibleDataSources = computed(() => {
  if (!maintainFocus.value) return dataSources.value
  return dataSources.value.filter((ds) => isMaintenanceReady(ds))
})

const validNewUrls = computed(() =>
  newUrls.value
    .map((url) => url.trim())
    .filter((url) => url.startsWith('http://') || url.startsWith('https://') || url.startsWith('git@')),
)

const preparedCount = computed(() =>
  dataSources.value.filter((ds) => isIngestionPreparedAtHead(ds)).length,
)

const sourcesNeedingPrepare = computed(() =>
  visibleDataSources.value.filter(
    (ds) => needsIngestionPrepare(ds) && !isActiveSyncStatus(latestStatus(ds)),
  ),
)

const canBulkPrepare = computed(
  () =>
    sourcesNeedingPrepare.value.length > 0
    && !preparingAll.value
    && !hasAnyActiveSync(dataSources.value),
)

const allSourcesPrepared = computed(
  () =>
    dataSources.value.length > 0
    && preparedCount.value === dataSources.value.length,
)

const pollInterval = ref<ReturnType<typeof setInterval> | null>(null)

function stopPolling() {
  if (pollInterval.value !== null) {
    clearInterval(pollInterval.value)
    pollInterval.value = null
  }
}

function startPolling() {
  if (pollInterval.value !== null) return
  pollInterval.value = setInterval(async () => {
    await loadDataSources()
    if (!hasAnyActiveSync(dataSources.value)) {
      stopPolling()
    }
  }, 3000)
}

function addUrlField() {
  newUrls.value.push('')
}

function removeUrlField(index: number) {
  newUrls.value.splice(index, 1)
  if (newUrls.value.length === 0) {
    newUrls.value.push('')
  }
}

function updateUrl(index: number, value: string) {
  newUrls.value[index] = value
}

async function detectDefaultBranch(url: string): Promise<string> {
  try {
    const parsed = new URL(url)
    const [owner, repoRaw] = parsed.pathname.split('/').filter(Boolean)
    const repo = repoRaw?.replace(/\.git$/, '')
    if (!owner || !repo) return 'main'
    const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`)
    if (!response.ok) return 'main'
    const payload = (await response.json()) as { default_branch?: string }
    return payload.default_branch ?? 'main'
  } catch {
    return 'main'
  }
}

async function addRepositories() {
  if (validNewUrls.value.length === 0) {
    toast.error('Please enter at least one valid URL')
    return
  }

  addingUrls.value = true
  const seen = new Set<string>()
  let added = 0

  try {
    for (const url of validNewUrls.value) {
      if (seen.has(url)) continue
      seen.add(url)

      const adapterId = detectAdapterFromUrl(url)
      if (adapterId !== 'github') {
        toast.error('Unsupported repository URL', { description: url })
        continue
      }

      const branch = await detectDefaultBranch(url)
      const name = inferNameFromRepoUrl(url) || 'repository'

      try {
        await apiFetch(buildDataSourceCreationUrl(kgId.value), {
          method: 'POST',
          body: buildDataSourceCreationBody({
            name,
            adapter_type: 'github',
            connection_config: {
              repo_url: url,
              branch,
            },
            credentials: addToken.value.trim()
              ? { access_token: addToken.value.trim() }
              : undefined,
          }),
        })
        added += 1
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to add source'
        toast.error(`Failed to add ${url}`, { description: msg })
      }
    }

    if (added > 0) {
      newUrls.value = ['']
      addToken.value = ''
      toast.success(`Added ${added} source${added === 1 ? '' : 's'}`, {
        description: 'Check for new commits or prepare ingestion context when ready.',
      })
      await loadDataSources()
    }
  } finally {
    addingUrls.value = false
  }
}

async function loadKnowledgeGraph() {
  try {
    const result = await apiFetch<{ name: string }>(
      `/management/knowledge-graphs/${kgId.value}`,
    )
    kgName.value = result.name ?? kgId.value
  } catch {
    kgName.value = kgId.value
  }
}

async function loadDataSources() {
  if (!hasTenant.value) return
  loading.value = true
  try {
    const sources = await apiFetch<DataSourceItem[]>(
      `/management/knowledge-graphs/${kgId.value}/data-sources`,
    )
    for (const ds of sources) {
      try {
        ds.sync_runs = await apiFetch<SyncRun[]>(
          `/management/data-sources/${ds.id}/sync-runs`,
        )
      } catch {
        ds.sync_runs = []
      }
      try {
        ds.diff_summary = await apiFetch<DataSourceDiffSummary>(
          `/management/data-sources/${ds.id}/diff-summary`,
        )
      } catch {
        ds.diff_summary = null
      }
    }
    dataSources.value = sources
  } catch {
    dataSources.value = []
  } finally {
    loading.value = false
  }
}

async function ensureEntryRoute() {
  await loadDataSources()
  if (dataSources.value.length === 0) {
    await navigateTo(newSourceUrl.value, { replace: true })
    return
  }
  if (hasAnyActiveSync(dataSources.value)) {
    startPolling()
  }
}

function latestStatus(ds: DataSourceItem): SyncRunStatus | undefined {
  return latestSyncRun(ds.sync_runs)?.status
}

function isDiffExpanded(dsId: string): boolean {
  return expandedDiffLists.value[dsId] === true
}

function toggleDiffExpanded(dsId: string) {
  expandedDiffLists.value[dsId] = !isDiffExpanded(dsId)
}

async function checkAllCommitRefs() {
  if (visibleDataSources.value.length === 0) return
  checkingAllCommits.value = true
  try {
    await Promise.allSettled(
      visibleDataSources.value.map((ds) =>
        apiFetch(`/management/data-sources/${ds.id}/commit-refs/refresh`, { method: 'POST' }),
      ),
    )
    await loadDataSources()
    const unpulled = visibleDataSources.value.filter((ds) => hasUnpulledCommits(ds))
    if (unpulled.length === 0) {
      toast.success('Up to date with remote branches')
    } else {
      toast.success(
        `${unpulled.length} source${unpulled.length === 1 ? '' : 's'} have unpulled commits`,
        {
          description: 'Newest unpulled commit is shown in the table.',
        },
      )
    }
  } catch {
    toast.error('Failed to check for new commits')
  } finally {
    checkingAllCommits.value = false
  }
}

async function prepareAllDataSources() {
  const queue = sourcesNeedingPrepare.value
  if (queue.length === 0) {
    toast.error('No data sources need preparation')
    return
  }

  preparingAll.value = true
  try {
    await Promise.allSettled(
      queue.map((ds) =>
        apiFetch(`/management/data-sources/${ds.id}/sync`, {
          method: 'POST',
          body: { mode: 'ingest_only' },
        }),
      ),
    )
    toast.success(`Preparing ${queue.length} data source${queue.length === 1 ? '' : 's'}`)
    await loadDataSources()
    if (hasAnyActiveSync(dataSources.value)) startPolling()
  } catch {
    toast.error('Failed to start preparation')
  } finally {
    preparingAll.value = false
  }
}

// Edit config sheet
const editConfigOpen = ref(false)
const editConfigDs = ref<DataSourceItem | null>(null)
const editConfigName = ref('')
const editConfigToken = ref('')
const editConfigNameError = ref('')
const savingConfig = ref(false)

function openEditConfig(ds: DataSourceItem) {
  editConfigDs.value = ds
  editConfigName.value = ds.name
  editConfigToken.value = ''
  editConfigNameError.value = ''
  editConfigOpen.value = true
}

async function handleEditConfig() {
  if (!editConfigName.value.trim()) {
    editConfigNameError.value = 'Data source name is required'
    return
  }
  savingConfig.value = true
  try {
    const body: Record<string, unknown> = { name: editConfigName.value.trim() }
    if (editConfigToken.value.trim()) {
      body.credentials = { access_token: editConfigToken.value.trim() }
    }
    await apiFetch(`/management/data-sources/${editConfigDs.value!.id}`, {
      method: 'PATCH',
      body,
    })
    toast.success('Data source updated')
    editConfigOpen.value = false
    await loadDataSources()
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to update'
    toast.error('Failed to update data source', { description: msg })
  } finally {
    savingConfig.value = false
  }
}

// Delete
const deleteDsOpen = ref(false)
const deletingDs = ref<DataSourceItem | null>(null)
const deletingDsFlag = ref(false)

function openDeleteDs(ds: DataSourceItem) {
  deletingDs.value = ds
  deleteDsOpen.value = true
}

async function handleDeleteDs() {
  if (!deletingDs.value) return
  deletingDsFlag.value = true
  try {
    await apiFetch(`/management/data-sources/${deletingDs.value.id}`, { method: 'DELETE' })
    toast.success(`Data source "${deletingDs.value.name}" deleted`)
    deleteDsOpen.value = false
    await loadDataSources()
    if (dataSources.value.length === 0) {
      await navigateTo(newSourceUrl.value, { replace: true })
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to delete'
    toast.error('Failed to delete data source', { description: msg })
  } finally {
    deletingDsFlag.value = false
    deletingDs.value = null
  }
}

// Sync logs sheet
const logSheetOpen = ref(false)
const selectedLogRunId = ref<string | null>(null)
const runLogs = ref<string[]>([])
const logsLoading = ref(false)
const logsError = ref<string | null>(null)

async function viewLogs(ds: DataSourceItem, run: SyncRun) {
  selectedLogRunId.value = run.id
  runLogs.value = []
  logsError.value = null
  logSheetOpen.value = true
  logsLoading.value = true
  try {
    const result = await apiFetch<{ logs: string[] }>(
      `/management/data-sources/${ds.id}/sync-runs/${run.id}/logs`,
    )
    runLogs.value = result.logs ?? []
  } catch (err) {
    logsError.value = err instanceof Error ? err.message : 'Failed to load logs'
  } finally {
    logsLoading.value = false
  }
}

onMounted(async () => {
  if (!hasTenant.value) return
  await loadKnowledgeGraph()
  await ensureEntryRoute()
  if (maintainFocus.value) {
    await nextTick()
    document.getElementById('maintain-section')?.scrollIntoView({ behavior: 'smooth' })
  }
})

onUnmounted(() => stopPolling())

watch(tenantVersion, async () => {
  dataSources.value = []
  await loadKnowledgeGraph()
  await ensureEntryRoute()
})
</script>

<template>
  <div class="mx-auto max-w-7xl space-y-6">
    <NuxtLink
      :to="manageUrl"
      class="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
    >
      <ChevronLeft class="mr-1 size-4" />
      Back to workspace overview
    </NuxtLink>

    <div class="flex items-center gap-3">
      <div class="rounded-lg bg-primary/10 p-2">
        <Cable class="size-5 text-primary" />
      </div>
      <div class="min-w-0 flex-1">
        <h1 class="text-2xl font-semibold tracking-tight">Data Sources</h1>
        <p class="text-sm text-muted-foreground">
          <template v-if="kgName">{{ kgName }} — </template>
          Manage connected repositories, sync runs, and commit tracking.
        </p>
      </div>
      <div v-if="allSourcesPrepared" class="ml-auto shrink-0">
        <Badge variant="success">
          <Check class="mr-1 size-3" />
          Ready
        </Badge>
      </div>
    </div>

    <Separator />

    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
    </div>

    <div v-else-if="loading" class="flex justify-center py-12">
      <Loader2 class="size-8 animate-spin text-muted-foreground" />
    </div>

    <template v-else>
      <Card>
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <Plus class="size-4" />
            Add repositories
          </CardTitle>
          <CardDescription>
            Paste Git URLs (HTTPS or <span class="font-mono text-xs">git@</span>). Private repos need a token below.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-3">
          <div v-for="(url, index) in newUrls" :key="index" class="flex items-center gap-2">
            <input
              :value="url"
              type="text"
              autocomplete="off"
              autocorrect="off"
              autocapitalize="off"
              spellcheck="false"
              data-lpignore="true"
              data-1p-ignore
              :name="`kg-ds-repo-url-${index}`"
              class="flex h-9 flex-1 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              placeholder="https://github.com/org/repo"
              @input="updateUrl(index, ($event.target as HTMLInputElement).value)"
              @keyup.enter="addRepositories"
            />
            <Button
              variant="ghost"
              size="icon"
              :disabled="newUrls.length === 1 && !newUrls[0]"
              @click="removeUrlField(index)"
            >
              <Trash2 class="size-4" />
            </Button>
          </div>
          <div class="space-y-1.5">
            <Label class="text-xs text-muted-foreground">GitHub access token (optional, for new private repos)</Label>
            <Input v-model="addToken" type="password" placeholder="ghp_…" autocomplete="off" />
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" @click="addUrlField">
              <Plus class="mr-2 size-4" />
              Add another
            </Button>
            <Button size="sm" :disabled="addingUrls || validNewUrls.length === 0" @click="addRepositories">
              <Loader2 v-if="addingUrls" class="mr-2 size-4 animate-spin" />
              Add to project
            </Button>
          </div>
        </CardContent>
      </Card>

      <div v-if="dataSources.length > 0" id="maintain-section" class="space-y-4">
        <Card v-if="maintainFocus" class="border-amber-300/50">
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">Maintenance focus</CardTitle>
            <CardDescription class="text-xs">
              Showing sources with new commits since the last extraction baseline.
            </CardDescription>
          </CardHeader>
        </Card>

        <Card class="border-border/80 bg-muted/15">
          <CardHeader class="pb-2">
            <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle class="flex items-center gap-2 text-base">
                  <GitBranch class="size-4 text-primary" />
                  Data sources overview
                </CardTitle>
              </div>
              <div class="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="checkingAllCommits || visibleDataSources.length === 0"
                  @click="checkAllCommitRefs"
                >
                  <Loader2 v-if="checkingAllCommits" class="mr-2 size-4 animate-spin" />
                  <RefreshCw v-else class="mr-2 size-4" />
                  Check for new commits
                </Button>
                <Button
                  size="sm"
                  :disabled="!canBulkPrepare"
                  @click="prepareAllDataSources"
                >
                  <Loader2 v-if="preparingAll" class="mr-2 size-4 animate-spin" />
                  Prepare data sources
                </Button>
              </div>
            </div>
            <CardDescription>
              Check for new commits resolves the remote branch tip (like after
              <span class="font-mono text-xs">git fetch</span>) and shows the newest commit you
              have not ingested yet. Prepare pulls that content into a JobPackage.
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-3">
            <div
              v-if="visibleDataSources.length === 0"
              class="rounded-md border bg-muted/20 px-4 py-8 text-center text-sm text-muted-foreground"
            >
              <template v-if="maintainFocus">No sources need maintenance right now.</template>
              <template v-else>No data sources to display.</template>
            </div>

            <div v-else class="overflow-x-auto rounded-md border">
              <table class="w-full min-w-[1000px] text-sm">
                <thead>
                  <tr class="border-b bg-muted/50 text-left">
                    <th class="px-3 py-2 font-medium">Source</th>
                    <th class="px-3 py-2 font-medium">Branch</th>
                    <th class="px-3 py-2 font-medium">Status</th>
                    <th class="px-3 py-2 font-medium">Files on branch</th>
                    <th class="px-3 py-2 font-medium">Last extraction baseline</th>
                    <th class="px-3 py-2 font-medium">Ingested at</th>
                    <th class="px-3 py-2 font-medium">Newest unpulled</th>
                    <th class="px-3 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="ds in visibleDataSources"
                    :key="ds.id"
                    class="border-b border-border/60 align-top last:border-0"
                    :class="hasUnpulledCommits(ds) ? 'bg-amber-50/40 dark:bg-amber-950/10' : ''"
                  >
                    <td class="px-3 py-2">
                      <p class="font-medium leading-tight">{{ ds.name }}</p>
                      <p
                        class="mt-0.5 max-w-[20rem] truncate font-mono text-xs text-muted-foreground"
                        :title="resolveRepoUrl(ds.connection_config)"
                      >
                        {{ resolveRepoUrl(ds.connection_config) }}
                      </p>
                    </td>
                    <td class="px-3 py-2 font-mono text-xs">
                      {{ resolveTrackedBranch(ds.connection_config) }}
                    </td>
                    <td class="px-3 py-2">
                      <Badge :variant="prepStatusBadgeVariant(latestStatus(ds))" class="text-xs">
                        {{ resolvePrepStatusLabel(latestStatus(ds)) }}
                      </Badge>
                      <div v-if="latestStatus(ds) && !isSyncTerminal(latestStatus(ds))" class="mt-1">
                        <SyncPhaseIndicator :status="latestStatus(ds)!" />
                      </div>
                    </td>
                    <td class="px-3 py-2 font-mono text-xs tabular-nums">
                      {{ formatPreparedFileCount(ds.last_prepared_file_count) }}
                    </td>
                    <td class="px-3 py-2 font-mono text-xs">
                      <div
                        :class="
                          commitStatusClass(
                            ds.last_extraction_baseline_commit,
                            ds.tracked_branch_head_commit,
                          )
                        "
                      >
                        <span :title="ds.last_extraction_baseline_commit || ''">
                          {{ shortCommitHash(ds.last_extraction_baseline_commit) }}
                        </span>
                      </div>
                      <div
                        class="mt-0.5 text-[10px]"
                        :class="
                          commitStatusClass(
                            ds.last_extraction_baseline_commit,
                            ds.tracked_branch_head_commit,
                          )
                        "
                      >
                        {{
                          commitStatusLabel(
                            ds.last_extraction_baseline_commit,
                            ds.tracked_branch_head_commit,
                          )
                        }}
                      </div>
                    </td>
                    <td class="px-3 py-2 font-mono text-xs">
                      <span :title="resolveIngestedHeadCommit(ds) || ''">
                        {{ shortCommitHash(resolveIngestedHeadCommit(ds)) }}
                      </span>
                      <div class="mt-0.5 text-[10px] text-muted-foreground">
                        {{ resolveIngestedHeadCommit(ds) ? 'have locally' : 'nothing ingested yet' }}
                      </div>
                    </td>
                    <td class="px-3 py-2 font-mono text-xs">
                      <div
                        :class="
                          hasUnpulledCommits(ds)
                            ? 'text-amber-600 dark:text-amber-400'
                            : 'text-green-600 dark:text-green-400'
                        "
                      >
                        <span :title="resolveNewestUnpulledCommit(ds) || ''">
                          {{ shortCommitHash(resolveNewestUnpulledCommit(ds)) }}
                        </span>
                      </div>
                      <div
                        class="mt-0.5 text-[10px]"
                        :class="
                          hasUnpulledCommits(ds)
                            ? 'text-amber-600 dark:text-amber-400'
                            : 'text-muted-foreground'
                        "
                      >
                        {{
                          unpulledCommitStatusLabel(
                            resolveNewestUnpulledCommit(ds),
                            resolveBranchTipCommit(ds),
                          )
                        }}
                      </div>
                    </td>
                    <td class="px-3 py-2">
                      <div class="flex flex-wrap gap-1">
                        <Button size="sm" variant="ghost" class="h-7 px-2 text-[10px]" @click="openEditConfig(ds)">
                          <Settings class="mr-1 size-3" />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          class="h-7 px-2 text-[10px] text-destructive"
                          @click="openDeleteDs(ds)"
                        >
                          <Trash2 class="mr-1 size-3" />
                          Delete
                        </Button>
                      </div>

                      <div
                        v-if="ds.diff_summary && ds.diff_summary.total_changed_files > 0"
                        class="mt-2 rounded border p-2 text-[11px]"
                        :class="hasUnpulledCommits(ds) ? 'border-amber-300 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-950/20' : 'bg-muted/10'"
                      >
                        <div class="flex items-center justify-between gap-2">
                          <span>
                            <span class="font-medium">{{ ds.diff_summary.total_changed_files }}</span>
                            changed files
                          </span>
                          <Badge :variant="hasUnpulledCommits(ds) ? 'default' : 'secondary'" class="text-[10px]">
                            {{ hasUnpulledCommits(ds) ? 'Unpulled commits' : 'Up to date' }}
                          </Badge>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          class="mt-1 h-6 px-2 text-[10px]"
                          @click="toggleDiffExpanded(ds.id)"
                        >
                          {{ isDiffExpanded(ds.id) ? 'Hide files' : 'Show files' }}
                        </Button>
                        <div
                          v-if="isDiffExpanded(ds.id)"
                          class="mt-1 max-h-32 space-y-1 overflow-y-auto"
                        >
                          <div
                            v-for="file in ds.diff_summary.changed_files"
                            :key="`${file.status}:${file.path}`"
                            class="flex justify-between gap-2 font-mono"
                          >
                            <span class="break-all">{{ file.path }}</span>
                            <Badge variant="outline" class="h-5 text-[10px] uppercase">{{ file.status }}</Badge>
                          </div>
                        </div>
                      </div>

                      <div v-if="ds.sync_runs?.length" class="mt-2 space-y-1">
                        <div
                          v-for="run in ds.sync_runs.slice(0, 2)"
                          :key="run.id"
                          class="flex items-center gap-2 text-[10px] text-muted-foreground"
                        >
                          <SyncPhaseIndicator :status="run.status" />
                          <span>{{ new Date(run.started_at).toLocaleString() }}</span>
                          <Button
                            size="sm"
                            variant="ghost"
                            class="ml-auto h-5 px-1"
                            @click="viewLogs(ds, run)"
                          >
                            <ScrollText class="mr-1 size-3" />
                            Logs
                          </Button>
                        </div>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card v-if="allSourcesPrepared" class="border-primary/40">
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base text-green-600 dark:text-green-400">
            <Check class="size-5" />
            Data Sources ready
          </CardTitle>
          <CardDescription>
            {{ preparedCount }} of {{ dataSources.length }} source{{ dataSources.length === 1 ? '' : 's' }}
            prepared for graph management and extraction.
          </CardDescription>
        </CardHeader>
        <CardContent class="flex flex-col gap-4 sm:flex-row sm:flex-wrap">
          <p class="w-full text-sm text-muted-foreground">
            Ingestion context is prepared. Open graph management to design schema, run extraction,
            or continue in the manage workspace.
          </p>
          <Button as-child>
            <NuxtLink :to="graphManagementUrl" class="inline-flex items-center gap-2">
              Open Graph Management
              <ArrowRight class="size-4" />
            </NuxtLink>
          </Button>
          <Button as-child variant="outline">
            <NuxtLink :to="manageUrl" class="inline-flex items-center gap-2">
              <LayoutDashboard class="size-4" />
              Back to workspace overview
            </NuxtLink>
          </Button>
        </CardContent>
      </Card>

      <div
        v-if="!allSourcesPrepared && dataSources.length === 0"
        class="rounded-lg border bg-muted/50 p-4"
      >
        <p class="text-sm text-muted-foreground">
          <strong>Flow:</strong> add repository URLs above, check for new commits to resolve branch heads,
          then prepare data sources before opening graph management.
        </p>
      </div>
    </template>

    <Sheet v-model:open="editConfigOpen">
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Edit configuration</SheetTitle>
          <SheetDescription>Update name or rotate credentials.</SheetDescription>
        </SheetHeader>
        <div class="mt-4 space-y-4">
          <div class="space-y-1.5">
            <Label>Name</Label>
            <Input v-model="editConfigName" />
            <p v-if="editConfigNameError" class="text-xs text-destructive">{{ editConfigNameError }}</p>
          </div>
          <div class="space-y-1.5">
            <Label>New access token (optional)</Label>
            <Input v-model="editConfigToken" type="password" autocomplete="off" />
          </div>
          <Button :disabled="savingConfig" @click="handleEditConfig">
            <Loader2 v-if="savingConfig" class="mr-2 size-4 animate-spin" />
            Save
          </Button>
        </div>
      </SheetContent>
    </Sheet>

    <Sheet v-model:open="logSheetOpen">
      <SheetContent class="sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Sync logs</SheetTitle>
          <SheetDescription>Run {{ selectedLogRunId }}</SheetDescription>
        </SheetHeader>
        <div class="mt-4 max-h-[70vh] overflow-y-auto font-mono text-xs">
          <Loader2 v-if="logsLoading" class="mx-auto size-6 animate-spin" />
          <p v-else-if="logsError" class="text-destructive">{{ logsError }}</p>
          <pre v-else class="whitespace-pre-wrap">{{ runLogs.join('\n') || 'No log lines.' }}</pre>
        </div>
      </SheetContent>
    </Sheet>

    <AlertDialog v-model:open="deleteDsOpen">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete data source?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently deletes "{{ deletingDs?.name }}" and its sync history.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction :disabled="deletingDsFlag" @click="handleDeleteDs">
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>
