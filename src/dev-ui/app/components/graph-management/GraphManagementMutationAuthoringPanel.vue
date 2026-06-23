<script setup lang="ts">
import { ref } from 'vue'
import { toast } from 'vue-sonner'
import {
  BookOpen,
  GitBranch,
  Loader2,
  PencilRuler,
  Play,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import MutationTemplates from '@/components/graph/MutationTemplates.vue'
import { useGraphApi } from '@/composables/api/useGraphApi'
import { generateHexId } from '@/utils/mutationParser'
import { getMergedEditorContent } from '@/utils/mutationConsole'

const props = defineProps<{
  kgId: string
}>()

const emit = defineEmits<{
  applied: []
}>()

const graphApi = useGraphApi()
const jsonlContent = ref('')
const applying = ref(false)
const applyError = ref<string | null>(null)

const quickStartTemplates = [
  {
    name: 'Create a Node',
    description: 'Define a type and create a node',
    icon: Plus,
    content: () => [
      '{"op": "DEFINE", "type": "node", "label": "person", "description": "A person entity", "required_properties": ["name"]}',
      `{"op": "CREATE", "type": "node", "label": "person", "id": "person:${generateHexId()}", "set_properties": {"name": "Alice", "slug": "alice", "data_source_id": "dev-ui", "source_path": "manual"}}`,
    ].join('\n'),
  },
  {
    name: 'Create an Edge',
    description: 'Define a relationship and connect nodes',
    icon: GitBranch,
    content: () => [
      '{"op": "DEFINE", "type": "edge", "label": "knows", "description": "Two entities know each other", "required_properties": []}',
      `{"op": "CREATE", "type": "edge", "label": "knows", "id": "knows:${generateHexId()}", "start_id": "person:a1b2c3d4e5f67890", "end_id": "person:f6e5d4c3b2a10987", "set_properties": {"data_source_id": "dev-ui", "source_path": "manual"}}`,
    ].join('\n'),
  },
  {
    name: 'Update Properties',
    description: 'Modify properties on an existing entity',
    icon: RefreshCw,
    content: () =>
      '{"op": "UPDATE", "type": "node", "id": "person:a1b2c3d4e5f67890", "set_properties": {"email": "alice@example.com"}}',
  },
  {
    name: 'Delete an Entity',
    description: 'Remove a node or edge from the graph',
    icon: Trash2,
    content: () => '{"op": "DELETE", "type": "node", "id": "person:a1b2c3d4e5f67890"}',
  },
] as const

function insertTemplate(content: string) {
  jsonlContent.value = getMergedEditorContent(jsonlContent.value, content)
  applyError.value = null
}

function clearEditor() {
  jsonlContent.value = ''
  applyError.value = null
}

async function applyMutations() {
  const body = jsonlContent.value.trim()
  if (!body) {
    applyError.value = 'Add one or more JSONL mutation operations first.'
    return
  }

  applying.value = true
  applyError.value = null
  try {
    await graphApi.applyMutations(props.kgId, body)
    toast.success('Mutations applied')
    jsonlContent.value = ''
    emit('applied')
  } catch (err) {
    applyError.value = err instanceof Error ? err.message : 'Failed to apply mutations'
    toast.error('Failed to apply mutations', { description: applyError.value })
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle class="flex items-center gap-2 text-base">
        <PencilRuler class="size-4" />
        Mutation Authoring
      </CardTitle>
      <CardDescription>
        Compose JSONL mutations yourself — independent from the assistant chat above. Use templates
        to populate the editor, then apply directly to this knowledge graph.
      </CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <button
          v-for="template in quickStartTemplates"
          :key="template.name"
          type="button"
          class="rounded-lg border bg-card p-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          @click="insertTemplate(template.content())"
        >
          <div class="flex items-center gap-2">
            <component :is="template.icon" class="size-4 shrink-0 text-primary" />
            <span class="text-sm font-medium">{{ template.name }}</span>
          </div>
          <p class="mt-1 text-xs text-muted-foreground">{{ template.description }}</p>
        </button>
      </div>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_17.5rem]">
        <div class="space-y-3 rounded-lg border bg-muted/20 p-3">
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              JSONL editor
            </p>
            <Button
              size="sm"
              variant="ghost"
              class="h-7 px-2 text-xs"
              :disabled="!jsonlContent.trim() || applying"
              @click="clearEditor"
            >
              <Trash2 class="mr-1 size-3" />
              Clear
            </Button>
          </div>
          <textarea
            v-model="jsonlContent"
            class="min-h-56 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder='{"op":"UPDATE","type":"node","id":"adapter:abc123","set_properties":{"transport":"maestro"}}'
          />
          <div class="flex flex-wrap items-center gap-2">
            <Button size="sm" :disabled="applying || !jsonlContent.trim()" @click="applyMutations">
              <Loader2 v-if="applying" class="mr-1.5 size-3.5 animate-spin" />
              <Play v-else class="mr-1.5 size-3.5" />
              Apply mutations
            </Button>
            <span class="text-xs text-muted-foreground">
              Applies immediately — not tracked in the assistant session journal.
            </span>
          </div>
          <p v-if="applyError" class="text-xs text-destructive">
            {{ applyError }}
          </p>
        </div>

        <div class="rounded-lg border bg-card p-3">
          <p class="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <BookOpen class="size-3.5" />
            Templates
          </p>
          <div class="max-h-[min(28rem,60dvh)] overflow-y-auto overscroll-contain pr-1">
            <MutationTemplates @insert="insertTemplate" />
          </div>
        </div>
      </div>

      <Separator />

      <p class="text-xs text-muted-foreground">
        Tip: click any template to append its JSONL into the editor. Fresh IDs are generated for
        create operations each time you insert.
      </p>
    </CardContent>
  </Card>
</template>
