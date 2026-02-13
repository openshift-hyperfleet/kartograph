<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Share2, Search, Loader2, Info, ChevronDown, ChevronUp, ChevronsUpDown, Check, X, Building2,
  Database, Terminal, Compass, ArrowRight, ArrowLeft, CornerDownRight,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CopyableText } from '@/components/ui/copyable-text'
import { Separator } from '@/components/ui/separator'
import {
  Popover, PopoverContent, PopoverTrigger,
} from '@/components/ui/popover'
import {
  Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from '@/components/ui/command'
import {
  Table, TableBody, TableRow, TableCell,
} from '@/components/ui/table'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import type { NodeRecord, EdgeRecord } from '~/types'

const { findNodesBySlug, listNodeLabels, getNodeNeighbors } = useGraphApi()
const { queryGraph } = useQueryApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── State ──────────────────────────────────────────────────────────────────

// Search
const searchQuery = ref('')
const nodeTypeFilter = ref<string>('')
const availableNodeTypes = ref<string[]>([])
const nodeTypesLoading = ref(false)
const searching = ref(false)
const searchResults = ref<NodeRecord[]>([])
const hasSearched = ref(false)
const searchDescription = ref('')
const resultLimitHit = ref(false)

// Type filter combobox
const typeFilterOpen = ref(false)
const typeFilterSearch = ref('')
const COMBOBOX_LIMIT = 100
const BROWSE_LIMIT = 50
const SEARCH_LIMIT = 25

const filteredNodeTypes = computed(() => {
  let types = availableNodeTypes.value
  if (typeFilterSearch.value) {
    const q = typeFilterSearch.value.toLowerCase()
    types = types.filter(t => t.toLowerCase().includes(q))
  }
  return types.slice(0, COMBOBOX_LIMIT)
})

const typeFilterLabel = computed(() => {
  if (!nodeTypeFilter.value) return 'All types'
  return nodeTypeFilter.value
})

function selectNodeType(value: string) {
  nodeTypeFilter.value = value
  typeFilterOpen.value = false
  typeFilterSearch.value = ''
}

function clearNodeTypeFilter() {
  nodeTypeFilter.value = ''
  typeFilterSearch.value = ''
}

// Property expansion tracking
const expandedProps = ref(new Set<string>())

// Neighbor exploration state
const neighborsLoading = ref<string | null>(null)
const expandedNeighbors = ref<string | null>(null)
const neighborNodes = ref<NodeRecord[]>([])
const neighborEdges = ref<EdgeRecord[]>([])
const centralNode = ref<NodeRecord | null>(null)
const explorationPath = ref<NodeRecord[]>([])

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

// ── Search Modes ───────────────────────────────────────────────────────────

async function handleSearch() {
  const query = searchQuery.value.trim()
  const typeFilter = nodeTypeFilter.value

  // Must have at least a type selected or text entered
  if (!query && !typeFilter) return

  searching.value = true
  hasSearched.value = true
  clearNeighborState()

  try {
    let nodes: NodeRecord[]

    if (!query && typeFilter) {
      // Mode: Browse all instances of a type
      nodes = await browseByType(typeFilter)
      searchDescription.value = `Browsing all ${typeFilter} nodes`
      resultLimitHit.value = nodes.length >= BROWSE_LIMIT
    } else if (query && typeFilter) {
      // Mode: Search within a type (try slug first, then property search)
      nodes = await searchWithinType(query, typeFilter)
      searchDescription.value = `Searching for "${query}" in ${typeFilter} nodes`
      resultLimitHit.value = nodes.length >= SEARCH_LIMIT
    } else {
      // Mode: Search across all types (try slug first, then property search)
      nodes = await searchAcrossTypes(query)
      searchDescription.value = `Searching for "${query}" across all types`
      resultLimitHit.value = nodes.length >= SEARCH_LIMIT
    }

    searchResults.value = nodes
  } catch (err) {
    toast.error('Search failed', {
      description: extractErrorMessage(err),
    })
    searchResults.value = []
    searchDescription.value = ''
    resultLimitHit.value = false
  } finally {
    searching.value = false
  }
}

async function browseByType(label: string): Promise<NodeRecord[]> {
  const cypher = `MATCH (n:\`${label}\`) RETURN {id: id(n), label: label(n), props: properties(n)} LIMIT ${BROWSE_LIMIT}`
  return await executeCypherSearch(cypher)
}

async function searchWithinType(term: string, label: string): Promise<NodeRecord[]> {
  // Try slug search first via REST API for exact matches
  try {
    const result = await findNodesBySlug(term, label)
    if (result.nodes.length > 0) return result.nodes
  } catch {
    // Fall through to Cypher search
  }

  // Property-based Cypher search within the type
  const escaped = escapeCypherString(term)
  const cypher = `MATCH (n:\`${label}\`) WHERE n.slug CONTAINS '${escaped}' OR n.name CONTAINS '${escaped}' OR n.title CONTAINS '${escaped}' RETURN {id: id(n), label: label(n), props: properties(n)} LIMIT ${SEARCH_LIMIT}`
  return await executeCypherSearch(cypher)
}

async function searchAcrossTypes(term: string): Promise<NodeRecord[]> {
  // Try slug search first via REST API for exact matches
  try {
    const result = await findNodesBySlug(term)
    if (result.nodes.length > 0) return result.nodes
  } catch {
    // Fall through to Cypher search
  }

  // Property-based Cypher search across all types
  const escaped = escapeCypherString(term)
  const cypher = `MATCH (n) WHERE n.slug CONTAINS '${escaped}' OR n.name CONTAINS '${escaped}' OR n.title CONTAINS '${escaped}' RETURN {id: id(n), label: label(n), props: properties(n)} LIMIT ${SEARCH_LIMIT}`
  return await executeCypherSearch(cypher)
}

async function executeCypherSearch(cypher: string): Promise<NodeRecord[]> {
  const result = await queryGraph(cypher, 15, 100)
  return result.rows.map(transformCypherRow)
}

function transformCypherRow(row: Record<string, unknown>): NodeRecord {
  // Each row has a single key whose value is {id, label, props}
  const values = Object.values(row)
  const data = values[0] as Record<string, unknown> | undefined

  if (!data) {
    return { id: 'unknown', label: 'Unknown', properties: {} }
  }

  const props = (data.props as Record<string, unknown>) || {}
  const nodeId = props.id as string
    || String(data.id || 'unknown')
  const nodeLabel = String(data.label || 'Unknown')

  return {
    id: nodeId,
    label: nodeLabel,
    properties: props,
  }
}

function escapeCypherString(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
}

// ── Quick Browse from Type Badge ───────────────────────────────────────────

function browseType(label: string) {
  nodeTypeFilter.value = label
  searchQuery.value = ''
  handleSearch()
}

// ── Neighbor Exploration ───────────────────────────────────────────────────

async function exploreNeighbors(node: NodeRecord) {
  if (expandedNeighbors.value === node.id) {
    clearNeighborState()
    return
  }

  neighborsLoading.value = node.id
  expandedNeighbors.value = node.id

  try {
    const result = await getNodeNeighbors(node.id)
    centralNode.value = result.central_node
    neighborNodes.value = result.nodes
    neighborEdges.value = result.edges

    // Add to exploration path if not already the last item
    const lastInPath = explorationPath.value[explorationPath.value.length - 1]
    if (!lastInPath || lastInPath.id !== node.id) {
      explorationPath.value.push(node)
    }
  } catch (err) {
    toast.error('Failed to load neighbors', {
      description: extractErrorMessage(err),
    })
    expandedNeighbors.value = null
  } finally {
    neighborsLoading.value = null
  }
}

function drillIntoNeighbor(neighbor: NodeRecord) {
  // Replace search results with the neighbor as a single result and explore it
  searchResults.value = [neighbor]
  hasSearched.value = true
  searchDescription.value = `Exploring node: ${getNodeDisplayName(neighbor)}`
  resultLimitHit.value = false
  expandedNeighbors.value = null
  neighborNodes.value = []
  neighborEdges.value = []
  centralNode.value = null

  // Trigger neighbor exploration on the new node
  exploreNeighbors(neighbor)
}

function navigateBackTo(index: number) {
  const node = explorationPath.value[index]
  explorationPath.value = explorationPath.value.slice(0, index)
  drillIntoNeighbor(node)
}

function clearNeighborState() {
  expandedNeighbors.value = null
  neighborNodes.value = []
  neighborEdges.value = []
  centralNode.value = null
}

function getEdgeLabelForNeighbor(neighborId: string): { label: string; direction: 'outgoing' | 'incoming' } | null {
  if (!centralNode.value) return null
  const edge = neighborEdges.value.find(
    e => e.start_id === neighborId || e.end_id === neighborId,
  )
  if (!edge) return null
  const direction = edge.start_id === centralNode.value.id ? 'outgoing' : 'incoming'
  return { label: edge.label, direction }
}

// ── Cross-Page Navigation ──────────────────────────────────────────────────

function navigateToQuery(node: NodeRecord) {
  const cypher = `MATCH (n:\`${node.label}\`) WHERE n.id = '${escapeCypherString(node.id)}' RETURN n`
  navigateTo({
    path: '/query',
    query: { query: cypher },
  })
}

function navigateToSchema(label: string) {
  navigateTo({
    path: '/graph/schema',
  })
}

function navigateToQueryConsole() {
  navigateTo('/query')
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
  const next = new Set(expandedProps.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedProps.value = next
}

const canSearch = computed(() => {
  return searching.value === false && (searchQuery.value.trim() !== '' || nodeTypeFilter.value !== '')
})

onMounted(() => {
  if (hasTenant.value) loadNodeTypes()

  // Accept ?type= URL parameter for cross-page deep-linking (e.g., from Schema Browser)
  const route = useRoute()
  const typeParam = route.query.type
  if (typeof typeParam === 'string' && typeParam.trim()) {
    nodeTypeFilter.value = typeParam.trim()
    // Auto-browse when arriving with a type parameter
    handleSearch()
  }
})

// Re-fetch when tenant changes
watch(tenantVersion, () => {
  if (hasTenant.value) {
    searchResults.value = []
    hasSearched.value = false
    searchQuery.value = ''
    nodeTypeFilter.value = ''
    searchDescription.value = ''
    resultLimitHit.value = false
    clearNeighborState()
    explorationPath.value = []
    loadNodeTypes()
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <div class="flex items-center gap-3">
        <Share2 class="size-6 text-muted-foreground" />
        <h1 class="text-2xl font-bold tracking-tight">Graph Explorer</h1>
      </div>
      <p class="mt-1 text-muted-foreground">Browse, search, and traverse nodes in the knowledge graph.</p>
    </div>

    <!-- No tenant selected -->
    <template v-if="!hasTenant">
      <div class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
        <Building2 class="size-10" />
        <p class="font-medium">No tenant selected</p>
        <p class="text-sm">Select a tenant from the header to explore the graph.</p>
      </div>
    </template>

    <template v-else>

    <!-- Search Section -->
    <Card>
      <CardContent class="pt-6">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-end">
          <!-- Type filter -->
          <div class="w-full space-y-1.5 sm:w-56">
            <Label>Node Type</Label>
            <Popover v-model:open="typeFilterOpen">
              <PopoverTrigger as-child>
                <Button
                  variant="outline"
                  role="combobox"
                  :aria-expanded="typeFilterOpen"
                  class="w-full justify-between font-normal"
                >
                  <Loader2 v-if="nodeTypesLoading" class="mr-2 size-4 animate-spin" />
                  <span class="truncate">{{ typeFilterLabel }}</span>
                  <div class="ml-2 flex shrink-0 items-center gap-1">
                    <button
                      v-if="nodeTypeFilter"
                      class="rounded-sm p-0.5 hover:bg-accent"
                      @click.stop="clearNodeTypeFilter"
                    >
                      <X class="size-3" />
                    </button>
                    <ChevronsUpDown class="size-4 opacity-50" />
                  </div>
                </Button>
              </PopoverTrigger>
              <PopoverContent class="w-[280px] p-0" align="start">
                <Command>
                  <CommandInput v-model="typeFilterSearch" placeholder="Search types..." />
                  <CommandList class="max-h-64">
                    <CommandEmpty>No types found.</CommandEmpty>
                    <CommandGroup>
                      <CommandItem
                        v-for="nt in filteredNodeTypes"
                        :key="nt"
                        :value="nt"
                        @select="selectNodeType(nt)"
                      >
                        <Check
                          class="mr-2 size-4"
                          :class="nodeTypeFilter === nt ? 'opacity-100' : 'opacity-0'"
                        />
                        {{ nt }}
                      </CommandItem>
                      <div
                        v-if="!typeFilterSearch && availableNodeTypes.length > COMBOBOX_LIMIT"
                        class="px-2 py-1.5 text-center text-xs text-muted-foreground"
                      >
                        Showing {{ COMBOBOX_LIMIT }} of {{ availableNodeTypes.length }} types. Search to narrow down.
                      </div>
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>

          <!-- Search input -->
          <div class="flex-1 space-y-1.5">
            <Label for="search-input">Search</Label>
            <div class="relative">
              <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="search-input"
                v-model="searchQuery"
                placeholder="Search by name, slug, or title..."
                class="pl-9"
                @keydown.enter="handleSearch"
              />
            </div>
          </div>

          <Button :disabled="!canSearch" @click="handleSearch">
            <Loader2 v-if="searching" class="mr-2 size-4 animate-spin" />
            <Search v-else class="mr-2 size-4" />
            {{ !searchQuery.trim() && nodeTypeFilter ? 'Browse' : 'Search' }}
          </Button>
        </div>
        <p class="mt-2 text-xs text-muted-foreground">
          Select a type to browse all instances, or enter text to search by name, slug, or title.
        </p>
      </CardContent>
    </Card>

    <!-- Exploration Breadcrumb Trail -->
    <div v-if="explorationPath.length > 1" class="flex items-center gap-1 text-sm">
      <Compass class="size-4 text-muted-foreground" />
      <template v-for="(node, index) in explorationPath" :key="`path-${index}`">
        <button
          v-if="index < explorationPath.length - 1"
          class="rounded px-1.5 py-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          @click="navigateBackTo(index)"
        >
          {{ getNodeDisplayName(node) }}
        </button>
        <span v-else class="rounded bg-accent px-1.5 py-0.5 font-medium">
          {{ getNodeDisplayName(node) }}
        </span>
        <ArrowRight v-if="index < explorationPath.length - 1" class="size-3 text-muted-foreground" />
      </template>
    </div>

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
          <p class="text-sm">
            <template v-if="searchQuery">No nodes match "{{ searchQuery }}".</template>
            <template v-else>No instances of this type exist yet.</template>
            Try a different search term or type.
          </p>
        </CardContent>
      </Card>

      <!-- Results list -->
      <div v-else class="space-y-3">
        <!-- Results header with search mode indicator -->
        <div class="flex items-center justify-between">
          <div class="space-y-0.5">
            <h2 class="text-sm font-medium text-muted-foreground">
              Found {{ searchResults.length }} node{{ searchResults.length === 1 ? '' : 's' }}
            </h2>
            <p v-if="searchDescription" class="text-xs text-muted-foreground">
              {{ searchDescription }}
            </p>
          </div>
        </div>

        <!-- Pagination hint -->
        <div
          v-if="resultLimitHit"
          class="flex items-center gap-2 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground"
        >
          <Info class="size-3.5 shrink-0" />
          <span>
            Showing first {{ searchResults.length }} results. Refine your search or use the
            <button class="font-medium text-foreground underline underline-offset-2" @click="navigateToQueryConsole">
              Query Console
            </button>
            for custom queries.
          </span>
        </div>

        <div class="grid gap-3 md:grid-cols-2">
          <Card v-for="node in searchResults" :key="node.id" class="flex flex-col">
            <CardHeader class="pb-3">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <CardTitle class="truncate text-base">{{ getNodeDisplayName(node) }}</CardTitle>
                  <CopyableText :text="node.id" label="Node ID copied" />
                </div>
                <Badge variant="default" class="shrink-0 cursor-pointer" @click="browseType(node.label)">
                  {{ node.label }}
                </Badge>
              </div>
            </CardHeader>
            <CardContent class="flex flex-1 flex-col gap-3">
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

              <!-- Action buttons -->
              <div class="mt-auto flex items-center gap-1 border-t pt-3">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="sm"
                      class="h-7 gap-1.5 text-xs"
                      :disabled="neighborsLoading === node.id"
                      @click="exploreNeighbors(node)"
                    >
                      <Loader2 v-if="neighborsLoading === node.id" class="size-3 animate-spin" />
                      <Compass v-else class="size-3" />
                      {{ expandedNeighbors === node.id ? 'Hide' : 'Explore' }} Neighbors
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent><p>Explore connected nodes</p></TooltipContent>
                </Tooltip>

                <Separator orientation="vertical" class="mx-1 h-4" />

                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="size-7"
                      @click="navigateToQuery(node)"
                    >
                      <Terminal class="size-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent><p>Query in console</p></TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="size-7"
                      @click="navigateToSchema(node.label)"
                    >
                      <Database class="size-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent><p>View type schema</p></TooltipContent>
                </Tooltip>
              </div>

              <!-- Neighbor Exploration Panel -->
              <div
                v-if="expandedNeighbors === node.id && neighborNodes.length > 0"
                class="rounded-md border bg-muted/30 p-3"
              >
                <h3 class="mb-2 text-xs font-medium text-muted-foreground">
                  {{ neighborNodes.length }} connected node{{ neighborNodes.length === 1 ? '' : 's' }}
                </h3>
                <div class="space-y-1.5">
                  <button
                    v-for="neighbor in neighborNodes"
                    :key="neighbor.id"
                    class="flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-accent"
                    @click="drillIntoNeighbor(neighbor)"
                  >
                    <CornerDownRight class="size-3 shrink-0 text-muted-foreground" />
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-2">
                        <span class="truncate font-medium">{{ getNodeDisplayName(neighbor) }}</span>
                        <Badge variant="outline" class="shrink-0 text-[10px]">{{ neighbor.label }}</Badge>
                      </div>
                      <div v-if="getEdgeLabelForNeighbor(neighbor.id)" class="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                        <ArrowRight v-if="getEdgeLabelForNeighbor(neighbor.id)!.direction === 'outgoing'" class="size-2.5" />
                        <ArrowLeft v-else class="size-2.5" />
                        <span class="font-mono">{{ getEdgeLabelForNeighbor(neighbor.id)!.label }}</span>
                      </div>
                    </div>
                  </button>
                </div>
              </div>

              <!-- Empty neighbors -->
              <div
                v-else-if="expandedNeighbors === node.id && !neighborsLoading && neighborNodes.length === 0"
                class="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground"
              >
                No connected nodes found.
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </template>

    <!-- Initial state (no search yet) -->
    <Card v-else>
      <CardContent class="flex flex-col items-center gap-4 py-12 text-center">
        <Share2 class="size-10 text-muted-foreground" />
        <div>
          <p class="font-medium">Start Exploring</p>
          <p class="mt-1 text-sm text-muted-foreground">
            Select a type to browse instances, or search by name or slug.
          </p>
        </div>

        <!-- Type chips for quick browse -->
        <div v-if="availableNodeTypes.length > 0" class="space-y-2">
          <p class="text-xs text-muted-foreground">Quick browse by type:</p>
          <div class="flex flex-wrap justify-center gap-1.5">
            <button
              v-for="label in availableNodeTypes.slice(0, 20)"
              :key="label"
              class="rounded-full border px-3 py-1 text-xs transition-colors hover:bg-accent hover:text-accent-foreground"
              @click="browseType(label)"
            >
              {{ label }}
            </button>
            <span
              v-if="availableNodeTypes.length > 20"
              class="rounded-full border border-dashed px-3 py-1 text-xs text-muted-foreground"
            >
              +{{ availableNodeTypes.length - 20 }} more
            </span>
          </div>
        </div>

        <!-- Loading types -->
        <div v-else-if="nodeTypesLoading" class="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading types...
        </div>

        <!-- Link to schema browser -->
        <div class="pt-2">
          <NuxtLink
            to="/graph/schema"
            class="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <Database class="size-3.5" />
            Browse type definitions in the Schema Browser
          </NuxtLink>
        </div>
      </CardContent>
    </Card>

    </template>
  </div>
</template>
