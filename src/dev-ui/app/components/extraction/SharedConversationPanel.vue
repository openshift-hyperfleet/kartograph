<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  captureScrollPositions,
  isScrollNearBottom,
  restoreScrollPositions,
} from '@/composables/useScrollPositionPreserve'
import DOMPurify from 'isomorphic-dompurify'
import { marked } from 'marked'
import { Bot, Loader2, RefreshCw, RotateCcw, Send, Sparkles, User } from 'lucide-vue-next'
import {
  normalizeThinkingActivityLines,
  THINKING_DISPLAY_LINE_COUNT,
} from '@/utils/thinkingActivityLines'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
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

interface ConversationEntry {
  role?: string
  content?: string
  message?: string
}

interface ConversationSession {
  message_history: ConversationEntry[]
  runtime_context: Record<string, unknown>
}

const props = withDefaults(defineProps<{
  modeLabel: string
  session: ConversationSession | null
  loading?: boolean
  clearing?: boolean
  sending?: boolean
  preparingRuntime?: boolean
  draftMessage?: string
  activityLines?: string[]
  inputPlaceholder?: string
  sessionStatusLabel?: string
  inputDisabled?: boolean
  inputDisabledReason?: string | null
  forbidden?: boolean
  forbiddenReason?: string | null
  title?: string
  description?: string
  footerHint?: string
}>(), {
  loading: false,
  clearing: false,
  sending: false,
  preparingRuntime: false,
  draftMessage: '',
  activityLines: () => [],
  inputPlaceholder: 'Describe what you want to do in this graph management session…',
  sessionStatusLabel: 'No active session',
  inputDisabled: false,
  inputDisabledReason: null,
  forbidden: false,
  forbiddenReason: null,
  title: 'Graph Management Assistant',
  description:
    'Design and refine schema readiness, validation, and extraction operations for this knowledge graph. Use the assistant below to drive workspace changes.',
  footerHint:
    'Use Schema & artifacts and Session pointers below to inspect workspace state; send notes or questions here.',
})

const emit = defineEmits<{
  refresh: []
  clearChat: []
  sendMessage: [message: string]
  'update:draftMessage': [value: string]
}>()

const clearConfirmOpen = ref(false)
const chatScrollRef = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const composerInputId = 'graph-management-chat-input'
const stickToBottom = ref(true)
const trackedMessageCount = ref(0)

marked.setOptions({ gfm: true, breaks: true })

const messageHistory = computed(() => props.session?.message_history ?? [])

const showInitialConversationLoading = computed(
  () => props.loading && messageHistory.value.length === 0,
)

const showConversationRefreshIndicator = computed(
  () => props.loading && messageHistory.value.length > 0,
)

const composerBlocked = computed(
  () => props.loading || props.clearing || props.inputDisabled || props.forbidden,
)

const chatSendDisabled = computed(
  () => composerBlocked.value || props.sending || !props.draftMessage.trim(),
)

const sendDisabledReason = computed(() => {
  if (props.sending) {
    return 'Wait for the assistant to finish this turn before sending.'
  }
  return props.inputDisabledReason ?? undefined
})

const showRuntimeActivity = computed(
  () => props.preparingRuntime || props.sending,
)

const runtimeActivityTitle = computed(() =>
  props.preparingRuntime && !props.sending
    ? 'Starting assistant container…'
    : 'Thinking...',
)

const thinkingDisplayLines = computed(() =>
  normalizeThinkingActivityLines(props.activityLines, THINKING_DISPLAY_LINE_COUNT),
)

function isUserRole(role: string | undefined): boolean {
  return role === 'user' || role === 'human'
}

function messageText(entry: ConversationEntry): string {
  return entry.content ?? entry.message ?? '(empty)'
}

function scrollToBottom(force = false) {
  const el = chatScrollRef.value
  if (!el) return
  if (!force && !stickToBottom.value && !isScrollNearBottom(el)) return
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const target = chatScrollRef.value
      if (target) target.scrollTop = target.scrollHeight
    })
  })
}

function onChatScroll() {
  const el = chatScrollRef.value
  if (!el) return
  stickToBottom.value = isScrollNearBottom(el)
}

function adjustTextareaHeight() {
  const el = textareaRef.value
  if (!el) return
  const lh = parseFloat(getComputedStyle(el).lineHeight)
  const line = Number.isFinite(lh) && lh > 0 ? lh : 21
  const minH = Math.round(line * 2.5)
  el.style.height = '0'
  el.style.height = `${Math.max(el.scrollHeight, minH)}px`
  el.style.overflowY = 'hidden'
}

function onComposerInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:draftMessage', target.value)
  adjustTextareaHeight()
}

function handleComposerEnter(event: KeyboardEvent) {
  if (event.shiftKey) return
  if (chatSendDisabled.value) return
  event.preventDefault()
  sendDraftMessage()
}

function renderAssistantMarkdown(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) return ''
  const raw = marked.parse(trimmed, { async: false }) as string
  return DOMPurify.sanitize(raw, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target', 'rel', 'class'],
  })
}

