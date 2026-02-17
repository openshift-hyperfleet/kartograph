<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, ChevronRight, Eye, EyeOff } from 'lucide-vue-next'

const props = defineProps<{
  labelColors: Map<string, string>
}>()

const emit = defineEmits<{
  'toggle-label': [label: string, visible: boolean]
}>()

const isOpen = ref(true)
const hiddenLabels = ref(new Set<string>())

const labels = computed(() => {
  return Array.from(props.labelColors.entries()).sort(([a], [b]) => a.localeCompare(b))
})

function toggleLabel(label: string) {
  const newHidden = new Set(hiddenLabels.value)
  if (newHidden.has(label)) {
    newHidden.delete(label)
    emit('toggle-label', label, true)
  } else {
    newHidden.add(label)
    emit('toggle-label', label, false)
  }
  hiddenLabels.value = newHidden
}
</script>

<template>
  <div
    v-if="labels.length > 0"
    class="max-h-48 max-w-56 overflow-hidden rounded-md border bg-card/90 shadow-sm backdrop-blur-sm"
  >
    <button
      class="flex w-full items-center justify-between px-3 py-1.5 text-left"
      @click="isOpen = !isOpen"
    >
      <span class="text-[10px] font-semibold uppercase text-muted-foreground">Legend</span>
      <component
        :is="isOpen ? ChevronDown : ChevronRight"
        class="size-3 text-muted-foreground"
      />
    </button>
    <div v-if="isOpen" class="max-h-36 overflow-y-auto px-2 pb-2">
      <button
        v-for="[label, color] in labels"
        :key="label"
        class="flex w-full items-center gap-2 rounded px-1.5 py-0.5 text-left transition-colors hover:bg-muted"
        :class="{ 'opacity-40': hiddenLabels.has(label) }"
        @click="toggleLabel(label)"
      >
        <span
          class="size-2.5 shrink-0 rounded-full"
          :style="{ backgroundColor: color }"
        />
        <span class="min-w-0 flex-1 truncate font-mono text-[10px]">{{ label }}</span>
        <component
          :is="hiddenLabels.has(label) ? EyeOff : Eye"
          class="size-3 shrink-0 text-muted-foreground"
        />
      </button>
    </div>
  </div>
</template>
