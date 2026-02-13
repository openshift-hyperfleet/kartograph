<script setup lang="ts">
import { ref } from 'vue'
import { toast } from 'vue-sonner'
import {
  Plus, Copy, Dices, HelpCircle,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from '@/components/ui/tooltip'
import { generateHexId } from '@/utils/mutationParser'

// ── Types ──────────────────────────────────────────────────────────────────

interface FieldInfo {
  name: string
  required: boolean
  description: string
}

interface MutationTemplate {
  name: string
  description: string
  content: string
  fields: FieldInfo[]
}

// ── Events ─────────────────────────────────────────────────────────────────

const emit = defineEmits<{
  insert: [content: string]
}>()

// ── Templates ──────────────────────────────────────────────────────────────

const templates: MutationTemplate[] = [
  {
    name: 'Define Type',
    description: 'Define a new node or edge type schema',
    content: '{"op": "DEFINE", "type": "node", "label": "person", "description": "A person entity", "required_properties": ["name"], "optional_properties": ["email", "age"]}',
    fields: [
      { name: 'op', required: true, description: 'Always "DEFINE"' },
      { name: 'type', required: true, description: '"node" or "edge"' },
      { name: 'label', required: true, description: 'Type name (e.g. "person")' },
      { name: 'description', required: false, description: 'Human-readable description' },
      { name: 'required_properties', required: false, description: 'Array of required property names' },
      { name: 'optional_properties', required: false, description: 'Array of optional property names' },
    ],
  },
  {
    name: 'Create Node',
    description: 'Create a new node instance',
    content: '{"op": "CREATE", "type": "node", "label": "person", "id": "person:a1b2c3d4e5f67890", "set_properties": {"name": "Alice", "slug": "alice", "data_source_id": "dev-ui", "source_path": "manual"}}',
    fields: [
      { name: 'op', required: true, description: 'Always "CREATE"' },
      { name: 'type', required: true, description: '"node"' },
      { name: 'label', required: true, description: 'Type name (e.g. "person")' },
      { name: 'id', required: true, description: 'Format: label:16hexchars' },
      { name: 'set_properties', required: true, description: 'Object with properties to set' },
      { name: 'slug', required: true, description: 'Required in set_properties for nodes' },
      { name: 'data_source_id', required: true, description: 'Required in set_properties' },
      { name: 'source_path', required: true, description: 'Required in set_properties' },
    ],
  },
  {
    name: 'Create Edge',
    description: 'Create a relationship between nodes',
    content: '{"op": "CREATE", "type": "edge", "label": "knows", "id": "knows:a1b2c3d4e5f67890", "start_id": "person:a1b2c3d4e5f67890", "end_id": "person:f6e5d4c3b2a10987", "set_properties": {"data_source_id": "dev-ui", "source_path": "manual"}}',
    fields: [
      { name: 'op', required: true, description: 'Always "CREATE"' },
      { name: 'type', required: true, description: '"edge"' },
      { name: 'label', required: true, description: 'Relationship type (e.g. "knows")' },
      { name: 'id', required: true, description: 'Format: label:16hexchars' },
      { name: 'start_id', required: true, description: 'Source node ID (same format)' },
      { name: 'end_id', required: true, description: 'Target node ID (same format)' },
      { name: 'data_source_id', required: true, description: 'Required in set_properties' },
      { name: 'source_path', required: true, description: 'Required in set_properties' },
    ],
  },
  {
    name: 'Update Node',
    description: 'Update properties on an existing node',
    content: '{"op": "UPDATE", "type": "node", "id": "person:a1b2c3d4e5f67890", "set_properties": {"email": "alice@example.com"}}',
    fields: [
      { name: 'op', required: true, description: 'Always "UPDATE"' },
      { name: 'type', required: true, description: '"node" or "edge"' },
      { name: 'id', required: true, description: 'Format: label:16hexchars' },
      { name: 'set_properties', required: false, description: 'Properties to set/update' },
      { name: 'remove_properties', required: false, description: 'Property names to remove' },
    ],
  },
  {
    name: 'Delete Node',
    description: 'Remove a node from the graph',
    content: '{"op": "DELETE", "type": "node", "id": "person:a1b2c3d4e5f67890"}',
    fields: [
      { name: 'op', required: true, description: 'Always "DELETE"' },
      { name: 'type', required: true, description: '"node" or "edge"' },
      { name: 'id', required: true, description: 'Format: label:16hexchars' },
    ],
  },
]

// ── State ──────────────────────────────────────────────────────────────────

const expandedTemplate = ref<string | null>(null)

function toggleFieldHelp(name: string) {
  expandedTemplate.value = expandedTemplate.value === name ? null : name
}

function handleInsert(template: MutationTemplate) {
  emit('insert', template.content)
}

function copyGeneratedId() {
  const hex = generateHexId()
  const id = `label:${hex}`
  navigator.clipboard.writeText(id).then(() => {
    toast.success('Copied to clipboard', { description: id })
  }).catch(() => {
    toast.info('Generated ID', { description: id })
  })
}
</script>

<template>
  <div class="space-y-3">
    <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
      <Plus class="size-4" />
      Templates
    </h2>

    <div class="space-y-2">
      <Card
        v-for="template in templates"
        :key="template.name"
      >
        <CardContent class="p-3">
          <div class="space-y-2">
            <div
              class="flex cursor-pointer items-center justify-between"
              @click="handleInsert(template)"
            >
              <span class="text-sm font-medium">{{ template.name }}</span>
              <Plus class="size-3.5 text-muted-foreground" />
            </div>
            <p class="text-xs text-muted-foreground">{{ template.description }}</p>

            <!-- Field help toggle -->
            <button
              class="flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
              @click.stop="toggleFieldHelp(template.name)"
            >
              <HelpCircle class="size-3" />
              {{ expandedTemplate === template.name ? 'Hide' : 'Show' }} fields
            </button>

            <!-- Field details -->
            <div
              v-if="expandedTemplate === template.name"
              class="space-y-0.5 border-l-2 border-muted pl-2"
            >
              <div
                v-for="field in template.fields"
                :key="field.name"
                class="flex items-baseline gap-1.5 text-[11px]"
              >
                <code class="rounded bg-muted px-1 py-0.5 font-mono">{{ field.name }}</code>
                <Badge
                  :variant="field.required ? 'default' : 'outline'"
                  class="h-4 text-[9px]"
                >
                  {{ field.required ? 'req' : 'opt' }}
                </Badge>
                <span class="text-muted-foreground">{{ field.description }}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <Separator />

    <!-- Generate ID helper -->
    <div class="space-y-2">
      <p class="text-xs font-medium text-muted-foreground">ID Helper</p>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button
            variant="outline"
            size="sm"
            class="w-full gap-2"
            @click="copyGeneratedId"
          >
            <Dices class="size-3.5" />
            Generate ID
            <Copy class="ml-auto size-3" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>Generate a random label:16hexchars ID and copy to clipboard</p>
        </TooltipContent>
      </Tooltip>
      <p class="text-[11px] text-muted-foreground">
        IDs must match the pattern <code class="rounded bg-muted px-1 py-0.5 font-mono">label:16hexchars</code>
      </p>
      <p class="text-[11px] text-muted-foreground">
        Example: <code class="rounded bg-muted px-1 py-0.5 font-mono">person:a1b2c3d4e5f67890</code>
      </p>
    </div>

    <Separator />

    <div class="space-y-2 text-xs text-muted-foreground">
      <p class="font-medium">JSONL Format</p>
      <p>Each line must be a valid JSON object representing a single mutation operation. You can also paste a JSON array.</p>
      <p>Required field: <code class="rounded bg-muted px-1 py-0.5">op</code> — one of <code class="rounded bg-muted px-1 py-0.5">DEFINE</code>, <code class="rounded bg-muted px-1 py-0.5">CREATE</code>, <code class="rounded bg-muted px-1 py-0.5">UPDATE</code>, <code class="rounded bg-muted px-1 py-0.5">DELETE</code></p>
      <p>Other fields: <code class="rounded bg-muted px-1 py-0.5">type</code> (node/edge), <code class="rounded bg-muted px-1 py-0.5">label</code>, <code class="rounded bg-muted px-1 py-0.5">id</code>, <code class="rounded bg-muted px-1 py-0.5">set_properties</code></p>
      <p>ID format: <code class="rounded bg-muted px-1 py-0.5">label:16hexchars</code> (lowercase hex, exactly 16 chars)</p>
    </div>
  </div>
</template>
