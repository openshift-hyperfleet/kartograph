<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { toast } from 'vue-sonner'
import { keymap, lineNumbers } from '@codemirror/view'
import { Prec, type Extension } from '@codemirror/state'
import { json } from '@codemirror/lang-json'
import { autocompletion } from '@codemirror/autocomplete'
import { linter, lintGutter } from '@codemirror/lint'
import { useMediaQuery } from '@vueuse/core'
import {
  FileCode, Play, Trash2, Upload, Loader2,
  FileUp, XCircle, AlertTriangle, Building2,
  Plus, GitBranch, RefreshCw, BookOpen,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
// CodeMirror
import { useCodemirror } from '@/composables/useCodemirror'
import { kartographTheme, jsonHighlightStyle } from '@/lib/codemirror/theme'
import { mutationAutocomplete } from '@/lib/codemirror/mutation-jsonl/autocomplete'
import { mutationLinter } from '@/lib/codemirror/mutation-jsonl/linter'

// Modifier keys
import { useModifierKeys } from '@/composables/useModifierKeys'

// Local components
import MutationPreview from '@/components/graph/MutationPreview.vue'
import MutationTemplates from '@/components/graph/MutationTemplates.vue'
import WarningBrowser from '@/components/graph/WarningBrowser.vue'

// Parser
import { parseContent, toJsonl, generateHexId, getBreakdown, type ParseResult } from '@/utils/mutationParser'

// Worker-based parsing for large files
import { useMutationWorker, LARGE_FILE_THRESHOLD } from '@/composables/useMutationWorker'

// ── Quick Start Templates ───────────────────────────────────────────────────

const quickStartTemplates = [
  {
    name: 'Create a Node',
    description: 'Define a type and create a node in one batch',
    icon: Plus,
    content: [
      `{"op": "DEFINE", "type": "node", "label": "person", "description": "A person entity", "required_properties": ["name"]}`,
      `{"op": "CREATE", "type": "node", "label": "person", "id": "person:${generateHexId()}", "set_properties": {"name": "Alice", "slug": "alice", "data_source_id": "dev-ui", "source_path": "manual"}}`,
    ].join('\n'),
  },
  {
    name: 'Create an Edge',
    description: 'Define a relationship type and connect two nodes',
    icon: GitBranch,
    content: [
      `{"op": "DEFINE", "type": "edge", "label": "knows", "description": "Indicates two people know each other", "required_properties": []}`,
      `{"op": "CREATE", "type": "edge", "label": "knows", "id": "knows:${generateHexId()}", "start_id": "person:a1b2c3d4e5f67890", "end_id": "person:f6e5d4c3b2a10987", "set_properties": {"data_source_id": "dev-ui", "source_path": "manual"}}`,
    ].join('\n'),
  },
  {
    name: 'Update Properties',
    description: 'Modify properties on an existing entity',
    icon: RefreshCw,
    content: '{"op": "UPDATE", "type": "node", "id": "person:a1b2c3d4e5f67890", "set_properties": {"email": "alice@example.com"}}',
  },
  {
    name: 'Delete an Entity',
    description: 'Remove a node or edge (nodes cascade-delete edges)',
    icon: Trash2,
    content: '{"op": "DELETE", "type": "node", "id": "person:a1b2c3d4e5f67890"}',
  },
]

const { hasTenant } = useTenant()
const { ctrlHeld } = useModifierKeys()
const submission = useMutationSubmission()
const router = useRouter()
const route = useRoute()

// ── Worker ─────────────────────────────────────────────────────────────────

const { workerResult, parsing, parseTimeMs, isLargeFile, requestParse } = useMutationWorker()

// ── Responsive ─────────────────────────────────────────────────────────────

const isDesktop = useMediaQuery('(min-width: 1024px)')

// ── State ──────────────────────────────────────────────────────────────────

const { editorContent, largeFileMode, uploadFileName, clearState: clearEditorState } = useMutationEditorState()
const isDragOver = ref(false)
const editorContainer = ref<HTMLElement | null>(null)
const showTemplateSheet = ref(false)
const uploadProgress = ref<number | null>(null)
const showWarningBrowser = ref(false)

// Initialize showEditor from URL query or persisted state
const showEditor = ref(
  route.query.view === 'editor' || !!editorContent.value.trim() || largeFileMode.value,
)

// ── Editor state ↔ URL sync ────────────────────────────────────────────────

function activateEditor() {
  if (!showEditor.value) {
    showEditor.value = true
  }
  if (route.query.view !== 'editor') {
    router.push({ query: { ...route.query, view: 'editor' } })
  }
}

function deactivateEditor() {
  showEditor.value = false
  clearEditorState()
  submission.dismiss()
  const { view: _view, ...rest } = route.query
  router.push({ query: Object.keys(rest).length ? rest : undefined })
}

// Handle browser back/forward button
watch(() => route.query.view, (newView) => {
  if (newView === 'editor') {
    showEditor.value = true
  } else {
    // Only deactivate if there's no content to preserve
    if (!editorContent.value.trim() && !largeFileMode.value) {
      showEditor.value = false
    }
  }
})

// Derived from the cross-app submission composable
const submitting = computed(() => submission.state.value.status === 'submitting')
const apiError = computed(() => submission.state.value.error)

// ── CodeMirror Setup ───────────────────────────────────────────────────────

// Base extensions that are always present
const staticBaseExtensions: Extension[] = [
  kartographTheme,
  jsonHighlightStyle,
  json(),
  lineNumbers(),
  Prec.highest(keymap.of([
    {
      key: 'Ctrl-Enter',
      mac: 'Cmd-Enter',
      run: () => {
        handleSubmit()
        return true
      },
    },
  ])),
]

// Full extensions including linter/autocomplete (disabled for large files)
const cmExtensions = computed<Extension[]>(() => {
  if (largeFileMode.value) return staticBaseExtensions
  return [
    ...staticBaseExtensions,
    autocompletion({ override: [mutationAutocomplete] }),
    linter(mutationLinter, { delay: 300 }),
    lintGutter(),
  ]
})

const { view: editorView } = useCodemirror(
  editorContainer,
  editorContent,
  cmExtensions,
)

// ── Live Preview (hybrid: sync for small, worker for large) ────────────────

// For small files: synchronous parsing (instant feedback)
const syncParseResult = computed<ParseResult | null>(() => {
  if (isLargeFile.value) return null
  return parseContent(editorContent.value)
})

// Watch content changes and dispatch to worker for large files
watch(editorContent, (content) => {
  requestParse(content)
})

// Unified accessors that work for both small and large files
const totalOps = computed(() => {
  if (isLargeFile.value) return workerResult.value?.totalOps ?? 0
  return syncParseResult.value?.operations.length ?? 0
})

const hasValidationIssues = computed(() => {
  if (isLargeFile.value) return workerResult.value?.hasWarnings ?? false
  const r = syncParseResult.value
  return r ? (r.parseErrors.length > 0 || r.operations.some(op => op.warnings.length > 0)) : false
})

const breakdown = computed(() => {
  if (isLargeFile.value && workerResult.value) return workerResult.value.breakdown
  if (syncParseResult.value) return getBreakdown(syncParseResult.value.operations)
  return { DEFINE: 0, CREATE: 0, UPDATE: 0, DELETE: 0, unknown: 0 }
})

// ── Actions ────────────────────────────────────────────────────────────────

async function insertTemplate(content: string) {
  activateEditor()

  // Wait for Vue to render the editor container
  await nextTick()
  // Wait one more tick for the watch(container) to fire and create CM
  await nextTick()

  const view = editorView.value
  if (view) {
    const currentDoc = view.state.doc.toString()
    if (currentDoc.trim()) {
      view.dispatch({ changes: { from: view.state.doc.length, insert: '\n' + content } })
    } else {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: content } })
    }
    view.focus()
  } else {
    // CM still not ready — set content on the ref, CM will pick it up when it initializes
    if (editorContent.value.trim()) {
      editorContent.value += '\n' + content
    } else {
      editorContent.value = content
    }
  }
  submission.dismiss()
}

