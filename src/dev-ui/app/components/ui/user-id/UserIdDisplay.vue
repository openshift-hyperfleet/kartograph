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

const { isCurrentUser, displayName: currentUserDisplayName } = useCurrentUser()
const { getDisplayName, resolveUsers } = useUserDirectory()

const isMe = computed(() => isCurrentUser(props.userId))

const displayLabel = computed(() => {
  if (isMe.value && currentUserDisplayName.value) return currentUserDisplayName.value
  return getDisplayName(props.userId)
})

const tooltipLabel = computed(() => {
  if (!isMe.value) return props.userId
  return currentUserDisplayName.value ? `You (${currentUserDisplayName.value})` : 'You'
})

// Trigger resolution on mount for non-current users
onMounted(() => {
  if (!isMe.value) {
    resolveUsers([props.userId])
  }
})
</script>

<template>
  <div class="inline-flex items-center gap-1.5 min-w-0">
    <span class="truncate text-sm" :title="userId">{{ displayLabel }}</span>
    <CopyableText :text="userId" :label="label" class="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
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
