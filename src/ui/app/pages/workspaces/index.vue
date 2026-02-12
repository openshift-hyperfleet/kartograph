<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import {
  FolderTree, Plus, Trash2, Loader2, ChevronRight, ChevronDown, Info,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Card, CardContent, CardHeader, CardTitle,
} from '@/components/ui/card'
import type { WorkspaceResponse } from '~/types'

const { listWorkspaces, createWorkspace, deleteWorkspace } = useIamApi()
const { extractErrorMessage } = useErrorHandler()

// ── State ──────────────────────────────────────────────────────────────────

const workspaces = ref<WorkspaceResponse[]>([])
const loading = ref(true)

// Create dialog
const showCreateDialog = ref(false)
const createName = ref('')
const createParentId = ref('')
const creating = ref(false)

// Delete dialog
const showDeleteDialog = ref(false)
const workspaceToDelete = ref<WorkspaceResponse | null>(null)
const deleting = ref(false)

// Details
const selectedWorkspace = ref<WorkspaceResponse | null>(null)

// Tree expand/collapse
const expandedIds = ref<Set<string>>(new Set())

// ── Tree building ──────────────────────────────────────────────────────────

interface WorkspaceNode {
  workspace: WorkspaceResponse
  children: WorkspaceNode[]
  depth: number
}

const workspaceTree = computed<WorkspaceNode[]>(() => {
  const byParent = new Map<string | null, WorkspaceResponse[]>()
  for (const ws of workspaces.value) {
    const parentKey = ws.parent_workspace_id
    if (!byParent.has(parentKey)) byParent.set(parentKey, [])
    byParent.get(parentKey)!.push(ws)
  }

  function build(parentId: string | null, depth: number): WorkspaceNode[] {
    const children = byParent.get(parentId) ?? []
    return children.map((ws) => ({
      workspace: ws,
      children: build(ws.id, depth + 1),
      depth,
    }))
  }

  return build(null, 0)
})

function flattenTree(nodes: WorkspaceNode[]): WorkspaceNode[] {
  const result: WorkspaceNode[] = []
  function walk(nodeList: WorkspaceNode[]) {
    for (const node of nodeList) {
      result.push(node)
      if (expandedIds.value.has(node.workspace.id)) {
        walk(node.children)
      }
    }
  }
  walk(nodes)
  return result
}

const flatNodes = computed(() => flattenTree(workspaceTree.value))

function toggleExpand(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}

function expandAll() {
  for (const ws of workspaces.value) {
    expandedIds.value.add(ws.id)
  }
}

// ── Data loading ───────────────────────────────────────────────────────────

async function fetchWorkspaces() {
  loading.value = true
  try {
    const response = await listWorkspaces()
    workspaces.value = response.workspaces
    // Auto-expand root workspaces
    for (const ws of workspaces.value) {
      if (ws.is_root) expandedIds.value.add(ws.id)
    }
  } catch (err) {
    toast.error('Failed to load workspaces', {
      description: extractErrorMessage(err),
    })
  } finally {
    loading.value = false
  }
}

// ── Actions ────────────────────────────────────────────────────────────────

function openCreateDialog() {
  createName.value = ''
  createParentId.value = ''
  showCreateDialog.value = true
}

async function handleCreate() {
  if (!createName.value.trim() || !createParentId.value) return
  creating.value = true
  try {
    await createWorkspace({
      name: createName.value.trim(),
      parent_workspace_id: createParentId.value,
    })
    toast.success('Workspace created')
    createName.value = ''
    createParentId.value = ''
    await fetchWorkspaces()
  } catch (err) {
    toast.error('Failed to create workspace', {
      description: extractErrorMessage(err),
    })
  } finally {
    showCreateDialog.value = false
    creating.value = false
  }
}

function confirmDelete(ws: WorkspaceResponse) {
  workspaceToDelete.value = ws
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!workspaceToDelete.value) return
  deleting.value = true
  try {
    await deleteWorkspace(workspaceToDelete.value.id)
    toast.success('Workspace deleted')
    if (selectedWorkspace.value?.id === workspaceToDelete.value.id) {
      selectedWorkspace.value = null
    }
    await fetchWorkspaces()
  } catch (err) {
    toast.error('Failed to delete workspace', {
      description: extractErrorMessage(err),
    })
  } finally {
    showDeleteDialog.value = false
    workspaceToDelete.value = null
    deleting.value = false
  }
}

