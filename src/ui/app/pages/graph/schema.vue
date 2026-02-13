<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import {
  Database, GitBranch, Search, Loader2, Info, ChevronRight, ChevronDown,
  Building2, Terminal, Share2, FileCode, Plus,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Table, TableBody, TableRow, TableCell,
} from '@/components/ui/table'
import { CopyableText } from '@/components/ui/copyable-text'
import type { TypeDefinition } from '~/types'

const { listNodeLabels, listEdgeLabels, getNodeSchema, getEdgeSchema } = useGraphApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── State ──────────────────────────────────────────────────────────────────

const activeTab = ref('nodes')

// Node types
const nodeLabels = ref<string[]>([])
const nodeTotalCount = ref(0)
const nodeLabelsLoading = ref(false)

// Edge types
const edgeLabels = ref<string[]>([])
const edgeTotalCount = ref(0)
const edgeLabelsLoading = ref(false)

// Unified search (covers type names + cached property names)
const searchQuery = ref('')
const searchInputRef = ref<InstanceType<typeof Input> | null>(null)

// Inline-expand schema detail
const expandedLabels = reactive(new Set<string>())
const schemaCache = reactive(new Map<string, TypeDefinition>())
const schemaLoadingLabels = reactive(new Set<string>())

// ── Data loading ───────────────────────────────────────────────────────────

let searchDebounce: ReturnType<typeof setTimeout> | null = null

async function fetchNodeLabels() {
  nodeLabelsLoading.value = true
  try {
    const result = await listNodeLabels()
    nodeLabels.value = result.labels
    nodeTotalCount.value = result.count
  } catch (err) {
    toast.error('Failed to load node types', {
      description: extractErrorMessage(err),
    })
  } finally {
    nodeLabelsLoading.value = false
  }
}

async function fetchEdgeLabels() {
  edgeLabelsLoading.value = true
  try {
    const result = await listEdgeLabels()
    edgeLabels.value = result.labels
    edgeTotalCount.value = result.count
  } catch (err) {
    toast.error('Failed to load edge types', {
      description: extractErrorMessage(err),
    })
  } finally {
    edgeLabelsLoading.value = false
  }
}

// ── Filtering ──────────────────────────────────────────────────────────────

const filteredNodeLabels = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return nodeLabels.value

  return nodeLabels.value.filter((label) => {
    // Match label name
    if (label.toLowerCase().includes(q)) return true
    // Match cached property names
    const schema = schemaCache.get(label)
    if (schema) {
      const allProps = [...schema.required_properties, ...schema.optional_properties]
      if (allProps.some(p => p.toLowerCase().includes(q))) return true
    }
    return false
  })
})

const filteredEdgeLabels = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return edgeLabels.value

  return edgeLabels.value.filter((label) => {
    if (label.toLowerCase().includes(q)) return true
    const schema = schemaCache.get(label)
    if (schema) {
      const allProps = [...schema.required_properties, ...schema.optional_properties]
      if (allProps.some(p => p.toLowerCase().includes(q))) return true
    }
    return false
  })
})

// ── Inline Expand ──────────────────────────────────────────────────────────

function toggleExpand(label: string, entityType: 'node' | 'edge') {
  if (expandedLabels.has(label)) {
    expandedLabels.delete(label)
    return
  }

  expandedLabels.add(label)
  if (!schemaCache.has(label)) {
    fetchLabelSchema(label, entityType)
  }
}

async function fetchLabelSchema(label: string, entityType: 'node' | 'edge') {
  schemaLoadingLabels.add(label)
  try {
    const schema = entityType === 'node'
      ? await getNodeSchema(label)
      : await getEdgeSchema(label)
    schemaCache.set(label, schema)
  } catch (err) {
    toast.error(`Failed to load schema for "${label}"`, {
      description: extractErrorMessage(err),
    })
    expandedLabels.delete(label)
  } finally {
    schemaLoadingLabels.delete(label)
  }
}

// ── Cross-page Navigation ──────────────────────────────────────────────────

function navigateToQuery(label: string, entityType: 'node' | 'edge') {
  const cypher = entityType === 'node'
    ? `MATCH (n:\`${label}\`) RETURN n LIMIT 25`
    : `MATCH (a)-[r:\`${label}\`]->(b) RETURN a, r, b LIMIT 25`

  navigateTo({
    path: '/query',
    query: { query: cypher },
  })
}

