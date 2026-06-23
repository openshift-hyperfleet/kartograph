<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'

const props = defineProps<{
  kgId: string
  jobId: string | null
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const { apiFetch } = useApiClient()

interface ActivityMessage {
  timestamp: string
  kind: string
  text: string
}

interface JobActivityPayload {
  jobId: string
  status: string
  log: string
  messages: ActivityMessage[]
  detail: {
    jobSet: string
    workerId: string | null
    inputTokens: number
    outputTokens: number
    cacheReadTokens: number
    cacheCreationTokens: number
    costUsd: number
    entitiesCreated: number
    entitiesModified: number
    relationshipsCreated: number
    relationshipsModified: number
    writeOps: number
    instanceCount: number
    fileCount: number
    errorMessage: string | null
    targetInstances: Array<{ slug: string; entity_type: string }>
    targetFiles: Array<{ path: string; repository_folder: string }>
  }
}

const loading = ref(false)
const error = ref<string | null>(null)
const payload = ref<JobActivityPayload | null>(null)
const logContainer = ref<HTMLElement | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

const isLive = computed(() => payload.value?.status === 'in_progress')
const displayMessages = computed(() => payload.value?.messages || [])

async function loadActivity() {
  if (!props.jobId) return
  if (!payload.value) loading.value = true
  error.value = null
  try {
    payload.value = await apiFetch<JobActivityPayload>(
      `/management/knowledge-graphs/${encodeURIComponent(props.kgId)}/extraction-jobs/jobs/${encodeURIComponent(props.jobId)}/activity`,
    )
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load activity'
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => { void loadActivity() }, 1000)
}

function stopPolling() {
  if (!pollTimer) return
  clearInterval(pollTimer)
  pollTimer = null
}

watch(
  () => [props.open, props.jobId] as const,
  ([open, jobId]) => {
    if (!open || !jobId) {
      stopPolling()
      payload.value = null
      return
    }
    void loadActivity()
    startPolling()
  },
  { immediate: true },
)

watch(
  () => displayMessages.value.length,
  async () => {
    await nextTick()
    const el = logContainer.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

onUnmounted(stopPolling)

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

function messageLabel(kind: string): string {
  switch (kind) {
    case 'thought':
      return 'Thinking'
    case 'tool':
      return 'Tool'
    case 'system':
      return 'System'
    case 'error':
      return 'Error'
    case 'success':
      return 'Done'
    default:
      return 'Info'
  }
}

function messageClass(kind: string): string {
  switch (kind) {
    case 'thought':
      return 'border-l-primary/60 bg-primary/5'
    case 'tool':
      return 'border-l-amber-500/60 bg-amber-500/5'
    case 'system':
      return 'border-l-muted-foreground/40 bg-muted/30'
    case 'error':
      return 'border-l-destructive/60 bg-destructive/5 text-destructive'
    case 'success':
      return 'border-l-green-600/60 bg-green-600/5'
    default:
      return 'border-l-border bg-muted/10'
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="flex max-h-[90dvh] flex-col gap-0 overflow-hidden sm:max-w-4xl">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          Watch extraction job
          <Badge v-if="payload" variant="outline" class="font-mono text-[10px]">
            {{ payload.status }}
          </Badge>
          <Loader2 v-if="isLive" class="size-3.5 animate-spin text-muted-foreground" />
        </DialogTitle>
        <DialogDescription class="font-mono text-xs">
          {{ jobId || '—' }}
        </DialogDescription>
      </DialogHeader>

      <div v-if="loading && !payload" class="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 class="size-4 animate-spin" />
        Loading activity...
      </div>
      <div v-else-if="error" class="py-4 text-sm text-destructive">{{ error }}</div>
      <template v-else-if="payload">
        <div class="grid min-h-0 flex-1 gap-4 py-3 sm:grid-cols-[minmax(0,1fr)_220px]">
          <div class="flex min-h-0 flex-col gap-2">
            <p class="text-xs font-medium text-foreground/90">
              Agent activity
              <span v-if="isLive" class="text-muted-foreground">(live, refreshes every 1s)</span>
            </p>
            <div
              ref="logContainer"
              class="min-h-[40dvh] max-h-[60dvh] flex-1 space-y-2 overflow-y-auto rounded-lg border bg-muted/10 p-2"
            >
              <div
                v-if="displayMessages.length === 0"
                class="p-3 text-xs text-muted-foreground"
              >
                Waiting for agent output. Thoughts and tool calls appear here as the worker runs.
              </div>
              <div
                v-for="(message, index) in displayMessages"
                :key="`${message.timestamp}-${index}-${message.text.slice(0, 24)}`"
                class="rounded-md border-l-2 px-2 py-1.5 text-[11px] leading-relaxed"
                :class="messageClass(message.kind)"
              >
                <div class="mb-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                  <span class="font-medium uppercase tracking-wide">{{ messageLabel(message.kind) }}</span>
                  <span v-if="message.timestamp" class="font-mono">{{ message.timestamp }}</span>
                </div>
                <p class="whitespace-pre-wrap break-words">{{ message.text }}</p>
              </div>
            </div>
          </div>

          <div class="space-y-3 overflow-y-auto text-xs">
            <div>
              <p class="font-medium">{{ payload.detail.jobSet }}</p>
              <p v-if="payload.detail.workerId" class="font-mono text-muted-foreground">
                {{ payload.detail.workerId }}
              </p>
            </div>

            <Separator />

            <div class="space-y-1 text-muted-foreground">
              <p>Tokens: {{ formatCompactNumber(payload.detail.inputTokens) }} in / {{ formatCompactNumber(payload.detail.outputTokens) }} out</p>
              <p v-if="payload.detail.cacheReadTokens || payload.detail.cacheCreationTokens">
                Cache: {{ formatCompactNumber(payload.detail.cacheReadTokens) }} read / {{ formatCompactNumber(payload.detail.cacheCreationTokens) }} write
              </p>
              <p>Cost: ${{ payload.detail.costUsd.toFixed(4) }}</p>
            </div>

            <div class="space-y-1 text-muted-foreground">
              <p class="font-medium text-foreground">Graph writes</p>
              <p>{{ payload.detail.entitiesCreated }} entities created</p>
              <p>{{ payload.detail.entitiesModified }} entities modified</p>
              <p>{{ payload.detail.relationshipsCreated }} relationships created</p>
              <p v-if="payload.detail.relationshipsModified">
                {{ payload.detail.relationshipsModified }} relationships modified
              </p>
              <p class="font-medium text-foreground">{{ payload.detail.writeOps }} total write ops</p>
            </div>

            <div v-if="payload.detail.instanceCount" class="space-y-1">
              <p class="font-medium">Target instances ({{ payload.detail.instanceCount }})</p>
              <p
                v-for="instance in payload.detail.targetInstances"
                :key="`${instance.entity_type}:${instance.slug}`"
                class="font-mono text-[10px] text-muted-foreground"
              >
                {{ instance.entity_type }}: {{ instance.slug }}
              </p>
            </div>

            <p v-if="payload.detail.errorMessage" class="text-destructive">
              {{ payload.detail.errorMessage }}
            </p>
          </div>
        </div>
      </template>
    </DialogContent>
  </Dialog>
</template>
