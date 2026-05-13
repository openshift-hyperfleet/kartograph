<script setup lang="ts">
/**
 * UserSearchInput — combobox that searches users by name/username/email.
 *
 * Uses Popover + Command from shadcn/vue. Calls searchUsers() from useIamApi
 * with a 300 ms debounce after the user types 2+ characters.
 *
 * Also accepts raw UUIDs: if the typed text matches a UUID pattern and the
 * user presses Enter (or the popover closes), the UUID is emitted directly.
 */
import { ref, computed, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { ChevronsUpDown, Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  Popover, PopoverContent, PopoverTrigger,
} from '@/components/ui/popover'
import {
  Command, CommandEmpty, CommandGroup, CommandItem, CommandList,
} from '@/components/ui/command'
import { Input } from '@/components/ui/input'
import type { UserProfileResponse } from '~/types'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { searchUsers } = useIamApi()

const open = ref(false)
const searchQuery = ref('')
const searchResults = ref<UserProfileResponse[]>([])
const loading = ref(false)
const hasSearched = ref(false)
const selectedUser = ref<UserProfileResponse | null>(null)
let searchToken = 0

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const displayText = computed(() => {
  if (selectedUser.value) {
    return selectedUser.value.name || selectedUser.value.username
  }
  if (props.modelValue) {
    return props.modelValue
  }
  return 'Search users...'
})

const emptyText = computed(() => {
  if (loading.value) return 'Searching...'
  if (hasSearched.value && searchResults.value.length === 0) return 'No users found'
  return 'Type to search users...'
})

async function doSearch(query: string) {
  if (query.length < 2) {
    searchResults.value = []
    hasSearched.value = false
    return
  }
  const token = ++searchToken
  loading.value = true
  try {
    const result = await searchUsers(query)
    if (token !== searchToken) return
    searchResults.value = result.users
    hasSearched.value = true
  }
  catch {
    if (token !== searchToken) return
    searchResults.value = []
    hasSearched.value = true
  }
  finally {
    if (token === searchToken) loading.value = false
  }
}

const debouncedSearch = useDebounceFn(doSearch, 300)

watch(searchQuery, (val) => {
  if (val.length < 2) {
    searchToken++
    searchResults.value = []
    hasSearched.value = false
    return
  }
  debouncedSearch(val)
})

function resetSearch() {
  searchToken++
  searchQuery.value = ''
  searchResults.value = []
  hasSearched.value = false
}

function selectUser(user: UserProfileResponse) {
  selectedUser.value = user
  emit('update:modelValue', user.id)
  open.value = false
  resetSearch()
}

function handleKeydown(event: KeyboardEvent) {
  const val = searchQuery.value.trim()
  if (event.key === 'Enter' && (UUID_RE.test(val) || EMAIL_RE.test(val))) {
    event.preventDefault()
    selectedUser.value = null
    emit('update:modelValue', val)
    open.value = false
    resetSearch()
  }
}

// Clear selected user display when modelValue is cleared externally
watch(() => props.modelValue, (val) => {
  if (!val) {
    selectedUser.value = null
  }
})
</script>

<template>
  <Popover v-model:open="open">
    <PopoverTrigger as-child>
      <Button
        variant="outline"
        role="combobox"
        :aria-expanded="open"
        class="w-full justify-between"
      >
        <span class="truncate">{{ displayText }}</span>
        <ChevronsUpDown class="ml-2 size-4 shrink-0 opacity-50" />
      </Button>
    </PopoverTrigger>
    <PopoverContent class="w-[--reka-popover-trigger-width] p-0" align="start">
      <Command>
        <div class="flex h-9 items-center gap-2 border-b px-3">
          <Loader2 v-if="loading" class="size-4 shrink-0 opacity-50 animate-spin" />
          <Input
            v-model="searchQuery"
            placeholder="Search users..."
            class="flex h-10 w-full rounded-md border-0 bg-transparent py-3 text-sm shadow-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            @keydown="handleKeydown"
          />
        </div>
        <CommandList>
          <CommandEmpty>{{ emptyText }}</CommandEmpty>
          <CommandGroup>
            <CommandItem
              v-for="user in searchResults"
              :key="user.id"
              :value="user.id"
              @select="selectUser(user)"
            >
              <div>
                <div class="text-sm">{{ user.name || user.username }}</div>
                <div class="text-xs text-muted-foreground">
                  {{ user.username }}{{ user.email ? ` · ${user.email}` : '' }}
                </div>
              </div>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </PopoverContent>
  </Popover>
</template>
