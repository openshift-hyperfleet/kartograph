<script setup lang="ts">
import { computed } from 'vue'
import {
  AlertTriangle, CheckCircle2, Info, Loader2,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import type { ParsedOperation, ParseResult, OperationBreakdown } from '@/utils/mutationParser'
import { getBreakdown, operationSummary } from '@/utils/mutationParser'
import type { WorkerParseResult, LightParsedOperation } from '@/composables/useMutationWorker'

const MAX_PREVIEW_OPS = 200

const props = defineProps<{
  parseResult?: ParseResult
  workerResult?: WorkerParseResult | null
  parsing?: boolean
  parseTimeMs?: number
}>()

const emit = defineEmits<{
  (e: 'browseWarnings'): void
}>()

// ── Unified computed properties ────────────────────────────────────────────

const breakdown = computed<OperationBreakdown>(() => {
  if (props.workerResult) return props.workerResult.breakdown
  return props.parseResult ? getBreakdown(props.parseResult.operations) : { DEFINE: 0, CREATE: 0, UPDATE: 0, DELETE: 0, unknown: 0 }
})

const totalOps = computed(() => {
  if (props.workerResult) return props.workerResult.totalOps
  return props.parseResult?.operations.length ?? 0
})

const displayOps = computed<Array<ParsedOperation | LightParsedOperation>>(() => {
  if (props.workerResult) return props.workerResult.previewOps
  const ops = props.parseResult?.operations ?? []
  return ops.slice(0, MAX_PREVIEW_OPS)
})

const isPreviewCapped = computed(() => {
  if (props.workerResult) return props.workerResult.totalOps > props.workerResult.previewOps.length
  return (props.parseResult?.operations.length ?? 0) > MAX_PREVIEW_OPS
})

const parseErrors = computed(() => {
  if (props.workerResult) return props.workerResult.parseErrors
  return props.parseResult?.parseErrors ?? []
})

const hasWarnings = computed(() => {
  if (props.workerResult) return props.workerResult.hasWarnings
  return props.parseResult?.operations.some(op => op.warnings.length > 0) ?? false
})

const totalWarnings = computed(() => {
  if (props.workerResult) return props.workerResult.warningCount
  return props.parseResult?.operations.reduce((sum, op) => sum + op.warnings.length, 0) ?? 0
})

const opBadgeVariant: Record<string, string> = {
  DEFINE: 'outline',
  CREATE: 'default',
  UPDATE: 'secondary',
  DELETE: 'destructive',
}

/**
 * Compact summary for an operation — works for both ParsedOperation
 * and LightParsedOperation (which lacks operationSummary compatibility).
 */
function opSummary(op: ParsedOperation | LightParsedOperation): string {
  if ('raw' in op) return operationSummary(op as ParsedOperation)
  const parts: string[] = []
  if (op.type) parts.push(op.type)
  if (op.label) parts.push(`"${op.label}"`)
  if (op.id) parts.push(op.id)
  return parts.join(' ') || 'unknown'
}
</script>

<template>
  <Card v-if="totalOps > 0 || parseErrors.length > 0 || parsing">
    <CardHeader class="pb-3">
      <div class="flex items-center justify-between">
        <CardTitle class="text-sm font-medium">Operation Preview</CardTitle>
        <div class="flex items-center gap-2">
          <div v-if="parsing" class="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 class="size-3 animate-spin" />
            Parsing...
          </div>
          <template v-else>
            <Badge variant="secondary">
              {{ totalOps.toLocaleString() }} op{{ totalOps === 1 ? '' : 's' }}
            </Badge>
            <Badge
              v-if="totalWarnings > 0"
              variant="destructive"
              class="gap-1 cursor-pointer hover:opacity-80"
              @click="emit('browseWarnings')"
            >
              <AlertTriangle class="size-3" />
              {{ totalWarnings.toLocaleString() }}
            </Badge>
            <Badge
              v-else-if="totalOps > 0 && parseErrors.length === 0"
              variant="outline"
              class="gap-1 border-green-500/30 text-green-600 dark:text-green-400"
            >
              <CheckCircle2 class="size-3" />
              Valid
            </Badge>
          </template>
        </div>
      </div>
    </CardHeader>
    <CardContent class="space-y-3">
      <!-- Breakdown by type -->
      <div
        v-if="totalOps > 0"
        class="flex flex-wrap gap-2"
      >
        <Badge
          v-if="breakdown.DEFINE > 0"
          variant="outline"
          class="gap-1"
        >
          DEFINE
          <span class="font-mono">{{ breakdown.DEFINE.toLocaleString() }}</span>
        </Badge>
        <Badge
          v-if="breakdown.CREATE > 0"
          class="gap-1"
        >
          CREATE
          <span class="font-mono">{{ breakdown.CREATE.toLocaleString() }}</span>
        </Badge>
        <Badge
          v-if="breakdown.UPDATE > 0"
          variant="secondary"
          class="gap-1"
        >
          UPDATE
          <span class="font-mono">{{ breakdown.UPDATE.toLocaleString() }}</span>
        </Badge>
        <Badge
          v-if="breakdown.DELETE > 0"
          variant="destructive"
          class="gap-1"
        >
          DELETE
          <span class="font-mono">{{ breakdown.DELETE.toLocaleString() }}</span>
        </Badge>
        <Badge
          v-if="breakdown.unknown > 0"
          variant="destructive"
          class="gap-1"
        >
          UNKNOWN
          <span class="font-mono">{{ breakdown.unknown.toLocaleString() }}</span>
        </Badge>
      </div>

      <!-- Parse errors -->
      <div v-if="parseErrors.length > 0" class="space-y-1">
        <div
          v-for="(error, idx) in parseErrors.slice(0, 20)"
          :key="'pe-' + idx"
          class="flex items-start gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive"
        >
          <AlertTriangle class="mt-0.5 size-3 shrink-0" />
          <span>{{ error }}</span>
        </div>
        <p v-if="parseErrors.length > 20" class="text-xs text-muted-foreground">
          ...and {{ parseErrors.length - 20 }} more errors
        </p>
      </div>

      <Separator v-if="totalOps > 0" />

      <!-- Operation summary rows -->
      <div
        v-if="displayOps.length > 0"
        class="max-h-[240px] space-y-1 overflow-y-auto"
      >
        <div
          v-for="op in displayOps"
          :key="op.index"
          class="flex items-start gap-2 rounded-md px-2 py-1.5 text-xs"
          :class="op.warnings.length > 0 ? 'bg-yellow-500/10' : 'bg-muted/50'"
        >
          <!-- Op badge -->
          <Badge
            :variant="(op.op ? opBadgeVariant[op.op] : 'destructive') as any"
            class="shrink-0 text-[10px] uppercase"
          >
            {{ op.op || '??' }}
          </Badge>

          <!-- Summary -->
          <div class="min-w-0 flex-1">
            <span class="font-mono text-muted-foreground">{{ opSummary(op) }}</span>
            <!-- Warnings -->
            <div
              v-if="op.warnings.length > 0"
              class="mt-0.5 space-y-0.5"
            >
              <div
                v-for="(warn, wIdx) in op.warnings"
                :key="wIdx"
                class="flex items-start gap-1 text-yellow-600 dark:text-yellow-400"
              >
                <Info class="mt-0.5 size-3 shrink-0" />
                <span>{{ warn }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Capped preview notice -->
        <div
          v-if="isPreviewCapped"
          class="flex items-center justify-center gap-2 rounded-md bg-muted/50 px-2 py-2 text-xs text-muted-foreground"
        >
          <Info class="size-3 shrink-0" />
          Showing {{ displayOps.length.toLocaleString() }} of {{ totalOps.toLocaleString() }} operations
        </div>
      </div>

      <!-- Parse time (worker mode only) -->
      <p v-if="parseTimeMs && !parsing" class="text-xs text-muted-foreground">
        Analyzed in {{ parseTimeMs.toFixed(0) }}ms
      </p>
    </CardContent>
  </Card>
</template>