function confirmClearChat() {
  clearConfirmOpen.value = false
  emit('clearChat')
}

function sendDraftMessage() {
  const trimmed = props.draftMessage.trim()
  if (!trimmed || chatSendDisabled.value) return
  stickToBottom.value = true
  emit('sendMessage', trimmed)
  emit('update:draftMessage', '')
  void nextTick(() => {
    adjustTextareaHeight()
    scrollToBottom(true)
  })
}

let sessionScrollSnapshot: ReturnType<typeof captureScrollPositions> | null = null

watch(
  () => props.session,
  () => {
    sessionScrollSnapshot = captureScrollPositions([chatScrollRef.value])
  },
  { deep: true, flush: 'sync' },
)

watch(
  () => props.session,
  async (session) => {
    const nextCount = session?.message_history?.length ?? 0
    const grew = nextCount > trackedMessageCount.value
    trackedMessageCount.value = nextCount
    await nextTick()
    if (grew && (stickToBottom.value || props.sending)) {
      scrollToBottom(true)
      return
    }
    if (sessionScrollSnapshot) {
      restoreScrollPositions(sessionScrollSnapshot)
      sessionScrollSnapshot = null
    }
  },
  { deep: true, flush: 'post' },
)

watch(
  () => [props.activityLines, props.sending, props.loading, showRuntimeActivity.value] as const,
  async () => {
    const snapshot = captureScrollPositions([chatScrollRef.value])
    await nextTick()
    if (props.sending || stickToBottom.value) {
      scrollToBottom(props.sending)
      return
    }
    restoreScrollPositions(snapshot)
  },
  { deep: true, flush: 'post' },
)

watch(
  () => props.draftMessage,
  () => {
    void nextTick(() => adjustTextareaHeight())
  },
)

watch(
  () => props.loading,
  (busy) => {
    if (!busy) void nextTick(() => adjustTextareaHeight())
  },
)

onMounted(() => {
  trackedMessageCount.value = messageHistory.value.length
  void nextTick(() => {
    adjustTextareaHeight()
    scrollToBottom(true)
  })
})
</script>