function showAllTemplates() {
  if (isDesktop.value) {
    activateEditor()
  } else {
    showTemplateSheet.value = true
  }
}

// Local flag for immediate visual feedback while preparing large file submissions
const preparing = ref(false)

async function handleSubmit() {
  if (submitting.value || preparing.value || !editorContent.value.trim()) return

  // For large files, skip client-side re-parse and submit raw content directly
  if (isLargeFile.value) {
    // Show loading state immediately before expensive string processing
    preparing.value = true
    const opCount = totalOps.value

    // Yield to let Vue render the loading state on the button
    await nextTick()
    await new Promise(resolve => requestAnimationFrame(resolve))

    // Now do the expensive line filtering
    const lines = editorContent.value.split('\n')
    const cleanLines = lines.filter((l) => {
      const t = l.trim()
      return t && !t.startsWith('//') && !t.startsWith('#')
    })
    const body = cleanLines.join('\n')
    preparing.value = false
    submission.submit(body, opCount)
    return
  }

  // Small file: use full parse result (existing behavior)
  const result = syncParseResult.value
  if (!result || result.parseErrors.length > 0) {
    toast.error('Fix parse errors before submitting')
    return
  }

  if (result.operations.length === 0) {
    toast.error('No operations to submit')
    return
  }

  // Convert parsed operations to clean JSONL for submission
  const jsonlBody = toJsonl(result.operations)
  submission.submit(jsonlBody, result.operations.length)
}

