<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  BookOpen,
  Plus,
  Building2,
  Loader2,
  ArrowRight,
  Search,
  Cable,
  Database,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

const { hasTenant, currentTenantName, tenantVersion } = useTenant()
const { extractErrorMessage } = useErrorHandler()

// ── Types ──────────────────────────────────────────────────────────────────

interface KnowledgeGraphItem {
  id: string
  name: string
  description?: string
  created_at?: string
}

// ── State ──────────────────────────────────────────────────────────────────

// Knowledge graph list
const knowledgeGraphs = ref<KnowledgeGraphItem[]>([])
const loadingKgs = ref(false)

// Create dialog
const createDialogOpen = ref(false)
const createName = ref('')
const createDescription = ref('')
const creating = ref(false)
const createNameError = ref('')

// ── Actions ────────────────────────────────────────────────────────────────

async function loadKnowledgeGraphs() {
  if (!hasTenant.value) return
  loadingKgs.value = true
  try {
    const { apiFetch } = useApiClient()
    const result = await apiFetch<{ knowledge_graphs: KnowledgeGraphItem[] }>(
      '/management/knowledge-graphs'
    )
    knowledgeGraphs.value = result.knowledge_graphs ?? []
  } catch {
    knowledgeGraphs.value = []
  } finally {
    loadingKgs.value = false
  }
}

function openCreateDialog() {
  createName.value = ''
  createDescription.value = ''
  createNameError.value = ''
  createDialogOpen.value = true
}

async function handleCreate() {
  createNameError.value = ''
  if (!createName.value.trim()) {
    createNameError.value = 'Knowledge graph name is required'
    return
  }
  creating.value = true
  try {
    const { apiFetch } = useApiClient()
    await apiFetch('/management/knowledge-graphs', {
      method: 'POST',
      body: {
        name: createName.value.trim(),
        description: createDescription.value.trim() || undefined,
      },
    })
    toast.success(`Knowledge graph "${createName.value.trim()}" created`, {
      description: 'Next: connect a data source to start populating your graph.',
      action: {
        label: 'Add Data Source',
        onClick: () => navigateTo('/data-sources'),
      },
      duration: 8000,
    })
    createDialogOpen.value = false
    await loadKnowledgeGraphs()
  } catch (err) {
    toast.error('Failed to create knowledge graph', {
      description: extractErrorMessage(err),
    })
  } finally {
    creating.value = false
  }
}

// ── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(() => {
  loadKnowledgeGraphs()
})

watch(tenantVersion, () => {
  loadKnowledgeGraphs()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="rounded-lg bg-primary/10 p-2">
          <BookOpen class="size-5 text-primary" />
        </div>
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Knowledge Graphs</h1>
          <p class="text-sm text-muted-foreground">
            Create and manage knowledge graphs that map your data sources into structured graphs
          </p>
        </div>
      </div>
      <Button :disabled="!hasTenant" @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Create Knowledge Graph
      </Button>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view knowledge graphs.</p>
    </div>

    <template v-else>
      <!-- Loading state -->
      <div v-if="loadingKgs" class="flex items-center justify-center py-16">
        <Loader2 class="size-6 animate-spin text-muted-foreground" />
      </div>

      <!-- Empty state — guide new users toward setup flow -->
      <div v-else-if="knowledgeGraphs.length === 0" class="flex flex-col items-center gap-4 py-16 text-center">
        <div class="rounded-full bg-muted p-5">
          <BookOpen class="size-10 text-muted-foreground" />
        </div>
        <div class="space-y-1">
          <h2 class="text-lg font-semibold">No knowledge graphs yet</h2>
          <p class="max-w-sm text-sm text-muted-foreground">
            Create your first knowledge graph to start connecting data sources and querying
            structured relationships.
          </p>
        </div>

        <Button @click="openCreateDialog">
          <Plus class="mr-2 size-4" />
          Create your first knowledge graph
        </Button>

        <!-- What to expect -->
        <div class="mt-4 grid w-full max-w-xl gap-3 sm:grid-cols-3 text-left">
          <Card>
            <CardContent class="flex items-start gap-3 p-4">
              <div class="rounded-md bg-muted p-1.5 shrink-0 mt-0.5">
                <BookOpen class="size-4 text-muted-foreground" />
              </div>
              <div>
                <p class="text-sm font-medium">Create</p>
                <p class="text-xs text-muted-foreground">Name and describe your knowledge graph</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="flex items-start gap-3 p-4">
              <div class="rounded-md bg-muted p-1.5 shrink-0 mt-0.5">
                <Cable class="size-4 text-muted-foreground" />
              </div>
              <div>
                <p class="text-sm font-medium">Connect</p>
                <p class="text-xs text-muted-foreground">Add data sources like GitHub repos</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent class="flex items-start gap-3 p-4">
              <div class="rounded-md bg-muted p-1.5 shrink-0 mt-0.5">
                <Database class="size-4 text-muted-foreground" />
              </div>
              <div>
                <p class="text-sm font-medium">Query</p>
                <p class="text-xs text-muted-foreground">Explore relationships via Cypher</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <!-- Knowledge graph list -->
      <div v-else class="space-y-3">
        <div v-for="kg in knowledgeGraphs" :key="kg.id" class="rounded-lg border bg-card">
          <div class="flex items-center justify-between p-4">
            <div class="flex items-center gap-3">
              <div class="rounded-md bg-muted p-2">
                <BookOpen class="size-4 text-muted-foreground" />
              </div>
              <div>
                <p class="font-medium text-sm">{{ kg.name }}</p>
                <p v-if="kg.description" class="text-xs text-muted-foreground">{{ kg.description }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Button size="sm" variant="outline" @click="navigateTo('/data-sources')">
                <Cable class="mr-1.5 size-3.5" />
                Add Data Source
              </Button>
              <Button size="sm" variant="outline" @click="navigateTo('/query')">
                <Database class="mr-1.5 size-3.5" />
                Query
              </Button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Create Knowledge Graph Dialog -->
    <Dialog v-model:open="createDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Knowledge Graph</DialogTitle>
          <DialogDescription>
            Create a new knowledge graph
            <template v-if="currentTenantName">
              within <span class="font-medium">{{ currentTenantName }}</span>
            </template>
            . You will be prompted to add a data source after creation.
          </DialogDescription>
        </DialogHeader>
        <form class="space-y-4" @submit.prevent="handleCreate">
          <div class="space-y-1.5">
            <Label for="kg-name">Name <span class="text-destructive">*</span></Label>
            <Input
              id="kg-name"
              v-model="createName"
              placeholder="e.g. Engineering Knowledge Base"
              :disabled="creating"
              @input="createNameError = ''"
            />
            <p v-if="createNameError" class="text-sm text-destructive">{{ createNameError }}</p>
          </div>
          <div class="space-y-1.5">
            <Label for="kg-description">Description</Label>
            <Input
              id="kg-description"
              v-model="createDescription"
              placeholder="What does this knowledge graph represent?"
              :disabled="creating"
            />
            <p class="text-xs text-muted-foreground">
              Optional — describe the purpose and scope of this knowledge graph.
            </p>
          </div>
          <DialogFooter>
            <DialogClose as-child>
              <Button type="button" variant="outline" :disabled="creating">Cancel</Button>
            </DialogClose>
            <Button type="submit" :disabled="creating || !createName.trim()">
              <Loader2 v-if="creating" class="mr-2 size-4 animate-spin" />
              {{ creating ? 'Creating...' : 'Create' }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
</template>
