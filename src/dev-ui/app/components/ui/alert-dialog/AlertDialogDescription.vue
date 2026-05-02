<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import type { AlertDialogDescriptionProps } from 'reka-ui'
import { AlertDialogDescription } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<AlertDialogDescriptionProps & { class?: HTMLAttributes['class'] }>()
</script>

<template>
  <AlertDialogDescription
    data-slot="alert-dialog-description"
    :class="cn('text-muted-foreground text-sm', props.class)"
  >
    <slot />
  </AlertDialogDescription>
</template>
