<script setup lang="ts">
/**
 * LargeFileSummary
 *
 * Displays a read-only summary panel when a mutation file exceeds the 5 MB
 * large-file threshold.  Editing is intentionally disabled for large files to
 * prevent the browser from hanging on multi-MB JSONL content; users submit
 * directly from this panel.
 *
 * Spec: Mutations Console — File upload scenario
 * "files larger than 5 MB activate large-file mode: editing is disabled,
 *  a summary of operation counts is shown, and the user can submit directly"
 */
import { AlertTriangle, Loader2, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { WorkerParseResult } from '@/composables/useMutationWorker'

interface Props {
  /** Parse result from the Web Worker (null while parsing is in progress). */
  workerResult: WorkerParseResult | null
  /** True while the worker is still scanning the file. */
  parsing: boolean
  /** Milliseconds taken by the last worker parse (displayed after analysis). */
  parseTimeMs: number
  /** Size of the loaded content in megabytes (displayed in the header badge). */
  fileSizeMb: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  /** User clicked the Clear button to discard the large file. */
  'clear': []
  /** User clicked "Browse Warnings" — parent should open the warning browser. */
  'browse-warnings': []
}>()
</script>

<template>
  <Card>
    <CardHeader class="pb-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <CardTitle class="text-base">Large File Mode</CardTitle>
          <Badge variant="secondary">
            {{ props.fileSizeMb.toFixed(1) }} MB
          </Badge>
        </div>
        <Button variant="ghost" size="sm" @click="emit('clear')">
          <Trash2 class="mr-2 size-4" />
          Clear
        </Button>
      </div>
    </CardHeader>
    <CardContent class="space-y-3">
      <p class="text-sm text-muted-foreground">
        File too large for interactive editing. Review the summary below and submit directly.
      </p>

      <!-- Parsing indicator -->
      <div v-if="props.parsing" class="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 class="size-4 animate-spin" />
        Analyzing operations...
      </div>

      <!-- Breakdown badges -->
      <div v-else-if="props.workerResult" class="space-y-2">
        <div class="flex flex-wrap gap-2">
          <Badge variant="secondary">
            {{ props.workerResult.totalOps.toLocaleString() }} operations
          </Badge>
          <Badge v-if="props.workerResult.breakdown.DEFINE > 0" variant="outline" class="gap-1">
            DEFINE <span class="font-mono">{{ props.workerResult.breakdown.DEFINE.toLocaleString() }}</span>
          </Badge>
          <Badge v-if="props.workerResult.breakdown.CREATE > 0" class="gap-1">
            CREATE <span class="font-mono">{{ props.workerResult.breakdown.CREATE.toLocaleString() }}</span>
          </Badge>
          <Badge v-if="props.workerResult.breakdown.UPDATE > 0" variant="secondary" class="gap-1">
            UPDATE <span class="font-mono">{{ props.workerResult.breakdown.UPDATE.toLocaleString() }}</span>
          </Badge>
          <Badge v-if="props.workerResult.breakdown.DELETE > 0" variant="destructive" class="gap-1">
            DELETE <span class="font-mono">{{ props.workerResult.breakdown.DELETE.toLocaleString() }}</span>
          </Badge>
        </div>

        <div v-if="props.workerResult.warningCount > 0" class="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            class="gap-2 border-yellow-500/30 text-yellow-600 dark:text-yellow-400 hover:bg-yellow-500/10"
            @click="emit('browse-warnings')"
          >
            <AlertTriangle class="size-3.5" />
            Browse {{ props.workerResult.warningCount.toLocaleString() }} Warning{{ props.workerResult.warningCount === 1 ? '' : 's' }}
          </Button>
        </div>

        <div v-if="props.workerResult.parseErrors.length > 0" class="space-y-1">
          <div
            v-for="(error, idx) in props.workerResult.parseErrors.slice(0, 10)"
            :key="idx"
            class="flex items-start gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs"
          >
            <AlertTriangle class="mt-0.5 size-3 shrink-0 text-destructive" />
            <span class="font-mono">{{ error }}</span>
          </div>
          <p v-if="props.workerResult.parseErrors.length > 10" class="text-xs text-muted-foreground">
            ...and {{ props.workerResult.parseErrors.length - 10 }} more errors
          </p>
        </div>

        <p class="text-xs text-muted-foreground">
          Analyzed in {{ props.parseTimeMs.toFixed(0) }}ms
        </p>
      </div>
    </CardContent>
  </Card>
</template>