<template>
  <Card
    id="graph-management-design-assistant"
    class="overflow-hidden border-2 border-primary/25 shadow-md scroll-mt-6"
  >
    <CardHeader class="border-b bg-muted/30 pb-4">
      <div class="flex flex-wrap items-start gap-3">
        <div
          class="flex size-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-primary"
        >
          <Sparkles class="size-5" aria-hidden="true" />
        </div>
        <div class="min-w-0 flex-1 space-y-1">
          <CardTitle class="text-lg leading-tight">{{ title }}</CardTitle>
          <CardDescription class="text-sm leading-relaxed">
            {{ description }}
          </CardDescription>
          <p class="text-xs text-muted-foreground">
            Mode:
            <span class="font-medium text-foreground">{{ modeLabel }}</span>
            · Session:
            <span class="font-medium text-foreground">{{ sessionStatusLabel }}</span>
          </p>
        </div>
        <div class="flex shrink-0 flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            class="gap-1.5"
            :disabled="loading"
            @click="emit('refresh')"
          >
            <RefreshCw class="size-4" />
            Resume session
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            class="gap-1.5"
            :disabled="clearing || loading || forbidden"
            @click="clearConfirmOpen = true"
          >
            <Loader2 v-if="clearing" class="size-4 animate-spin" />
            <RotateCcw v-else class="size-4" />
            Clear chat
          </Button>
        </div>
      </div>
    </CardHeader>

    <CardContent class="p-0">
      <div
        v-if="forbidden"
        class="border-b border-destructive/40 bg-destructive/5 px-4 py-3 text-xs text-destructive sm:px-6"
        role="alert"
      >
        {{ forbiddenReason ?? 'You do not have permission to use graph management chat for this knowledge graph.' }}
      </div>

      <div
        ref="chatScrollRef"
        class="min-h-[14rem] max-h-[min(32rem,60vh)] space-y-4 overflow-y-auto bg-muted/10 px-4 py-4 sm:px-6"
        @scroll.passive="onChatScroll"
      >
        <div
          v-if="showInitialConversationLoading"
          class="flex flex-col items-center justify-center gap-3 py-12 text-muted-foreground"
          aria-busy="true"
          aria-live="polite"
        >
          <Loader2 class="size-8 shrink-0 animate-spin" />
          <p class="text-center text-sm text-foreground/80">Loading conversation session…</p>
        </div>
        <template v-else>
          <div
            v-if="showConversationRefreshIndicator"
            class="flex items-center justify-center gap-2 py-1 text-xs text-muted-foreground"
            aria-busy="true"
            aria-live="polite"
          >
            <Loader2 class="size-3.5 shrink-0 animate-spin" />
            <span>Refreshing conversation…</span>
          </div>
          <div
            v-for="(entry, idx) in messageHistory"
            :key="`msg-${idx}-${entry.role ?? 'unknown'}`"
            class="flex gap-3"
            :class="isUserRole(entry.role) ? 'flex-row-reverse' : ''"
          >
            <div
              class="flex size-9 shrink-0 items-center justify-center rounded-full border bg-card"
              :class="
                isUserRole(entry.role)
                  ? 'border-primary/35 bg-primary/12 text-primary'
                  : 'border-slate-300/60 bg-slate-100/80 text-slate-600 dark:border-slate-700/60 dark:bg-slate-900/70 dark:text-slate-300'
              "
            >
              <User v-if="isUserRole(entry.role)" class="size-4 text-primary" />
              <Bot v-else class="size-4 text-muted-foreground" />
            </div>
            <div
              class="min-w-0 max-w-[min(100%,42rem)] rounded-2xl border px-4 py-3 text-sm leading-relaxed shadow-sm"
              :class="
                isUserRole(entry.role)
                  ? 'border-primary/25 bg-primary/[0.07] text-foreground shadow-primary/5'
                  : 'border-slate-300/65 bg-slate-50/95 text-foreground shadow-slate-300/20 dark:border-slate-700/70 dark:bg-slate-900/65 dark:shadow-black/20'
              "
            >
              <p v-if="isUserRole(entry.role)" class="whitespace-pre-wrap break-words">
                {{ messageText(entry) }}
              </p>
              <div
                v-else
                class="chat-md space-y-1 break-words [&_a]:break-all [&_code]:break-all"
                v-html="renderAssistantMarkdown(messageText(entry))"
              />
            </div>
          </div>

          <div
            v-if="showRuntimeActivity"
            class="flex gap-3 text-muted-foreground"
            aria-live="polite"
            aria-busy="true"
          >
            <div class="flex size-9 shrink-0 items-center justify-center rounded-full border bg-card">
              <Bot class="size-4" />
            </div>
            <div
              class="min-w-0 max-w-[min(100%,42rem)] flex-1 overflow-hidden rounded-2xl border border-dashed border-primary/25 bg-gradient-to-b from-slate-50/90 via-card to-card px-4 py-3 text-sm shadow-sm dark:from-slate-900/65"
            >
              <div class="mb-2 flex items-center gap-2 text-foreground">
                <Loader2 class="size-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
                <span class="font-medium tracking-tight">{{ runtimeActivityTitle }}</span>
              </div>
              <ol class="m-0 max-h-48 list-none space-y-2 overflow-y-auto border-l-2 border-primary/25 pl-3">
                <li
                  v-for="(line, lineIdx) in thinkingDisplayLines"
                  :key="`${lineIdx}-${line || 'empty'}`"
                  class="flex gap-2 text-xs leading-snug"
                >
                  <span
                    class="w-4 shrink-0 select-none pt-0.5 text-center font-mono text-xs text-primary/45"
                    aria-hidden="true"
                  >
                    –
                  </span>
                  <span
                    class="min-w-0 flex-1 break-words font-mono text-[13px]"
                    :class="line ? 'text-foreground/90' : 'text-muted-foreground/35'"
                  >
                    {{ line || '—' }}
                  </span>
                </li>
              </ol>
            </div>
          </div>

          <p
            v-if="messageHistory.length === 0 && !showRuntimeActivity"
            class="py-8 text-center text-sm text-muted-foreground"
          >
            No messages yet. Send a prompt or use validate/transition actions to drive session activity.
          </p>
        </template>
      </div>

      <div class="border-t bg-muted/20 p-4 sm:p-6">
        <label class="sr-only" :for="composerInputId">Message to graph management assistant</label>
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end">
          <textarea
            :id="composerInputId"
            ref="textareaRef"
            :value="draftMessage"
            rows="1"
            :disabled="composerBlocked"
            :placeholder="inputPlaceholder"
            class="w-full flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm leading-relaxed shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            @input="onComposerInput"
            @keydown.enter="handleComposerEnter"
          />
          <Button
            type="button"
            class="h-10 min-h-10 w-full shrink-0 sm:w-auto sm:px-6"
            :disabled="chatSendDisabled"
            :title="sendDisabledReason"
            @click="sendDraftMessage"
          >
            <Loader2 v-if="sending" class="size-4 animate-spin" />
            <template v-else>
              <Send class="size-4 sm:mr-2" />
              <span class="hidden sm:inline">Send</span>
            </template>
          </Button>
        </div>
        <p class="mt-2 text-xs text-muted-foreground">
          {{ footerHint }}
          <span class="text-muted-foreground/90"> · Enter to send, Shift+Enter for a new line.</span>
        </p>
      </div>
    </CardContent>
  </Card>

  <AlertDialog v-model:open="clearConfirmOpen">
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>Clear conversation?</AlertDialogTitle>
        <AlertDialogDescription>
          This starts a fresh server-side session timeline while keeping the selected graph management mode.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel>Cancel</AlertDialogCancel>
        <AlertDialogAction @click="confirmClearChat">
          Clear chat
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
</template>
