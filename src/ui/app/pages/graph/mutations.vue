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
  FileUp, CheckCircle2, XCircle, AlertTriangle, Building2, X,
  Plus, GitBranch, RefreshCw, Lightbulb, BookOpen,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import type { MutationResult } from '~/types'

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

// Parser
import { parseContent, toJsonl, generateHexId, type ParseResult } from '@/utils/mutationParser'

// ── Quick Start Templates ───────────────────────────────────────────────────

const quickStartTemplates = [
  {
    name: 'Create Node',
    description: 'Add a new entity to the knowledge graph',
    icon: Plus,
    content: `{"op": "CREATE", "type": "node", "label": "person", "id": "person:${generateHexId()}", "set_properties": {"name": "Alice", "slug": "alice", "data_source_id": "dev-ui", "source_path": "manual"}}`,
  },
  {
    name: 'Create Edge',
    description: 'Connect two nodes with a relationship',
    icon: GitBranch,
    content: `{"op": "CREATE", "type": "edge", "label": "knows", "id": "knows:${generateHexId()}", "start_id": "person:a1b2c3d4e5f67890", "end_id": "person:f6e5d4c3b2a10987", "set_properties": {"data_source_id": "dev-ui", "source_path": "manual"}}`,
  },
  {
    name: 'Update Node',
    description: 'Modify properties on an existing node',
    icon: RefreshCw,
    content: '{"op": "UPDATE", "type": "node", "id": "person:a1b2c3d4e5f67890", "set_properties": {"email": "alice@example.com"}}',
  },
  {
    name: 'Delete Node',
    description: 'Remove a node from the graph',
    icon: Trash2,
    content: '{"op": "DELETE", "type": "node", "id": "person:a1b2c3d4e5f67890"}',
  },
]

const { applyMutations } = useGraphApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant } = useTenant()
const { ctrlHeld } = useModifierKeys()

// ── Responsive ─────────────────────────────────────────────────────────────

const isDesktop = useMediaQuery('(min-width: 1024px)')

// ── State ──────────────────────────────────────────────────────────────────

const editorContent = ref('')
const submitting = ref(false)
const lastResult = ref<MutationResult | null>(null)
const apiError = ref<string | null>(null)
const isDragOver = ref(false)
const editorContainer = ref<HTMLElement | null>(null)
const showTemplateSheet = ref(false)

// ── Computed ───────────────────────────────────────────────────────────────

const isEmpty = computed(() => !editorContent.value.trim())

// ── CodeMirror Setup ───────────────────────────────────────────────────────

const staticExtensions: Extension[] = [
  kartographTheme,
  jsonHighlightStyle,
  json(),
  lineNumbers(),
  autocompletion({ override: [mutationAutocomplete] }),
  linter(mutationLinter, { delay: 300 }),
  lintGutter(),
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

const cmExtensions = computed<Extension[]>(() => [...staticExtensions])

const { view: editorView, focus: focusEditor } = useCodemirror(
  editorContainer,
  editorContent,
  cmExtensions,
)

// Force CodeMirror to re-measure when the editor container becomes visible.
// The active-state div uses v-show="!isEmpty", so CodeMirror mounts inside a
// display:none container and calculates zero dimensions. When isEmpty flips to
// false the container becomes visible but CM doesn't know — we must tell it.
watch(isEmpty, (newVal, oldVal) => {
  if (oldVal && !newVal) {
    nextTick(() => {
      requestAnimationFrame(() => {
        editorView.value?.requestMeasure()
      })
    })
  }
})

// ── Live Preview ───────────────────────────────────────────────────────────

const parseResult = computed<ParseResult>(() => parseContent(editorContent.value))

const totalOps = computed(() => parseResult.value.operations.length)

const hasValidationIssues = computed(() =>
  parseResult.value.parseErrors.length > 0
  || parseResult.value.operations.some(op => op.warnings.length > 0),
)

// ── Actions ────────────────────────────────────────────────────────────────

function insertTemplate(content: string) {
  const view = editorView.value
  if (view) {
    const currentDoc = view.state.doc.toString()
    const trimmed = currentDoc.trim()
    if (trimmed) {
      // Append on a new line
      const insert = '\n' + content
      view.dispatch({
        changes: { from: view.state.doc.length, insert },
      })
    } else {
      // Replace empty content
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: content },
      })
    }
    view.focus()
  } else {
    // Fallback: no CM view yet
    if (editorContent.value.trim()) {
      editorContent.value += '\n' + content
    } else {
      editorContent.value = content
    }
  }
  lastResult.value = null
}