function navigateToExplorer(label: string) {
  navigateTo({
    path: '/graph/explorer',
    query: { type: label },
  })
}

function navigateToMutations(label: string, entityType: 'node' | 'edge') {
  const template = JSON.stringify({
    op: 'DEFINE',
    type: entityType,
    label,
    description: '',
    required_properties: [],
    optional_properties: [],
  })

  navigateTo({
    path: '/graph/mutations',
    query: { template },
  })
}

function navigateToMutationsCreate() {
  navigateTo('/graph/mutations')
}

// ── Keyboard Shortcuts ─────────────────────────────────────────────────────

function handleGlobalKeydown(e: KeyboardEvent) {
  // Focus search on / or Ctrl+K
  if (
    (e.key === '/' && !isInputFocused())
    || ((e.ctrlKey || e.metaKey) && e.key === 'k')
  ) {
    e.preventDefault()
    const el = searchInputRef.value?.$el as HTMLInputElement | undefined
    el?.focus()
  }
}

function isInputFocused(): boolean {
  const active = document.activeElement
  return active instanceof HTMLInputElement
    || active instanceof HTMLTextAreaElement
    || active?.getAttribute('contenteditable') === 'true'
}

// ── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(() => {
  if (hasTenant.value) {
    fetchNodeLabels()
    fetchEdgeLabels()
  }
  document.addEventListener('keydown', handleGlobalKeydown)
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    nodeLabels.value = []
    edgeLabels.value = []
    nodeTotalCount.value = 0
    edgeTotalCount.value = 0
    searchQuery.value = ''
    expandedLabels.clear()
    schemaCache.clear()
    fetchNodeLabels()
    fetchEdgeLabels()
  }
})

