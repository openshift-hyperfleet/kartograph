<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Loader2, RefreshCw, SendHorizontal } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
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
import { handleChatInputKeydown } from '@/utils/kgManageState'

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
  draftMessage?: string
  activityLines?: string[]
  inputPlaceholder?: string
  sessionStatusLabel?: string
  inputDisabled?: boolean
  inputDisabledReason?: string | null
  forbidden?: boolean
  forbiddenReason?: string | null
}>(), {
  loading: false,
  clearing: false,
  sending: false,
  draftMessage: '',
  activityLines: () => [],
  inputPlaceholder: 'Describe what you want to do in this graph management session…',
  sessionStatusLabel: 'No active session',
  inputDisabled: false,
  inputDisabledReason: null,
  forbidden: false,
  forbiddenReason: null,
})

const emit = defineEmits<{
  refresh: []
  clearChat: []
  sendMessage: [message: string]
  'update:draftMessage': [value: string]
}>()

const clearConfirmOpen = ref(false)
const timelineRef = ref<HTMLElement | null>(null)

const messageHistory = computed(() => props.session?.message_history ?? [])
const activityTimeline = computed(() => props.activityLines)

const combinedTimelineLength = computed(
  () => messageHistory.value.length + activityTimeline.value.length,
)

const chatInputDisabled = computed(
  () => props.loading || props.clearing || props.sending || props.inputDisabled || props.forbidden,
)

const chatInputHelp = computed(() => {
  if (props.forbidden) {
    return props.forbiddenReason ?? 'Chat is unavailable because you lack permission for this action.'
  }
  if (props.inputDisabledReason) return props.inputDisabledReason
  return 'Press Enter to send. Shift+Enter adds a new line.'
})

watch(combinedTimelineLength, async () => {
  await nextTick()
  if (timelineRef.value) {
    timelineRef.value.scrollTop = timelineRef.value.scrollHeight
  }
})

function confirmClearChat() {
  clearConfirmOpen.value = false
  emit('clearChat')
}

function sendDraftMessage() {
  const trimmed = props.draftMessage.trim()
  if (!trimmed || chatInputDisabled.value) return
  emit('sendMessage', trimmed)
  emit('update:draftMessage', '')
}

function onChatInputKeydown(event: KeyboardEvent) {
  handleChatInputKeydown(event, sendDraftMessage)
}
</script>

<template>
  <Card>
    <CardHeader>
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div>
          <CardTitle class="text-base">Conversation</CardTitle>
          <CardDescription>
            Shared conversation feed for {{ modeLabel }} with server-side session resume.
          </CardDescription>
        </div>
        <p class="text-xs text-muted-foreground">
          Session: <span class="font-medium text-foreground">{{ sessionStatusLabel }}</span>
        </p>
      </div>
    </CardHeader>
    <CardContent class="space-y-3">
      <div
        v-if="forbidden"
        class="rounded border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive"
        role="alert"
      >
        {{ forbiddenReason ?? 'You do not have permission to use graph management chat for this knowledge graph.' }}
      </div>

      <div class="flex items-center justify-between">
        <p class="text-xs text-muted-foreground">No local cache: conversation state is server-side only.</p>
        <Button size="sm" variant="ghost" class="h-7 px-2 text-[11px]" :disabled="loading" @click="emit('refresh')">
          <RefreshCw class="mr-1 size-3.5" />
          Resume session
        </Button>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 class="size-3.5 animate-spin" />
        Loading active conversation session...
      </div>
      <div
        v-else
        ref="timelineRef"
        class="space-y-2 max-h-56 overflow-auto rounded border p-2"
      >
        <div
          v-for="(entry, idx) in messageHistory"
          :key="`msg-${idx}-${entry.role ?? 'unknown'}`"
          class="rounded px-2 py-1 text-xs"
          :class="entry.role === 'assistant' ? 'bg-muted' : 'bg-primary/10'"
        >
          <p class="mb-0.5 font-medium">{{ entry.role ?? 'system' }}</p>
          <p>{{ entry.content ?? entry.message ?? '(empty)' }}</p>
        </div>

        <div
          v-for="(line, idx) in activityTimeline"
          :key="`activity-${idx}`"
          class="rounded border border-dashed px-2 py-1 text-xs text-muted-foreground"
        >
          {{ line }}
        </div>

        <p
          v-if="messageHistory.length === 0 && activityTimeline.length === 0"
          class="text-xs text-muted-foreground"
        >
          No messages yet. Send a prompt or use validate/transition actions to drive session activity.
        </p>
      </div>

      <div class="space-y-2">
        <div class="flex items-start gap-2">
          <Textarea
            :model-value="draftMessage"
            :disabled="chatInputDisabled"
            :placeholder="inputPlaceholder"
            class="min-h-20"
            aria-label="Graph management chat input"
            @update:model-value="(value) => emit('update:draftMessage', value)"
            @keydown="onChatInputKeydown"
          />
          <Button
            variant="default"
            class="shrink-0"
            :disabled="chatInputDisabled || !draftMessage.trim()"
            :title="chatInputHelp"
            @click="sendDraftMessage"
          >
            <Loader2 v-if="sending" class="size-3.5 animate-spin" />
            <SendHorizontal v-else class="size-3.5" />
          </Button>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="text-[11px] text-muted-foreground">{{ chatInputHelp }}</p>
          <Button variant="outline" :disabled="clearing || loading || forbidden" @click="clearConfirmOpen = true">
            <Loader2 v-if="clearing" class="mr-1.5 size-3.5 animate-spin" />
            Clear chat
          </Button>
        </div>
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
