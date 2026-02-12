<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import {
  Share2, Search, Loader2, Info, ChevronDown, ChevronUp,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableRow, TableCell,
} from '@/components/ui/table'
import type { NodeRecord } from '~/types'

const { findNodesBySlug, listNodeLabels } = useGraphApi()

// ── State ──────────────────────────────────────────────────────────────────

// Search
const slugQuery = ref('')
const nodeTypeFilter = ref<string>('__all__')
const availableNodeTypes = ref<string[]>([])
const nodeTypesLoading = ref(false)
const searching = ref(false)
const searchResults = ref<NodeRecord[]>([])
const hasSearched = ref(false)

// Property expansion tracking
const expandedProps = reactive(new Set<string>())

// ── Data loading ───────────────────────────────────────────────────────────

async function loadNodeTypes() {
  nodeTypesLoading.value = true
  try {
    const result = await listNodeLabels()
    availableNodeTypes.value = result.labels
  } catch {
    // Non-critical: filter dropdown just won't have options
  } finally {
    nodeTypesLoading.value = false
  }
}

async function handleSearch() {
  if (!slugQuery.value.trim()) return
  searching.value = true
  hasSearched.value = true
  try {
    const typeArg = nodeTypeFilter.value && nodeTypeFilter.value !== '__all__' ? nodeTypeFilter.value : undefined
    const result = await findNodesBySlug(slugQuery.value.trim(), typeArg)
    searchResults.value = result.nodes
  } catch (err) {
    toast.error('Search failed', {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

function getNodeDisplayName(node: NodeRecord): string {
  return (node.properties.name as string)
    || (node.properties.slug as string)
    || (node.properties.title as string)
    || node.id
}

function getPropertyEntries(properties: Record<string, unknown>): [string, unknown][] {
  return Object.entries(properties)
}

function formatPropertyValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function togglePropExpansion(key: string) {
  if (expandedProps.has(key)) {
    expandedProps.delete(key)
  } else {
    expandedProps.add(key)
  }
}

onMounted(loadNodeTypes)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <Share2 class="size-6 text-muted-foreground" />
      <h1 class="text-2xl font-bold tracking-tight">Graph Explorer</h1>
    </div>
    <p class="text-muted-foreground">Search for nodes in the knowledge graph.</p>

    <!-- Search Section -->
    <Card>
      <CardContent class="pt-6">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div class="flex-1 space-y-1.5">
            <Label for="slug-search">Node Slug</Label>
            <div class="relative">
              <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="slug-search"
                v-model="slugQuery"
                placeholder="Search by slug..."
                class="pl-9"
                @keydown.enter="handleSearch"
              />
            </div>
          </div>
          <div class="w-full space-y-1.5 sm:w-48">
            <Label>Type Filter</Label>
            <Select v-model="nodeTypeFilter">
              <SelectTrigger>
                <Loader2 v-if="nodeTypesLoading" class="mr-2 size-4 animate-spin" />
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All types</SelectItem>
                <SelectItem v-for="nt in availableNodeTypes" :key="nt" :value="nt">
                  {{ nt }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button :disabled="searching || !slugQuery.trim()" @click="handleSearch">
            <Loader2 v-if="searching" class="mr-2 size-4 animate-spin" />
            <Search v-else class="mr-2 size-4" />
            Search
          </Button>
        </div>
      </CardContent>
    </Card>

    <!-- Search Results -->
    <template v-if="hasSearched">
      <!-- Loading -->
      <div v-if="searching" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
        <Loader2 class="size-4 animate-spin" />
        Searching...
      </div>

      <!-- Empty results -->
      <Card v-else-if="searchResults.length === 0">
        <CardContent class="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
          <Info class="size-8" />
          <p class="font-medium">No nodes found</p>
          <p class="text-sm">No nodes match the slug "{{ slugQuery }}". Try a different search term.</p>
        </CardContent>
      </Card>

      <!-- Results list -->
      <div v-else class="space-y-3">
        <h2 class="text-sm font-medium text-muted-foreground">
          Found {{ searchResults.length }} node{{ searchResults.length === 1 ? '' : 's' }}
        </h2>

        <div class="grid gap-3 md:grid-cols-2">
          <Card v-for="node in searchResults" :key="node.id">
            <CardHeader class="pb-3">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <CardTitle class="truncate text-base">{{ getNodeDisplayName(node) }}</CardTitle>
                  <CardDescription class="font-mono text-xs">{{ node.id }}</CardDescription>
                </div>
                <Badge variant="default">{{ node.label }}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <!-- Properties table -->
              <div v-if="getPropertyEntries(node.properties).length > 0" class="rounded-md border">
                <Table>
                  <TableBody>
                    <TableRow v-for="[key, value] in getPropertyEntries(node.properties)" :key="key">
                      <TableCell class="w-[120px] align-top font-mono text-xs font-medium text-muted-foreground">{{ key }}</TableCell>
                      <TableCell class="font-mono text-xs">
                        <template v-if="formatPropertyValue(value).length > 100">
                          <div
                            :class="expandedProps.has(`${node.id}:${key}`) ? 'whitespace-pre-wrap break-all' : 'truncate max-w-[300px]'"
                          >
                            {{ expandedProps.has(`${node.id}:${key}`) ? formatPropertyValue(value) : formatPropertyValue(value).slice(0, 100) + '...' }}
                          </div>
                          <button
                            class="mt-1 inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
                            @click="togglePropExpansion(`${node.id}:${key}`)"
                          >
                            <ChevronUp v-if="expandedProps.has(`${node.id}:${key}`)" class="size-3" />
                            <ChevronDown v-else class="size-3" />
                            {{ expandedProps.has(`${node.id}:${key}`) ? 'Collapse' : 'Expand' }}
                          </button>
                        </template>
                        <template v-else>
                          {{ formatPropertyValue(value) }}
                        </template>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </template>

    <!-- Initial state (no search yet) -->
    <Card v-else>
      <CardContent class="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
        <Share2 class="size-10" />
        <p class="font-medium">Start Exploring</p>
        <p class="text-sm">Enter a slug in the search bar above to find nodes in the graph.</p>
      </CardContent>
    </Card>
  </div>
</template>