function selectWorkspace(ws: WorkspaceResponse) {
  selectedWorkspace.value = selectedWorkspace.value?.id === ws.id ? null : ws
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

onMounted(() => {
  fetchWorkspaces()
  expandAll()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <FolderTree class="size-6 text-muted-foreground" />
        <h1 class="text-2xl font-bold tracking-tight">Workspaces</h1>
      </div>
      <Button @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Create Workspace
      </Button>
    </div>

    <div class="grid gap-6" :class="selectedWorkspace ? 'lg:grid-cols-[1fr_320px]' : ''">
      <!-- Tree view -->
      <div class="rounded-md border">
        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading workspaces...
        </div>

        <!-- Empty -->
        <div v-else-if="workspaces.length === 0" class="py-12 text-center text-muted-foreground">
          No workspaces found. Create one to get started.
        </div>

        <!-- Tree rows -->
        <div v-else class="divide-y">
          <div
            v-for="node in flatNodes"
            :key="node.workspace.id"
            class="flex items-center gap-2 px-4 py-2.5 transition-colors hover:bg-muted/50"
            :class="[
              selectedWorkspace?.id === node.workspace.id ? 'bg-muted' : '',
            ]"
            :style="{ paddingLeft: `${node.depth * 24 + 16}px` }"
          >
            <!-- Expand/collapse toggle -->
            <button
              v-if="node.children.length > 0"
              class="flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground"
              @click="toggleExpand(node.workspace.id)"
            >
              <ChevronDown v-if="expandedIds.has(node.workspace.id)" class="size-4" />
              <ChevronRight v-else class="size-4" />
            </button>
            <div v-else class="size-5 shrink-0" />

            <!-- Workspace info -->
            <button
              class="flex flex-1 items-center gap-2 text-left"
              @click="selectWorkspace(node.workspace)"
            >
              <FolderTree class="size-4 shrink-0 text-muted-foreground" />
              <span class="text-sm font-medium">{{ node.workspace.name }}</span>
              <Badge v-if="node.workspace.is_root" variant="outline" class="text-[10px]">
                Root
              </Badge>
            </button>

            <!-- Actions -->
            <Button
              v-if="!node.workspace.is_root"
              variant="ghost"
              size="icon"
              class="size-7 shrink-0 text-destructive hover:text-destructive"
              title="Delete workspace"
              @click.stop="confirmDelete(node.workspace)"
            >
              <Trash2 class="size-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <!-- Details panel -->
      <Card v-if="selectedWorkspace">
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <Info class="size-4" />
            Workspace Details
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-3 text-sm">
          <div>
            <span class="text-muted-foreground">Name</span>
            <p class="font-medium">{{ selectedWorkspace.name }}</p>
          </div>
          <div>
            <span class="text-muted-foreground">ID</span>
            <p class="font-mono text-xs">{{ selectedWorkspace.id }}</p>
          </div>
          <div>
            <span class="text-muted-foreground">Tenant ID</span>
            <p class="font-mono text-xs">{{ selectedWorkspace.tenant_id }}</p>
          </div>
          <div>
            <span class="text-muted-foreground">Parent Workspace</span>
            <p class="font-mono text-xs">{{ selectedWorkspace.parent_workspace_id ?? 'None (root)' }}</p>
          </div>
          <div>
            <span class="text-muted-foreground">Root</span>
            <p>
              <Badge :variant="selectedWorkspace.is_root ? 'default' : 'secondary'">
                {{ selectedWorkspace.is_root ? 'Yes' : 'No' }}
              </Badge>
            </p>
          </div>
          <div>
            <span class="text-muted-foreground">Created</span>
            <p>{{ formatDate(selectedWorkspace.created_at) }}</p>
          </div>
          <div>
            <span class="text-muted-foreground">Updated</span>
            <p>{{ formatDate(selectedWorkspace.updated_at) }}</p>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Create workspace dialog -->
    <Dialog v-model:open="showCreateDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Workspace</DialogTitle>
          <DialogDescription>
            Create a new workspace under an existing parent.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-1.5">
            <Label for="workspace-name">Name</Label>
            <Input
              id="workspace-name"
              v-model="createName"
              placeholder="My Workspace"
              @keydown.enter="handleCreate"
            />
          </div>
          <div class="space-y-1.5">
            <Label>Parent Workspace</Label>
            <Select v-model="createParentId">
              <SelectTrigger>
                <SelectValue placeholder="Select parent..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="ws in workspaces"
                  :key="ws.id"
                  :value="ws.id"
                >
                  {{ ws.name }}{{ ws.is_root ? ' (Root)' : '' }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button
            :disabled="creating || !createName.trim() || !createParentId"
            @click="handleCreate"
          >
            <Loader2 v-if="creating" class="mr-2 size-4 animate-spin" />
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Delete confirmation dialog -->
    <Dialog v-model:open="showDeleteDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Workspace</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete "{{ workspaceToDelete?.name }}"? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button variant="destructive" :disabled="deleting" @click="handleDelete">
            <Loader2 v-if="deleting" class="mr-2 size-4 animate-spin" />
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