function clearEditor() {
  deactivateEditor()
}

// ── File Upload ────────────────────────────────────────────────────────────

function handleFileUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) readFile(file)
  input.value = '' // reset so same file can be re-selected
}

function handleDrop(event: DragEvent) {
  isDragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) readFile(file)
}

function readFile(file: File) {
  if (!file.name.endsWith('.jsonl') && !file.name.endsWith('.json') && !file.name.endsWith('.ndjson')) {
    toast.error('Invalid file type', { description: 'Please upload a .jsonl, .json, or .ndjson file.' })
    return
  }

  uploadFileName.value = file.name
  uploadProgress.value = 0

  const reader = new FileReader()
  reader.onprogress = (e) => {
    if (e.lengthComputable) {
      uploadProgress.value = Math.round((e.loaded / e.total) * 100)
    }
  }
  reader.onload = (e) => {
    const text = e.target?.result as string
    uploadProgress.value = null
    activateEditor()

    // For large files, set content directly and enable large-file mode
    if (text.length > LARGE_FILE_THRESHOLD) {
      editorContent.value = text

      if (text.length > 5_000_000) {
        // For files > 5MB, disable CM editing and use read-only summary mode
        largeFileMode.value = true
        toast.success(`Loaded ${file.name}`, {
          description: `${(text.length / 1_000_000).toFixed(1)} MB — preview mode enabled`,
        })
      } else {
        toast.success(`Loaded ${file.name}`)
      }
    } else {
      // Small file: set content directly — CM will pick it up via reactivity
      if (editorContent.value.trim()) {
        editorContent.value += '\n' + text
      } else {
        editorContent.value = text
      }
      toast.success(`Loaded ${file.name}`)
    }
    submission.dismiss()
  }
  reader.onerror = () => {
    uploadProgress.value = null
    toast.error('Failed to read file')
  }
  reader.readAsText(file)
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = true
}

function handleDragLeave() {
  isDragOver.value = false
}

// ── Keyboard Shortcut (global fallback) ────────────────────────────────────

