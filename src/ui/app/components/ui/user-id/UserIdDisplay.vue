<script setup lang="ts">
import { Badge } from '@/components/ui/badge'
import { CopyableText } from '@/components/ui/copyable-text'

const props = withDefaults(defineProps<{
  /** The user ID to display */
  userId: string
  /** Custom toast label shown when the ID is copied (default: "User ID copied") */
  label?: string
}>(), {
  label: 'User ID copied',
})

const { isCurrentUser, displayName } = useCurrentUser()

const isMe = computed(() => isCurrentUser(props.userId))

const tooltipLabel = computed(() => {
  if (!isMe.value) return undefined
  return displayName.value ? `You (${displayName.value})` : 'You'
})
</script>

<template>
  <div class="inline-flex items-center gap-1.5 min-w-0">
    <CopyableText :text="userId" :label="label" />
    <Badge
      v-if="isMe"
      variant="outline"
      class="shrink-0 px-1.5 py-0 text-[10px] font-normal"
      :title="tooltipLabel"
    >
      You
    </Badge>
  </div>
</template>
