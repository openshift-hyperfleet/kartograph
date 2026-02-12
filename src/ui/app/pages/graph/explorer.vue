<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import {
  Share2, Search, Loader2, ArrowRight, ArrowLeft,
  ChevronRight, Compass, CircleDot, Info,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty,
} from '@/components/ui/table'
import type { NodeRecord, EdgeRecord, NodeNeighborsResult } from '~/types'

const { findNodesBySlug, getNodeNeighbors, listNodeLabels } = useGraphApi()

// ── State ──────────────────────────────────────────────────────────────────

// Search
const slugQuery = ref('')
const nodeTypeFilter = ref<string>('')
const availableNodeTypes = ref<string[]>([])
const searching = ref(false)
const searchResults = ref<NodeRecord[]>([])
const hasSearched = ref(false)

// Neighbor exploration
const neighborResult = ref<NodeNeighborsResult | null>(null)
const neighborsLoading = ref(false)

// Breadcrumb trail
interface BreadcrumbEntry {
  nodeId: string
  label: string
  displayName: string
}
const breadcrumbs = ref<BreadcrumbEntry[]>([])

// ── Computed ───────────────────────────────────────────────────────────────

const currentCentralNode = computed(() => neighborResult.value?.central_node ?? null)

// ── Data loading ───────────────────────────────────────────────────────────

async function loadNodeTypes() {
  try {
    const result = await listNodeLabels()
    availableNodeTypes.value = result.labels
  } catch {
    // Non-critical: filter dropdown just won't have options
  }
}