onUnmounted(() => {
  if (searchDebounce) clearTimeout(searchDebounce)
  document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <div class="flex items-center gap-3">
        <Database class="size-6 text-muted-foreground" />
        <h1 class="text-2xl font-bold tracking-tight">Schema Browser</h1>
      </div>
      <p class="mt-1 text-muted-foreground">
        Browse and inspect the knowledge graph schema definitions.
      </p>
    </div>

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the header to browse the graph schema.</p>
    </div>

    <template v-else>
      <!-- Search bar (unified across both tabs) -->
      <div class="relative">
        <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref="searchInputRef"
          v-model="searchQuery"
          placeholder="Filter types and properties...  (/ to focus)"
          class="pl-9 pr-16"
        />
        <kbd
          class="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline"
        >
          Ctrl+K
        </kbd>
      </div>

      <!-- Tabs -->
      <Tabs v-model="activeTab">
        <TabsList class="w-full">
          <TabsTrigger value="nodes" class="flex-1">
            <Database class="mr-1.5 size-3.5" />
            Node Types
            <Badge variant="secondary" class="ml-2">{{ nodeTotalCount }}</Badge>
          </TabsTrigger>
          <TabsTrigger value="edges" class="flex-1">
            <GitBranch class="mr-1.5 size-3.5" />
            Edge Types
            <Badge variant="secondary" class="ml-2">{{ edgeTotalCount }}</Badge>
          </TabsTrigger>
        </TabsList>

        <!-- Node Types Tab -->
        <TabsContent value="nodes" class="mt-4 space-y-3">
          <p v-if="searchQuery && !nodeLabelsLoading" class="text-sm text-muted-foreground">
            Showing {{ filteredNodeLabels.length }} of {{ nodeTotalCount }} node types
          </p>

          <!-- Loading -->
          <div v-if="nodeLabelsLoading" class="flex items-center justify-center gap-2 py-8 text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />
            Loading node types...
          </div>

          <!-- Empty (no types defined) -->
          <Card v-else-if="nodeLabels.length === 0">
            <CardContent class="flex flex-col items-center gap-3 py-8 text-center text-muted-foreground">
              <Info class="size-8" />
              <p class="font-medium">No node types defined</p>
              <p class="text-sm">Define your first node type schema via the Mutations console.</p>
              <Button variant="outline" size="sm" @click="navigateToMutationsCreate">
                <FileCode class="mr-2 size-4" />
                Open Mutations Console
              </Button>
            </CardContent>
          </Card>

          <!-- Empty (search has no results) -->
          <Card v-else-if="filteredNodeLabels.length === 0">
            <CardContent class="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
              <Search class="size-8" />
              <p class="font-medium">No matching node types</p>
              <p class="text-sm">No node types match "{{ searchQuery }}".</p>
            </CardContent>
          </Card>

          <!-- Label list -->
          <div v-else role="list" aria-label="Node types" class="max-h-[calc(100vh-16rem)] space-y-1 overflow-y-auto">
            <div v-for="label in filteredNodeLabels" :key="label" role="listitem">
              <!-- Type row -->
              <div
                class="group flex w-full items-center gap-1 rounded-md border px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent"
              >
                <!-- Expand chevron -->
                <button
                  class="flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  :aria-expanded="expandedLabels.has(label)"
                  :aria-label="`Expand properties for ${label}`"
                  @click="toggleExpand(label, 'node')"
                >
                  <Loader2 v-if="schemaLoadingLabels.has(label)" class="size-3.5 animate-spin" />
                  <ChevronDown v-else-if="expandedLabels.has(label)" class="size-3.5" />
                  <ChevronRight v-else class="size-3.5" />
                </button>

                <!-- Label name (clickable to expand) -->
                <button
                  class="flex min-w-0 flex-1 items-center gap-2"
                  @click="toggleExpand(label, 'node')"
                >
                  <Badge variant="default" class="shrink-0">Node</Badge>
                  <CopyableText :text="label" label="Type label copied" :truncate="false" />
                </button>

                <!-- Contextual action buttons -->
                <div class="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-7"
                        @click.stop="navigateToQuery(label, 'node')"
                      >
                        <Terminal class="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent><p>Query instances</p></TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-7"
                        @click.stop="navigateToExplorer(label)"
                      >
                        <Share2 class="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent><p>Explore instances</p></TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-7"
                        @click.stop="navigateToMutations(label, 'node')"
                      >
                        <FileCode class="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent><p>Edit type definition</p></TooltipContent>
                  </Tooltip>
                </div>
              </div>

              <!-- Expanded properties (inline) -->
              <div
                v-if="expandedLabels.has(label)"
                class="ml-7 mt-1 mb-2 rounded-md border bg-muted/30 p-3"
              >
                <div v-if="schemaLoadingLabels.has(label)" class="flex items-center gap-2 py-2">
                  <Loader2 class="size-3.5 animate-spin text-muted-foreground" />
                  <span class="text-sm text-muted-foreground">Loading properties...</span>
                </div>
                <template v-else-if="schemaCache.has(label)">
                  <!-- Description -->
                  <p
                    v-if="schemaCache.get(label)!.description"
                    class="mb-3 text-sm text-muted-foreground"
                  >
                    {{ schemaCache.get(label)!.description }}
                  </p>

                  <!-- No properties -->
                  <p
                    v-if="schemaCache.get(label)!.required_properties.length === 0 && schemaCache.get(label)!.optional_properties.length === 0"
                    class="text-sm text-muted-foreground"
                  >
                    No properties defined.
                  </p>

                  <!-- Properties table -->
                  <div
                    v-else
                    class="rounded-md border"
                  >
                    <Table>
                      <TableBody>
                        <TableRow
                          v-for="prop in schemaCache.get(label)!.required_properties"
                          :key="`req-${prop}`"
                        >
                          <TableCell class="py-1.5 font-mono text-xs">
                            {{ prop }}
                          </TableCell>
                          <TableCell class="w-24 py-1.5 text-right">
                            <Badge variant="default" class="text-[10px]">Required</Badge>
                          </TableCell>
                        </TableRow>
                        <TableRow
                          v-for="prop in schemaCache.get(label)!.optional_properties"
                          :key="`opt-${prop}`"
                        >
                          <TableCell class="py-1.5 font-mono text-xs">
                            {{ prop }}
                          </TableCell>
                          <TableCell class="w-24 py-1.5 text-right">
                            <Badge variant="secondary" class="text-[10px]">Optional</Badge>
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </TabsContent>

        <!-- Edge Types Tab -->
        <TabsContent value="edges" class="mt-4 space-y-3">
          <p v-if="searchQuery && !edgeLabelsLoading" class="text-sm text-muted-foreground">
            Showing {{ filteredEdgeLabels.length }} of {{ edgeTotalCount }} edge types
          </p>

          <!-- Loading -->
          <div v-if="edgeLabelsLoading" class="flex items-center justify-center gap-2 py-8 text-muted-foreground">
            <Loader2 class="size-4 animate-spin" />
            Loading edge types...
          </div>

          <!-- Empty (no types defined) -->
          <Card v-else-if="edgeLabels.length === 0">
            <CardContent class="flex flex-col items-center gap-3 py-8 text-center text-muted-foreground">
              <Info class="size-8" />
              <p class="font-medium">No edge types defined</p>
              <p class="text-sm">Define your first edge type schema via the Mutations console.</p>
              <Button variant="outline" size="sm" @click="navigateToMutationsCreate">
                <FileCode class="mr-2 size-4" />
                Open Mutations Console
              </Button>
            </CardContent>
          </Card>

          <!-- Empty (search has no results) -->
          <Card v-else-if="filteredEdgeLabels.length === 0">
            <CardContent class="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
              <Search class="size-8" />
              <p class="font-medium">No matching edge types</p>
              <p class="text-sm">No edge types match "{{ searchQuery }}".</p>
            </CardContent>
          </Card>

          <!-- Label list -->
          <div v-else role="list" aria-label="Edge types" class="max-h-[calc(100vh-16rem)] space-y-1 overflow-y-auto">
            <div v-for="label in filteredEdgeLabels" :key="label" role="listitem">
              <!-- Type row -->
              <div
                class="group flex w-full items-center gap-1 rounded-md border px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent"
              >
                <!-- Expand chevron -->
                <button
                  class="flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  :aria-expanded="expandedLabels.has(label)"
                  :aria-label="`Expand properties for ${label}`"
                  @click="toggleExpand(label, 'edge')"
                >
                  <Loader2 v-if="schemaLoadingLabels.has(label)" class="size-3.5 animate-spin" />
                  <ChevronDown v-else-if="expandedLabels.has(label)" class="size-3.5" />
                  <ChevronRight v-else class="size-3.5" />
                </button>

                <!-- Label name (clickable to expand) -->
                <button
                  class="flex min-w-0 flex-1 items-center gap-2"
                  @click="toggleExpand(label, 'edge')"
                >
                  <Badge variant="outline" class="shrink-0">Edge</Badge>
                  <CopyableText :text="label" label="Type label copied" :truncate="false" />
                </button>

                <!-- Contextual action buttons -->
                <div class="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-7"
                        @click.stop="navigateToQuery(label, 'edge')"
                      >
                        <Terminal class="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent><p>Query instances</p></TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-7"
                        @click.stop="navigateToMutations(label, 'edge')"
                      >
                        <FileCode class="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent><p>Edit type definition</p></TooltipContent>
                  </Tooltip>
                </div>
              </div>

              <!-- Expanded properties (inline) -->
              <div
                v-if="expandedLabels.has(label)"
                class="ml-7 mt-1 mb-2 rounded-md border bg-muted/30 p-3"
              >
                <div v-if="schemaLoadingLabels.has(label)" class="flex items-center gap-2 py-2">
                  <Loader2 class="size-3.5 animate-spin text-muted-foreground" />
                  <span class="text-sm text-muted-foreground">Loading properties...</span>
                </div>
                <template v-else-if="schemaCache.has(label)">
                  <!-- Description -->
                  <p
                    v-if="schemaCache.get(label)!.description"
                    class="mb-3 text-sm text-muted-foreground"
                  >
                    {{ schemaCache.get(label)!.description }}
                  </p>

                  <!-- No properties -->
                  <p
                    v-if="schemaCache.get(label)!.required_properties.length === 0 && schemaCache.get(label)!.optional_properties.length === 0"
                    class="text-sm text-muted-foreground"
                  >
                    No properties defined.
                  </p>

                  <!-- Properties table -->
                  <div
                    v-else
                    class="rounded-md border"
                  >
                    <Table>
                      <TableBody>
                        <TableRow
                          v-for="prop in schemaCache.get(label)!.required_properties"
                          :key="`req-${prop}`"
                        >
                          <TableCell class="py-1.5 font-mono text-xs">
                            {{ prop }}
                          </TableCell>
                          <TableCell class="w-24 py-1.5 text-right">
                            <Badge variant="default" class="text-[10px]">Required</Badge>
                          </TableCell>
                        </TableRow>
                        <TableRow
                          v-for="prop in schemaCache.get(label)!.optional_properties"
                          :key="`opt-${prop}`"
                        >
                          <TableCell class="py-1.5 font-mono text-xs">
                            {{ prop }}
                          </TableCell>
                          <TableCell class="w-24 py-1.5 text-right">
                            <Badge variant="secondary" class="text-[10px]">Optional</Badge>
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </template>
  </div>
</template>
