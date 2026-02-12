<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { toast } from 'vue-sonner'
import { keymap } from '@codemirror/view'
import { Prec, type Extension } from '@codemirror/state'
import { useLocalStorage } from '@vueuse/core'
import {
  Terminal, Play, Trash2, Loader2, Clock, Hash,
  PanelRight, PanelRightClose,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  Card, CardContent, CardHeader, CardTitle,
} from '@/components/ui/card'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Sheet, SheetContent, SheetTitle, SheetHeader,
  SheetDescription,
} from '@/components/ui/sheet'
import type { CypherResult, HistoryEntry } from '~/types'

// Modifier key tracking
import { useModifierKeys } from '@/composables/useModifierKeys'

// CodeMirror
import { useCodemirror } from '@/composables/useCodemirror'
import { kartographTheme, kartographHighlightStyle } from '@/lib/codemirror/theme'
import { cypher } from '@/lib/codemirror/lang-cypher'
import { cypherAutocomplete } from '@/lib/codemirror/lang-cypher/autocomplete'
import { ageCypherLinter } from '@/lib/codemirror/lang-cypher/age-linter'
import { cypherTooltips } from '@/lib/codemirror/lang-cypher/tooltips'
import { applyServerError, clearServerErrors } from '@/lib/codemirror/error-parser'

// Components
import QueryResultsPanel from '@/components/query/QueryResultsPanel.vue'
import QuerySidebar from '@/components/query/QuerySidebar.vue'

const { ctrlHeld } = useModifierKeys()

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

// Schema reference
const nodeLabels = ref<string[]>([])
const edgeLabels = ref<string[]>([])
const schemaLoading = ref(false)

// History
const HISTORY_KEY = 'kartograph:query-history'
const MAX_HISTORY = 20

const history = ref<HistoryEntry[]>([])

// Responsive sidebar sheet
const sheetOpen = ref(false)

// Resizable & collapsible sidebar
const SIDEBAR_WIDTH_KEY = 'kartograph:sidebar-width'
const SIDEBAR_COLLAPSED_KEY = 'kartograph:sidebar-collapsed'
const SIDEBAR_MIN = 180
const SIDEBAR_MAX = 800
const SIDEBAR_DEFAULT = 320

const sidebarWidth = useLocalStorage(SIDEBAR_WIDTH_KEY, SIDEBAR_DEFAULT)
const sidebarCollapsed = useLocalStorage(SIDEBAR_COLLAPSED_KEY, false)
const isResizing = ref(false)

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
  Prec.highest(keymap.of([
    {
      key: 'Ctrl-Enter',
      mac: 'Cmd-Enter',
      run: () => {
        executeQuery()
        return true
      },
    },
  ])),
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
  sheetOpen.value = false
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

function handleExecuteFromSidebar(cypherText: string) {
  query.value = cypherText
  if (editorView.value) {
    clearServerErrors(editorView.value)
  }
  sheetOpen.value = false
  nextTick(() => executeQuery())
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

// ── Resizable sidebar ──────────────────────────────────────────────────────

function startResize(e: MouseEvent) {
  e.preventDefault()
  isResizing.value = true
  const startX = e.clientX
  const startWidth = sidebarWidth.value

  function onMouseMove(ev: MouseEvent) {
    // Sidebar is on the right, so dragging left increases width
    const delta = startX - ev.clientX
    const newWidth = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, startWidth + delta))
    sidebarWidth.value = newWidth
  }

  function onMouseUp() {
    isResizing.value = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

// ── Keyboard shortcuts ─────────────────────────────────────────────────────

function handleCtrlEnter(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    executeQuery()
  }
}

onMounted(() => {
  loadHistory()
  fetchSchema()
  document.addEventListener('keydown', handleCtrlEnter)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleCtrlEnter)
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
            <CardTitle class="text-sm font-medium">Query Editor</CardTitle>
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
                      :class="ctrlHeld && !executing && query.trim() ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : ''"
                      @click="executeQuery"
                    >
                      <Loader2 v-if="executing" class="mr-2 size-4 animate-spin" />
                      <Play v-else class="mr-2 size-4" />
                      Execute
                      <kbd
                        v-if="ctrlHeld"
                        class="ml-2 rounded bg-primary-foreground/20 px-1 py-0.5 font-mono text-[10px]"
                      >
                        Enter
                      </kbd>
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

                <!-- Sidebar toggle (below xl) -->
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      variant="outline"
                      size="icon"
                      class="xl:hidden"
                      @click="sheetOpen = true"
                    >
                      <PanelRight class="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Open sidebar</p>
                  </TooltipContent>
                </Tooltip>
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

        <!-- Results panel (stats bar + tabbed results) -->
        <QueryResultsPanel
          :result="result"
          :error="error"
          :executing="executing"
          :execution-time="executionTime"
          :max-rows="maxRows"
        />
      </div>

      <!-- Right sidebar: resizable with drag handle, collapsible -->
      <div
        class="relative hidden flex-shrink-0 overflow-hidden xl:flex"
        :style="{ width: sidebarCollapsed ? '40px' : `${sidebarWidth}px` }"
      >
        <!-- Drag handle (hidden when collapsed) -->
        <div
          v-if="!sidebarCollapsed"
          class="absolute inset-y-0 left-0 z-10 w-1 cursor-col-resize transition-colors hover:bg-primary/30"
          :class="isResizing ? 'bg-primary/40' : 'bg-transparent'"
          @mousedown="startResize"
        />

        <!-- Collapsed state: just a vertical toggle bar -->
        <div v-if="sidebarCollapsed" class="flex h-full w-full flex-col items-center pt-1">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="ghost"
                size="icon"
                class="size-8"
                @click="sidebarCollapsed = false"
              >
                <PanelRight class="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              <p>Expand sidebar</p>
            </TooltipContent>
          </Tooltip>
        </div>

        <!-- Expanded sidebar content -->
        <div v-else class="ml-1.5 flex min-h-0 min-w-0 flex-1 flex-col">
          <!-- Collapse button -->
          <div class="mb-1 flex justify-end">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-6"
                  @click="sidebarCollapsed = true"
                >
                  <PanelRightClose class="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">
                <p>Collapse sidebar</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <QuerySidebar
            :node-labels="nodeLabels"
            :edge-labels="edgeLabels"
            :schema-loading="schemaLoading"
            :history="history"
            :current-query="query"
            @select-query="setQuery"
            @insert-at-cursor="insertAtCursor"
            @clear-history="clearHistory"
            @execute-query="handleExecuteFromSidebar"
          />
        </div>
      </div>
    </div>

    <!-- Responsive sidebar sheet (below xl) -->
    <Sheet v-model:open="sheetOpen">
      <SheetContent side="right" class="w-80 p-4 sm:max-w-sm">
        <SheetHeader class="sr-only">
          <SheetTitle>Query Sidebar</SheetTitle>
          <SheetDescription>Schema, templates, reference, and history</SheetDescription>
        </SheetHeader>
        <div class="flex h-full flex-col pt-6">
          <QuerySidebar
            :node-labels="nodeLabels"
            :edge-labels="edgeLabels"
            :schema-loading="schemaLoading"
            :history="history"
            :current-query="query"
            @select-query="setQuery"
            @insert-at-cursor="insertAtCursor"
            @clear-history="clearHistory"
            @execute-query="handleExecuteFromSidebar"
          />
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>
