<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import {
  Loader2, CheckCircle2, XCircle, Minus, Maximize2,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const { state, dismiss } = useMutationSubmission()

const minimized = ref(false)

const isVisible = computed(() => state.value.status !== 'idle')

// ── Local elapsed time (avoids mutating shared reactive state every second) ──

const elapsedSeconds = ref(0)
let elapsedInterval: ReturnType<typeof setInterval> | null = null

function startLocalTimer() {
  stopLocalTimer()
  elapsedSeconds.value = state.value.startedAt
    ? Math.floor((Date.now() - state.value.startedAt) / 1000)
    : 0
  elapsedInterval = setInterval(() => {
    if (state.value.startedAt) {
      elapsedSeconds.value = Math.floor((Date.now() - state.value.startedAt) / 1000)
    }
  }, 1000)
}

function stopLocalTimer() {
  if (elapsedInterval) {
    clearInterval(elapsedInterval)
    elapsedInterval = null
  }
}

// Compute final elapsed for completed states
const finalElapsedSeconds = computed(() => {
  const { startedAt, completedAt } = state.value
  if (startedAt && completedAt) {
    return Math.floor((completedAt - startedAt) / 1000)
  }
  return elapsedSeconds.value
})

// Start/stop the local timer based on submission status
watch(() => state.value.status, (status) => {
  if (status === 'submitting') {
    startLocalTimer()
  } else {
    stopLocalTimer()
  }
}, { immediate: true })

onBeforeUnmount(stopLocalTimer)

const truncatedError = computed(() => {
  const err = state.value.error
  if (!err) return ''
  return err.length > 120 ? err.slice(0, 120) + '...' : err
})

const statusBorderClass = computed(() => {
  switch (state.value.status) {
    case 'submitting': return 'border-primary/50'
    case 'success': return 'border-green-500/50'
    case 'failed': return 'border-destructive/50'
    default: return ''
  }
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
    <div v-if="isVisible" class="fixed bottom-4 right-4 z-[90]">
      <!-- Minimized: compact pill -->
      <div
        v-if="minimized"
        class="flex items-center gap-1.5 rounded-full border px-3 py-1.5 bg-card shadow-lg"
        :class="statusBorderClass"
      >
        <NuxtLink
          to="/graph/mutations"
          class="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
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

          <Badge variant="secondary" class="shrink-0 text-[10px]">
            {{ state.operationCount.toLocaleString() }}
          </Badge>
        </NuxtLink>

        <Button
          variant="ghost"
          size="icon"
          class="size-5"
          @click.stop="minimized = false"
        >
          <Maximize2 class="size-3" />
        </Button>
        <Button
          v-if="state.status !== 'submitting'"
          variant="ghost"
          size="icon"
          class="size-5"
          @click.stop="dismiss"
        >
          <XCircle class="size-3" />
        </Button>
      </div>

      <!-- Expanded: full card -->
      <div
        v-else
        class="w-80 rounded-lg border bg-card shadow-lg overflow-hidden"
        :class="statusBorderClass"
      >
        <!-- Indeterminate progress bar during submission -->
        <div v-if="state.status === 'submitting'" class="h-0.5 w-full overflow-hidden bg-primary/20">
          <div class="h-full w-1/3 bg-primary rounded-full indeterminate-bar" />
        </div>

        <!-- Header bar -->
        <div class="flex items-center justify-between px-3 py-2 border-b">
          <NuxtLink
            to="/graph/mutations"
            class="flex items-center gap-2 min-w-0 hover:opacity-80 transition-opacity"
          >
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
          </NuxtLink>

          <div class="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              class="size-6"
              @click.stop="minimized = true"
            >
              <Minus class="size-3" />
            </Button>
            <Button
              v-if="state.status !== 'submitting'"
              variant="ghost"
              size="icon"
              class="size-6"
              @click.stop="dismiss"
            >
              <XCircle class="size-3" />
            </Button>
          </div>
        </div>

        <!-- Body -->
        <div class="px-3 py-2 space-y-1">
          <!-- Submitting state -->
          <template v-if="state.status === 'submitting'">
            <p class="text-xs text-muted-foreground">
              Applying {{ state.operationCount.toLocaleString() }} mutation{{ state.operationCount === 1 ? '' : 's' }}...
              <span class="font-mono">{{ elapsedSeconds }}s</span>
            </p>
          </template>

          <!-- Success state -->
          <template v-else-if="state.status === 'success' && state.result">
            <p class="text-xs text-green-600 dark:text-green-400">
              {{ state.result.operations_applied.toLocaleString() }}
              operation{{ state.result.operations_applied === 1 ? '' : 's' }} applied successfully.
            </p>
            <p class="text-xs text-muted-foreground">
              Completed in {{ finalElapsedSeconds }}s
            </p>
          </template>

          <!-- Failed state -->
          <template v-else-if="state.status === 'failed'">
            <p
              class="text-xs text-destructive cursor-default truncate"
              :title="state.error ?? ''"
            >
              {{ truncatedError }}
            </p>
            <p v-if="state.result" class="text-xs text-muted-foreground">
              {{ state.result.operations_applied }} applied before failure
            </p>
          </template>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.indeterminate-bar {
  animation: indeterminate-slide 1.5s ease-in-out infinite;
}

@keyframes indeterminate-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}
</style>
