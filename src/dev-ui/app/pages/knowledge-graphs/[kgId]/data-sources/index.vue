<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import {
  Cable,
  ChevronLeft,
  Plus,
  Loader2,
  Trash2,
  Settings,
  RefreshCw,
  ScrollText,
  Building2,
} from 'lucide-vue-next'
import {
  buildKgDataSourcesNewUrl,
  buildKgManageUrl,
  parseKgDataSourcesFocusQuery,
} from '@/utils/kgDataSourcesNavigation'
import { isMaintenanceReady } from '@/utils/kgManageWorkspace'
import { hasAnyActiveSync, type SyncRunStatus } from '@/utils/kgDataSourcesSync'
import SyncPhaseIndicator from '@/components/graph/SyncPhaseIndicator.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CopyableText } from '@/components/ui/copyable-text'
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
  clone_head_commit?: string | null
  last_extraction_baseline_commit?: string | null
  tracked_branch_head_commit?: string | null
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
const refreshingCommitRefs = ref<Record<string, boolean>>({})
const adoptingBaselines = ref<Record<string, boolean>>({})

const manageUrl = computed(() => buildKgManageUrl(kgId.value))
const newSourceUrl = computed(() => buildKgDataSourcesNewUrl(kgId.value))

const visibleDataSources = computed(() => {
  if (!maintainFocus.value) return dataSources.value
  return dataSources.value.filter((ds) => isMaintenanceReady(ds))
})

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

function isDiffExpanded(dsId: string): boolean {
  return expandedDiffLists.value[dsId] === true
}

function toggleDiffExpanded(dsId: string) {
  expandedDiffLists.value[dsId] = !isDiffExpanded(dsId)
}

async function triggerSync(dsId: string) {
  try {
    await apiFetch(`/management/data-sources/${dsId}/sync`, { method: 'POST' })
    toast.success('Sync triggered')
    await loadDataSources()
    if (hasAnyActiveSync(dataSources.value)) startPolling()
  } catch {
    toast.error('Failed to trigger sync')
  }
}

async function refreshCommitRefs(dsId: string) {
  refreshingCommitRefs.value[dsId] = true
  try {
    await apiFetch(`/management/data-sources/${dsId}/commit-refs/refresh`, { method: 'POST' })
    toast.success('Commit references refreshed')
    await loadDataSources()
  } catch {
    toast.error('Failed to refresh commit references')
  } finally {
    refreshingCommitRefs.value[dsId] = false
  }
}

