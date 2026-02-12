<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import { keymap } from '@codemirror/view'
import type { Extension } from '@codemirror/state'
import {
  Terminal, Play, Trash2, Loader2, Clock, Hash,
  ChevronRight, ChevronDown, Database, GitBranch,
  Clipboard, Search,
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
import { Input } from '@/components/ui/input'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import type { CypherResult } from '~/types'

// CodeMirror
import { useCodemirror } from '@/composables/useCodemirror'
import { kartographTheme, kartographHighlightStyle } from '@/lib/codemirror/theme'
import { cypher } from '@/lib/codemirror/lang-cypher'
import { cypherAutocomplete } from '@/lib/codemirror/lang-cypher/autocomplete'
import { ageCypherLinter } from '@/lib/codemirror/lang-cypher/age-linter'
import { cypherTooltips } from '@/lib/codemirror/lang-cypher/tooltips'
import { applyServerError, clearServerErrors } from '@/lib/codemirror/error-parser'

// Components
import QueryTemplates from '@/components/query/QueryTemplates.vue'
import CypherCheatSheet from '@/components/query/CypherCheatSheet.vue'
import GraphVisualization from '@/components/query/GraphVisualization.vue'
import { extractGraphData } from '@/composables/query/graph/useGraphExtraction'

// ── API ────────────────────────────────────────────────────────────────────

const { queryGraph } = useQueryApi()
const { listNodeLabels, listEdgeLabels } = useGraphApi()
const { extractErrorMessage } = useErrorHandler()

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

// Schema search & filtering
const schemaSearch = ref('')
const SCHEMA_INITIAL_LIMIT = 50
const schemaShowAll = ref(false)

const filteredNodeLabels = computed(() => {
  const search = schemaSearch.value.toLowerCase().trim()
  let labels = nodeLabels.value
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
  let labels = edgeLabels.value
  if (search) {
    labels = labels.filter(l => l.toLowerCase().includes(search))
  }
  if (!schemaShowAll.value && !search) {
    return labels.slice(0, SCHEMA_INITIAL_LIMIT)
  }
  return labels
})

// History
const HISTORY_KEY = 'kartograph:query-history'
const MAX_HISTORY = 20

interface HistoryEntry {
  query: string
  timestamp: number
  rowCount: number | null
}

const history = ref<HistoryEntry[]>([])
const historyOpen = ref(true)

// ── CodeMirror Setup ───────────────────────────────────────────────────────

const editorContainer = ref<HTMLElement | null>(null)

// Static extensions that never change — created once to avoid unnecessary
// CodeMirror reconfiguration cycles when reactive schema data updates.
const staticExtensions: Extension[] = [
  kartographTheme,
  kartographHighlightStyle,
  cypher(),
  ageCypherLinter(),
  cypherTooltips(),
  keymap.of([
    {
      key: 'Ctrl-Enter',
      mac: 'Cmd-Enter',
      run: () => {
        executeQuery()
        return true
      },
    },
  ]),
]

// Only the autocomplete extension needs to react to schema changes
const cmExtensions = computed<Extension[]>(() => [
  ...staticExtensions,
  cypherAutocomplete({
    labels: nodeLabels.value,
    relationshipTypes: edgeLabels.value,
  }),
])

const { view: editorView, focus: focusEditor } = useCodemirror(
  editorContainer,
  query,
  cmExtensions,
)

// ── Computed ────────────────────────────────────────────────────────────────

const columns = computed<string[]>(() => {
  if (!result.value || result.value.rows.length === 0) return []
  return Object.keys(result.value.rows[0])
})

const hasGraphElements = computed(() => {
  if (!result.value) return false
  const data = extractGraphData(result.value)
  return data.nodes.length > 0
})

// ── Actions ────────────────────────────────────────────────────────────────

async function executeQuery() {
  const cypherQuery = query.value.trim()
  if (!cypherQuery || executing.value) return

  executing.value = true
  error.value = null
  result.value = null
  executionTime.value = null

  // Clear any previous server error markers
  if (editorView.value) {
    clearServerErrors(editorView.value)
  }

  const start = performance.now()

  try {
    const res = await queryGraph(
      cypherQuery,
      Number(timeout.value),
      Number(maxRows.value),
    )
    executionTime.value = Math.round(performance.now() - start)
    result.value = res
    activeResultTab.value = 'table'

    addToHistory(cypherQuery, res.row_count)
    toast.success(`Query returned ${res.row_count} row${res.row_count !== 1 ? 's' : ''}`, {
      description: `Completed in ${executionTime.value}ms`,
    })
  } catch (err) {
    executionTime.value = Math.round(performance.now() - start)
    const message = extractErrorMessage(err)
    error.value = message

    // Apply inline error markers in the editor
    if (editorView.value) {
      applyServerError(editorView.value, message)
    }

    addToHistory(cypherQuery, null)
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
  if (editorView.value) {
    clearServerErrors(editorView.value)
  }
  nextTick(focusEditor)
}

function setQuery(cypherText: string) {
  query.value = cypherText
  if (editorView.value) {
    clearServerErrors(editorView.value)
  }
  nextTick(focusEditor)
}

function insertAtCursor(text: string) {
  const view = editorView.value
  if (!view) {
    query.value += text
    return
  }

  const { from, to } = view.state.selection.main
  view.dispatch({
    changes: { from, to, insert: text },
    selection: { anchor: from + text.length },
  })
  view.focus()
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  } catch {
    toast.error('Failed to copy to clipboard')
  }
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

function addToHistory(cypherText: string, rowCount: number | null) {
  history.value = history.value.filter(h => h.query !== cypherText)
  history.value.unshift({ query: cypherText, timestamp: Date.now(), rowCount })
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
      description: extractErrorMessage(err),
    })
  } finally {
    schemaLoading.value = false
  }
}