function showAllTemplates() {
  if (isDesktop.value) {
    // Insert a comment to transition to the active state where the sidebar is visible
    insertTemplate('// Choose a template from the sidebar, or start typing JSONL here')
  } else {
    showTemplateSheet.value = true
  }
}

async function handleSubmit() {
  if (submitting.value || !editorContent.value.trim()) return

  const result = parseResult.value
  if (result.parseErrors.length > 0) {
    toast.error('Fix parse errors before submitting')
    return
  }

  if (result.operations.length === 0) {
    toast.error('No operations to submit')
    return
  }

  // Convert parsed operations to clean JSONL for submission
  const jsonlBody = toJsonl(result.operations)

  apiError.value = null
  submitting.value = true

  try {
    const mutationResult = await applyMutations(jsonlBody)
    lastResult.value = mutationResult
    if (mutationResult.success) {
      toast.success(`Applied ${mutationResult.operations_applied} mutation${mutationResult.operations_applied === 1 ? '' : 's'}`)
    } else {
      toast.error('Some mutations failed', {
        description: `${mutationResult.errors.length} error${mutationResult.errors.length === 1 ? '' : 's'} occurred`,
      })
    }
  } catch (err) {
    const message = extractErrorMessage(err)
    apiError.value = message
    toast.error('Failed to apply mutations', { description: message })
  } finally {
    submitting.value = false
  }
}

function clearEditor() {
  editorContent.value = ''
  lastResult.value = null
  apiError.value = null
  nextTick(focusEditor)
}

