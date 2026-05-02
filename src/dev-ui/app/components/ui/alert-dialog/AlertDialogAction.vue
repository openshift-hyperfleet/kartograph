<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import type { AlertDialogActionProps } from 'reka-ui'
import { AlertDialogAction } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<AlertDialogActionProps & { class?: HTMLAttributes['class'] }>()
</script>

<template>
  <AlertDialogAction
    data-slot="alert-dialog-action"
    :class="cn(
      'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground shadow-xs hover:bg-primary/90 h-9 px-4 py-2',
      props.class,
    )"
  >
    <slot />
  </AlertDialogAction>
</template>
