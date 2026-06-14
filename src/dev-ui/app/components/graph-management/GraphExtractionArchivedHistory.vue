<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2, Archive, ChevronRight } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

const props = defineProps<{
  kgId: string
}>()

const { apiFetch } = useApiClient()

interface ArchivedJob {
  jobId: string
  jobSet: string
  status: string
  strategy: string
  workerId: string | null
  startedAt: string | null
  completedAt: string | null
  archivedAt: string | null
  runStartedAt: string | null
  inputTokens: number
  outputTokens: number
  costUsd: number
  entitiesCreated: number
  entitiesModified: number
  relationshipsCreated: number
  relationshipsModified: number
  writeOps: number
  instanceCount: number
  hasMutations: boolean
}

interface ArchivedJobSetGroup {
  jobSet: string
  jobCount: number
  writeOps: number
  jobs: ArchivedJob[]
}

interface ArchivedRunGroup {
  runStartedAt: string | null
  jobCount: number
  writeOps: number
  inputTokens: number
  outputTokens: number
  costUsd: number
  jobSets: ArchivedJobSetGroup[]
}

interface ArchivedHistoryPayload {
  archivedJobCount: number
  runs: ArchivedRunGroup[]
}

const loading = ref(false)
const error = ref<string | null>(null)
const payload = ref<ArchivedHistoryPayload | null>(null)
const selectedRunIndex = ref(0)
const selectedJobSetIndex = ref(0)
const selectedJobId = ref<string | null>(null)
const mutationJsonl = ref<string | null>(null)
const mutationLoading = ref(false)

const selectedRun = computed(() => payload.value?.runs[selectedRunIndex.value] ?? null)
const selectedJobSet = computed(() => selectedRun.value?.jobSets[selectedJobSetIndex.value] ?? null)
const selectedJob = computed(
  () => selectedJobSet.value?.jobs.find((job) => job.jobId === selectedJobId.value) ?? null,
)

async function loadHistory() {
  loading.value = true
  error.value = null
  try {
    payload.value = await apiFetch<ArchivedHistoryPayload>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs/archived-history`,
    )
    selectedRunIndex.value = 0
    selectedJobSetIndex.value = 0
    selectedJobId.value = payload.value?.runs[0]?.jobSets[0]?.jobs[0]?.jobId ?? null
    await loadSelectedMutations()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load graph writes history'
    payload.value = null
  } finally {
    loading.value = false
  }
}

async function loadSelectedMutations() {
  mutationJsonl.value = null
  if (!selectedJobId.value) return
  mutationLoading.value = true
  try {
    const detail = await apiFetch<{ jsonl: string }>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs/jobs/${encodeURIComponent(selectedJobId.value)}/archived-mutations`,
    )
    mutationJsonl.value = detail.jsonl || ''
  } catch {
    mutationJsonl.value = null
  } finally {
    mutationLoading.value = false
  }
}

function selectRun(index: number) {
  selectedRunIndex.value = index
  selectedJobSetIndex.value = 0
  selectedJobId.value = payload.value?.runs[index]?.jobSets[0]?.jobs[0]?.jobId ?? null
  void loadSelectedMutations()
}

function selectJobSet(index: number) {
  selectedJobSetIndex.value = index
  selectedJobId.value = selectedRun.value?.jobSets[index]?.jobs[0]?.jobId ?? null
  void loadSelectedMutations()
}

function selectJob(jobId: string) {
  selectedJobId.value = jobId
  void loadSelectedMutations()
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return 'Unknown run'
  return new Date(value).toLocaleString()
}

function formatCost(value: number | null | undefined): string {
  const amount = Number(value ?? 0)
  if (!Number.isFinite(amount) || amount <= 0) return '$0.00'
  if (amount < 0.01) return `$${amount.toFixed(4)}`
  return `$${amount.toFixed(2)}`
}

function jobKindLabel(job: ArchivedJob): string {
  return job.strategy === 'graph_management_session' ? 'GMA session' : 'Extraction job'
}

function jobKindVariant(job: ArchivedJob): 'secondary' | 'outline' {
  return job.strategy === 'graph_management_session' ? 'secondary' : 'outline'
}

