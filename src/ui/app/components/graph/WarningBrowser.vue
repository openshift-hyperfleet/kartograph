<script setup lang="ts">
import { ref, computed } from 'vue'
import { AlertTriangle, Save, X } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import type { LightParsedOperation, WorkerParseResult } from '@/composables/useMutationWorker'
import type { ParseResult, ParsedOperation } from '@/utils/mutationParser'

const props = defineProps<{
  workerResult?: WorkerParseResult | null
  parseResult?: ParseResult
  editorContent: string
}>()

const emit = defineEmits<{
  (e: 'update:editorContent', value: string): void
}>()

// ── Warning collection ──────────────────────────────────────────────────────

interface WarningEntry {
  opIndex: number
  op: string
  lineStart: number
  message: string
}

const warnings = computed<WarningEntry[]>(() => {
  const entries: WarningEntry[] = []

  if (props.workerResult) {
    for (const op of props.workerResult.previewOps) {
      for (const msg of op.warnings) {
        entries.push({
          opIndex: op.index,
          op: op.op ?? '??',
          lineStart: op.lineStart,
          message: msg,
        })
      }
    }
  } else if (props.parseResult) {
    for (const op of props.parseResult.operations) {
      for (const msg of op.warnings) {
        entries.push({
          opIndex: op.index,
          op: op.op ?? '??',
          lineStart: op.lineStart,
          message: msg,
        })
      }
    }
  }

  return entries
})

const previewWarningCount = computed(() => warnings.value.length)

const totalWarningCount = computed(() => {
  if (props.workerResult) return props.workerResult.warningCount
  return previewWarningCount.value
})

const remainingWarnings = computed(() => {
  return totalWarningCount.value - previewWarningCount.value
})

// ── Line editor dialog ──────────────────────────────────────────────────────

const editDialogOpen = ref(false)
const editingWarning = ref<WarningEntry | null>(null)
const editLineContent = ref('')

const opBadgeVariant: Record<string, string> = {
  DEFINE: 'outline',
  CREATE: 'default',
  UPDATE: 'secondary',
  DELETE: 'destructive',
}

function openLineEditor(warning: WarningEntry) {
  editingWarning.value = warning
  const lines = props.editorContent.split('\n')
  editLineContent.value = lines[warning.lineStart] ?? ''
  editDialogOpen.value = true
}

function saveLineEdit() {
  if (!editingWarning.value) return

  const lines = props.editorContent.split('\n')
  lines[editingWarning.value.lineStart] = editLineContent.value
  emit('update:editorContent', lines.join('\n'))
  editDialogOpen.value = false
  editingWarning.value = null
}

function cancelEdit() {
  editDialogOpen.value = false
  editingWarning.value = null
}
</script>

<template>
  <div class="space-y-2">
    <!-- Warning list -->
    <div class="max-h-[320px] space-y-1 overflow-y-auto">
      <div
        v-for="(warn, idx) in warnings"
        :key="idx"
        class="flex items-start gap-2 rounded-md bg-yellow-500/10 px-2.5 py-1.5 text-xs cursor-pointer hover:bg-yellow-500/20 transition-colors"
        role="button"
        tabindex="0"
        @click="openLineEditor(warn)"
        @keydown.enter="openLineEditor(warn)"
      >
        <!-- Line number -->
        <span class="shrink-0 font-mono text-muted-foreground w-10 text-right">
          L{{ warn.lineStart + 1 }}
        </span>

        <!-- Op badge -->
        <Badge
          :variant="(opBadgeVariant[warn.op] ?? 'destructive') as any"
          class="shrink-0 text-[10px] uppercase"
        >
          {{ warn.op }}
        </Badge>

        <!-- Warning message -->
        <span class="text-yellow-600 dark:text-yellow-400 min-w-0 flex-1">
          {{ warn.message }}
        </span>
      </div>
    </div>

    <!-- Remaining warnings summary -->
    <div
      v-if="remainingWarnings > 0"
      class="flex items-center gap-2 rounded-md bg-muted/50 px-2.5 py-2 text-xs text-muted-foreground"
    >
      <AlertTriangle class="size-3 shrink-0" />
      {{ remainingWarnings.toLocaleString() }} more warning{{ remainingWarnings === 1 ? '' : 's' }} in remaining operations (beyond preview window)
    </div>

    <p v-if="warnings.length === 0" class="text-xs text-muted-foreground py-2 text-center">
      No warnings found in preview operations.
    </p>
  </div>

  <!-- Line editor dialog -->
  <Dialog v-model:open="editDialogOpen">
    <DialogContent class="sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          Edit Line {{ editingWarning ? editingWarning.lineStart + 1 : '' }}
          <Badge
            v-if="editingWarning"
            :variant="(opBadgeVariant[editingWarning.op] ?? 'destructive') as any"
            class="text-[10px] uppercase"
          >
            {{ editingWarning.op }}
          </Badge>
        </DialogTitle>
        <DialogDescription>
          <span v-if="editingWarning" class="text-yellow-600 dark:text-yellow-400">
            {{ editingWarning.message }}
          </span>
        </DialogDescription>
      </DialogHeader>

      <Separator />

      <div class="space-y-2">
        <label class="text-sm font-medium">Line content</label>
        <textarea
          v-model="editLineContent"
          class="w-full min-h-[120px] rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          spellcheck="false"
        />
      </div>

      <DialogFooter>
        <Button variant="outline" @click="cancelEdit">
          <X class="mr-2 size-4" />
          Cancel
        </Button>
        <Button @click="saveLineEdit">
          <Save class="mr-2 size-4" />
          Save
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
