<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import {
  ChevronLeft,
  GitBranch,
  Plus,
  Trash2,
  Loader2,
  Check,
  X,
  Cable,
  ArrowRight,
  Settings2,
  LayoutDashboard,
} from 'lucide-vue-next'
import {
  inferNameFromRepoUrl,
  validateStep1,
  validateStep2,
  buildDataSourceCreationUrl,
  buildDataSourceCreationBody,
  detectAdapterFromUrl,
} from '@/utils/dataSourceWizard'
import type { DetectedAdapterId } from '@/utils/dataSourceWizard'
import {
  buildKgDataSourcesUrl,
  buildKgManageUrl,
} from '@/utils/kgDataSourcesNavigation'
import {
  isActiveSyncStatus,
  isSyncTerminal,
  latestSyncRun,
  type SyncRunStatus,
} from '@/utils/kgDataSourcesSync'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import SyncPhaseIndicator from '@/components/graph/SyncPhaseIndicator.vue'

type FlowPhase = 'urls' | 'configure' | 'sync' | 'stats'

interface PendingSourceDraft {
  id: string
  url: string
  detectedAdapterId: DetectedAdapterId
  name: string
  branch: string
  nameError: string
  urlError: string
  branchError: string
}

interface SourceUrlInputRow {
  id: string
  url: string
}

interface CreatedSourceRow {
  id: string
  name: string
  url: string
  branch: string
  syncStatus: SyncRunStatus | 'idle' | 'queued'
  syncError: string | null
  token_usage_total: number | null
  cost_total_usd: number | null
}

const route = useRoute()
const kgId = computed(() => route.params.kgId as string)

const { hasTenant, tenantVersion } = useTenant()
const { apiFetch } = useApiClient()

const kgName = ref('')
const loadingKg = ref(false)

const flowPhase = ref<FlowPhase>('urls')
const sourceUrlInputs = ref<SourceUrlInputRow[]>([{ id: 'source-1', url: '' }])
const sourceUrlError = ref('')
const providerError = ref('')
const pendingSources = ref<PendingSourceDraft[]>([])
const detectingSourceDetails = ref(false)
const connToken = ref('')
const creating = ref(false)

const createdSources = ref<CreatedSourceRow[]>([])
const syncRunActive = ref(false)
const syncCompletedInRun = ref(0)
const syncRunTotal = ref(0)
const syncActiveName = ref<string | null>(null)
const syncStepLabel = ref('')
const readyForStats = ref(false)

const wizardSectionRef = ref<HTMLElement | null>(null)

const manageUrl = computed(() => buildKgManageUrl(kgId.value))
const operationsUrl = computed(() => buildKgDataSourcesUrl(kgId.value))

const validUrlRows = computed(() =>
  sourceUrlInputs.value
    .map((row) => row.url.trim())
    .filter((url) => url.length > 0),
)

const syncProgressPercent = computed(() => {
  if (syncRunTotal.value === 0) return 0
  return Math.round((syncCompletedInRun.value / syncRunTotal.value) * 100)
})

const preparedSourceCount = computed(() =>
  createdSources.value.filter((s) => s.syncStatus === 'ingested').length,
)

function addUrlField() {
  sourceUrlInputs.value.push({
    id: `source-${Date.now()}-${sourceUrlInputs.value.length + 1}`,
    url: '',
  })
}

function removeUrlField(id: string) {
  if (sourceUrlInputs.value.length === 1) {
    sourceUrlInputs.value[0]!.url = ''
    return
  }
  sourceUrlInputs.value = sourceUrlInputs.value.filter((row) => row.id !== id)
}

async function loadKnowledgeGraph() {
  loadingKg.value = true
  try {
    const result = await apiFetch<{ name: string }>(
      `/management/knowledge-graphs/${kgId.value}`,
    )
    kgName.value = result.name ?? kgId.value
  } catch {
    kgName.value = kgId.value
  } finally {
    loadingKg.value = false
  }
}