function clearResults() {
  lastResult.value = null
  apiError.value = null
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
  const reader = new FileReader()
  reader.onload = (e) => {
    const text = e.target?.result as string
    const view = editorView.value
    if (view) {
      const currentDoc = view.state.doc.toString()
      const trimmed = currentDoc.trim()
      if (trimmed) {
        view.dispatch({
          changes: { from: view.state.doc.length, insert: '\n' + text },
        })
      } else {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
        })
      }
    } else {
      if (editorContent.value.trim()) {
        editorContent.value += '\n' + text
      } else {
        editorContent.value = text
      }
    }
    lastResult.value = null
    toast.success(`Loaded ${file.name}`)
  }
  reader.onerror = () => {
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

  // Accept ?template= URL parameter for cross-page deep-linking (e.g., from Schema Browser)
  const route = useRoute()
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

    <!-- Empty state -->
    <div
      v-else-if="isEmpty && hasTenant"
      class="flex flex-col items-center text-center py-12 space-y-8"
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

      <div class="space-y-3">
        <div class="mx-auto flex size-16 items-center justify-center rounded-full bg-muted">
          <FileCode class="size-8 text-muted-foreground" />
        </div>
        <h2 class="text-xl font-semibold">Mutation Console</h2>
        <p class="mx-auto max-w-md text-sm text-muted-foreground">
          Create, update, and delete nodes and edges in your knowledge graph using JSONL mutation operations.
        </p>
      </div>

      <!-- Quick start grid -->
      <div class="w-full max-w-2xl space-y-4">
        <h3 class="text-sm font-medium text-muted-foreground flex items-center justify-center gap-2">
          <Lightbulb class="size-4" />
          Quick Start — Choose a template
        </h3>
        <div class="grid gap-3 sm:grid-cols-2">
          <Card
            v-for="template in quickStartTemplates"
            :key="template.name"
            class="cursor-pointer transition-colors hover:bg-muted/50 text-left"
            @click="insertTemplate(template.content)"
          >
            <CardContent class="p-4 space-y-1.5">
              <div class="flex items-center gap-2">
                <component :is="template.icon" class="size-4 text-primary" />
                <span class="text-sm font-medium">{{ template.name }}</span>
              </div>
              <p class="text-xs text-muted-foreground">{{ template.description }}</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <!-- Additional options row -->
      <div class="flex flex-wrap items-center justify-center gap-3">
        <label>
          <input
            type="file"
            accept=".jsonl,.json,.ndjson"
            class="hidden"
            aria-label="Upload JSONL mutation file"
            @change="handleFileUpload"
          >
          <Button variant="outline" size="sm" as="span" class="cursor-pointer gap-2">
            <Upload class="size-4" />
            Upload File
          </Button>
        </label>
        <Button variant="outline" size="sm" class="gap-2" @click="showAllTemplates">
          <BookOpen class="size-4" />
          All Templates
        </Button>
      </div>

      <!-- Format hint -->
      <div class="mx-auto max-w-md space-y-2 rounded-lg border bg-muted/30 p-4 text-left">
        <p class="text-xs font-medium">JSONL Format</p>
        <p class="text-xs text-muted-foreground">
          Each line is a JSON object representing one mutation. Operations:
          <code class="rounded bg-muted px-1 py-0.5">CREATE</code>,
          <code class="rounded bg-muted px-1 py-0.5">UPDATE</code>,
          <code class="rounded bg-muted px-1 py-0.5">DELETE</code>,
          <code class="rounded bg-muted px-1 py-0.5">DEFINE</code>
        </p>
        <p class="text-xs text-muted-foreground">
          Submit with
          <kbd class="rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px]">Ctrl</kbd> +
          <kbd class="rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd>
        </p>
      </div>
    </div>

    <!-- Active state (editor has content) — always rendered so CodeMirror mounts -->
    <div v-if="hasTenant" v-show="!isEmpty" class="space-y-4">
      <!-- Editor + right panel grid -->
      <div class="grid gap-6" :class="isDesktop ? 'lg:grid-cols-[1fr_400px]' : ''">
        <!-- Left: Editor area -->
        <div class="space-y-4">
          <!-- Editor card -->
          <Card
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
                  :disabled="submitting || !editorContent.trim()"
                  :class="ctrlHeld && !submitting && editorContent.trim() ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : ''"
                  @click="handleSubmit"
                >
                  <Loader2 v-if="submitting" class="mr-2 size-4 animate-spin" />
                  <Play v-else class="mr-2 size-4" />
                  Apply Mutations
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
              {{ totalOps }} operation{{ totalOps === 1 ? '' : 's' }} ready
              <span v-if="hasValidationIssues" class="text-yellow-600 dark:text-yellow-400">
                (has warnings)
              </span>
            </span>
            <!-- Mobile: Templates button -->
            <Button
              v-if="!isDesktop"
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

          <!-- Result display -->
          <template v-if="lastResult">
            <Card v-if="lastResult.success" class="border-green-500/30">
              <CardContent class="flex items-start gap-3 p-4">
                <CheckCircle2 class="mt-0.5 size-5 shrink-0 text-green-600 dark:text-green-400" />
                <div class="min-w-0 flex-1 space-y-1">
                  <p class="text-sm font-medium text-green-600 dark:text-green-400">
                    Mutations Applied Successfully
                  </p>
                  <p class="text-sm text-muted-foreground">
                    {{ lastResult.operations_applied }} operation{{ lastResult.operations_applied === 1 ? '' : 's' }} applied to the graph.
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-7 shrink-0"
                  @click="clearResults"
                >
                  <X class="size-3.5" />
                </Button>
              </CardContent>
            </Card>

            <Card v-else class="border-destructive/30">
              <CardContent class="flex items-start gap-3 p-4">
                <XCircle class="mt-0.5 size-5 shrink-0 text-destructive" />
                <div class="min-w-0 flex-1 space-y-2">
                  <p class="text-sm font-medium text-destructive">
                    Mutations Failed
                  </p>
                  <p class="text-sm text-muted-foreground">
                    {{ lastResult.operations_applied }} operation{{ lastResult.operations_applied === 1 ? '' : 's' }} applied before failure.
                  </p>
                  <div v-if="lastResult.errors.length > 0" class="space-y-1">
                    <div
                      v-for="(error, idx) in lastResult.errors"
                      :key="idx"
                      class="flex items-start gap-2 rounded-md bg-destructive/10 px-2.5 py-1.5 text-xs"
                    >
                      <AlertTriangle class="mt-0.5 size-3 shrink-0 text-destructive" />
                      <span class="font-mono">{{ error }}</span>
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-7 shrink-0"
                  @click="clearResults"
                >
                  <X class="size-3.5" />
                </Button>
              </CardContent>
            </Card>
          </template>
        </div>

        <!-- Right panel (desktop only) -->
        <div v-if="isDesktop" class="space-y-4">
          <!-- Live preview -->
          <MutationPreview :parse-result="parseResult" />

          <!-- Templates in a collapsible card -->
          <Card>
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
      <MutationPreview v-if="!isDesktop" :parse-result="parseResult" />

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
    </div>
  </div>
</template>
