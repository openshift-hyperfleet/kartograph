<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Loader2, CheckCircle2, XCircle, Minus, Maximize2,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'

const { state, dismiss } = useMutationSubmission()

const minimized = ref(false)

const isVisible = computed(() => state.value.status !== 'idle')

const truncatedError = computed(() => {
  const err = state.value.error
  if (!err) return ''
  return err.length > 120 ? err.slice(0, 120) + '...' : err
})
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="translate-y-4 opacity-0 scale-95"
    enter-to-class="translate-y-0 opacity-100 scale-100"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="translate-y-0 opacity-100 scale-100"
    leave-to-class="translate-y-4 opacity-0 scale-95"
  >
    <div
      v-if="isVisible"
      class="fixed bottom-4 right-4 z-[90] w-80 rounded-lg border bg-card shadow-lg"
      :class="{
        'animate-pulse border-primary/50': state.status === 'submitting',
        'border-green-500/50': state.status === 'success',
        'border-destructive/50': state.status === 'failed',
      }"
    >
      <!-- Header bar — always visible -->
      <div
        class="flex items-center justify-between px-3 py-2"
        :class="minimized ? 'rounded-lg' : 'rounded-t-lg border-b'"
      >
        <div class="flex items-center gap-2 min-w-0">
          <!-- Status icon -->
          <Loader2
            v-if="state.status === 'submitting'"
            class="size-4 shrink-0 animate-spin text-primary"
          />
          <CheckCircle2
            v-else-if="state.status === 'success'"
            class="size-4 shrink-0 text-green-600 dark:text-green-400"
          />
          <XCircle
            v-else-if="state.status === 'failed'"
            class="size-4 shrink-0 text-destructive"
          />

          <!-- Title -->
          <span class="text-sm font-medium truncate">
            <template v-if="state.status === 'submitting'">
              Applying mutations...
            </template>
            <template v-else-if="state.status === 'success'">
              Mutations applied
            </template>
            <template v-else-if="state.status === 'failed'">
              Mutations failed
            </template>
          </span>

          <!-- Count badge -->
          <Badge variant="secondary" class="shrink-0 text-[10px]">
            {{ state.operationCount.toLocaleString() }}
          </Badge>
        </div>

        <div class="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            class="size-6"
            @click="minimized = !minimized"
          >
            <Minus v-if="!minimized" class="size-3" />
            <Maximize2 v-else class="size-3" />
          </Button>
          <Button
            v-if="state.status !== 'submitting'"
            variant="ghost"
            size="icon"
            class="size-6"
            @click="dismiss"
          >
            <XCircle class="size-3" />
          </Button>
        </div>
      </div>

      <!-- Body — hidden when minimized -->
      <div v-if="!minimized" class="px-3 py-2 space-y-1">
        <!-- Submitting state -->
        <template v-if="state.status === 'submitting'">
          <p class="text-xs text-muted-foreground">
            Applying {{ state.operationCount.toLocaleString() }} mutation{{ state.operationCount === 1 ? '' : 's' }}...
            <span class="font-mono">{{ state.elapsedSeconds }}s</span>
          </p>
        </template>

        <!-- Success state -->
        <template v-else-if="state.status === 'success' && state.result">
          <p class="text-xs text-green-600 dark:text-green-400">
            {{ state.result.operations_applied.toLocaleString() }}
            operation{{ state.result.operations_applied === 1 ? '' : 's' }} applied successfully.
          </p>
          <p class="text-xs text-muted-foreground">
            Completed in {{ state.elapsedSeconds }}s
          </p>
        </template>

        <!-- Failed state -->
        <template v-else-if="state.status === 'failed'">
          <Tooltip>
            <TooltipTrigger as-child>
              <p class="text-xs text-destructive cursor-default truncate">
                {{ truncatedError }}
              </p>
            </TooltipTrigger>
            <TooltipContent side="top" class="max-w-sm">
              <p class="text-xs break-all">{{ state.error }}</p>
            </TooltipContent>
          </Tooltip>
          <p v-if="state.result" class="text-xs text-muted-foreground">
            {{ state.result.operations_applied }} applied before failure
          </p>
        </template>
      </div>
    </div>
  </Transition>
</template>