watch(
  () => props.kgId,
  () => { void loadHistory() },
  { immediate: true },
)
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle class="flex items-center gap-2 text-base">
        <Archive class="size-4" />
        Graph Writes History
      </CardTitle>
      <CardDescription>
        Permanent history of graph writes from Graph Management Assistant sessions and extraction
        worker jobs, grouped by run and job set.
      </CardDescription>
    </CardHeader>
    <CardContent class="grid gap-4 xl:grid-cols-[260px_220px_minmax(0,1fr)]">
      <div v-if="loading" class="col-span-full flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 class="size-4 animate-spin" />
        Loading graph writes history...
      </div>
      <div v-else-if="error" class="col-span-full text-sm text-destructive">
        {{ error }}
        <Button class="mt-2" size="sm" variant="outline" @click="loadHistory">Retry</Button>
      </div>
      <div v-else-if="!payload?.runs.length" class="col-span-full text-sm text-muted-foreground">
        No archived graph writes yet. GMA sessions and extraction jobs that apply writes or incur
        assistant cost are archived automatically when sessions end or jobs complete.
      </div>
      <template v-else>
        <div class="rounded border">
          <div class="flex items-center justify-between border-b px-3 py-2">
            <p class="text-xs font-medium text-muted-foreground">Entries ({{ payload.archivedJobCount }})</p>
            <Button size="sm" variant="ghost" class="h-6 px-2 text-[10px]" @click="loadHistory">Refresh</Button>
          </div>
          <div class="max-h-80 space-y-1 overflow-auto p-2">
            <button
              v-for="(run, index) in payload.runs"
              :key="`${run.runStartedAt}-${index}`"
              type="button"
              class="w-full rounded-md border px-2 py-2 text-left text-xs transition hover:bg-muted/40"
              :class="index === selectedRunIndex ? 'border-primary bg-primary/5' : 'border-transparent'"
              @click="selectRun(index)"
            >
              <p class="font-medium">{{ formatWhen(run.runStartedAt) }}</p>
              <p class="text-[10px] text-muted-foreground">
                {{ run.jobCount }} entries · {{ run.writeOps }} writes · {{ formatCost(run.costUsd) }}
              </p>
            </button>
          </div>
        </div>

        <div class="rounded border">
          <div class="border-b px-3 py-2">
            <p class="text-xs font-medium text-muted-foreground">Job sets</p>
          </div>
          <div class="max-h-80 space-y-1 overflow-auto p-2">
            <button
              v-for="(set, index) in selectedRun?.jobSets || []"
              :key="set.jobSet"
              type="button"
              class="flex w-full items-center justify-between rounded-md border px-2 py-2 text-left text-xs transition hover:bg-muted/40"
              :class="index === selectedJobSetIndex ? 'border-primary bg-primary/5' : 'border-transparent'"
              @click="selectJobSet(index)"
            >
              <span class="font-medium leading-snug">{{ set.jobSet }}</span>
              <ChevronRight class="size-3 shrink-0 text-muted-foreground" />
            </button>
          </div>
        </div>

        <div class="space-y-3">
          <div class="rounded border">
            <div class="border-b px-3 py-2">
              <p class="text-xs font-medium text-muted-foreground">Jobs in {{ selectedJobSet?.jobSet }}</p>
            </div>
            <div class="max-h-48 space-y-1 overflow-auto p-2">
              <button
                v-for="job in selectedJobSet?.jobs || []"
                :key="job.jobId"
                type="button"
                class="w-full rounded-md border px-2 py-2 text-left text-[11px] transition hover:bg-muted/40"
                :class="job.jobId === selectedJobId ? 'border-primary bg-primary/5' : 'border-transparent'"
                @click="selectJob(job.jobId)"
              >
                <div class="flex items-center gap-2">
                  <Badge :variant="jobKindVariant(job)" class="text-[9px] px-1 py-0">
                    {{ jobKindLabel(job) }}
                  </Badge>
                  <p class="truncate font-mono">{{ job.jobId }}</p>
                </div>
                <p class="mt-1 text-[10px] text-muted-foreground">
                  {{ job.writeOps }} writes · {{ formatCost(job.costUsd) }}
                </p>
              </button>
            </div>
          </div>

          <div v-if="selectedJob" class="rounded border p-3 text-xs">
            <div class="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{{ selectedJob.status }}</Badge>
              <Badge :variant="jobKindVariant(selectedJob)">{{ jobKindLabel(selectedJob) }}</Badge>
              <span v-if="selectedJob.workerId" class="font-mono text-muted-foreground">{{ selectedJob.workerId }}</span>
            </div>
            <Separator class="my-2" />
            <div class="grid gap-1 text-muted-foreground sm:grid-cols-2">
              <p>{{ selectedJob.entitiesCreated }} entities created</p>
              <p>{{ selectedJob.entitiesModified }} entities modified</p>
              <p>{{ selectedJob.relationshipsCreated }} relationships created</p>
              <p>{{ selectedJob.relationshipsModified }} relationships modified</p>
              <p class="font-medium text-foreground sm:col-span-2">
                {{ selectedJob.writeOps }} total write ops · {{ formatCost(selectedJob.costUsd) }}
              </p>
            </div>
          </div>

          <div class="rounded border">
            <div class="border-b px-3 py-2">
              <p class="text-xs font-medium text-muted-foreground">Applied mutations (JSONL)</p>
            </div>
            <div v-if="mutationLoading" class="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground">
              <Loader2 class="size-3.5 animate-spin" />
              Loading mutations...
            </div>
            <pre
              v-else-if="mutationJsonl"
              class="max-h-64 overflow-auto p-3 font-mono text-[10px] leading-relaxed whitespace-pre-wrap break-all"
            >{{ mutationJsonl }}</pre>
            <p v-else class="px-3 py-4 text-xs text-muted-foreground">
              No stored mutation JSONL for this entry (token-only GMA session or no graph writes).
            </p>
          </div>
        </div>
      </template>
    </CardContent>
  </Card>
</template>
