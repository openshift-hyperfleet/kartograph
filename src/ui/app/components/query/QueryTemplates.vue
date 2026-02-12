<script setup lang="ts">
import { ref, reactive } from 'vue'
import {
  Sparkles, ChevronDown, ChevronRight, Play,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'

const props = defineProps<{
  nodeLabels: string[]
  edgeLabels: string[]
}>()

const emit = defineEmits<{
  'select-query': [query: string]
}>()

const isOpen = ref(true)
const expandedTemplate = ref<string | null>(null)

interface TemplateParam {
  key: string
  label: string
  type: 'text' | 'number' | 'label-select' | 'edge-select'
  default: string
}

interface QueryTemplate {
  id: string
  name: string
  description: string
  template: string
  params: TemplateParam[]
}

const templates: QueryTemplate[] = [
  {
    id: 'all-nodes',
    name: 'All Nodes',
    description: 'Retrieve all nodes with a limit',
    template: 'MATCH (n) RETURN n LIMIT {{limit}}',
    params: [
      { key: 'limit', label: 'Limit', type: 'number', default: '25' },
    ],
  },
  {
    id: 'by-label',
    name: 'Find by Label',
    description: 'Find all nodes of a specific type',
    template: 'MATCH (n:{{label}}) RETURN n LIMIT {{limit}}',
    params: [
      { key: 'label', label: 'Node Label', type: 'label-select', default: '' },
      { key: 'limit', label: 'Limit', type: 'number', default: '25' },
    ],
  },
  {
    id: 'by-property',
    name: 'Find by Property',
    description: 'Find nodes matching a property value',
    template: "MATCH (n:{{label}}) WHERE n.{{property}} = '{{value}}' RETURN n LIMIT {{limit}}",
    params: [
      { key: 'label', label: 'Node Label', type: 'label-select', default: '' },
      { key: 'property', label: 'Property', type: 'text', default: 'name' },
      { key: 'value', label: 'Value', type: 'text', default: '' },
      { key: 'limit', label: 'Limit', type: 'number', default: '25' },
    ],
  },
  {
    id: 'count-labels',
    name: 'Count by Label',
    description: 'Count nodes grouped by their label',
    template: 'MATCH (n) WITH labels(n) AS label, count(*) AS cnt RETURN {label: label, count: cnt}',
    params: [],
  },
  {
    id: 'relationships',
    name: 'Find Relationships',
    description: 'Find relationships between node types',
    template: 'MATCH (a:{{sourceLabel}})-[r:{{edgeType}}]->(b) RETURN {source: a, rel: type(r), target: b} LIMIT {{limit}}',
    params: [
      { key: 'sourceLabel', label: 'Source Label', type: 'label-select', default: '' },
      { key: 'edgeType', label: 'Edge Type', type: 'edge-select', default: '' },
      { key: 'limit', label: 'Limit', type: 'number', default: '25' },
    ],
  },
  {
    id: 'connected',
    name: 'Find Connected Nodes',
    description: 'Find all nodes connected to a specific node by slug',
    template: "MATCH (a)-[r]->(b) WHERE a.slug = '{{slug}}' RETURN {source: a, rel: type(r), target: b} LIMIT {{limit}}",
    params: [
      { key: 'slug', label: 'Node Slug', type: 'text', default: '' },
      { key: 'limit', label: 'Limit', type: 'number', default: '25' },
    ],
  },
  {
    id: 'nodes-with-slugs',
    name: 'Nodes with Slugs',
    description: 'Find all nodes that have a slug property',
    template: 'MATCH (n) WHERE n.slug IS NOT NULL RETURN {slug: n.slug, labels: labels(n)} LIMIT {{limit}}',
    params: [
      { key: 'limit', label: 'Limit', type: 'number', default: '50' },
    ],
  },
]

// Store parameter values per template
const paramValues = reactive<Record<string, Record<string, string>>>({})

function getParamValue(templateId: string, paramKey: string, defaultVal: string): string {
  if (!paramValues[templateId]) paramValues[templateId] = {}
  if (paramValues[templateId][paramKey] === undefined) {
    paramValues[templateId][paramKey] = defaultVal
  }
  return paramValues[templateId][paramKey]
}

function setParamValue(templateId: string, paramKey: string, value: string) {
  if (!paramValues[templateId]) paramValues[templateId] = {}
  paramValues[templateId][paramKey] = value
}

function toggleTemplate(id: string) {
  expandedTemplate.value = expandedTemplate.value === id ? null : id
}

function generateQuery(template: QueryTemplate): string {
  let query = template.template
  for (const param of template.params) {
    const value = getParamValue(template.id, param.key, param.default)
    query = query.replace(`{{${param.key}}}`, value || param.default || `<${param.key}>`)
  }
  return query
}

function useTemplate(template: QueryTemplate) {
  emit('select-query', generateQuery(template))
}
</script>

<template>
  <Card class="flex flex-col">
    <CardHeader
      class="cursor-pointer pb-3"
      @click="isOpen = !isOpen"
    >
      <div class="flex items-center justify-between">
        <CardTitle class="flex items-center gap-1.5 text-sm font-medium">
          <Sparkles class="size-3.5" />
          Query Templates
        </CardTitle>
        <div class="flex items-center gap-1">
          <Badge variant="secondary" class="h-4 px-1 text-[10px]">
            {{ templates.length }}
          </Badge>
          <ChevronDown v-if="isOpen" class="size-4 text-muted-foreground" />
          <ChevronRight v-else class="size-4 text-muted-foreground" />
        </div>
      </div>
    </CardHeader>

    <CardContent v-if="isOpen" class="max-h-[32rem] overflow-y-auto pt-0">
      <div class="space-y-2">
        <div
          v-for="template in templates"
          :key="template.id"
          class="rounded-md border transition-colors"
          :class="expandedTemplate === template.id ? 'border-ring' : 'hover:border-muted-foreground/30'"
        >
          <!-- Template header -->
          <button
            class="flex w-full items-center justify-between px-3 py-2 text-left"
            @click="template.params.length > 0 ? toggleTemplate(template.id) : useTemplate(template)"
          >
            <div class="min-w-0">
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-medium">{{ template.name }}</span>
                <Badge
                  v-if="template.params.length === 0"
                  variant="secondary"
                  class="h-4 px-1 text-[9px]"
                >
                  Quick
                </Badge>
              </div>
              <p class="truncate text-[10px] text-muted-foreground">
                {{ template.description }}
              </p>
            </div>
            <div v-if="template.params.length > 0" class="ml-2 shrink-0">
              <ChevronDown
                v-if="expandedTemplate === template.id"
                class="size-3.5 text-muted-foreground"
              />
              <ChevronRight v-else class="size-3.5 text-muted-foreground" />
            </div>
          </button>

          <!-- Expanded parameters -->
          <div
            v-if="expandedTemplate === template.id && template.params.length > 0"
            class="border-t px-3 py-2"
          >
            <div class="space-y-2">
              <div
                v-for="param in template.params"
                :key="param.key"
                class="space-y-1"
              >
                <Label class="text-[11px]">{{ param.label }}</Label>

                <!-- Label select -->
                <Select
                  v-if="param.type === 'label-select'"
                  :key="`${template.id}-${param.key}-${props.nodeLabels.length}`"
                  :model-value="getParamValue(template.id, param.key, param.default) || undefined"
                  @update:model-value="(v: string) => setParamValue(template.id, param.key, v)"
                >
                  <SelectTrigger class="h-7 text-xs">
                    <SelectValue placeholder="Select label..." />
                  </SelectTrigger>
                  <SelectContent>
                    <div v-if="props.nodeLabels.length === 0" class="px-2 py-1.5 text-xs text-muted-foreground">
                      Loading labels...
                    </div>
                    <SelectItem
                      v-for="lbl in props.nodeLabels"
                      :key="lbl"
                      :value="lbl"
                    >
                      {{ lbl }}
                    </SelectItem>
                  </SelectContent>
                </Select>

                <!-- Edge select -->
                <Select
                  v-else-if="param.type === 'edge-select'"
                  :key="`${template.id}-${param.key}-${props.edgeLabels.length}`"
                  :model-value="getParamValue(template.id, param.key, param.default) || undefined"
                  @update:model-value="(v: string) => setParamValue(template.id, param.key, v)"
                >
                  <SelectTrigger class="h-7 text-xs">
                    <SelectValue placeholder="Select edge type..." />
                  </SelectTrigger>
                  <SelectContent>
                    <div v-if="props.edgeLabels.length === 0" class="px-2 py-1.5 text-xs text-muted-foreground">
                      Loading edge types...
                    </div>
                    <SelectItem
                      v-for="lbl in props.edgeLabels"
                      :key="lbl"
                      :value="lbl"
                    >
                      {{ lbl }}
                    </SelectItem>
                  </SelectContent>
                </Select>

                <!-- Number input -->
                <Input
                  v-else-if="param.type === 'number'"
                  type="number"
                  class="h-7 text-xs"
                  :model-value="getParamValue(template.id, param.key, param.default)"
                  @update:model-value="(v: string | number) => setParamValue(template.id, param.key, String(v))"
                />

                <!-- Text input -->
                <Input
                  v-else
                  class="h-7 text-xs"
                  :placeholder="param.default || `Enter ${param.label.toLowerCase()}...`"
                  :model-value="getParamValue(template.id, param.key, param.default)"
                  @update:model-value="(v: string | number) => setParamValue(template.id, param.key, String(v))"
                />
              </div>
            </div>

            <!-- Preview + Use button -->
            <div class="mt-3 space-y-2">
              <div class="rounded bg-muted p-2">
                <code class="break-all font-mono text-[10px] text-foreground">
                  {{ generateQuery(template) }}
                </code>
              </div>
              <Button
                size="sm"
                class="h-7 w-full text-xs"
                @click="useTemplate(template)"
              >
                <Play class="mr-1.5 size-3" />
                Use Query
              </Button>
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
