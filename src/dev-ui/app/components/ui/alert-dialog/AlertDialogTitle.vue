<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { type AlertDialogTitleProps, AlertDialogTitle } from 'reka-ui'
import { cn } from '@/lib/utils'

const props = defineProps<AlertDialogTitleProps & { class?: HTMLAttributes['class'] }>()
</script>

<template>
  <AlertDialogTitle
    data-slot="alert-dialog-title"
    :class="cn('text-lg font-semibold', props.class)"
  >
    <slot />
  </AlertDialogTitle>
</template>
