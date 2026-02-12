<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { toast } from 'vue-sonner'
import {
  Loader2, Clipboard, Table2, Braces, AlertTriangle,
  ArrowUp, ArrowDown, ArrowUpDown, Download, FileSpreadsheet,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import {
  Card, CardContent, CardHeader,
} from '@/components/ui/card'
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  FlexRender,
  type SortingState,
  type ColumnDef,
  type ColumnResizeMode,
} from '@tanstack/vue-table'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import type { CypherResult } from '~/types'
import { useModifierKeys } from '@/composables/useModifierKeys'

import { EditorView, lineNumbers, keymap } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { json } from '@codemirror/lang-json'
import { foldGutter, foldKeymap } from '@codemirror/language'
import { kartographTheme, jsonHighlightStyle } from '@/lib/codemirror/theme'
import GraphVisualization from '@/components/query/GraphVisualization.vue'
import { extractGraphData } from '@/composables/query/graph/useGraphExtraction'

// ── Props & Emits ──────────────────────────────────────────────────────────

const props = defineProps<{
  result: CypherResult | null
  error: string | null
  executing: boolean
  executionTime: number | null
  maxRows: string
}>()

const emit = defineEmits<{
  copy: [text: string]
}>()

const { altHeld } = useModifierKeys()

// ── Local state ────────────────────────────────────────────────────────────

const activeResultTab = ref('table')

// Row expansion
const expandedRow = ref<number | null>(null)

// TanStack Table sorting & resize state
const sorting = ref<SortingState>([])
const columnResizeMode = ref<ColumnResizeMode>('onChange')

// ── Computed ────────────────────────────────────────────────────────────────

const columns = computed<string[]>(() => {
  if (!props.result || props.result.rows.length === 0) return []
  return Object.keys(props.result.rows[0])
})

const graphDataComputed = computed(() => {
  if (!props.result) return null
  return extractGraphData(props.result)
})
const hasGraphElements = computed(() => (graphDataComputed.value?.nodes.length ?? 0) > 0)
const graphNodeCount = computed(() => graphDataComputed.value?.nodes.length ?? 0)
const graphEdgeCount = computed(() => graphDataComputed.value?.edges.length ?? 0)

// ── TanStack Table ──────────────────────────────────────────────────────────

const tableColumns = computed<ColumnDef<Record<string, unknown>>[]>(() => {
  if (!props.result || props.result.rows.length === 0) return []
  return Object.keys(props.result.rows[0]).map(key => ({
    accessorKey: key,
    header: key,
    cell: (info: any) => formatCellValue(info.getValue()),
    size: 200,
    minSize: 80,
    maxSize: 600,
  }))
})

const table = useVueTable({
  get data() { return props.result?.rows ?? [] },
  get columns() { return tableColumns.value },
  state: {
    get sorting() { return sorting.value },
  },
  onSortingChange: (updaterOrValue) => {
    sorting.value = typeof updaterOrValue === 'function'
      ? updaterOrValue(sorting.value)
      : updaterOrValue
  },
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  columnResizeMode: columnResizeMode.value,
  enableColumnResizing: true,
})

// ── Actions ─────────────────────────────────────────────────────────────────

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

