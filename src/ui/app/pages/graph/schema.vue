<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import { Database, Search, Loader2, Info, ChevronRight } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog'
import type { TypeDefinition } from '~/types'

const { listNodeLabels, listEdgeLabels, getNodeSchema, getEdgeSchema } = useGraphApi()

// ── State ──────────────────────────────────────────────────────────────────

const activeTab = ref('nodes')

// Node types
const nodeLabels = ref<string[]>([])
const nodeCount = ref(0)
const nodeSearch = ref('')
const nodeLabelsLoading = ref(false)

// Edge types
const edgeLabels = ref<string[]>([])
const edgeCount = ref(0)
const edgeSearch = ref('')
const edgeLabelsLoading = ref(false)

// Selected type detail (shown in dialog)
const selectedType = ref<TypeDefinition | null>(null)
const selectedLabel = ref<string | null>(null)
const typeLoading = ref(false)
const detailDialogOpen = ref(false)

// ── Data loading ───────────────────────────────────────────────────────────

let nodeSearchDebounce: ReturnType<typeof setTimeout> | null = null
let edgeSearchDebounce: ReturnType<typeof setTimeout> | null = null

async function fetchNodeLabels() {
  nodeLabelsLoading.value = true
  try {
    const result = await listNodeLabels(nodeSearch.value || undefined)
    nodeLabels.value = result.labels
    nodeCount.value = result.count
  } catch (err) {
    toast.error('Failed to load node types', {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
  } finally {
    nodeLabelsLoading.value = false
  }
}

async function fetchEdgeLabels() {
  edgeLabelsLoading.value = true
  try {
    const result = await listEdgeLabels(edgeSearch.value || undefined)
    edgeLabels.value = result.labels
    edgeCount.value = result.count
  } catch (err) {
    toast.error('Failed to load edge types', {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
  } finally {
    edgeLabelsLoading.value = false
  }
}

function onNodeSearchInput() {
  if (nodeSearchDebounce) clearTimeout(nodeSearchDebounce)
  nodeSearchDebounce = setTimeout(fetchNodeLabels, 300)
}

function onEdgeSearchInput() {
  if (edgeSearchDebounce) clearTimeout(edgeSearchDebounce)
  edgeSearchDebounce = setTimeout(fetchEdgeLabels, 300)
}

async function selectNodeType(label: string) {
  selectedLabel.value = label
  selectedType.value = null
  typeLoading.value = true
  detailDialogOpen.value = true
  try {
    selectedType.value = await getNodeSchema(label)
  } catch (err) {
    toast.error(`Failed to load schema for "${label}"`, {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
    selectedLabel.value = null
    detailDialogOpen.value = false
  } finally {
    typeLoading.value = false
  }
}

async function selectEdgeType(label: string) {
  selectedLabel.value = label
  selectedType.value = null
  typeLoading.value = true
  detailDialogOpen.value = true
  try {
    selectedType.value = await getEdgeSchema(label)
  } catch (err) {
    toast.error(`Failed to load schema for "${label}"`, {
      description: err instanceof Error ? err.message : 'Unknown error',
    })
    selectedLabel.value = null
    detailDialogOpen.value = false
  } finally {
    typeLoading.value = false
  }
}

function onDialogClose(open: boolean) {
  if (!open) {
    selectedLabel.value = null
    selectedType.value = null
    detailDialogOpen.value = false
  }
}

function onTabChange() {
  selectedLabel.value = null
  selectedType.value = null
  detailDialogOpen.value = false
}

onMounted(() => {
  fetchNodeLabels()
  fetchEdgeLabels()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <Database class="size-6 text-muted-foreground" />
      <h1 class="text-2xl font-bold tracking-tight">Schema Browser</h1>
    </div>
    <p class="text-muted-foreground">Browse and inspect the knowledge graph schema definitions.</p>

    <!-- Type list -->
    <Tabs v-model="activeTab" @update:model-value="onTabChange">
      <TabsList class="w-full">
        <TabsTrigger value="nodes" class="flex-1">
          Node Types
          <Badge variant="secondary" class="ml-2">{{ nodeCount }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="edges" class="flex-1">
          Edge Types
          <Badge variant="secondary" class="ml-2">{{ edgeCount }}</Badge>
        </TabsTrigger>
      </TabsList>

      <!-- Node Types Tab -->
      <TabsContent value="nodes" class="mt-4 space-y-3">
        <div class="relative">
          <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            v-model="nodeSearch"
            placeholder="Filter node types..."
            class="pl-9"
            @input="onNodeSearchInput"
          />
        </div>

        <p v-if="nodeSearch && !nodeLabelsLoading" class="text-sm text-muted-foreground">
          Showing {{ nodeLabels.length }} matching of {{ nodeCount }} node types
        </p>

        <!-- Loading -->
        <div v-if="nodeLabelsLoading" class="flex items-center justify-center gap-2 py-8 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading node types...
        </div>

        <!-- Empty -->
        <Card v-else-if="nodeLabels.length === 0">
          <CardContent class="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
            <Info class="size-8" />
            <p class="font-medium">No node types defined</p>
            <p class="text-sm">Use the Mutations console to define node type schemas.</p>
          </CardContent>
        </Card>

        <!-- Label list -->
        <div v-else class="max-h-[calc(100vh-12rem)] space-y-1 overflow-y-auto">
          <button
            v-for="label in nodeLabels"
            :key="label"
            class="flex w-full items-center justify-between rounded-md border px-4 py-3 text-left text-sm transition-colors hover:bg-accent"
            @click="selectNodeType(label)"
          >
            <div class="flex items-center gap-2">
              <Badge variant="default">Node</Badge>
              <span class="font-medium">{{ label }}</span>
            </div>
            <ChevronRight class="size-4 text-muted-foreground" />
          </button>
        </div>
      </TabsContent>

      <!-- Edge Types Tab -->
      <TabsContent value="edges" class="mt-4 space-y-3">
        <div class="relative">
          <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            v-model="edgeSearch"
            placeholder="Filter edge types..."
            class="pl-9"
            @input="onEdgeSearchInput"
          />
        </div>

        <p v-if="edgeSearch && !edgeLabelsLoading" class="text-sm text-muted-foreground">
          Showing {{ edgeLabels.length }} matching of {{ edgeCount }} edge types
        </p>

        <!-- Loading -->
        <div v-if="edgeLabelsLoading" class="flex items-center justify-center gap-2 py-8 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading edge types...
        </div>

        <!-- Empty -->
        <Card v-else-if="edgeLabels.length === 0">
          <CardContent class="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
            <Info class="size-8" />
            <p class="font-medium">No edge types defined</p>
            <p class="text-sm">Use the Mutations console to define edge type schemas.</p>
          </CardContent>
        </Card>

        <!-- Label list -->
        <div v-else class="max-h-[calc(100vh-12rem)] space-y-1 overflow-y-auto">
          <button
            v-for="label in edgeLabels"
            :key="label"
            class="flex w-full items-center justify-between rounded-md border px-4 py-3 text-left text-sm transition-colors hover:bg-accent"
            @click="selectEdgeType(label)"
          >
            <div class="flex items-center gap-2">
              <Badge variant="outline">Edge</Badge>
              <span class="font-medium">{{ label }}</span>
            </div>
            <ChevronRight class="size-4 text-muted-foreground" />
          </button>
        </div>
      </TabsContent>
    </Tabs>

    <!-- Type detail dialog -->
    <Dialog :open="detailDialogOpen" @update:open="onDialogClose">
      <DialogContent class="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <!-- Loading detail -->
        <div v-if="typeLoading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading schema...
        </div>

        <!-- Detail view -->
        <template v-else-if="selectedType">
          <DialogHeader>
            <div class="flex items-center gap-2">
              <Badge :variant="selectedType.entity_type === 'node' ? 'default' : 'outline'">
                {{ selectedType.entity_type }}
              </Badge>
              <DialogTitle class="text-xl">{{ selectedType.label }}</DialogTitle>
            </div>
            <DialogDescription v-if="selectedType.description">
              {{ selectedType.description }}
            </DialogDescription>
          </DialogHeader>

          <div class="space-y-6">
            <!-- Required properties -->
            <div>
              <h3 class="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Required Properties
              </h3>
              <div v-if="selectedType.required_properties.length === 0" class="text-sm text-muted-foreground">
                No required properties.
              </div>
              <div v-else class="space-y-2">
                <div
                  v-for="prop in selectedType.required_properties"
                  :key="prop"
                  class="flex items-center gap-2 rounded-md border bg-muted/50 px-3 py-2"
                >
                  <span class="font-mono text-sm">{{ prop }}</span>
                  <Badge variant="default" class="ml-auto text-[10px]">Required</Badge>
                </div>
              </div>
            </div>

            <Separator />

            <!-- Optional properties -->
            <div>
              <h3 class="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Optional Properties
              </h3>
              <div v-if="selectedType.optional_properties.length === 0" class="text-sm text-muted-foreground">
                No optional properties.
              </div>
              <div v-else class="space-y-2">
                <div
                  v-for="prop in selectedType.optional_properties"
                  :key="prop"
                  class="flex items-center gap-2 rounded-md border px-3 py-2"
                >
                  <span class="font-mono text-sm">{{ prop }}</span>
                  <Badge variant="secondary" class="ml-auto text-[10px]">Optional</Badge>
                </div>
              </div>
            </div>
          </div>
        </template>
      </DialogContent>
    </Dialog>
  </div>
</template>
