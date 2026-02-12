<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Terminal, Play, Trash2, Loader2, Clock, Hash,
  ChevronRight, ChevronDown, Database, GitBranch,
  Clipboard, X,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Card, CardContent, CardHeader, CardTitle,
} from '@/components/ui/card'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty,
} from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'
import type { CypherResult } from '~/types'

// ── API ────────────────────────────────────────────────────────────────────

const { queryGraph } = useQueryApi()
const { listNodeLabels, listEdgeLabels } = useGraphApi()

// ── State ──────────────────────────────────────────────────────────────────

const query = ref('MATCH (n) RETURN n LIMIT 25')
const timeout = ref('30')
const maxRows = ref('1000')
const executing = ref(false)
const result = ref<CypherResult | null>(null)
const error = ref<string | null>(null)
const executionTime = ref<number | null>(null)
const activeResultTab = ref('table')

// Schema reference
const nodeLabels = ref<string[]>([])
const edgeLabels = ref<string[]>([])
const schemaLoading = ref(false)
const schemaOpen = ref(true)

// History
const HISTORY_KEY = 'kartograph:query-history'
const MAX_HISTORY = 20

interface HistoryEntry {
  query: string
  timestamp: number
  rowCount: number | null
}

const history = ref<HistoryEntry[]>([])
const historyOpen = ref(false)

// Textarea ref
const textareaRef = ref<HTMLTextAreaElement | null>()

// ── Example queries ────────────────────────────────────────────────────────

const exampleQueries = [
  { label: 'All Nodes', cypher: 'MATCH (n) RETURN n LIMIT 25' },
  { label: 'Node Counts', cypher: 'MATCH (n) RETURN labels(n) as label, count(*) as count' },
  { label: 'All Relationships', cypher: 'MATCH (n)-[r]->(m) RETURN n, type(r), m LIMIT 25' },
  { label: 'Nodes with Slugs', cypher: 'MATCH (n) WHERE n.slug IS NOT NULL RETURN n.slug, labels(n) LIMIT 50' },
]

// ── Computed ────────────────────────────────────────────────────────────────

const columns = computed<string[]>(() => {
  if (!result.value || result.value.rows.length === 0) return []
  return Object.keys(result.value.rows[0])
})

// ── Actions ────────────────────────────────────────────────────────────────

async function executeQuery() {
  const cypher = query.value.trim()
  if (!cypher || executing.value) return

  executing.value = true
  error.value = null
  result.value = null
  executionTime.value = null

  const start = performance.now()

  try {
    const res = await queryGraph(
      cypher,
      Number(timeout.value),
      Number(maxRows.value),
    )
    executionTime.value = Math.round(performance.now() - start)
    result.value = res
    activeResultTab.value = 'table'

    addToHistory(cypher, res.row_count)
    toast.success(`Query returned ${res.row_count} row${res.row_count !== 1 ? 's' : ''}`, {
      description: `Completed in ${executionTime.value}ms`,
    })
  } catch (err) {
    executionTime.value = Math.round(performance.now() - start)
    const message = err instanceof Error ? err.message : 'An unexpected error occurred'
    error.value = message
    addToHistory(cypher, null)
    toast.error('Query failed', { description: message })
  } finally {
    executing.value = false
  }
}

function clearEditor() {
  query.value = ''
  result.value = null
  error.value = null
  executionTime.value = null
  nextTick(() => textareaRef.value?.focus())
}

function setQuery(cypher: string) {
  query.value = cypher
  nextTick(() => textareaRef.value?.focus())
}

function insertAtCursor(text: string) {
  const el = textareaRef.value
  if (!el) {
    query.value += text
    return
  }

  const start = el.selectionStart
  const end = el.selectionEnd
  const before = query.value.slice(0, start)
  const after = query.value.slice(end)
  query.value = before + text + after

  nextTick(() => {
    el.selectionStart = el.selectionEnd = start + text.length
    el.focus()
  })
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// ── History ────────────────────────────────────────────────────────────────

function loadHistory() {
  try {
    const stored = localStorage.getItem(HISTORY_KEY)
    if (stored) history.value = JSON.parse(stored)
  } catch {
    history.value = []
  }
}

function saveHistory() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
  } catch { /* storage full – ignore */ }
}

