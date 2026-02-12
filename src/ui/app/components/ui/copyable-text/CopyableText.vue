<script setup lang="ts">
import { ref } from 'vue'
import { Copy, Check } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

const props = withDefaults(defineProps<{
  text: string
  truncate?: boolean
  maxLength?: number
  label?: string
}>(), {
  truncate: true,
  maxLength: 12,
  label: undefined,
})

const copied = ref(false)

function displayText(): string {
  if (!props.truncate || props.text.length <= props.maxLength) return props.text
  return props.text.slice(0, props.maxLength - 4) + '...'
}

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
    class="inline-flex items-center gap-1 rounded px-1 py-0.5 font-mono text-xs hover:bg-muted"
    :title="text"
    @click.stop="copy"
  >
    <span class="text-muted-foreground">{{ displayText() }}</span>
    <component :is="copied ? Check : Copy" class="size-3 shrink-0 text-muted-foreground" />
  </button>
</template>