function exportCsv() {
  if (!props.result || columns.value.length === 0) return
  const header = columns.value.join(',')
  const rows = table.getRowModel().rows.map(row =>
    columns.value.map(col => {
      const val = formatCellValue(row.getValue(col))
      return val.includes(',') || val.includes('"') || val.includes('\n')
        ? `"${val.replace(/"/g, '""')}"`
        : val
    }).join(','),
  )
  const csv = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `query-result-${Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function downloadJson() {
  if (!props.result) return
  const blob = new Blob([JSON.stringify(props.result, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `query-result-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Keyboard shortcuts ─────────────────────────────────────────────────────

function handleGlobalKeydown(e: KeyboardEvent) {
  if (e.altKey && !e.ctrlKey && !e.metaKey) {
    const tabMap: Record<string, string> = { '1': 'table', '2': 'json', '3': 'graph' }
    const tab = tabMap[e.key]
    if (tab) {
      if (tab === 'graph' && !hasGraphElements.value) return
      activeResultTab.value = tab
      e.preventDefault()
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
  if (jsonView) {
    jsonView.destroy()
    jsonView = null
  }
})

// ── JSON CodeMirror viewer ───────────────────────────────────────────────────

const jsonContainer = ref<HTMLElement | null>(null)
let jsonView: EditorView | null = null

function mountJsonViewer() {
  // Destroy previous instance
  if (jsonView) {
    jsonView.destroy()
    jsonView = null
  }

  if (!jsonContainer.value || !props.result) return

  const doc = JSON.stringify(props.result, null, 2)
  jsonView = new EditorView({
    state: EditorState.create({
      doc,
      extensions: [
          json(),
          kartographTheme,
          jsonHighlightStyle,
        lineNumbers(),
        foldGutter(),
        keymap.of(foldKeymap),
        EditorView.editable.of(false),
        EditorState.readOnly.of(true),
        EditorView.lineWrapping,
      ],
    }),
    parent: jsonContainer.value,
  })
}

// Watch the ref itself — when reka-ui mounts/unmounts TabsContent children,
// the ref transitions between null and the DOM element. This is the most
// reliable way to detect when the container is available.
watch(jsonContainer, (el) => {
  if (el && props.result) {
    mountJsonViewer()
  }
})

// Also remount when result changes while JSON tab is already active
watch(() => props.result, (newResult) => {
  if (newResult && activeResultTab.value === 'json') {
    // Container should already be in DOM since tab is active
    nextTick(() => mountJsonViewer())
  }
})

// ── Reset state when result changes ─────────────────────────────────────────

watch(() => props.result, (newResult) => {
  if (newResult) {
    activeResultTab.value = 'table'
    sorting.value = []
    expandedRow.value = null
  }
})
</script>

<template>
  <!-- Stats bar -->
  <div
    v-if="result || error"
    class="flex items-center gap-3 rounded-md border bg-muted/50 px-4 py-1.5 text-xs text-muted-foreground"
  >
    <span v-if="result">
      <strong class="font-medium text-foreground">{{ result.row_count.toLocaleString() }}</strong>
      {{ result.row_count === 1 ? 'row' : 'rows' }}
    </span>
    <span v-if="executionTime !== null">
      in <strong class="font-medium text-foreground">{{ executionTime }}ms</strong>
    </span>
    <span v-if="columns.length > 0">
      · {{ columns.length }} {{ columns.length === 1 ? 'column' : 'columns' }}
    </span>
    <span
      v-if="result && result.row_count >= Number(maxRows)"
      class="ml-auto text-amber-500"
    >
      Results may be truncated (limit: {{ Number(maxRows).toLocaleString() }})
    </span>
  </div>

  <!-- Results panel -->
  <Card class="flex min-h-0 flex-1 flex-col">
    <Tabs v-model="activeResultTab" class="flex min-h-0 flex-1 flex-col">
      <CardHeader class="pb-3">
        <div class="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="table">
              <span v-if="altHeld" class="mr-1 inline-flex size-4 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">1</span>
              Table
              <Badge v-if="result" variant="secondary" class="ml-1.5 h-4 px-1 font-mono text-[10px]">
                {{ result.row_count }}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="json">
              <span v-if="altHeld" class="mr-1 inline-flex size-4 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">2</span>
              JSON
            </TabsTrigger>
            <Tooltip>
              <TooltipTrigger as-child>
                <span>
                  <TabsTrigger value="graph" :disabled="!hasGraphElements">
                    <span v-if="altHeld && hasGraphElements" class="mr-1 inline-flex size-4 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">3</span>
                    Graph
                    <Badge v-if="graphNodeCount > 0" variant="secondary" class="ml-1.5 h-4 px-1 font-mono text-[10px]">
                      {{ graphNodeCount }}
                    </Badge>
                  </TabsTrigger>
                </span>
              </TooltipTrigger>
              <TooltipContent v-if="!hasGraphElements">
                <p>Return nodes/edges to enable graph view</p>
              </TooltipContent>
            </Tooltip>
          </TabsList>
        </div>
      </CardHeader>
      <CardContent class="flex min-h-0 flex-1 flex-col overflow-hidden">
        <!-- Table tab -->
        <TabsContent value="table" class="mt-0 flex min-h-0 flex-1 flex-col">
          <div v-if="executing" class="flex h-full items-center justify-center">
            <div class="flex items-center gap-2 text-muted-foreground">
              <Loader2 class="size-5 animate-spin" />
              Executing query...
            </div>
          </div>
          <div v-else-if="!result" class="flex h-full flex-col items-center justify-center gap-2">
            <Table2 class="size-8 text-muted-foreground/50" />
            <p class="text-sm text-muted-foreground">Run a query to view results as a table.</p>
            <p class="text-xs text-muted-foreground">
              Try <code class="rounded bg-muted px-1.5 py-0.5 font-mono">MATCH (n) RETURN n LIMIT 25</code>
            </p>
          </div>
          <template v-else>
            <!-- Sticky toolbar — never scrolls -->
            <div class="flex-shrink-0">
              <Alert v-if="result.row_count >= Number(maxRows)" variant="warning" class="mb-2">
                <AlertTriangle class="size-4" />
                <AlertDescription class="text-xs">
                  Results capped at {{ Number(maxRows).toLocaleString() }} rows. Increase the limit or add a LIMIT clause.
                </AlertDescription>
              </Alert>
              <div class="mb-2 flex items-center justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  class="h-7 text-xs"
                  @click="exportCsv"
                >
                  <FileSpreadsheet class="mr-1.5 size-3" />
                  Export CSV
                </Button>
              </div>
            </div>
            <!-- Scrollable table area — scrolls both X and Y independently -->
            <div class="min-h-0 flex-1 overflow-auto rounded-md border">
              <table class="w-full caption-bottom text-sm">
                <thead class="sticky top-0 z-10 bg-background [&_tr]:border-b">
                  <tr v-for="headerGroup in table.getHeaderGroups()" :key="headerGroup.id" class="border-b">
                    <th
                      v-for="header in headerGroup.headers"
                      :key="header.id"
                      class="relative h-10 cursor-pointer select-none whitespace-nowrap px-4 text-left align-middle font-mono text-xs font-medium text-muted-foreground hover:bg-muted/50"
                      :style="{ minWidth: `${header.getSize()}px` }"
                      @click="header.column.getToggleSortingHandler()?.($event)"
                    >
                      <div class="flex items-center gap-1">
                        <FlexRender
                          v-if="!header.isPlaceholder"
                          :render="header.column.columnDef.header"
                          :props="header.getContext()"
                        />
                        <ArrowUp v-if="header.column.getIsSorted() === 'asc'" class="size-3 text-foreground" />
                        <ArrowDown v-else-if="header.column.getIsSorted() === 'desc'" class="size-3 text-foreground" />
                        <ArrowUpDown v-else class="size-3 text-muted-foreground/40" />
                      </div>
                      <!-- Column resize handle -->
                      <div
                        class="absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none"
                        :class="header.column.getIsResizing() ? 'bg-primary' : 'hover:bg-border'"
                        @mousedown="header.getResizeHandler()($event)"
                        @touchstart="header.getResizeHandler()($event)"
                        @click.stop
                      />
                    </th>
                  </tr>
                </thead>
                <tbody class="[&_tr:last-child]:border-0">
                  <template v-if="table.getRowModel().rows.length === 0">
                    <tr>
                      <td :colspan="columns.length || 1" class="h-24 text-center text-sm text-muted-foreground">
                        Query returned no rows.
                      </td>
                    </tr>
                  </template>
                  <template v-for="row in table.getRowModel().rows" :key="row.id">
                    <tr
                      class="cursor-pointer border-b transition-colors hover:bg-muted/50"
                      :class="{ 'bg-muted/30': expandedRow === row.index }"
                      @click="expandedRow = expandedRow === row.index ? null : row.index"
                    >
                      <td
                        v-for="cell in row.getVisibleCells()"
                        :key="cell.id"
                        class="group/cell relative truncate p-4 align-middle font-mono text-xs hover:bg-muted/50"
                        :style="{ minWidth: `${cell.column.getSize()}px` }"
                        :title="formatCellValue(cell.getValue())"
                        @click.stop="copyToClipboard(formatCellValue(cell.getValue()))"
                      >
                        <FlexRender :render="cell.column.columnDef.cell" :props="cell.getContext()" />
                        <Clipboard class="absolute right-1 top-1/2 hidden size-3 -translate-y-1/2 text-muted-foreground group-hover/cell:inline-block" />
                      </td>
                    </tr>
                    <tr v-if="expandedRow === row.index" class="border-b bg-muted/20">
                      <td :colspan="columns.length" class="p-4">
                        <div class="grid gap-x-6 gap-y-2" style="grid-template-columns: auto 1fr;">
                          <template v-for="col in columns" :key="col">
                            <span class="self-start font-mono text-[10px] font-medium text-muted-foreground">{{ col }}</span>
                            <pre
                              class="max-h-40 cursor-pointer overflow-auto whitespace-pre-wrap rounded bg-muted px-2 py-1 font-mono text-xs text-foreground hover:bg-muted/80"
                              @click.stop="copyToClipboard(formatCellValue(row.original[col]))"
                            >{{ typeof row.original[col] === 'object' ? JSON.stringify(row.original[col], null, 2) : formatCellValue(row.original[col]) }}</pre>
                          </template>
                        </div>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </template>
        </TabsContent>

        <!-- JSON tab -->
        <TabsContent value="json" class="mt-0 flex min-h-0 flex-1 flex-col">
          <div v-if="executing" class="flex h-full items-center justify-center">
            <div class="flex items-center gap-2 text-muted-foreground">
              <Loader2 class="size-5 animate-spin" />
              Executing query...
            </div>
          </div>
          <div v-else-if="!result" class="flex h-full flex-col items-center justify-center gap-2">
            <Braces class="size-8 text-muted-foreground/50" />
            <p class="text-sm text-muted-foreground">Raw JSON response will appear here.</p>
          </div>
          <template v-else>
            <!-- Sticky toolbar — never scrolls -->
            <div class="mb-2 flex flex-shrink-0 items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                class="h-7 text-xs"
                @click="copyToClipboard(JSON.stringify(result, null, 2))"
              >
                <Clipboard class="mr-1.5 size-3" />
                Copy JSON
              </Button>
              <Button
                variant="outline"
                size="sm"
                class="h-7 text-xs"
                @click="downloadJson"
              >
                <Download class="mr-1.5 size-3" />
                Download
              </Button>
            </div>
            <!-- Scrollable JSON area -->
            <div
              ref="jsonContainer"
              class="min-h-0 flex-1 overflow-auto rounded-md border"
            />
          </template>
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
</template>
