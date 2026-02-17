<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import {
  Star, Search, Trash2, Clock, CheckCircle2, XCircle,
  Play, Pencil, X, AlertTriangle,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog'

// ── Types ───────────────────────────────────────────────────────────────────

interface HistoryEntry {
  query: string
  timestamp: number
  rowCount: number | null
}

interface SavedQuery {
  id: string
  name: string
  query: string
  createdAt: number
}

interface HistoryGroup {
  label: string
  entries: (HistoryEntry & { originalIndex: number })[]
}

// ── Props & Emits ───────────────────────────────────────────────────────────

const props = defineProps<{
  history: HistoryEntry[]
  currentQuery: string
}>()

const emit = defineEmits<{
  'select-query': [query: string]
  'clear-history': []
}>()

// ── Constants ───────────────────────────────────────────────────────────────

const SAVED_QUERIES_KEY = 'kartograph:saved-queries'
const MAX_SAVED_QUERIES = 50

// ── Search & Filter State ───────────────────────────────────────────────────

const searchQuery = ref('')
type FilterMode = 'all' | 'success' | 'failed'
const activeFilter = ref<FilterMode>('all')

// ── Saved Queries (localStorage) ────────────────────────────────────────────

const savedQueries = ref<SavedQuery[]>([])

function loadSavedQueries() {
  try {
    const stored = localStorage.getItem(SAVED_QUERIES_KEY)
    if (stored) savedQueries.value = JSON.parse(stored)
  } catch {
    savedQueries.value = []
  }
}

function persistSavedQueries() {
  try {
    localStorage.setItem(SAVED_QUERIES_KEY, JSON.stringify(savedQueries.value))
  } catch { /* storage full – ignore */ }
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function saveQuery(query: string) {
  if (savedQueries.value.length >= MAX_SAVED_QUERIES) return
  if (savedQueries.value.some(s => s.query === query)) return

  const name = query.length > 40 ? query.slice(0, 40) + '...' : query
  savedQueries.value.unshift({
    id: generateId(),
    name,
    query,
    createdAt: Date.now(),
  })
  persistSavedQueries()
}

function unsaveQuery(id: string) {
  savedQueries.value = savedQueries.value.filter(s => s.id !== id)
  persistSavedQueries()
}

function isQuerySaved(query: string): boolean {
  return savedQueries.value.some(s => s.query === query)
}

function toggleSaveQuery(query: string) {
  const existing = savedQueries.value.find(s => s.query === query)
  if (existing) {
    unsaveQuery(existing.id)
  } else {
    saveQuery(query)
  }
}

// ── Inline Rename ───────────────────────────────────────────────────────────

const renamingId = ref<string | null>(null)
const renameValue = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

function startRename(saved: SavedQuery) {
  renamingId.value = saved.id
  renameValue.value = saved.name
  nextTick(() => {
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

function commitRename(id: string) {
  const trimmed = renameValue.value.trim()
  if (!trimmed) {
    cancelRename()
    return
  }
  const entry = savedQueries.value.find(s => s.id === id)
  if (entry) {
    entry.name = trimmed
    persistSavedQueries()
  }
  renamingId.value = null
}

function cancelRename() {
  renamingId.value = null
}

// ── Inline Replace Confirmation ─────────────────────────────────────────────

const confirmingEntryIndex = ref<number | null>(null)
const confirmingSavedId = ref<string | null>(null)

function handleHistoryClick(entry: HistoryEntry, originalIndex: number) {
  if (props.currentQuery.trim().length > 0) {
    confirmingEntryIndex.value = originalIndex
    confirmingSavedId.value = null
  } else {
    emit('select-query', entry.query)
  }
}

function handleSavedClick(saved: SavedQuery) {
  if (renamingId.value === saved.id) return
  if (props.currentQuery.trim().length > 0) {
    confirmingSavedId.value = saved.id
    confirmingEntryIndex.value = null
  } else {
    emit('select-query', saved.query)
  }
}

function confirmReplace(query: string) {
  emit('select-query', query)
  confirmingEntryIndex.value = null
  confirmingSavedId.value = null
}

function cancelReplace() {
  confirmingEntryIndex.value = null
  confirmingSavedId.value = null
}

// ── Clear History Dialog ────────────────────────────────────────────────────

const showClearDialog = ref(false)

function confirmClearHistory() {
  emit('clear-history')
  showClearDialog.value = false
}

// ── Time Formatting ─────────────────────────────────────────────────────────

function formatRelativeTime(ts: number): string {
  const now = Date.now()
  const diff = now - ts
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 60) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days}d ago`
  return new Date(ts).toLocaleDateString()
}

// ── Grouping & Filtering ────────────────────────────────────────────────────

const filteredHistory = computed<HistoryEntry[]>(() => {
  let entries = props.history

  // Apply status filter
  if (activeFilter.value === 'success') {
    entries = entries.filter(e => e.rowCount !== null)
  } else if (activeFilter.value === 'failed') {
    entries = entries.filter(e => e.rowCount === null)
  }

  // Apply search filter (case-insensitive substring)
  const search = searchQuery.value.trim().toLowerCase()
  if (search) {
    entries = entries.filter(e => e.query.toLowerCase().includes(search))
  }

  return entries
})

const groupedHistory = computed<HistoryGroup[]>(() => {
  if (filteredHistory.value.length === 0) return []

  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86400000

  const groups: Record<string, (HistoryEntry & { originalIndex: number })[]> = {}
  const groupOrder: string[] = []

  filteredHistory.value.forEach((entry) => {
    // Find the original index in the unfiltered history for keying
    const originalIndex = props.history.indexOf(entry)

    let label: string
    if (entry.timestamp >= today) {
      label = 'Today'
    } else if (entry.timestamp >= yesterday) {
      label = 'Yesterday'
    } else {
      label = new Date(entry.timestamp).toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      })
    }
    if (!groups[label]) {
      groups[label] = []
      groupOrder.push(label)
    }
    groups[label].push({ ...entry, originalIndex })
  })

  return groupOrder.map(label => ({ label, entries: groups[label] }))
})

const filteredSavedQueries = computed<SavedQuery[]>(() => {
  const search = searchQuery.value.trim().toLowerCase()
  if (!search) return savedQueries.value
  return savedQueries.value.filter(
    s => s.query.toLowerCase().includes(search) || s.name.toLowerCase().includes(search),
  )
})

// ── Filter Chip Counts ─────────────────────────────────────────────────────

const successCount = computed(() => props.history.filter(e => e.rowCount !== null).length)
const failedCount = computed(() => props.history.filter(e => e.rowCount === null).length)

// ── Lifecycle ───────────────────────────────────────────────────────────────

onMounted(() => {
  loadSavedQueries()
})
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- Search Input -->
    <div class="px-1 pb-2">
      <div class="relative">
        <Search class="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          v-model="searchQuery"
          placeholder="Search queries..."
          class="h-8 pl-7 text-xs"
        />
        <button
          v-if="searchQuery"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          @click="searchQuery = ''"
        >
          <X class="size-3" />
        </button>
      </div>
    </div>

    <!-- Filter Chips -->
    <div class="flex flex-wrap gap-1 px-1 pb-2">
      <button
        class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors"
        :class="activeFilter === 'all'
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-transparent text-muted-foreground hover:bg-muted hover:text-foreground'"
        @click="activeFilter = 'all'"
      >
        All
        <Badge variant="secondary" class="ml-0.5 h-4 min-w-[1rem] px-1 text-[10px]">
          {{ history.length }}
        </Badge>
      </button>
      <button
        class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors"
        :class="activeFilter === 'success'
          ? 'border-green-600 bg-green-600/10 text-green-600'
          : 'border-transparent text-muted-foreground hover:bg-muted hover:text-foreground'"
        @click="activeFilter = 'success'"
      >
        <CheckCircle2 class="size-3" />
        Success
        <Badge variant="secondary" class="ml-0.5 h-4 min-w-[1rem] px-1 text-[10px]">
          {{ successCount }}
        </Badge>
      </button>
      <button
        class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors"
        :class="activeFilter === 'failed'
          ? 'border-red-500 bg-red-500/10 text-red-500'
          : 'border-transparent text-muted-foreground hover:bg-muted hover:text-foreground'"
        @click="activeFilter = 'failed'"
      >
        <XCircle class="size-3" />
        Failed
        <Badge variant="secondary" class="ml-0.5 h-4 min-w-[1rem] px-1 text-[10px]">
          {{ failedCount }}
        </Badge>
      </button>
    </div>

    <Separator />

    <!-- Scrollable Content -->
    <div class="min-h-0 flex-1 overflow-y-auto pt-2">
      <!-- Saved Queries Section -->
      <div v-if="filteredSavedQueries.length > 0" class="px-1 pb-2">
        <div class="mb-1 flex items-center gap-1.5">
          <Star class="size-3 text-yellow-500" fill="currentColor" />
          <span class="text-[11px] font-semibold uppercase text-muted-foreground">Saved</span>
          <Badge variant="secondary" class="h-4 min-w-[1rem] px-1 text-[10px]">
            {{ filteredSavedQueries.length }}
          </Badge>
        </div>
        <div class="space-y-0.5">
          <div
            v-for="saved in filteredSavedQueries"
            :key="saved.id"
            class="group rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
          >
            <!-- Normal display -->
            <div
              v-if="confirmingSavedId !== saved.id"
              class="flex items-start gap-1"
            >
              <!-- Star (unsave) button -->
              <button
                class="mt-0.5 shrink-0 text-yellow-500 hover:text-yellow-400"
                title="Unsave query"
                @click.stop="unsaveQuery(saved.id)"
              >
                <Star class="size-3.5" fill="currentColor" />
              </button>

              <!-- Content area (clickable to select) -->
              <div class="min-w-0 flex-1" @click="handleSavedClick(saved)">
                <!-- Editable name -->
                <div v-if="renamingId === saved.id" class="flex items-center gap-1">
                  <input
                    ref="renameInputRef"
                    v-model="renameValue"
                    class="h-5 w-full rounded border border-ring bg-background px-1 text-[11px] font-medium text-foreground outline-none"
                    @keydown.enter="commitRename(saved.id)"
                    @keydown.escape="cancelRename"
                    @blur="commitRename(saved.id)"
                    @click.stop
                  />
                </div>
                <div v-else class="flex items-center gap-1">
                  <TooltipProvider :delay-duration="300">
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <span class="cursor-pointer truncate text-[11px] font-medium text-foreground">
                          {{ saved.name }}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="left" class="max-w-xs">
                        <pre class="whitespace-pre-wrap font-mono text-[11px]">{{ saved.query }}</pre>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <button
                    class="shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-opacity"
                    title="Rename"
                    @click.stop="startRename(saved)"
                  >
                    <Pencil class="size-3" />
                  </button>
                </div>
              </div>

              <!-- Run button -->
              <button
                class="mt-0.5 shrink-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground transition-opacity"
                title="Load query"
                @click.stop="handleSavedClick(saved)"
              >
                <Play class="size-3" />
              </button>
            </div>

            <!-- Inline replace confirmation -->
            <div v-else class="space-y-1.5">
              <p class="truncate font-mono text-[11px] text-foreground">{{ saved.query }}</p>
              <p class="text-[11px] text-muted-foreground">Replace current query?</p>
              <div class="flex items-center gap-1.5">
                <Button
                  variant="default"
                  size="sm"
                  class="h-6 px-2 text-[11px]"
                  @click.stop="confirmReplace(saved.query)"
                >
                  Replace
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  class="h-6 px-2 text-[11px]"
                  @click.stop="cancelReplace"
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        </div>
        <Separator class="mt-2" />
      </div>

      <!-- Chronological History -->
      <div class="px-1">
        <!-- Header with Clear button -->
        <div v-if="history.length > 0" class="mb-1 flex items-center justify-between">
          <div class="flex items-center gap-1.5">
            <Clock class="size-3 text-muted-foreground" />
            <span class="text-[11px] font-semibold uppercase text-muted-foreground">History</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            class="h-6 px-2 text-[11px] text-muted-foreground"
            @click.stop="showClearDialog = true"
          >
            <Trash2 class="mr-1 size-3" />
            Clear
          </Button>
        </div>

        <!-- Empty state -->
        <div v-if="history.length === 0" class="py-6 text-center text-xs text-muted-foreground">
          No queries yet.
        </div>

        <!-- No results from search/filter -->
        <div
          v-else-if="filteredHistory.length === 0"
          class="py-4 text-center text-xs text-muted-foreground"
        >
          No matching queries found.
        </div>

        <!-- Grouped entries -->
        <div v-else class="space-y-3">
          <div v-for="group in groupedHistory" :key="group.label">
            <p class="mb-1 text-[11px] font-semibold uppercase text-muted-foreground">
              {{ group.label }}
            </p>
            <div class="space-y-0.5">
              <div
                v-for="entry in group.entries"
                :key="entry.originalIndex"
                class="group rounded-md px-2 py-1.5 transition-colors hover:bg-muted"
              >
                <!-- Normal entry display -->
                <div
                  v-if="confirmingEntryIndex !== entry.originalIndex"
                  class="flex items-start gap-1"
                >
                  <!-- Star toggle -->
                  <button
                    class="mt-0.5 shrink-0 transition-opacity"
                    :class="isQuerySaved(entry.query)
                      ? 'text-yellow-500 hover:text-yellow-400'
                      : 'opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-yellow-500'"
                    :title="isQuerySaved(entry.query) ? 'Unsave' : 'Save query'"
                    @click.stop="toggleSaveQuery(entry.query)"
                  >
                    <Star
                      class="size-3.5"
                      :fill="isQuerySaved(entry.query) ? 'currentColor' : 'none'"
                    />
                  </button>

                  <!-- Query text (clickable) -->
                  <div
                    class="min-w-0 flex-1 cursor-pointer"
                    @click="handleHistoryClick(entry, entry.originalIndex)"
                  >
                    <TooltipProvider :delay-duration="400">
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <p class="truncate font-mono text-[11px] text-foreground">
                            {{ entry.query }}
                          </p>
                        </TooltipTrigger>
                        <TooltipContent side="left" class="max-w-sm">
                          <pre class="whitespace-pre-wrap font-mono text-[11px]">{{ entry.query }}</pre>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <div class="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{{ formatRelativeTime(entry.timestamp) }}</span>
                      <span v-if="entry.rowCount !== null" class="flex items-center gap-0.5">
                        <CheckCircle2 class="size-2.5 text-green-500" />
                        {{ entry.rowCount }} row{{ entry.rowCount !== 1 ? 's' : '' }}
                      </span>
                      <Badge v-else variant="destructive" class="h-3.5 px-1 text-[10px]">
                        error
                      </Badge>
                    </div>
                  </div>
                </div>

                <!-- Inline replace confirmation -->
                <div v-else class="space-y-1.5">
                  <p class="truncate font-mono text-[11px] text-foreground">{{ entry.query }}</p>
                  <p class="text-[11px] text-muted-foreground">Replace current query?</p>
                  <div class="flex items-center gap-1.5">
                    <Button
                      variant="default"
                      size="sm"
                      class="h-6 px-2 text-[11px]"
                      @click.stop="confirmReplace(entry.query)"
                    >
                      Replace
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      class="h-6 px-2 text-[11px]"
                      @click.stop="cancelReplace"
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Clear History Confirmation Dialog -->
    <Dialog v-model:open="showClearDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <AlertTriangle class="size-5 text-destructive" />
            Clear all history?
          </DialogTitle>
          <DialogDescription>
            This will remove all {{ history.length }} query
            {{ history.length === 1 ? 'entry' : 'entries' }}.
            Saved queries will not be affected.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter class="gap-2 sm:gap-0">
          <Button
            variant="ghost"
            @click="showClearDialog = false"
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            @click="confirmClearHistory"
          >
            <Trash2 class="mr-1.5 size-4" />
            Clear History
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