function handleCtrlEnter(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    handleSubmit()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleCtrlEnter)

  const templateParam = route.query.template
  if (typeof templateParam === 'string' && templateParam.trim()) {
    nextTick(() => insertTemplate(templateParam.trim()))
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleCtrlEnter)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <div class="flex items-center gap-3">
          <FileCode class="size-6 text-muted-foreground" />
          <h1 class="text-2xl font-bold tracking-tight">Mutations Console</h1>
        </div>
        <p class="mt-1 text-muted-foreground">Author and submit JSONL mutations to the knowledge graph.</p>
      </div>
    </div>

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the header to apply mutations.</p>
    </div>

    <!-- Empty state — shown when editor is not active -->
    <div
      v-if="!showEditor && hasTenant && !largeFileMode"
      class="py-12"
      @drop.prevent="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
    >
      <!-- Drop overlay -->
      <Transition
        enter-active-class="transition-opacity duration-200"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-150"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="isDragOver"
          class="fixed inset-0 z-50 flex flex-col items-center justify-center gap-2 bg-primary/10 backdrop-blur-[2px]"
        >
          <div class="rounded-full bg-primary/20 p-4">
            <FileUp class="size-8 text-primary" />
          </div>
          <span class="text-sm font-medium text-primary">Drop .jsonl file here</span>
          <span class="text-xs text-muted-foreground">Supports .jsonl, .json, and .ndjson files</span>
        </div>
      </Transition>

      <div class="mx-auto max-w-2xl space-y-8">
        <p class="text-center text-muted-foreground">
          Get started by uploading a file, opening the editor, or choosing a template.
        </p>

        <!-- Primary actions -->
        <div class="grid gap-4 sm:grid-cols-2">
          <label>
            <input
              type="file"
              accept=".jsonl,.json,.ndjson"
              class="hidden"
              aria-label="Upload JSONL mutation file"
              @change="handleFileUpload"
            >
            <Card class="cursor-pointer transition-colors hover:bg-muted/50 h-full">
              <CardContent class="flex flex-col items-center gap-3 p-6 text-center">
                <div class="rounded-full bg-muted p-3">
                  <Upload class="size-5 text-muted-foreground" />
                </div>
                <div>
                  <p class="text-sm font-medium">Upload File</p>
                  <p class="text-xs text-muted-foreground">.jsonl, .json, or .ndjson</p>
                </div>
              </CardContent>
            </Card>
          </label>
          <Card
            class="cursor-pointer transition-colors hover:bg-muted/50"
            @click="activateEditor()"
          >
            <CardContent class="flex flex-col items-center gap-3 p-6 text-center">
              <div class="rounded-full bg-muted p-3">
                <FileCode class="size-5 text-muted-foreground" />
              </div>
              <div>
                <p class="text-sm font-medium">Open Editor</p>
                <p class="text-xs text-muted-foreground">Start with an empty JSONL editor</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <!-- Separator -->
        <div class="flex items-center gap-4">
          <Separator class="flex-1" />
          <span class="text-xs text-muted-foreground">or start from a template</span>
          <Separator class="flex-1" />
        </div>

        <!-- Template cards -->
        <div class="grid gap-3 sm:grid-cols-2">
          <Card
            v-for="template in quickStartTemplates"
            :key="template.name"
            class="cursor-pointer transition-colors hover:bg-muted/50 text-left"
            @click="insertTemplate(template.content)"
          >
            <CardContent class="p-4 space-y-1">
              <div class="flex items-center gap-2">
                <component :is="template.icon" class="size-4 text-primary" />
                <span class="text-sm font-medium">{{ template.name }}</span>
              </div>
              <p class="text-xs text-muted-foreground">{{ template.description }}</p>
            </CardContent>
          </Card>
        </div>

        <!-- Drag & drop hint -->
        <p class="text-center text-xs text-muted-foreground">
          Tip: You can also drag &amp; drop a .jsonl file anywhere on this page
        </p>
      </div>
    </div>

    <!-- Active state (editor + panels) — mutually exclusive with the empty state above -->
    <div v-if="hasTenant && (showEditor || largeFileMode)" class="space-y-4">
      <!-- Upload progress bar -->
      <Card v-if="uploadProgress !== null" class="border-primary/30">
        <CardContent class="p-4 space-y-2">
          <div class="flex items-center justify-between text-sm">
            <span class="flex items-center gap-2">
              <Loader2 class="size-4 animate-spin" />
              Loading {{ uploadFileName }}...
            </span>
            <span class="text-muted-foreground">{{ uploadProgress }}%</span>
          </div>
          <div class="h-2 w-full rounded-full bg-muted overflow-hidden">
            <div
              class="h-full rounded-full bg-primary transition-all duration-300"
              :style="{ width: `${uploadProgress}%` }"
            />
          </div>
        </CardContent>
      </Card>

      <!-- Editor + right panel grid -->
      <div class="grid gap-6" :class="isDesktop ? 'lg:grid-cols-[1fr_400px]' : ''">
        <!-- Left: Editor area -->
        <div class="space-y-4">
          <!-- Large file mode: summary instead of editor -->
          <Card v-if="largeFileMode">
            <CardHeader class="pb-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <CardTitle class="text-base">Large File Mode</CardTitle>
                  <Badge variant="secondary">
                    {{ (editorContent.length / 1_000_000).toFixed(1) }} MB
                  </Badge>
                </div>
                <Button variant="ghost" size="sm" @click="clearEditor">
                  <Trash2 class="mr-2 size-4" />
                  Clear
                </Button>
              </div>
            </CardHeader>
            <CardContent class="space-y-3">
              <p class="text-sm text-muted-foreground">
                File too large for interactive editing. Review the summary below and submit directly.
              </p>

              <!-- Parsing indicator -->
              <div v-if="parsing" class="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 class="size-4 animate-spin" />
                Analyzing operations...
              </div>

              <!-- Breakdown badges -->
              <div v-else-if="workerResult" class="space-y-2">
                <div class="flex flex-wrap gap-2">
                  <Badge variant="secondary">
                    {{ workerResult.totalOps.toLocaleString() }} operations
                  </Badge>
                  <Badge v-if="workerResult.breakdown.DEFINE > 0" variant="outline" class="gap-1">
                    DEFINE <span class="font-mono">{{ workerResult.breakdown.DEFINE.toLocaleString() }}</span>
                  </Badge>
                  <Badge v-if="workerResult.breakdown.CREATE > 0" class="gap-1">
                    CREATE <span class="font-mono">{{ workerResult.breakdown.CREATE.toLocaleString() }}</span>
                  </Badge>
                  <Badge v-if="workerResult.breakdown.UPDATE > 0" variant="secondary" class="gap-1">
                    UPDATE <span class="font-mono">{{ workerResult.breakdown.UPDATE.toLocaleString() }}</span>
                  </Badge>
                  <Badge v-if="workerResult.breakdown.DELETE > 0" variant="destructive" class="gap-1">
                    DELETE <span class="font-mono">{{ workerResult.breakdown.DELETE.toLocaleString() }}</span>
                  </Badge>
                </div>

                <div v-if="workerResult.warningCount > 0" class="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    class="gap-2 border-yellow-500/30 text-yellow-600 dark:text-yellow-400 hover:bg-yellow-500/10"
                    @click="showWarningBrowser = true"
                  >
                    <AlertTriangle class="size-3.5" />
                    Browse {{ workerResult.warningCount.toLocaleString() }} Warning{{ workerResult.warningCount === 1 ? '' : 's' }}
                  </Button>
                </div>

                <div v-if="workerResult.parseErrors.length > 0" class="space-y-1">
                  <div
                    v-for="(error, idx) in workerResult.parseErrors.slice(0, 10)"
                    :key="idx"
                    class="flex items-start gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs"
                  >
                    <AlertTriangle class="mt-0.5 size-3 shrink-0 text-destructive" />
                    <span class="font-mono">{{ error }}</span>
                  </div>
                  <p v-if="workerResult.parseErrors.length > 10" class="text-xs text-muted-foreground">
                    ...and {{ workerResult.parseErrors.length - 10 }} more errors
                  </p>
                </div>

                <p class="text-xs text-muted-foreground">
                  Analyzed in {{ parseTimeMs.toFixed(0) }}ms
                </p>
              </div>
            </CardContent>
          </Card>

          <!-- Normal editor card -->
          <Card
            v-if="!largeFileMode"
            @drop.prevent="handleDrop"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
          >
            <CardHeader class="pb-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <CardTitle class="text-base">JSONL Editor</CardTitle>
                  <Badge v-if="totalOps > 0" variant="secondary">
                    {{ totalOps }} operation{{ totalOps === 1 ? '' : 's' }}
                  </Badge>
                </div>
                <div class="flex items-center gap-2">
                  <!-- File upload -->
                  <label>
                    <input
                      type="file"
                      accept=".jsonl,.json,.ndjson"
                      class="hidden"
                      aria-label="Upload JSONL mutation file"
                      @change="handleFileUpload"
                    >
                    <Button variant="outline" size="sm" as="span" class="cursor-pointer">
                      <Upload class="mr-2 size-4" />
                      Upload
                    </Button>
                  </label>
                  <Button
                    variant="ghost"
                    size="sm"
                    :disabled="!editorContent"
                    @click="clearEditor"
                  >
                    <Trash2 class="mr-2 size-4" />
                    Clear
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div
                class="relative overflow-hidden rounded-md border transition-all duration-200"
                :class="isDragOver
                  ? 'border-primary ring-2 ring-primary/20'
                  : 'border-input'"
              >
                <!-- Drop overlay -->
                <Transition
                  enter-active-class="transition-opacity duration-200"
                  enter-from-class="opacity-0"
                  enter-to-class="opacity-100"
                  leave-active-class="transition-opacity duration-150"
                  leave-from-class="opacity-100"
                  leave-to-class="opacity-0"
                >
                  <div
                    v-if="isDragOver"
                    class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-md bg-primary/10 backdrop-blur-[2px]"
                  >
                    <div class="rounded-full bg-primary/20 p-4">
                      <FileUp class="size-8 text-primary" />
                    </div>
                    <span class="text-sm font-medium text-primary">Drop .jsonl file here</span>
                    <span class="text-xs text-muted-foreground">Supports .jsonl, .json, and .ndjson files</span>
                  </div>
                </Transition>

                <!-- CodeMirror Editor -->
                <div
                  ref="editorContainer"
                  class="[&_.cm-editor]:min-h-[300px] [&_.cm-editor]:max-h-[500px] [&_.cm-editor]:overflow-auto [&_.cm-editor.cm-focused]:ring-1 [&_.cm-editor.cm-focused]:ring-ring"
                />
              </div>
            </CardContent>
          </Card>

          <!-- Action bar -->
          <div class="flex items-center gap-3">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  :disabled="submitting || preparing || (!editorContent.trim() && !largeFileMode)"
                  :class="ctrlHeld && !submitting && !preparing && (editorContent.trim() || largeFileMode) ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : ''"
                  @click="handleSubmit"
                >
                  <Loader2 v-if="submitting || preparing" class="mr-2 size-4 animate-spin" />
                  <Play v-else class="mr-2 size-4" />
                  <template v-if="preparing">
                    Preparing...
                  </template>
                  <template v-else-if="submitting">
                    Applying mutations...
                  </template>
                  <template v-else>
                    Apply Mutations
                  </template>
                  <kbd
                    v-if="ctrlHeld"
                    class="ml-2 rounded bg-primary-foreground/20 px-1 py-0.5 font-mono text-[10px]"
                  >
                    Enter
                  </kbd>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Ctrl+Enter / Cmd+Enter</p>
              </TooltipContent>
            </Tooltip>
            <span v-if="totalOps > 0" class="text-sm text-muted-foreground">
              {{ totalOps.toLocaleString() }} operation{{ totalOps === 1 ? '' : 's' }} ready
              <span v-if="hasValidationIssues" class="text-yellow-600 dark:text-yellow-400">
                (has warnings)
              </span>
            </span>
            <span v-if="parsing" class="text-sm text-muted-foreground flex items-center gap-1.5">
              <Loader2 class="size-3 animate-spin" />
              Analyzing...
            </span>
            <!-- Mobile: Templates button -->
            <Button
              v-if="!isDesktop && !largeFileMode"
              variant="outline"
              size="sm"
              class="ml-auto gap-2"
              @click="showTemplateSheet = true"
            >
              <BookOpen class="size-4" />
              Templates
            </Button>
          </div>

          <!-- API error -->
          <Alert v-if="apiError" variant="destructive">
            <XCircle class="size-4" />
            <AlertTitle>Request Failed</AlertTitle>
            <AlertDescription class="font-mono text-xs">
              {{ apiError }}
            </AlertDescription>
          </Alert>

          <!-- Result display is now handled by the floating MutationProgress indicator -->
        </div>

        <!-- Right panel (desktop only) -->
        <div v-if="isDesktop" class="space-y-4">
          <!-- Live preview -->
          <MutationPreview
            :parse-result="syncParseResult ?? undefined"
            :worker-result="isLargeFile ? workerResult : undefined"
            :parsing="parsing"
            :parse-time-ms="isLargeFile ? parseTimeMs : undefined"
            @browse-warnings="showWarningBrowser = true"
          />

          <!-- Templates in a collapsible card (hidden in large file mode) -->
          <Card v-if="!largeFileMode">
            <CardHeader class="pb-3">
              <CardTitle class="text-sm font-medium flex items-center gap-2">
                <BookOpen class="size-4" />
                Templates
              </CardTitle>
            </CardHeader>
            <CardContent>
              <MutationTemplates @insert="insertTemplate" />
            </CardContent>
          </Card>
        </div>
      </div>

      <!-- Mobile: Preview below editor (always visible when there's content) -->
      <MutationPreview
        v-if="!isDesktop"
        :parse-result="syncParseResult ?? undefined"
        :worker-result="isLargeFile ? workerResult : undefined"
        :parsing="parsing"
        :parse-time-ms="isLargeFile ? parseTimeMs : undefined"
        @browse-warnings="showWarningBrowser = true"
      />

      <!-- Mobile: Template sheet -->
      <Sheet v-model:open="showTemplateSheet">
        <SheetContent side="right" class="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Mutation Templates</SheetTitle>
            <SheetDescription>Insert a template into the editor</SheetDescription>
          </SheetHeader>
          <div class="mt-6">
            <MutationTemplates @insert="(content: string) => { insertTemplate(content); showTemplateSheet = false }" />
          </div>
        </SheetContent>
      </Sheet>

      <!-- Warning Browser sheet -->
      <Sheet v-model:open="showWarningBrowser">
        <SheetContent side="right" class="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle class="flex items-center gap-2">
              <AlertTriangle class="size-4 text-yellow-600 dark:text-yellow-400" />
              Warning Browser
            </SheetTitle>
            <SheetDescription>
              Click a warning to edit the corresponding line.
            </SheetDescription>
          </SheetHeader>
          <div class="mt-4">
            <WarningBrowser
              :worker-result="isLargeFile ? workerResult : undefined"
              :parse-result="!isLargeFile ? syncParseResult ?? undefined : undefined"
              :editor-content="editorContent"
              @update:editor-content="editorContent = $event"
            />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  </div>
</template>
