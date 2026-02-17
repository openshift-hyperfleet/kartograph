<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { toast } from 'vue-sonner'
import {
  Database, GitBranch, Search, Play, ChevronRight, ChevronDown,
  RefreshCw, Loader2, ArrowRight, Keyboard, TextCursorInput,
} from 'lucide-vue-next'
import { useModifierKeys } from '@/composables/useModifierKeys'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '@/components/ui/tabs'
import type { TypeDefinition, CypherResult } from '~/types'

// ── Props & Emits ──────────────────────────────────────────────────────────

const props = defineProps<{
  nodeLabels: string[]
  edgeLabels: string[]
  schemaLoading: boolean
}>()

const emit = defineEmits<{
  'execute-query': [query: string]
  'insert-at-cursor': [text: string]
}>()

// ── API ────────────────────────────────────────────────────────────────────

const { altHeld } = useModifierKeys()

const { getNodeSchema, getEdgeSchema } = useGraphApi()
const { queryGraph } = useQueryApi()
const { extractErrorMessage } = useErrorHandler()

// ── View Toggle ────────────────────────────────────────────────────────────

const activeView = ref<string>('types')

// ── Search ─────────────────────────────────────────────────────────────────

const schemaSearch = ref('')
const SCHEMA_INITIAL_LIMIT = 50
const schemaShowAll = ref(false)

const filteredNodeLabels = computed(() => {
  const search = schemaSearch.value.toLowerCase().trim()
  let labels = props.nodeLabels
  if (search) {
    labels = labels.filter(l => l.toLowerCase().includes(search))
  }
  if (!schemaShowAll.value && !search) {
    return labels.slice(0, SCHEMA_INITIAL_LIMIT)
  }
  return labels
})

const filteredEdgeLabels = computed(() => {
  const search = schemaSearch.value.toLowerCase().trim()
  let labels = props.edgeLabels
  if (search) {
    labels = labels.filter(l => l.toLowerCase().includes(search))
  }
  if (!schemaShowAll.value && !search) {
    return labels.slice(0, SCHEMA_INITIAL_LIMIT)
  }
  return labels
})

// ── R2: One-click Schema Querying ──────────────────────────────────────────

function handleNodeClick(label: string, event: MouseEvent) {
  if (event.altKey) {
    emit('insert-at-cursor', label)
  } else {
    const query = `MATCH (n:\`${label}\`) RETURN n LIMIT 25`
    emit('execute-query', query)
  }
}

function handleEdgeClick(label: string, event: MouseEvent) {
  if (event.altKey) {
    emit('insert-at-cursor', label)
  } else {
    const query = `MATCH (a)-[r:\`${label}\`]->(b) RETURN {source: a, rel: r, target: b} LIMIT 25`
    emit('execute-query', query)
  }
}

// ── R12: Schema Property Introspection ─────────────────────────────────────

const expandedLabels = reactive(new Set<string>())
const schemaCache = reactive(new Map<string, TypeDefinition>())
const schemaLoadingLabels = reactive(new Set<string>())

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

function handlePropertyClick(propertyName: string) {
  emit('insert-at-cursor', `n.${propertyName}`)
}

// ── R4: Relationship Context / Structure View ──────────────────────────────

interface RelationshipTriple {
  src: string[]
  rel: string
  tgt: string[]
}

interface GroupedRelationship {
  sourceLabel: string
  relationships: { rel: string; targetLabel: string }[]
}

const structureData = ref<RelationshipTriple[]>([])
const structureLoading = ref(false)
const structureFetched = ref(false)
const structureError = ref<string | null>(null)

