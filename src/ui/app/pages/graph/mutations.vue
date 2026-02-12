<script setup lang="ts">
import { ref, computed } from 'vue'
import { toast } from 'vue-sonner'
import {
  FileCode, Play, Trash2, Upload, Loader2,
  FileUp, Plus, CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import type { MutationResult } from '~/types'

const { applyMutations } = useGraphApi()

// ── State ──────────────────────────────────────────────────────────────────

const editorContent = ref('')
const submitting = ref(false)
const lastResult = ref<MutationResult | null>(null)
const validationErrors = ref<string[]>([])
const isDragOver = ref(false)

// ── Templates ──────────────────────────────────────────────────────────────

interface MutationTemplate {
  name: string
  description: string
  content: string
}

const templates: MutationTemplate[] = [
  {
    name: 'Define Type',
    description: 'Define a new node or edge type schema',
    content: '{"op": "DEFINE", "type": "node", "label": "person", "description": "A person entity", "required_properties": ["name"], "optional_properties": ["email", "age"]}',
  },
  {
    name: 'Create Node',
    description: 'Create a new node instance',
    content: '{"op": "CREATE", "type": "node", "label": "person", "id": "person:a1b2c3d4e5f67890", "set_properties": {"name": "Alice", "slug": "alice"}}',
  },
  {
    name: 'Create Edge',
    description: 'Create a relationship between nodes',
    content: '{"op": "CREATE", "type": "edge", "label": "knows", "id": "knows:a1b2c3d4e5f67890", "start_id": "person:a1b2c3d4e5f67890", "end_id": "person:f6e5d4c3b2a10987", "set_properties": {}}',
  },
  {
    name: 'Update Node',
    description: 'Update properties on an existing node',
    content: '{"op": "UPDATE", "type": "node", "id": "person:a1b2c3d4e5f67890", "set_properties": {"email": "alice@example.com"}}',
  },
  {
    name: 'Delete Node',
    description: 'Remove a node from the graph',
    content: '{"op": "DELETE", "type": "node", "id": "person:a1b2c3d4e5f67890"}',
  },
]

// ── Computed ───────────────────────────────────────────────────────────────

const lineCount = computed(() => {
  if (!editorContent.value.trim()) return 0
  return editorContent.value.trim().split('\n').filter(line => line.trim()).length
})

const lineNumbers = computed(() => {
  if (!editorContent.value) return '1'
  const lines = editorContent.value.split('\n')
  return lines.map((_, i) => i + 1).join('\n')
})

// ── Actions ────────────────────────────────────────────────────────────────

function insertTemplate(template: MutationTemplate) {
  if (editorContent.value.trim()) {
    editorContent.value += '\n' + template.content
  } else {
    editorContent.value = template.content
  }
  lastResult.value = null
  validationErrors.value = []
}

function validateJsonl(): boolean {
  validationErrors.value = []
  const content = editorContent.value.trim()
  if (!content) {
    validationErrors.value = ['Editor is empty. Add at least one mutation operation.']
    return false
  }

  const lines = content.split('\n')
  const errors: string[] = []

  lines.forEach((line, index) => {
    const trimmed = line.trim()
    if (!trimmed) return // skip blank lines
    try {
      JSON.parse(trimmed)
    } catch {
      errors.push(`Line ${index + 1}: Invalid JSON`)
    }
  })

  validationErrors.value = errors
  return errors.length === 0
}

async function handleSubmit() {
  lastResult.value = null
  if (!validateJsonl()) return

  submitting.value = true
  try {
    const result = await applyMutations(editorContent.value.trim())
    lastResult.value = result
    if (result.success) {
      toast.success(`Applied ${result.operations_applied} mutation${result.operations_applied === 1 ? '' : 's'}`)
    } else {
      toast.error('Some mutations failed', {
        description: `${result.errors.length} error${result.errors.length === 1 ? '' : 's'} occurred`,
      })
    }
  } catch (err) {
    toast.error('Failed to apply mutations', {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
  } finally {
    submitting.value = false
  }
}

function clearEditor() {
  editorContent.value = ''
  lastResult.value = null
  validationErrors.value = []
}

// ── File upload ────────────────────────────────────────────────────────────

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
    if (editorContent.value.trim()) {
      editorContent.value += '\n' + text
    } else {
      editorContent.value = text
    }
    lastResult.value = null
    validationErrors.value = []
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

    <div class="grid gap-6 xl:grid-cols-[1fr_320px]">
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
                <Badge v-if="lineCount > 0" variant="secondary">
                  {{ lineCount }} operation{{ lineCount === 1 ? '' : 's' }}
                </Badge>
              </div>
              <div class="flex items-center gap-2">
                <!-- File upload -->
                <label>
                  <input
                    type="file"
                    accept=".jsonl,.json,.ndjson"
                    class="hidden"
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
              class="relative rounded-md border transition-colors"
              :class="{ 'border-primary bg-primary/5': isDragOver }"
            >
              <!-- Drop overlay -->
              <div
                v-if="isDragOver"
                class="absolute inset-0 z-10 flex items-center justify-center rounded-md bg-primary/10"
              >
                <div class="flex items-center gap-2 text-primary">
                  <FileUp class="size-6" />
                  <span class="font-medium">Drop .jsonl file here</span>
                </div>
              </div>

              <!-- Editor with line numbers -->
              <div class="flex">
                <div
                  class="select-none border-r bg-muted/50 px-3 py-3 text-right font-mono text-xs leading-6 text-muted-foreground"
                  aria-hidden="true"
                >
                  <pre>{{ lineNumbers }}</pre>
                </div>
                <Textarea
                  v-model="editorContent"
                  placeholder='{"op": "CREATE", "type": "node", "label": "person", ...}'
                  class="min-h-[300px] resize-y rounded-none border-0 font-mono text-xs leading-6 focus-visible:ring-0 focus-visible:ring-offset-0"
                  spellcheck="false"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- Action bar -->
        <div class="flex items-center gap-3">
          <Button
            :disabled="submitting || !editorContent.trim()"
            @click="handleSubmit"
          >
            <Loader2 v-if="submitting" class="mr-2 size-4 animate-spin" />
            <Play v-else class="mr-2 size-4" />
            Apply Mutations
          </Button>
          <span v-if="lineCount > 0" class="text-sm text-muted-foreground">
            {{ lineCount }} operation{{ lineCount === 1 ? '' : 's' }} ready
          </span>
        </div>

        <!-- Validation errors -->
        <Alert v-if="validationErrors.length > 0" variant="destructive">
          <AlertTriangle class="size-4" />
          <AlertTitle>Validation Errors</AlertTitle>
          <AlertDescription>
            <ul class="mt-1 list-inside list-disc space-y-0.5 text-sm">
              <li v-for="(error, idx) in validationErrors" :key="idx">{{ error }}</li>
            </ul>
          </AlertDescription>
        </Alert>

        <!-- Result display -->
        <template v-if="lastResult">
          <Alert v-if="lastResult.success" variant="default" class="border-green-500/50 bg-green-50 dark:bg-green-950/20">
            <CheckCircle2 class="size-4 text-green-600" />
            <AlertTitle class="text-green-700 dark:text-green-400">Mutations Applied</AlertTitle>
            <AlertDescription class="text-green-600 dark:text-green-400">
              Successfully applied {{ lastResult.operations_applied }} operation{{ lastResult.operations_applied === 1 ? '' : 's' }}.
            </AlertDescription>
          </Alert>

          <Alert v-else variant="destructive">
            <XCircle class="size-4" />
            <AlertTitle>Mutations Failed</AlertTitle>
            <AlertDescription>
              <p>{{ lastResult.operations_applied }} operation{{ lastResult.operations_applied === 1 ? '' : 's' }} applied before failure.</p>
              <ul v-if="lastResult.errors.length > 0" class="mt-2 list-inside list-disc space-y-0.5 text-sm">
                <li v-for="(error, idx) in lastResult.errors" :key="idx">{{ error }}</li>
              </ul>
            </AlertDescription>
          </Alert>
        </template>
      </div>

      <!-- Right: Templates sidebar -->
      <div class="space-y-3">
        <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <Plus class="size-4" />
          Templates
        </h2>

        <div class="space-y-2">
          <Card
            v-for="template in templates"
            :key="template.name"
            class="cursor-pointer transition-colors hover:bg-accent/50"
            @click="insertTemplate(template)"
          >
            <CardContent class="p-3">
              <div class="space-y-1">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium">{{ template.name }}</span>
                  <Plus class="size-3.5 text-muted-foreground" />
                </div>
                <p class="text-xs text-muted-foreground">{{ template.description }}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <Separator />

        <div class="space-y-2 text-xs text-muted-foreground">
          <p class="font-medium">JSONL Format</p>
          <p>Each line must be a valid JSON object representing a single mutation operation.</p>
          <p>Required field: <code class="rounded bg-muted px-1 py-0.5">op</code> — one of <code class="rounded bg-muted px-1 py-0.5">DEFINE</code>, <code class="rounded bg-muted px-1 py-0.5">CREATE</code>, <code class="rounded bg-muted px-1 py-0.5">UPDATE</code>, <code class="rounded bg-muted px-1 py-0.5">DELETE</code></p>
          <p>Other fields: <code class="rounded bg-muted px-1 py-0.5">type</code> (node/edge), <code class="rounded bg-muted px-1 py-0.5">label</code>, <code class="rounded bg-muted px-1 py-0.5">id</code>, <code class="rounded bg-muted px-1 py-0.5">set_properties</code></p>
          <p>ID format: <code class="rounded bg-muted px-1 py-0.5">label:16hexchars</code> (lowercase)</p>
        </div>
      </div>
    </div>
  </div>
</template>
