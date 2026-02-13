<script setup lang="ts">
import { computed } from 'vue'
import {
  AlertTriangle, CheckCircle2, Info,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import type { ParsedOperation, ParseResult, OperationBreakdown } from '@/utils/mutationParser'
import { getBreakdown, operationSummary } from '@/utils/mutationParser'

const props = defineProps<{
  parseResult: ParseResult
}>()

const breakdown = computed<OperationBreakdown>(() =>
  getBreakdown(props.parseResult.operations),
)

const totalOps = computed(() => props.parseResult.operations.length)

const hasWarnings = computed(() =>
  props.parseResult.operations.some(op => op.warnings.length > 0),
)

const totalWarnings = computed(() =>
  props.parseResult.operations.reduce((sum, op) => sum + op.warnings.length, 0),
)

const opBadgeVariant: Record<string, string> = {
  DEFINE: 'outline',
  CREATE: 'default',
  UPDATE: 'secondary',
  DELETE: 'destructive',
}
</script>

<template>
  <Card v-if="totalOps > 0 || parseResult.parseErrors.length > 0">
    <CardHeader class="pb-3">
      <div class="flex items-center justify-between">
        <CardTitle class="text-sm font-medium">Operation Preview</CardTitle>
        <div class="flex items-center gap-2">
          <Badge variant="secondary">
            {{ totalOps }} op{{ totalOps === 1 ? '' : 's' }}
          </Badge>
          <Badge v-if="totalWarnings > 0" variant="destructive" class="gap-1">
            <AlertTriangle class="size-3" />
            {{ totalWarnings }}
          </Badge>
          <Badge
            v-else-if="totalOps > 0 && parseResult.parseErrors.length === 0"
            variant="outline"
            class="gap-1 border-green-500/30 text-green-600 dark:text-green-400"
          >
            <CheckCircle2 class="size-3" />
            Valid
          </Badge>
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
          <span class="font-mono">{{ breakdown.DEFINE }}</span>
        </Badge>
        <Badge
          v-if="breakdown.CREATE > 0"
          class="gap-1"
        >
          CREATE
          <span class="font-mono">{{ breakdown.CREATE }}</span>
        </Badge>
        <Badge
          v-if="breakdown.UPDATE > 0"
          variant="secondary"
          class="gap-1"
        >
          UPDATE
          <span class="font-mono">{{ breakdown.UPDATE }}</span>
        </Badge>
        <Badge
          v-if="breakdown.DELETE > 0"
          variant="destructive"
          class="gap-1"
        >
          DELETE
          <span class="font-mono">{{ breakdown.DELETE }}</span>
        </Badge>
        <Badge
          v-if="breakdown.unknown > 0"
          variant="destructive"
          class="gap-1"
        >
          UNKNOWN
          <span class="font-mono">{{ breakdown.unknown }}</span>
        </Badge>
      </div>

      <!-- Parse errors -->
      <div v-if="parseResult.parseErrors.length > 0" class="space-y-1">
        <div
          v-for="(error, idx) in parseResult.parseErrors"
          :key="'pe-' + idx"
          class="flex items-start gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive"
        >
          <AlertTriangle class="mt-0.5 size-3 shrink-0" />
          <span>{{ error }}</span>
        </div>
      </div>

      <Separator v-if="totalOps > 0" />

      <!-- Operation summary rows -->
      <div
        v-if="totalOps > 0"
        class="max-h-[240px] space-y-1 overflow-y-auto"
      >
        <div
          v-for="op in parseResult.operations"
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
            <span class="font-mono text-muted-foreground">{{ operationSummary(op) }}</span>
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
      </div>
    </CardContent>
  </Card>
</template>
