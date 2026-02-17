<script setup lang="ts">
import { ref } from 'vue'
import { Copy, Check } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

const props = withDefaults(defineProps<{
  text: string
  /** Use CSS truncation to fit available space (default: true) */
  truncate?: boolean
  label?: string
}>(), {
  truncate: true,
  label: undefined,
})

const copied = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
    copied.value = true
    toast.success(props.label ?? 'Copied to clipboard')
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    toast.error('Failed to copy')
  }
}
</script>

<template>
  <button
    class="inline-flex min-w-0 max-w-full items-center gap-1 rounded px-1 py-0.5 font-mono text-xs hover:bg-muted"
    :title="text"
    @click.stop="copy"
  >
    <span
      class="text-muted-foreground"
      :class="truncate ? 'truncate' : ''"
    >{{ text }}</span>
    <component :is="copied ? Check : Copy" class="size-3 shrink-0 text-muted-foreground" />
  </button>
</template>
