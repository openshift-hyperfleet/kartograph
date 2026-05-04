<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, Download, Sparkles, Database, Clock } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'

type SyncStatus = 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'

const props = defineProps<{ status: SyncStatus; label?: string }>()

const phaseLabel = computed(() => {
  const labels: Record<SyncStatus, string> = {
    pending:       'Pending',
    ingesting:     'Ingesting',
    ai_extracting: 'Extracting',
    applying:      'Applying',
    completed:     'Completed',
    failed:        'Failed',
  }
  return props.label ?? labels[props.status] ?? props.status
})

const isActive = computed(() =>
  ['pending', 'ingesting', 'ai_extracting', 'applying'].includes(props.status),
)

const badgeVariant = computed<'default' | 'secondary' | 'destructive'>(() => {
  if (props.status === 'completed') return 'default'
  if (props.status === 'failed') return 'destructive'
  return 'secondary'
})

const phaseIcon = computed(() => {
  switch (props.status) {
    case 'pending':       return Clock
    case 'ingesting':     return Download
    case 'ai_extracting': return Sparkles
    case 'applying':      return Database
    default:              return null
  }
})

const animationClass = computed(() => {
  switch (props.status) {
    case 'ingesting':
    case 'ai_extracting': return 'animate-spin'
    case 'pending':
    case 'applying':      return 'animate-pulse'
    default:              return ''
  }
})
</script>

<template>
  <span class="inline-flex items-center gap-1.5">
    <!-- Animated icon for active phases -->
    <component
      :is="phaseIcon"
      v-if="isActive && phaseIcon"
      class="size-3.5 text-primary"
      :class="animationClass"
      aria-hidden="true"
    />
    <Badge :variant="badgeVariant" class="text-[10px]">
      {{ phaseLabel }}
    </Badge>
  </span>
</template>
