<script setup lang="ts">
import { computed, ref } from 'vue'
import { X, Copy, Check } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { GraphNode } from '~/types'

const props = defineProps<{
  node: GraphNode | null
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const copiedKey = ref<string | null>(null)

const properties = computed(() => {
  if (!props.node) return []
  return Object.entries(props.node.properties)
    .filter(([key]) => !key.startsWith('_'))
    .sort(([a], [b]) => a.localeCompare(b))
})

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function isLongValue(value: unknown): boolean {
  return formatValue(value).length > 60
}

async function copyValue(key: string, value: unknown) {
  try {
    await navigator.clipboard.writeText(formatValue(value))
    copiedKey.value = key
    setTimeout(() => {
      copiedKey.value = null
    }, 2000)
  } catch {
    toast.error('Failed to copy')
  }
}

async function copyAllProperties() {
  if (!props.node) return
  try {
    await navigator.clipboard.writeText(JSON.stringify(props.node.properties, null, 2))
    toast.success('All properties copied')
  } catch {
    toast.error('Failed to copy')
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition-transform duration-200 ease-out"
    leave-active-class="transition-transform duration-150 ease-in"
    enter-from-class="translate-x-full"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="open && node"
      class="absolute right-0 top-0 flex h-full w-80 flex-col border-l bg-card shadow-lg"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div class="min-w-0 flex-1">
          <h3 class="truncate font-mono text-sm font-semibold">
            {{ node.displayName }}
          </h3>
          <Badge variant="outline" class="mt-1 font-mono text-[10px]">
            {{ node.label }}
          </Badge>
        </div>
        <Button
          variant="ghost"
          size="icon"
          class="ml-2 shrink-0"
          aria-label="Close detail panel"
          @click="emit('close')"
        >
          <X class="size-4" />
        </Button>
      </div>

      <!-- ID -->
      <div class="border-b px-4 py-2">
        <span class="text-[10px] font-medium uppercase text-muted-foreground">ID</span>
        <p class="truncate font-mono text-xs text-foreground" :title="node.id">
          {{ node.id }}
        </p>
      </div>

      <!-- Properties header -->
      <div class="flex items-center justify-between border-b px-4 py-2">
        <span class="text-[10px] font-medium uppercase text-muted-foreground">
          Properties ({{ properties.length }})
        </span>
        <Button
          v-if="properties.length > 0"
          variant="ghost"
          size="sm"
          class="h-6 px-2 text-[10px]"
          @click="copyAllProperties"
        >
          <Copy class="mr-1 size-3" />
          Copy All
        </Button>
      </div>

      <!-- Properties list -->
      <div class="flex-1 overflow-y-auto">
        <div
          v-if="properties.length === 0"
          class="px-4 py-6 text-center text-xs text-muted-foreground"
        >
          No properties
        </div>
        <div v-else class="divide-y">
          <div
            v-for="[key, value] in properties"
            :key="key"
            class="group px-4 py-2"
          >
            <div class="flex items-center justify-between">
              <span class="font-mono text-[10px] font-medium text-muted-foreground">
                {{ key }}
              </span>
              <Button
                variant="ghost"
                size="icon"
                class="size-5 opacity-0 transition-opacity group-hover:opacity-100"
                :aria-label="`Copy ${key}`"
                @click="copyValue(key, value)"
              >
                <component :is="copiedKey === key ? Check : Copy" class="size-3" />
              </Button>
            </div>
            <pre
              v-if="isLongValue(value)"
              class="mt-1 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-muted px-2 py-1 font-mono text-xs text-foreground"
            >{{ formatValue(value) }}</pre>
            <p v-else class="mt-0.5 font-mono text-xs text-foreground">
              {{ formatValue(value) }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
