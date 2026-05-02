<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import type { AlertDialogCancelProps } from 'reka-ui'
import { AlertDialogCancel } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<AlertDialogCancelProps & { class?: HTMLAttributes['class'] }>()
</script>

<template>
  <AlertDialogCancel
    data-slot="alert-dialog-cancel"
    :class="cn(
      'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 border border-input bg-background shadow-xs hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2',
      props.class,
    )"
  >
    <slot />
  </AlertDialogCancel>
</template>