async function handleSearch() {
  if (!slugQuery.value.trim()) return
  searching.value = true
  hasSearched.value = true
  neighborResult.value = null
  breadcrumbs.value = []
  try {
    const typeArg = nodeTypeFilter.value || undefined
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

async function exploreNeighbors(node: NodeRecord) {
  neighborsLoading.value = true
  try {
    neighborResult.value = await getNodeNeighbors(node.id)
    // Update breadcrumbs
    const existingIndex = breadcrumbs.value.findIndex(b => b.nodeId === node.id)
    if (existingIndex >= 0) {
      // Navigating back to an already-visited node: truncate trail
      breadcrumbs.value = breadcrumbs.value.slice(0, existingIndex + 1)
    } else {
      breadcrumbs.value.push({
        nodeId: node.id,
        label: node.label,
        displayName: getNodeDisplayName(node),
      })
    }
  } catch (err) {
    toast.error('Failed to load neighbors', {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
  } finally {
    neighborsLoading.value = false
  }
}

function navigateBreadcrumb(entry: BreadcrumbEntry) {
  // Re-explore from that node
  exploreNeighbors({
    id: entry.nodeId,
    label: entry.label,
    properties: {},
  })
}

function backToSearch() {
  neighborResult.value = null
  breadcrumbs.value = []
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

function getEdgeDirection(edge: EdgeRecord, nodeId: string): 'outgoing' | 'incoming' {
  return edge.start_id === nodeId ? 'outgoing' : 'incoming'
}

function getNeighborForEdge(edge: EdgeRecord): NodeRecord | undefined {
  if (!neighborResult.value) return undefined
  const targetId = edge.start_id === neighborResult.value.central_node.id
    ? edge.end_id
    : edge.start_id
  return neighborResult.value.nodes.find(n => n.id === targetId)
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
    <p class="text-muted-foreground">Search for nodes and explore their relationships in the knowledge graph.</p>

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
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All types</SelectItem>
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

    <!-- Breadcrumb Trail -->
    <div v-if="breadcrumbs.length > 0" class="flex flex-wrap items-center gap-1 text-sm">
      <button
        class="text-muted-foreground transition-colors hover:text-foreground"
        @click="backToSearch"
      >
        Search Results
      </button>
      <template v-for="(crumb, idx) in breadcrumbs" :key="crumb.nodeId">
        <ChevronRight class="size-3 text-muted-foreground" />
        <button
          class="max-w-[200px] truncate rounded px-1.5 py-0.5 transition-colors hover:bg-accent"
          :class="{ 'font-medium text-foreground': idx === breadcrumbs.length - 1, 'text-muted-foreground': idx !== breadcrumbs.length - 1 }"
          @click="navigateBreadcrumb(crumb)"
        >
          {{ crumb.displayName }}
        </button>
      </template>
    </div>

    <!-- Neighbor Exploration View -->
    <template v-if="neighborResult">
      <!-- Loading overlay -->
      <div v-if="neighborsLoading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
        <Loader2 class="size-4 animate-spin" />
        Loading neighbors...
      </div>

      <template v-else>
        <!-- Central Node -->
        <Card class="border-primary">
          <CardHeader>
            <div class="flex items-center gap-2">
              <CircleDot class="size-5 text-primary" />
              <CardTitle>{{ getNodeDisplayName(neighborResult.central_node) }}</CardTitle>
              <Badge variant="default">{{ neighborResult.central_node.label }}</Badge>
            </div>
            <CardDescription class="font-mono text-xs">
              {{ neighborResult.central_node.id }}
            </CardDescription>
          </CardHeader>
          <CardContent v-if="getPropertyEntries(neighborResult.central_node.properties).length > 0">
            <div class="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead class="w-[180px]">Property</TableHead>
                    <TableHead>Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-for="[key, value] in getPropertyEntries(neighborResult.central_node.properties)" :key="key">
                    <TableCell class="font-mono text-xs font-medium">{{ key }}</TableCell>
                    <TableCell class="font-mono text-xs">{{ formatPropertyValue(value) }}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <!-- Connections -->
        <div v-if="neighborResult.edges.length > 0" class="space-y-3">
          <h2 class="flex items-center gap-2 text-lg font-semibold">
            <Compass class="size-5" />
            Connections
            <Badge variant="secondary">{{ neighborResult.edges.length }}</Badge>
          </h2>

          <div class="space-y-2">
            <Card
              v-for="edge in neighborResult.edges"
              :key="edge.id"
              class="transition-colors hover:bg-accent/50"
            >
              <CardContent class="py-4">
                <div class="flex items-start gap-4">
                  <!-- Direction indicator -->
                  <div class="mt-1 flex flex-col items-center gap-1">
                    <ArrowRight
                      v-if="getEdgeDirection(edge, neighborResult.central_node.id) === 'outgoing'"
                      class="size-5 text-primary"
                    />
                    <ArrowLeft
                      v-else
                      class="size-5 text-muted-foreground"
                    />
                    <span class="text-[10px] uppercase text-muted-foreground">
                      {{ getEdgeDirection(edge, neighborResult.central_node.id) === 'outgoing' ? 'out' : 'in' }}
                    </span>
                  </div>

                  <!-- Edge + neighbor info -->
                  <div class="min-w-0 flex-1 space-y-2">
                    <div class="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{{ edge.label }}</Badge>
                      <span class="text-xs text-muted-foreground">
                        {{ getEdgeDirection(edge, neighborResult.central_node.id) === 'outgoing' ? '→' : '←' }}
                      </span>
                      <template v-if="getNeighborForEdge(edge)">
                        <Badge variant="default">{{ getNeighborForEdge(edge)!.label }}</Badge>
                        <span class="truncate font-medium">
                          {{ getNodeDisplayName(getNeighborForEdge(edge)!) }}
                        </span>
                      </template>
                    </div>

                    <!-- Edge properties (inline) -->
                    <div v-if="getPropertyEntries(edge.properties).length > 0" class="flex flex-wrap gap-2">
                      <span
                        v-for="[key, value] in getPropertyEntries(edge.properties)"
                        :key="key"
                        class="rounded bg-muted px-2 py-0.5 font-mono text-xs"
                      >
                        {{ key }}: {{ formatPropertyValue(value) }}
                      </span>
                    </div>
                  </div>

                  <!-- Explore button -->
                  <Button
                    v-if="getNeighborForEdge(edge)"
                    variant="ghost"
                    size="sm"
                    @click="exploreNeighbors(getNeighborForEdge(edge)!)"
                  >
                    Explore
                    <ChevronRight class="ml-1 size-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <!-- No connections -->
        <Card v-else>
          <CardContent class="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
            <Info class="size-8" />
            <p class="font-medium">No connections</p>
            <p class="text-sm">This node has no edges to other nodes.</p>
          </CardContent>
        </Card>

        <Button variant="outline" @click="backToSearch">
          <ArrowLeft class="mr-2 size-4" />
          Back to Search Results
        </Button>
      </template>
    </template>

    <!-- Search Results (shown when not exploring) -->
    <template v-else-if="hasSearched">
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
            <CardContent class="space-y-3">
              <!-- Properties table -->
              <div v-if="getPropertyEntries(node.properties).length > 0" class="rounded-md border">
                <Table>
                  <TableBody>
                    <TableRow v-for="[key, value] in getPropertyEntries(node.properties)" :key="key">
                      <TableCell class="w-[120px] font-mono text-xs font-medium text-muted-foreground">{{ key }}</TableCell>
                      <TableCell class="font-mono text-xs">{{ formatPropertyValue(value) }}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>

              <Separator />

              <Button variant="outline" size="sm" class="w-full" @click="exploreNeighbors(node)">
                <Compass class="mr-2 size-4" />
                Explore Neighbors
              </Button>
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