async function adoptTrackedHeadBaseline(dsId: string) {
  adoptingBaselines.value[dsId] = true
  try {
    await apiFetch(`/management/data-sources/${dsId}/commit-refs/adopt-tracked-head`, {
      method: 'POST',
    })
    toast.success('Baseline updated to tracked head')
    await loadDataSources()
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to update baseline'
    toast.error('Failed to update baseline', { description: msg })
  } finally {
    adoptingBaselines.value[dsId] = false
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
  <div class="mx-auto max-w-5xl space-y-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <NuxtLink
        :to="manageUrl"
        class="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft class="mr-1 size-4" />
        Back to workspace overview
      </NuxtLink>
      <Button :disabled="!hasTenant" @click="navigateTo(newSourceUrl)">
        <Plus class="mr-2 size-4" />
        Add data source
      </Button>
    </div>

    <div class="flex items-center gap-3">
      <div class="rounded-lg bg-primary/10 p-2">
        <Cable class="size-5 text-primary" />
      </div>
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">Data Sources</h1>
        <p class="text-sm text-muted-foreground">
          <template v-if="kgName">{{ kgName }} — </template>
          Manage connected repositories, sync runs, and commit tracking.
        </p>
      </div>
    </div>

    <Separator />

    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
    </div>

    <div v-else-if="loading" class="flex justify-center py-16">
      <Loader2 class="size-8 animate-spin text-muted-foreground" />
    </div>

    <template v-else>
      <Card v-if="maintainFocus">
        <CardHeader class="pb-2">
          <CardTitle class="text-sm">Maintenance focus</CardTitle>
          <CardDescription class="text-xs">
            Showing sources with new commits since the last extraction baseline.
          </CardDescription>
        </CardHeader>
      </Card>

      <div
        v-if="visibleDataSources.length === 0"
        class="flex flex-col items-center gap-4 py-16 text-center"
      >
        <p class="text-sm text-muted-foreground">
          <template v-if="maintainFocus">
            No sources need maintenance right now.
          </template>
          <template v-else>
            No data sources connected.
          </template>
        </p>
        <Button v-if="!maintainFocus" @click="navigateTo(newSourceUrl)">
          <Plus class="mr-2 size-4" />
          Add your first data source
        </Button>
      </div>

      <div v-else id="maintain-section" class="space-y-3">
        <div
          v-for="ds in visibleDataSources"
          :key="ds.id"
          class="rounded-lg border bg-card"
          :class="isMaintenanceReady(ds) ? 'border-amber-300/60' : ''"
        >
          <div class="flex flex-wrap items-center justify-between gap-3 p-4">
            <div class="flex items-center gap-3">
              <div class="rounded-md bg-muted p-2">
                <Cable class="size-4 text-muted-foreground" />
              </div>
              <div>
                <p class="text-sm font-medium">{{ ds.name }}</p>
                <p class="text-xs text-muted-foreground">{{ ds.adapter_type }}</p>
                <CopyableText :text="ds.id" label="Data source ID copied" class="mt-0.5" />
              </div>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <SyncPhaseIndicator
                v-if="ds.sync_runs?.[0]"
                :status="ds.sync_runs[0].status"
              />
              <Badge v-else variant="secondary" class="text-[10px]">Idle</Badge>
              <Button size="sm" variant="outline" @click="openEditConfig(ds)">
                <Settings class="mr-1.5 size-3.5" />
                Edit Config
              </Button>
              <Button
                size="sm"
                variant="outline"
                class="text-destructive hover:bg-destructive/10"
                @click="openDeleteDs(ds)"
              >
                <Trash2 class="mr-1.5 size-3.5" />
                Delete
              </Button>
              <Button size="sm" variant="outline" @click="triggerSync(ds.id)">
                Sync Now
              </Button>
            </div>
          </div>

          <div class="border-t px-4 py-3">
            <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Commit Status
            </p>
            <div class="grid gap-2 sm:grid-cols-3">
              <div class="rounded-md border bg-muted/20 p-2">
                <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Local clone commit</p>
                <p class="mt-1 break-all font-mono text-xs">{{ ds.clone_head_commit ?? '—' }}</p>
              </div>
              <div class="rounded-md border bg-muted/20 p-2">
                <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Last extraction baseline</p>
                <p class="mt-1 break-all font-mono text-xs">{{ ds.last_extraction_baseline_commit ?? '—' }}</p>
              </div>
              <div class="rounded-md border bg-muted/20 p-2">
                <p class="text-[10px] uppercase tracking-wider text-muted-foreground">Tracked branch head</p>
                <p class="mt-1 break-all font-mono text-xs">{{ ds.tracked_branch_head_commit ?? '—' }}</p>
              </div>
            </div>
            <div class="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                class="h-7 text-[10px]"
                :disabled="refreshingCommitRefs[ds.id] === true"
                @click="refreshCommitRefs(ds.id)"
              >
                <RefreshCw
                  class="mr-1 size-3"
                  :class="refreshingCommitRefs[ds.id] ? 'animate-spin' : ''"
                />
                Refresh commits
              </Button>
              <Button
                size="sm"
                variant="outline"
                class="h-7 text-[10px]"
                :disabled="adoptingBaselines[ds.id] === true || !isMaintenanceReady(ds)"
                @click="adoptTrackedHeadBaseline(ds.id)"
              >
                Adopt tracked head as baseline
              </Button>
            </div>

            <div
              v-if="ds.diff_summary"
              class="mt-3 rounded-md border p-2"
              :class="isMaintenanceReady(ds) ? 'border-amber-300 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-950/20' : 'bg-muted/10'"
            >
              <div class="flex items-center justify-between gap-2 text-xs">
                <span>
                  <span class="font-medium">{{ ds.diff_summary.total_changed_files }}</span>
                  changed files
                </span>
                <Badge
                  :variant="isMaintenanceReady(ds) ? 'default' : 'secondary'"
                  class="text-[10px]"
                >
                  {{ isMaintenanceReady(ds) ? 'New commits available' : 'Up to date' }}
                </Badge>
              </div>
              <Button
                v-if="ds.diff_summary.changed_files.length > 0"
                size="sm"
                variant="ghost"
                class="mt-2 h-6 px-2 text-[10px]"
                @click="toggleDiffExpanded(ds.id)"
              >
                {{ isDiffExpanded(ds.id) ? 'Hide changed files' : 'Show changed files' }}
              </Button>
              <div
                v-if="isDiffExpanded(ds.id)"
                class="mt-2 max-h-48 space-y-1 overflow-y-auto rounded-md border bg-background/80 p-2"
              >
                <div
                  v-for="file in ds.diff_summary.changed_files"
                  :key="`${file.status}:${file.path}`"
                  class="flex justify-between gap-2 text-[11px]"
                >
                  <span class="break-all font-mono">{{ file.path }}</span>
                  <Badge variant="outline" class="h-5 text-[10px] uppercase">{{ file.status }}</Badge>
                </div>
              </div>
            </div>
          </div>

          <div v-if="ds.sync_runs?.length" class="border-t px-4 py-3">
            <p class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Sync History
            </p>
            <div class="space-y-1">
              <div
                v-for="run in ds.sync_runs"
                :key="run.id"
                class="flex items-center gap-2 text-xs text-muted-foreground"
              >
                <SyncPhaseIndicator :status="run.status" />
                <span>{{ new Date(run.started_at).toLocaleString() }}</span>
                <span v-if="run.error" class="text-destructive">{{ run.error }}</span>
                <Button
                  size="sm"
                  variant="ghost"
                  class="ml-auto h-6 px-2 text-[10px]"
                  @click="viewLogs(ds, run)"
                >
                  <ScrollText class="mr-1 size-3" />
                  View Logs
                </Button>
              </div>
            </div>
          </div>
        </div>
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
