<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import type { AlertDialogOverlayProps } from 'reka-ui'
import { AlertDialogOverlay } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<AlertDialogOverlayProps & { class?: HTMLAttributes['class'] }>()
</script>

<template>
  <AlertDialogOverlay
    data-slot="alert-dialog-overlay"
    :class="cn(
      'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/80',
      props.class,
    )"
  />
</template>
