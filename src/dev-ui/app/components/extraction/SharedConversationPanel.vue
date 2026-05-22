<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
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
  draftMessage?: string
  activityLines?: string[]
  inputPlaceholder?: string
  sessionStatusLabel?: string
}>(), {
  loading: false,
  clearing: false,
  draftMessage: '',
  activityLines: () => [],
  inputPlaceholder: 'Describe what you want to do in this graph management session…',
  sessionStatusLabel: 'No active session',
})

const emit = defineEmits<{
  refresh: []
  clearChat: []
  'update:draftMessage': [value: string]
}>()

const clearConfirmOpen = ref(false)
const timelineRef = ref<HTMLElement | null>(null)

const messageHistory = computed(() => props.session?.message_history ?? [])
const activityTimeline = computed(() => props.activityLines)

const combinedTimelineLength = computed(
  () => messageHistory.value.length + activityTimeline.value.length,
)

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
          No messages yet. Use validate/transition actions to drive session activity.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Input
          :model-value="draftMessage"
          disabled
          :placeholder="inputPlaceholder"
          @update:model-value="(value) => emit('update:draftMessage', value)"
        />
        <Button variant="outline" :disabled="clearing || loading" @click="clearConfirmOpen = true">
          <Loader2 v-if="clearing" class="mr-1.5 size-3.5 animate-spin" />
          Clear chat
        </Button>
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