function addToHistory(cypher: string, rowCount: number | null) {
  // Remove duplicate if exists
  history.value = history.value.filter(h => h.query !== cypher)
  history.value.unshift({ query: cypher, timestamp: Date.now(), rowCount })
  if (history.value.length > MAX_HISTORY) {
    history.value = history.value.slice(0, MAX_HISTORY)
  }
  saveHistory()
}

function clearHistory() {
  history.value = []
  saveHistory()
}

function formatTimestamp(ts: number): string {
  return new Date(ts).toLocaleTimeString()
}

// ── Schema ─────────────────────────────────────────────────────────────────

async function fetchSchema() {
  schemaLoading.value = true
  try {
    const [nodes, edges] = await Promise.all([
      listNodeLabels(),
      listEdgeLabels(),
    ])
    nodeLabels.value = nodes.labels
    edgeLabels.value = edges.labels
  } catch (err) {
    toast.error('Failed to load schema', {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
  } finally {
    schemaLoading.value = false
  }
}

// ── Keyboard shortcut ──────────────────────────────────────────────────────

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    executeQuery()
  }
}

onMounted(() => {
  loadHistory()
  fetchSchema()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="flex h-[calc(100vh-6rem)] flex-col gap-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Terminal class="size-6 text-muted-foreground" />
        <h1 class="text-2xl font-bold tracking-tight">Cypher Console</h1>
      </div>
    </div>

    <!-- Main layout: Editor + Results on left, Schema on right -->
    <div class="flex min-h-0 flex-1 gap-4">
      <!-- Left: Editor + Results -->
      <div class="flex min-w-0 flex-1 flex-col gap-4">
        <!-- Query Editor -->
        <Card class="flex flex-col">
          <CardHeader class="pb-3">
            <div class="flex items-center justify-between">
              <CardTitle class="text-sm font-medium">Query Editor</CardTitle>
              <div class="flex items-center gap-2">
                <!-- Example queries -->
                <div class="flex items-center gap-1.5">
                  <span class="text-xs text-muted-foreground">Examples:</span>
                  <div class="flex flex-wrap gap-1">
                    <Button
                      v-for="example in exampleQueries"
                      :key="example.label"
                      variant="outline"
                      size="sm"
                      class="h-6 px-2 text-xs"
                      @click="setQuery(example.cypher)"
                    >
                      {{ example.label }}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent class="space-y-3">
            <!-- Textarea editor -->
            <div class="relative">
              <textarea
                ref="textareaRef"
                v-model="query"
                class="min-h-[120px] w-full resize-y rounded-md border border-input bg-zinc-950 px-4 py-3 font-mono text-sm text-green-400 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                placeholder="Enter your Cypher query here..."
                spellcheck="false"
                autocomplete="off"
                autocorrect="off"
                autocapitalize="off"
              />
            </div>

            <!-- Controls bar -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <!-- Execute -->
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        :disabled="executing || !query.trim()"
                        @click="executeQuery"
                      >
                        <Loader2 v-if="executing" class="mr-2 size-4 animate-spin" />
                        <Play v-else class="mr-2 size-4" />
                        Execute
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Ctrl+Enter</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                <!-- Clear -->
                <Button variant="outline" @click="clearEditor">
                  <Trash2 class="mr-2 size-4" />
                  Clear
                </Button>
              </div>

              <div class="flex items-center gap-3">
                <!-- Timeout -->
                <div class="flex items-center gap-1.5">
                  <Clock class="size-3.5 text-muted-foreground" />
                  <span class="text-xs text-muted-foreground">Timeout:</span>
                  <Select v-model="timeout">
                    <SelectTrigger class="h-8 w-[80px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="5">5s</SelectItem>
                      <SelectItem value="10">10s</SelectItem>
                      <SelectItem value="30">30s</SelectItem>
                      <SelectItem value="60">60s</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <!-- Max rows -->
                <div class="flex items-center gap-1.5">
                  <Hash class="size-3.5 text-muted-foreground" />
                  <span class="text-xs text-muted-foreground">Max rows:</span>
                  <Select v-model="maxRows">
                    <SelectTrigger class="h-8 w-[100px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="100">100</SelectItem>
                      <SelectItem value="500">500</SelectItem>
                      <SelectItem value="1000">1,000</SelectItem>
                      <SelectItem value="5000">5,000</SelectItem>
                      <SelectItem value="10000">10,000</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- Error display -->
        <Alert v-if="error" variant="destructive">
          <AlertTitle>Query Error</AlertTitle>
          <AlertDescription class="font-mono text-xs">
            {{ error }}
          </AlertDescription>
        </Alert>

        <!-- Results panel -->
        <Card class="flex min-h-0 flex-1 flex-col">
          <Tabs v-model="activeResultTab" class="flex min-h-0 flex-1 flex-col">
            <CardHeader class="pb-3">
              <div class="flex items-center justify-between">
                <TabsList>
                  <TabsTrigger value="table">Table</TabsTrigger>
                  <TabsTrigger value="json">JSON</TabsTrigger>
                  <TabsTrigger value="info">Info</TabsTrigger>
                </TabsList>
                <Badge v-if="result" variant="secondary">
                  {{ result.row_count }} row{{ result.row_count !== 1 ? 's' : '' }}
                </Badge>
              </div>
            </CardHeader>
            <CardContent class="min-h-0 flex-1 overflow-auto">
              <!-- Table tab -->
              <TabsContent value="table" class="mt-0 h-full">
                <div v-if="executing" class="flex h-full items-center justify-center">
                  <div class="flex items-center gap-2 text-muted-foreground">
                    <Loader2 class="size-5 animate-spin" />
                    Executing query...
                  </div>
                </div>
                <div v-else-if="!result" class="flex h-full items-center justify-center">
                  <p class="text-sm text-muted-foreground">
                    Execute a query to see results here.
                  </p>
                </div>
                <div v-else class="rounded-md border">
                  <div class="max-h-[calc(100vh-30rem)] overflow-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead
                            v-for="col in columns"
                            :key="col"
                            class="whitespace-nowrap font-mono text-xs"
                          >
                            {{ col }}
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableEmpty v-if="result.rows.length === 0" :colspan="columns.length || 1">
                          Query returned no rows.
                        </TableEmpty>
                        <TableRow v-for="(row, idx) in result.rows" :key="idx">
                          <TableCell
                            v-for="col in columns"
                            :key="col"
                            class="max-w-[400px] truncate font-mono text-xs"
                            :title="formatCellValue(row[col])"
                          >
                            {{ formatCellValue(row[col]) }}
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </TabsContent>

              <!-- JSON tab -->
              <TabsContent value="json" class="mt-0 h-full">
                <div v-if="!result" class="flex h-full items-center justify-center">
                  <p class="text-sm text-muted-foreground">
                    Execute a query to see results here.
                  </p>
                </div>
                <div v-else class="relative">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="absolute right-2 top-2"
                    title="Copy JSON"
                    @click="navigator.clipboard.writeText(JSON.stringify(result, null, 2)); toast.success('Copied to clipboard')"
                  >
                    <Clipboard class="size-4" />
                  </Button>
                  <pre class="max-h-[calc(100vh-30rem)] overflow-auto rounded-md bg-zinc-950 p-4 font-mono text-xs text-green-400"><code>{{ JSON.stringify(result, null, 2) }}</code></pre>
                </div>
              </TabsContent>

              <!-- Info tab -->
              <TabsContent value="info" class="mt-0 h-full">
                <div v-if="!result && !error" class="flex h-full items-center justify-center">
                  <p class="text-sm text-muted-foreground">
                    Execute a query to see metadata here.
                  </p>
                </div>
                <div v-else class="space-y-4">
                  <div class="grid grid-cols-2 gap-4">
                    <Card>
                      <CardContent class="pt-6">
                        <div class="text-2xl font-bold">
                          {{ result?.row_count ?? '---' }}
                        </div>
                        <p class="text-xs text-muted-foreground">Rows returned</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent class="pt-6">
                        <div class="text-2xl font-bold">
                          {{ executionTime !== null ? `${executionTime}ms` : '---' }}
                        </div>
                        <p class="text-xs text-muted-foreground">Execution time (client)</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent class="pt-6">
                        <div class="text-2xl font-bold">
                          {{ columns.length || '---' }}
                        </div>
                        <p class="text-xs text-muted-foreground">Columns</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent class="pt-6">
                        <div class="text-2xl font-bold">
                          {{ timeout }}s / {{ Number(maxRows).toLocaleString() }}
                        </div>
                        <p class="text-xs text-muted-foreground">Timeout / Max rows</p>
                      </CardContent>
                    </Card>
                  </div>
                  <Alert v-if="error" variant="destructive">
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription class="font-mono text-xs">{{ error }}</AlertDescription>
                  </Alert>
                </div>
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>
      </div>

      <!-- Right sidebar: Schema + History -->
      <div class="flex w-64 flex-shrink-0 flex-col gap-4">
        <!-- Schema Reference -->
        <Card class="flex flex-col">
          <CardHeader class="cursor-pointer pb-3" @click="schemaOpen = !schemaOpen">
            <div class="flex items-center justify-between">
              <CardTitle class="text-sm font-medium">Schema Reference</CardTitle>
              <ChevronDown v-if="schemaOpen" class="size-4 text-muted-foreground" />
              <ChevronRight v-else class="size-4 text-muted-foreground" />
            </div>
          </CardHeader>
          <CardContent v-if="schemaOpen" class="space-y-4 pt-0">
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
                    {{ nodeLabels.length }}
                  </Badge>
                </div>
                <div v-if="nodeLabels.length === 0" class="text-xs text-muted-foreground">
                  No node types found.
                </div>
                <div v-else class="flex flex-wrap gap-1">
                  <Button
                    v-for="label in nodeLabels"
                    :key="label"
                    variant="outline"
                    size="sm"
                    class="h-6 px-2 font-mono text-[11px]"
                    @click="insertAtCursor(label)"
                  >
                    {{ label }}
                  </Button>
                </div>
              </div>

              <Separator />

              <!-- Edge labels -->
              <div>
                <div class="mb-2 flex items-center gap-1.5">
                  <GitBranch class="size-3.5 text-orange-500" />
                  <span class="text-xs font-medium">Edge Types</span>
                  <Badge variant="secondary" class="ml-auto h-4 px-1 text-[10px]">
                    {{ edgeLabels.length }}
                  </Badge>
                </div>
                <div v-if="edgeLabels.length === 0" class="text-xs text-muted-foreground">
                  No edge types found.
                </div>
                <div v-else class="flex flex-wrap gap-1">
                  <Button
                    v-for="label in edgeLabels"
                    :key="label"
                    variant="outline"
                    size="sm"
                    class="h-6 px-2 font-mono text-[11px]"
                    @click="insertAtCursor(label)"
                  >
                    {{ label }}
                  </Button>
                </div>
              </div>
            </template>
          </CardContent>
        </Card>

        <!-- Query History -->
        <Card class="flex min-h-0 flex-1 flex-col">
          <CardHeader class="cursor-pointer pb-3" @click="historyOpen = !historyOpen">
            <div class="flex items-center justify-between">
              <CardTitle class="text-sm font-medium">History</CardTitle>
              <div class="flex items-center gap-1">
                <Badge v-if="history.length > 0" variant="secondary" class="h-4 px-1 text-[10px]">
                  {{ history.length }}
                </Badge>
                <ChevronDown v-if="historyOpen" class="size-4 text-muted-foreground" />
                <ChevronRight v-else class="size-4 text-muted-foreground" />
              </div>
            </div>
          </CardHeader>
          <CardContent v-if="historyOpen" class="min-h-0 flex-1 overflow-auto pt-0">
            <div v-if="history.length === 0" class="py-4 text-center text-xs text-muted-foreground">
              No queries yet.
            </div>
            <template v-else>
              <div class="mb-2 flex justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  class="h-6 px-2 text-xs text-muted-foreground"
                  @click.stop="clearHistory"
                >
                  <Trash2 class="mr-1 size-3" />
                  Clear
                </Button>
              </div>
              <div class="space-y-1">
                <button
                  v-for="(entry, idx) in history"
                  :key="idx"
                  class="w-full rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted"
                  @click="setQuery(entry.query)"
                >
                  <p class="truncate font-mono text-[11px] text-foreground">
                    {{ entry.query }}
                  </p>
                  <div class="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span>{{ formatTimestamp(entry.timestamp) }}</span>
                    <span v-if="entry.rowCount !== null">
                      {{ entry.rowCount }} row{{ entry.rowCount !== 1 ? 's' : '' }}
                    </span>
                    <Badge v-else variant="destructive" class="h-3.5 px-1 text-[9px]">
                      error
                    </Badge>
                  </div>
                </button>
              </div>
            </template>
          </CardContent>
        </Card>
      </div>
    </div>
  </div>
</template>