const groupedStructure = computed<GroupedRelationship[]>(() => {
  const search = schemaSearch.value.toLowerCase().trim()
  const groups = new Map<string, { rel: string; targetLabel: string }[]>()

  for (const triple of structureData.value) {
    // Each src/tgt may have multiple labels; use all of them
    for (const src of triple.src) {
      for (const tgt of triple.tgt) {
        if (search) {
          const matches =
            src.toLowerCase().includes(search) ||
            triple.rel.toLowerCase().includes(search) ||
            tgt.toLowerCase().includes(search)
          if (!matches) continue
        }
        if (!groups.has(src)) {
          groups.set(src, [])
        }
        groups.get(src)!.push({ rel: triple.rel, targetLabel: tgt })
      }
    }
  }

  // Sort groups by source label, and relationships within each group
  return Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([sourceLabel, relationships]) => ({
      sourceLabel,
      relationships: relationships.sort((a, b) => a.rel.localeCompare(b.rel)),
    }))
})

async function fetchStructure() {
  structureLoading.value = true
  structureError.value = null
  try {
    // Sample edges rather than scanning the entire graph — LIMIT 500 returns
    // in under a second and captures all relationship patterns in any
    // reasonably designed knowledge graph. DISTINCT deduplicates afterward.
    const cypher = `MATCH (a)-[r]->(b) WITH labels(a) AS src, type(r) AS rel, labels(b) AS tgt RETURN DISTINCT {src: src, rel: rel, tgt: tgt} LIMIT 500`
    const result: CypherResult = await queryGraph(cypher, 10, 500)
    structureData.value = result.rows.map((row) => {
      // The query returns a single column with {src, rel, tgt} objects
      // The row keys are dynamic from AGE, so we take the first value
      const values = Object.values(row)
      const val = values[0] as RelationshipTriple
      return val
    })
    structureFetched.value = true
  } catch (err) {
    structureError.value = extractErrorMessage(err)
    toast.error('Failed to load graph structure', {
      description: structureError.value,
    })
  } finally {
    structureLoading.value = false
  }
}

function handleStructureRefresh() {
  fetchStructure()
}