onMounted(() => {
  loadHistory()
  fetchSchema()
})
</script>

<template>
  <div class="flex max-h-[calc(100vh-5.5rem)] flex-col gap-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Terminal class="size-6 text-muted-foreground" />
        <h1 class="text-2xl font-bold tracking-tight">Cypher Console</h1>
      </div>
    </div>

    <!-- Main layout: Editor + Results on left, Sidebar on right -->
    <div class="flex min-h-0 flex-1 gap-4">
      <!-- Left: Editor + Results -->
      <div class="flex min-w-0 flex-1 flex-col gap-4">
        <!-- Query Editor -->
        <Card class="flex flex-col">
          <CardHeader class="pb-3">
            <div class="flex items-center justify-between">
              <CardTitle class="text-sm font-medium">Query Editor</CardTitle>
              <div class="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <kbd class="rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px]">Ctrl</kbd>
                <span>+</span>
                <kbd class="rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd>
                <span class="ml-1">to execute</span>
              </div>
            </div>
          </CardHeader>
          <CardContent class="space-y-3">
            <!-- CodeMirror editor -->
            <div
              ref="editorContainer"
              class="overflow-hidden rounded-md border border-input [&_.cm-editor]:min-h-[120px] [&_.cm-editor]:max-h-[300px] [&_.cm-editor]:overflow-auto [&_.cm-editor.cm-focused]:ring-1 [&_.cm-editor.cm-focused]:ring-ring"
            />

            <!-- Controls bar -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <!-- Execute -->
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
          <AlertDescription class="whitespace-pre-wrap font-mono text-xs">
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
                  <TabsTrigger value="graph" :disabled="!hasGraphElements">Graph</TabsTrigger>
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
                    aria-label="Copy JSON to clipboard"
                    @click="copyToClipboard(JSON.stringify(result, null, 2))"
                  >
                    <Clipboard class="size-4" />
                  </Button>
                  <pre class="max-h-[calc(100vh-30rem)] overflow-auto rounded-md bg-muted p-4 font-mono text-xs text-foreground"><code>{{ JSON.stringify(result, null, 2) }}</code></pre>
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

              <!-- Graph tab -->
              <TabsContent value="graph" class="mt-0 h-full">
                <GraphVisualization
                  :result="result"
                  :executing="executing"
                />
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>
      </div>

      <!-- Right sidebar: Templates + Cheat Sheet + Schema + History -->
      <div class="hidden w-72 flex-shrink-0 flex-col gap-4 xl:flex">
        <!-- Query Templates -->
        <QueryTemplates
          :node-labels="nodeLabels"
          :edge-labels="edgeLabels"
          @select-query="setQuery"
        />

        <!-- Cheat Sheet -->
        <CypherCheatSheet />

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
              <!-- Search filter -->
              <div class="relative">
                <Search class="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  v-model="schemaSearch"
                  placeholder="Filter types..."
                  class="h-7 pl-7 text-xs"
                />
              </div>

              <!-- Node labels -->
              <div>
                <div class="mb-2 flex items-center gap-1.5">
                  <Database class="size-3.5 text-blue-500" />
                  <span class="text-xs font-medium">Node Types</span>
                  <Badge variant="secondary" class="ml-auto h-4 px-1 text-[10px]">
                    {{ schemaSearch ? `${filteredNodeLabels.length} of ` : '' }}{{ nodeLabels.length }}
                  </Badge>
                </div>
                <div v-if="nodeLabels.length === 0" class="text-xs text-muted-foreground">
                  No node types found.
                </div>
                <div v-else class="max-h-64 overflow-y-auto">
                  <div class="flex flex-wrap gap-1">
                    <Button
                      v-for="label in filteredNodeLabels"
                      :key="label"
                      variant="outline"
                      size="sm"
                      class="h-6 px-2 font-mono text-[11px]"
                      @click="insertAtCursor(label)"
                    >
                      {{ label }}
                    </Button>
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
                <div v-if="edgeLabels.length === 0" class="text-xs text-muted-foreground">
                  No edge types found.
                </div>
                <div v-else class="max-h-64 overflow-y-auto">
                  <div class="flex flex-wrap gap-1">
                    <Button
                      v-for="label in filteredEdgeLabels"
                      :key="label"
                      variant="outline"
                      size="sm"
                      class="h-6 px-2 font-mono text-[11px]"
                      @click="insertAtCursor(label)"
                    >
                      {{ label }}
                    </Button>
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
          <CardContent v-if="historyOpen" class="max-h-64 min-h-0 flex-1 overflow-y-auto pt-0">
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