async function detectGithubSourceDetails(entry: PendingSourceDraft) {
  if (entry.detectedAdapterId !== 'github') return
  try {
    const parsed = new URL(entry.url)
    const [owner, repoRaw] = parsed.pathname.split('/').filter(Boolean)
    const repo = repoRaw?.replace(/\.git$/, '')
    if (!owner || !repo) return
    const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`)
    if (!response.ok) return
    const payload = await response.json() as { default_branch?: string; name?: string }
    if (!entry.branch.trim() && payload.default_branch) {
      entry.branch = payload.default_branch
    }
    if (!entry.name.trim() && payload.name) {
      entry.name = payload.name
    }
  } catch {
    // Best effort only.
  }
}

function proceedToConfigure() {
  const seen = new Set<string>()
  const parsedEntries: Array<{ url: string; detectedAdapterId: DetectedAdapterId }> = []
  for (const row of sourceUrlInputs.value) {
    const url = row.url.trim()
    if (!url || seen.has(url)) continue
    seen.add(url)
    parsedEntries.push({ url, detectedAdapterId: detectAdapterFromUrl(url) })
  }

  if (parsedEntries.length === 0) {
    sourceUrlError.value = 'Provide at least one source URL.'
    return
  }

  const drafts: PendingSourceDraft[] = parsedEntries.map((entry, index) => ({
    id: `src-${index}-${entry.url}`,
    url: entry.url,
    detectedAdapterId: entry.detectedAdapterId,
    name: inferNameFromRepoUrl(entry.url) ?? '',
    branch: '',
    nameError: '',
    urlError: '',
    branchError: '',
  }))

  let hasError = false
  const providerIssues: string[] = []
  for (const entry of drafts) {
    const validation = validateStep1({
      selectedKnowledgeGraphId: kgId.value,
      sourceUrl: entry.url,
      detectedAdapterId: entry.detectedAdapterId,
    })
    entry.urlError = validation.sourceUrlError
    if (validation.providerError) {
      providerIssues.push(`${entry.url}: ${validation.providerError}`)
    }
    if (!validation.valid) hasError = true
  }

  pendingSources.value = drafts
  sourceUrlError.value = hasError && drafts.some((d) => !!d.urlError)
    ? 'One or more URLs are invalid.'
    : ''
  providerError.value = providerIssues.join(' | ')
  if (hasError) return

  detectingSourceDetails.value = true
  Promise.all(drafts.map((d) => detectGithubSourceDetails(d)))
    .finally(() => {
      detectingSourceDetails.value = false
      flowPhase.value = 'configure'
    })
}

async function createDataSources() {
  let hasError = false
  for (const entry of pendingSources.value) {
    const validation = validateStep2({
      connName: entry.name,
      connRepoUrl: entry.url,
    })
    entry.nameError = validation.connNameError
    entry.urlError = validation.connRepoUrlError
    entry.branchError = !entry.branch.trim() ? 'Tracked branch is required.' : ''
    if (!validation.valid || entry.branchError) hasError = true
  }
  if (hasError) return

  creating.value = true
  const rows: CreatedSourceRow[] = []
  const failed: string[] = []

  try {
    for (const entry of pendingSources.value) {
      try {
        const created = await apiFetch<{ id: string; name: string }>(
          buildDataSourceCreationUrl(kgId.value),
          {
            method: 'POST',
            body: buildDataSourceCreationBody({
              name: entry.name,
              adapter_type: 'github',
              connection_config: {
                repo_url: entry.url,
                branch: entry.branch,
              },
              credentials: connToken.value ? { access_token: connToken.value } : undefined,
            }),
          },
        )
        rows.push({
          id: created.id,
          name: created.name,
          url: entry.url,
          branch: entry.branch,
          syncStatus: 'idle',
          syncError: null,
          token_usage_total: null,
          cost_total_usd: null,
        })
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to connect source'
        failed.push(`${entry.url}: ${msg}`)
      }
    }

    if (rows.length === 0) {
      toast.error('Connection failed', { description: failed[0] ?? 'No sources were created.' })
      return
    }

    connToken.value = ''
    createdSources.value = rows
    flowPhase.value = 'sync'
    readyForStats.value = false

    toast.success('Data sources connected', {
      description: `${rows.length} source(s) ready for initial sync.`,
    })

    await nextTick()
    wizardSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })

    if (failed.length > 0) {
      toast.warning('Some sources were not connected', { description: failed.join(' | ') })
    }
  } finally {
    creating.value = false
  }
}

async function refreshSourceSyncStatus(row: CreatedSourceRow) {
  const runs = await apiFetch<Array<{
    status: SyncRunStatus
    error: string | null
    token_usage_total?: number | null
    cost_total_usd?: number | null
  }>>(`/management/data-sources/${row.id}/sync-runs`)
  const latest = latestSyncRun(runs)
  if (latest) {
    row.syncStatus = latest.status
    row.syncError = latest.error
    row.token_usage_total = latest.token_usage_total ?? null
    row.cost_total_usd = latest.cost_total_usd ?? null
  }
}

async function pollUntilTerminal(row: CreatedSourceRow, timeoutMs = 600_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    await refreshSourceSyncStatus(row)
    if (isSyncTerminal(row.syncStatus as SyncRunStatus)) return
    await new Promise((resolve) => setTimeout(resolve, 3000))
  }
  row.syncStatus = 'failed'
  row.syncError = 'Sync timed out'
}

async function runSequentialIngestionPrep() {
  const queue = createdSources.value.filter(
    (s) => s.syncStatus === 'idle' || s.syncStatus === 'failed' || s.syncStatus === 'queued',
  )
  if (queue.length === 0) {
    toast.error('No sources need preparation')
    return
  }

  syncRunActive.value = true
  syncRunTotal.value = queue.length
  syncCompletedInRun.value = 0
  readyForStats.value = false

  try {
    for (let i = 0; i < queue.length; i++) {
      const target = queue[i]!
      syncStepLabel.value = `${i + 1} / ${queue.length}`
      syncActiveName.value = target.name
      target.syncStatus = 'pending'
      target.syncError = null

      try {
        await apiFetch(`/management/data-sources/${target.id}/sync`, {
          method: 'POST',
          body: { mode: 'ingest_only' },
        })
        await pollUntilTerminal(target)
        if (target.syncStatus === 'failed') {
          toast.error(`Preparation failed: ${target.name}`, {
            description: target.syncError ?? undefined,
          })
        }
      } catch (err: unknown) {
        target.syncStatus = 'failed'
        target.syncError = err instanceof Error ? err.message : 'Preparation failed'
        toast.error(`Preparation failed: ${target.name}`, { description: target.syncError })
      }

      syncCompletedInRun.value = i + 1
    }

    const allPrepared = createdSources.value.every((s) => s.syncStatus === 'ingested')
    readyForStats.value = allPrepared

    if (allPrepared) {
      flowPhase.value = 'stats'
      await nextTick()
      wizardSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      toast.success('Ingestion context prepared', {
        description: 'Sources are ready for design and extraction when you open those steps.',
      })
    } else {
      toast('Preparation finished with issues', {
        description: 'Fix failed sources from the data sources page or retry.',
      })
    }
  } finally {
    syncRunActive.value = false
    syncActiveName.value = null
    syncStepLabel.value = ''
  }
}

function getSyncBadge(status: CreatedSourceRow['syncStatus']) {
  switch (status) {
    case 'ingested':
      return { variant: 'default' as const, label: 'Prepared', icon: Check }
    case 'completed':
      return { variant: 'default' as const, label: 'Completed', icon: Check }
    case 'failed':
      return { variant: 'destructive' as const, label: 'Failed', icon: X }
    case 'pending':
    case 'ingesting':
    case 'ai_extracting':
    case 'applying':
      return { variant: 'secondary' as const, label: 'Preparing…', icon: Loader2 }
    default:
      return { variant: 'outline' as const, label: 'Ready', icon: null }
  }
}

onMounted(async () => {
  if (!hasTenant.value) return
  await loadKnowledgeGraph()
})

watch(tenantVersion, () => {
  loadKnowledgeGraph()
})

onUnmounted(() => {
  syncRunActive.value = false
})
</script>

<template>
  <div class="mx-auto max-w-4xl space-y-6">
    <NuxtLink
      :to="manageUrl"
      class="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
    >
      <ChevronLeft class="mr-1 size-4" />
      Back to workspace overview
    </NuxtLink>

    <div v-if="!hasTenant" class="py-16 text-center text-muted-foreground">
      Select a tenant from the sidebar to connect data sources.
    </div>

    <template v-else>
      <!-- URLs -->
      <Card v-if="flowPhase === 'urls'">
        <CardHeader>
          <div class="flex items-center gap-2">
            <GitBranch class="size-5 text-primary" />
            <CardTitle>Add data sources</CardTitle>
          </div>
          <CardDescription>
            Connect Git repositories to
            <Badge v-if="kgName" variant="outline" class="mx-1">{{ kgName }}</Badge>
            <span v-else-if="loadingKg" class="text-muted-foreground">loading…</span>.
            You will confirm branch and credentials next, then run an initial sync.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-3">
            <div
              v-for="row in sourceUrlInputs"
              :key="row.id"
              class="flex items-center gap-2"
            >
              <Input
                v-model="row.url"
                type="text"
                placeholder="https://github.com/org/repo"
                class="flex-1 font-mono text-sm"
              />
              <Button
                variant="ghost"
                size="icon"
                :disabled="sourceUrlInputs.length === 1 && !sourceUrlInputs[0]?.url"
                @click="removeUrlField(row.id)"
              >
                <Trash2 class="size-4" />
              </Button>
            </div>
          </div>
          <Button variant="outline" size="sm" type="button" @click="addUrlField">
            <Plus class="mr-2 size-4" />
            Add another URL
          </Button>
          <p v-if="sourceUrlError" class="text-sm text-destructive">{{ sourceUrlError }}</p>
          <p v-if="providerError" class="text-sm text-destructive">{{ providerError }}</p>
          <p class="text-xs text-muted-foreground">
            GitHub repositories are supported today. You can add more sources later from the
            data sources page.
          </p>
        </CardContent>
        <CardFooter>
          <Button
            type="button"
            :disabled="validUrlRows.length === 0 || detectingSourceDetails"
            @click="proceedToConfigure"
          >
            <Loader2 v-if="detectingSourceDetails" class="mr-2 size-4 animate-spin" />
            Continue
            <ArrowRight v-if="!detectingSourceDetails" class="ml-2 size-4" />
          </Button>
        </CardFooter>
      </Card>

      <!-- Configure before create -->
      <Card v-if="flowPhase === 'configure'">
        <CardHeader>
          <div class="flex items-center gap-2">
            <Cable class="size-5 text-primary" />
            <CardTitle>Configure each repository</CardTitle>
          </div>
          <CardDescription>
            Review names and tracked branches. Use one access token for all private repos if needed.
          </CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div
            v-for="entry in pendingSources"
            :key="entry.id"
            class="rounded-lg border p-4 space-y-3"
          >
            <p class="truncate font-mono text-xs text-muted-foreground">{{ entry.url }}</p>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1.5">
                <Label>Name</Label>
                <Input v-model="entry.name" />
                <p v-if="entry.nameError" class="text-xs text-destructive">{{ entry.nameError }}</p>
              </div>
              <div class="space-y-1.5">
                <Label>Tracked branch</Label>
                <Input v-model="entry.branch" placeholder="main" />
                <p v-if="entry.branchError" class="text-xs text-destructive">{{ entry.branchError }}</p>
              </div>
            </div>
            <p v-if="entry.urlError" class="text-xs text-destructive">{{ entry.urlError }}</p>
          </div>
          <div class="space-y-1.5">
            <Label>GitHub access token (optional)</Label>
            <Input v-model="connToken" type="password" placeholder="ghp_…" autocomplete="off" />
            <p class="text-xs text-muted-foreground">
              Required for private repositories. Applied to all sources in this batch.
            </p>
          </div>
        </CardContent>
        <CardFooter class="flex justify-between">
          <Button variant="outline" type="button" @click="flowPhase = 'urls'">Back</Button>
          <Button type="button" :disabled="creating" @click="createDataSources">
            <Loader2 v-if="creating" class="mr-2 size-4 animate-spin" />
            <Check v-if="!creating" class="mr-2 size-4" />
            Connect data sources
          </Button>
        </CardFooter>
      </Card>

      <!-- Sync + stats -->
      <div
        v-if="flowPhase === 'sync' || flowPhase === 'stats'"
        ref="wizardSectionRef"
        class="space-y-6"
      >
        <Card>
          <CardHeader>
            <div class="flex flex-wrap items-center gap-2">
              <Badge variant="default">{{ kgName }}</Badge>
              <span class="text-sm text-muted-foreground">sources connected</span>
            </div>
            <CardTitle class="text-base">Prepare ingestion context</CardTitle>
            <CardDescription>
              Fetch repository content and build job packages for each source. No AI extraction
              runs here — that happens later in graph management. Sources are prepared one at a
              time so you can follow progress.
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div class="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                :disabled="syncRunActive || createdSources.length === 0"
                @click="runSequentialIngestionPrep"
              >
                <Loader2 v-if="syncRunActive" class="mr-2 size-4 animate-spin" />
                <GitBranch v-if="!syncRunActive" class="mr-2 size-4" />
                Prepare ingestion context
              </Button>
            </div>

            <div
              v-if="syncRunActive"
              class="space-y-2 rounded-lg border border-primary/30 bg-primary/5 p-4"
            >
              <div class="flex items-center justify-between text-sm">
                <span class="font-medium">Preparing {{ syncActiveName || '…' }}</span>
                <span class="tabular-nums text-muted-foreground">{{ syncStepLabel }}</span>
              </div>
              <div class="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  class="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                  :style="{ width: `${syncProgressPercent}%` }"
                />
              </div>
            </div>

            <div class="space-y-4">
              <div
                v-for="source in createdSources"
                :key="source.id"
                class="rounded-lg border p-4 transition-shadow"
                :class="[
                  source.syncStatus === 'failed' ? 'border-destructive/50 bg-destructive/5' : '',
                  syncActiveName === source.name ? 'ring-2 ring-primary/40' : '',
                ]"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div class="min-w-0 flex-1 space-y-1">
                    <p class="font-medium">{{ source.name }}</p>
                    <p class="truncate font-mono text-xs text-muted-foreground">{{ source.url }}</p>
                    <p v-if="source.syncError" class="text-xs text-destructive">{{ source.syncError }}</p>
                  </div>
                  <div class="flex shrink-0 flex-col items-end gap-2">
                    <SyncPhaseIndicator
                      v-if="isActiveSyncStatus(source.syncStatus as SyncRunStatus) || source.syncStatus === 'ingested' || source.syncStatus === 'completed' || source.syncStatus === 'failed'"
                      :status="(source.syncStatus === 'idle' || source.syncStatus === 'queued') ? 'pending' : (source.syncStatus as SyncRunStatus)"
                    />
                    <Badge v-else :variant="getSyncBadge(source.syncStatus).variant">
                      {{ getSyncBadge(source.syncStatus).label }}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card v-if="flowPhase === 'stats' && readyForStats" class="border-primary/30">
          <CardHeader>
            <div class="flex items-center gap-2">
              <Settings2 class="size-5 text-primary" />
              <CardTitle class="text-base">Preparation summary</CardTitle>
            </div>
            <CardDescription>
              Ingestion context is ready for all sources. Open data sources to manage commits, or
              continue in graph management when you are ready to extract.
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div class="overflow-x-auto rounded-md border">
              <table class="w-full min-w-[320px] text-sm">
                <thead>
                  <tr class="border-b bg-muted/50 text-left">
                    <th class="px-3 py-2 font-medium">Data source</th>
                    <th class="px-3 py-2 text-right font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="s in createdSources"
                    :key="s.id"
                    class="border-b border-border/60 last:border-0"
                  >
                    <td class="px-3 py-2 font-medium">{{ s.name }}</td>
                    <td class="px-3 py-2 text-right">
                      <Badge variant="default" class="text-[10px]">Prepared</Badge>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="text-sm text-muted-foreground">
              <span class="font-medium text-foreground">{{ preparedSourceCount }}</span>
              source{{ preparedSourceCount === 1 ? '' : 's' }} ready for later extraction.
            </p>
            <div class="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <Button as-child>
                <NuxtLink :to="operationsUrl" class="inline-flex items-center gap-2">
                  <Check class="size-4" />
                  Open data sources
                </NuxtLink>
              </Button>
              <Button as-child variant="outline">
                <NuxtLink :to="manageUrl" class="inline-flex items-center gap-2">
                  <LayoutDashboard class="size-4" />
                  Back to workspace overview
                </NuxtLink>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </template>
  </div>
</template>