// Auto-fetch structure when switching to the Structure view
function onViewChange(view: string | number | boolean) {
  if (view === 'structure' && !structureFetched.value && !structureLoading.value) {
    fetchStructure()
  }
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- View toggle: Types | Structure -->
    <Tabs
      :model-value="activeView"
      @update:model-value="(v) => { activeView = v as string; onViewChange(v) }"
    >
      <TabsList class="h-8 w-full">
        <TabsTrigger value="types" class="flex-1 text-xs">
          Types
        </TabsTrigger>
        <TabsTrigger value="structure" class="flex-1 text-xs">
          Structure
        </TabsTrigger>
      </TabsList>

      <!-- Search filter (shared across views) -->
      <div class="relative mt-2">
        <Search class="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          v-model="schemaSearch"
          :placeholder="activeView === 'types' ? 'Filter types...' : 'Filter relationships...'"
          class="h-7 pl-7 text-xs"
        />
      </div>

      <!-- Types View (R2 + R12) -->
      <TabsContent value="types" class="mt-2 space-y-3">
        <div v-if="schemaLoading" class="flex items-center justify-center py-4">
          <Loader2 class="size-4 animate-spin text-muted-foreground" />
        </div>
        <template v-else>
          <!-- Node labels -->
          <div>
            <div class="mb-2 flex items-center gap-1.5">
              <Database class="size-3.5 text-blue-500" />
              <span class="text-xs font-medium">Node Types</span>
              <Badge variant="secondary" class="ml-auto h-4 px-1 text-[10px]">
                {{ schemaSearch ? `${filteredNodeLabels.length} of ` : '' }}{{ nodeLabels.length }}
              </Badge>
            </div>
            <div v-if="nodeLabels.length === 0" class="text-[11px] text-muted-foreground">
              No node types found.
            </div>
            <div v-else class="max-h-64 overflow-y-auto">
              <div class="space-y-0.5">
                <div v-for="label in filteredNodeLabels" :key="label">
                  <div class="group flex items-center gap-0.5">
                    <!-- Expand chevron -->
                    <button
                      class="flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                      @click.stop="toggleExpand(label, 'node')"
                    >
                      <Loader2
                        v-if="schemaLoadingLabels.has(label)"
                        class="size-3 animate-spin"
                      />
                      <ChevronDown
                        v-else-if="expandedLabels.has(label)"
                        class="size-3"
                      />
                      <ChevronRight v-else class="size-3" />
                    </button>

                    <!-- Label button -->
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <button
                          class="flex min-w-0 flex-1 items-center gap-1 rounded px-1.5 py-1 font-mono text-[11px] transition-all hover:bg-muted"
                          @click="handleNodeClick(label, $event)"
                        >
                          <TextCursorInput v-if="altHeld" class="size-3 shrink-0 text-primary" />
                          <Play v-else class="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                          <span class="truncate" :class="altHeld ? 'text-primary underline' : ''">{{ label }}</span>
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="left" :side-offset="8">
                        <p class="text-xs">{{ altHeld ? 'Click to insert at cursor' : 'Click to query, Alt+click to insert' }}</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>

                  <!-- Expanded properties (R12) -->
                  <div
                    v-if="expandedLabels.has(label)"
                    class="ml-5 mt-0.5 mb-1 rounded border border-border/50 bg-muted/30 px-2 py-1.5"
                  >
                    <div v-if="schemaLoadingLabels.has(label)" class="flex items-center gap-1.5 py-1">
                      <Loader2 class="size-3 animate-spin text-muted-foreground" />
                      <span class="text-[11px] text-muted-foreground">Loading properties...</span>
                    </div>
                    <template v-else-if="schemaCache.has(label)">
                      <div
                        v-if="schemaCache.get(label)!.required_properties.length === 0 && schemaCache.get(label)!.optional_properties.length === 0"
                        class="text-[11px] text-muted-foreground"
                      >
                        No properties defined.
                      </div>
                      <template v-else>
                        <!-- Required properties -->
                        <div
                          v-for="prop in schemaCache.get(label)!.required_properties"
                          :key="`req-${prop}`"
                          class="flex items-center gap-1"
                        >
                          <Tooltip>
                            <TooltipTrigger as-child>
                              <button
                                class="truncate font-mono text-[11px] text-foreground hover:text-primary hover:underline"
                                @click="handlePropertyClick(prop)"
                              >
                                {{ prop }}
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="left" :side-offset="4">
                              <p class="text-xs">Click to insert n.{{ prop }}</p>
                            </TooltipContent>
                          </Tooltip>
                          <Badge variant="default" class="h-3.5 shrink-0 px-1 text-[9px]">
                            required
                          </Badge>
                        </div>
                        <!-- Optional properties -->
                        <div
                          v-for="prop in schemaCache.get(label)!.optional_properties"
                          :key="`opt-${prop}`"
                        >
                          <Tooltip>
                            <TooltipTrigger as-child>
                              <button
                                class="truncate font-mono text-[11px] text-muted-foreground hover:text-primary hover:underline"
                                @click="handlePropertyClick(prop)"
                              >
                                {{ prop }}
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="left" :side-offset="4">
                              <p class="text-xs">Click to insert n.{{ prop }}</p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      </template>
                    </template>
                  </div>
                </div>
              </div>
              <button
                v-if="!schemaSearch && !schemaShowAll && nodeLabels.length > SCHEMA_INITIAL_LIMIT"
                class="mt-1 w-full text-center text-[11px] text-muted-foreground hover:text-foreground"
                @click.stop="schemaShowAll = true"
              >
                Show all {{ nodeLabels.length }} types
              </button>
            </div>
          </div>

          <Separator />

          <!-- Edge labels -->
          <div>
            <div class="mb-2 flex items-center gap-1.5">
              <GitBranch class="size-3.5 text-orange-500" />
              <span class="text-xs font-medium">Edge Types</span>
              <Badge variant="secondary" class="ml-auto h-4 px-1 text-[10px]">
                {{ schemaSearch ? `${filteredEdgeLabels.length} of ` : '' }}{{ edgeLabels.length }}
              </Badge>
            </div>
            <div v-if="edgeLabels.length === 0" class="text-[11px] text-muted-foreground">
              No edge types found.
            </div>
            <div v-else class="max-h-64 overflow-y-auto">
              <div class="space-y-0.5">
                <div v-for="label in filteredEdgeLabels" :key="label">
                  <div class="group flex items-center gap-0.5">
                    <!-- Expand chevron -->
                    <button
                      class="flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                      @click.stop="toggleExpand(label, 'edge')"
                    >
                      <Loader2
                        v-if="schemaLoadingLabels.has(label)"
                        class="size-3 animate-spin"
                      />
                      <ChevronDown
                        v-else-if="expandedLabels.has(label)"
                        class="size-3"
                      />
                      <ChevronRight v-else class="size-3" />
                    </button>

                    <!-- Label button -->
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <button
                          class="flex min-w-0 flex-1 items-center gap-1 rounded px-1.5 py-1 font-mono text-[11px] transition-all hover:bg-muted"
                          @click="handleEdgeClick(label, $event)"
                        >
                          <TextCursorInput v-if="altHeld" class="size-3 shrink-0 text-primary" />
                          <Play v-else class="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                          <span class="truncate" :class="altHeld ? 'text-primary underline' : ''">{{ label }}</span>
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="left" :side-offset="8">
                        <p class="text-xs">{{ altHeld ? 'Click to insert at cursor' : 'Click to query, Alt+click to insert' }}</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>

                  <!-- Expanded properties (R12) -->
                  <div
                    v-if="expandedLabels.has(label)"
                    class="ml-5 mt-0.5 mb-1 rounded border border-border/50 bg-muted/30 px-2 py-1.5"
                  >
                    <div v-if="schemaLoadingLabels.has(label)" class="flex items-center gap-1.5 py-1">
                      <Loader2 class="size-3 animate-spin text-muted-foreground" />
                      <span class="text-[11px] text-muted-foreground">Loading properties...</span>
                    </div>
                    <template v-else-if="schemaCache.has(label)">
                      <div
                        v-if="schemaCache.get(label)!.required_properties.length === 0 && schemaCache.get(label)!.optional_properties.length === 0"
                        class="text-[11px] text-muted-foreground"
                      >
                        No properties defined.
                      </div>
                      <template v-else>
                        <!-- Required properties -->
                        <div
                          v-for="prop in schemaCache.get(label)!.required_properties"
                          :key="`req-${prop}`"
                          class="flex items-center gap-1"
                        >
                          <Tooltip>
                            <TooltipTrigger as-child>
                              <button
                                class="truncate font-mono text-[11px] text-foreground hover:text-primary hover:underline"
                                @click="handlePropertyClick(prop)"
                              >
                                {{ prop }}
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="left" :side-offset="4">
                              <p class="text-xs">Click to insert n.{{ prop }}</p>
                            </TooltipContent>
                          </Tooltip>
                          <Badge variant="default" class="h-3.5 shrink-0 px-1 text-[9px]">
                            required
                          </Badge>
                        </div>
                        <!-- Optional properties -->
                        <div
                          v-for="prop in schemaCache.get(label)!.optional_properties"
                          :key="`opt-${prop}`"
                        >
                          <Tooltip>
                            <TooltipTrigger as-child>
                              <button
                                class="truncate font-mono text-[11px] text-muted-foreground hover:text-primary hover:underline"
                                @click="handlePropertyClick(prop)"
                              >
                                {{ prop }}
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="left" :side-offset="4">
                              <p class="text-xs">Click to insert n.{{ prop }}</p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      </template>
                    </template>
                  </div>
                </div>
              </div>
              <button
                v-if="!schemaSearch && !schemaShowAll && edgeLabels.length > SCHEMA_INITIAL_LIMIT"
                class="mt-1 w-full text-center text-[11px] text-muted-foreground hover:text-foreground"
                @click.stop="schemaShowAll = true"
              >
                Show all {{ edgeLabels.length }} types
              </button>
            </div>
          </div>
        </template>
      </TabsContent>

      <!-- Structure View (R4) -->
      <TabsContent value="structure" class="mt-2 space-y-2">
        <!-- Refresh button -->
        <div class="flex items-center justify-between">
          <span class="text-[11px] text-muted-foreground">
            <template v-if="structureFetched && !structureLoading">
              {{ groupedStructure.length }} source{{ groupedStructure.length !== 1 ? 's' : '' }}
            </template>
          </span>
          <Button
            variant="ghost"
            size="sm"
            class="h-6 gap-1 px-2 text-[11px]"
            :disabled="structureLoading"
            @click="handleStructureRefresh"
          >
            <RefreshCw :class="['size-3', structureLoading ? 'animate-spin' : '']" />
            Refresh
          </Button>
        </div>

        <!-- Loading -->
        <div v-if="structureLoading" class="flex flex-col items-center gap-2 py-6">
          <Loader2 class="size-4 animate-spin text-muted-foreground" />
          <span class="text-[11px] text-muted-foreground">Loading graph structure...</span>
        </div>

        <!-- Error -->
        <div v-else-if="structureError && !structureFetched" class="space-y-2 py-4 text-center">
          <p class="text-[11px] text-destructive">{{ structureError }}</p>
          <Button
            variant="outline"
            size="sm"
            class="h-6 text-[11px]"
            @click="handleStructureRefresh"
          >
            Retry
          </Button>
        </div>

        <!-- Not yet fetched -->
        <div
          v-else-if="!structureFetched"
          class="py-6 text-center"
        >
          <p class="text-[11px] text-muted-foreground">
            Click Refresh to load the graph structure.
          </p>
        </div>

        <!-- Empty -->
        <div
          v-else-if="groupedStructure.length === 0"
          class="py-6 text-center"
        >
          <p class="text-[11px] text-muted-foreground">
            {{ schemaSearch ? 'No matching relationships.' : 'No relationships found in the graph.' }}
          </p>
        </div>

        <!-- Relationship list grouped by source -->
        <div v-else class="max-h-[calc(100vh-20rem)] space-y-2 overflow-y-auto">
          <div
            v-for="group in groupedStructure"
            :key="group.sourceLabel"
          >
            <div class="mb-1 flex items-center gap-1">
              <Database class="size-3 text-blue-500" />
              <span class="text-[11px] font-semibold text-foreground">{{ group.sourceLabel }}</span>
            </div>
            <div class="ml-3 space-y-0.5">
              <div
                v-for="(rel, idx) in group.relationships"
                :key="`${group.sourceLabel}-${rel.rel}-${rel.targetLabel}-${idx}`"
                class="flex items-center gap-1 text-[11px]"
              >
                <ArrowRight class="size-3 shrink-0 text-muted-foreground" />
                <Badge variant="outline" class="h-4 shrink-0 px-1 font-mono text-[10px]">
                  {{ rel.rel }}
                </Badge>
                <ArrowRight class="size-3 shrink-0 text-muted-foreground" />
                <span class="truncate font-medium text-foreground">{{ rel.targetLabel }}</span>
              </div>
            </div>
          </div>
        </div>
      </TabsContent>
    </Tabs>

    <!-- Keyboard hint -->
    <div
      class="flex items-center gap-1 rounded px-1 py-0.5 text-[10px] transition-colors"
      :class="altHeld ? 'bg-primary/10 text-primary' : 'text-muted-foreground'"
    >
      <Keyboard class="size-3" />
      <span>{{ altHeld ? 'Insert mode active' : 'Hold Alt to insert at cursor' }}</span>
    </div>
  </div>
</template>
