<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { toast } from 'vue-sonner'
import {
  FolderTree, Plus, Trash2, Loader2, ChevronRight, ChevronDown,
  Building2, Search,
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
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import type { WorkspaceResponse, WorkspaceMemberResponse, WorkspaceMemberType, WorkspaceRole } from '~/types'

const {
  listWorkspaces, createWorkspace, deleteWorkspace, updateWorkspace,
  listWorkspaceMembers, addWorkspaceMember, removeWorkspaceMember, updateWorkspaceMemberRole,
} = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── Responsive breakpoint ──────────────────────────────────────────────────

const isDesktop = useMediaQuery('(min-width: 1024px)')

// ── State ──────────────────────────────────────────────────────────────────

const workspaces = ref<WorkspaceResponse[]>([])
const loading = ref(true)

// Search / filter
const searchQuery = ref('')

// Create dialog
const showCreateDialog = ref(false)
const createName = ref('')
const createParentId = ref('')
const creating = ref(false)
const createNameError = ref('')
const createParentError = ref('')

// Delete dialog
const showDeleteDialog = ref(false)
const workspaceToDelete = ref<WorkspaceResponse | null>(null)
const deleting = ref(false)

// Details
const selectedWorkspace = ref<WorkspaceResponse | null>(null)

// Members
const members = ref<WorkspaceMemberResponse[]>([])
const membersLoading = ref(false)
const newMemberId = ref('')
const newMemberType = ref<WorkspaceMemberType>('user')
const newMemberRole = ref<WorkspaceRole>('member')
const addingMember = ref(false)

// Rename
const editingName = ref(false)
const editNameValue = ref('')
const savingName = ref(false)

// Role editing
const updatingRoleFor = ref<string | null>(null)

// Remove member dialog
const showRemoveMemberDialog = ref(false)
const memberToRemove = ref<WorkspaceMemberResponse | null>(null)
const removingMember = ref(false)

// Tree expand/collapse
const expandedIds = ref<Set<string>>(new Set())

// Mobile sheet open state (derived from selection on mobile)
const sheetOpen = computed({
  get: () => !isDesktop.value && selectedWorkspace.value !== null,
  set: (val: boolean) => {
    if (!val) closeDetails()
  },
})

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

// ── Search filtering ───────────────────────────────────────────────────────

const filteredFlatNodes = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return flatNodes.value
  return flatNodes.value.filter((node) =>
    node.workspace.name.toLowerCase().includes(q),
  )
})

function toggleExpand(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
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

async function fetchMembers(workspace: WorkspaceResponse) {
  membersLoading.value = true
  try {
    members.value = await listWorkspaceMembers(workspace.id)
  } catch (err) {
    toast.error('Failed to load members', {
      description: extractErrorMessage(err),
    })
    members.value = []
  } finally {
    membersLoading.value = false
  }
}

// ── Actions ────────────────────────────────────────────────────────────────

function openCreateDialog() {
  createName.value = ''
  createParentId.value = ''
  createNameError.value = ''
  createParentError.value = ''
  showCreateDialog.value = true
}

async function handleCreate() {
  createNameError.value = ''
  createParentError.value = ''
  if (!createName.value.trim()) {
    createNameError.value = 'Workspace name is required'
  }
  if (!createParentId.value) {
    createParentError.value = 'Parent workspace is required'
  }
  if (createNameError.value || createParentError.value) return
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
      closeDetails()
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
  if (selectedWorkspace.value?.id === ws.id) {
    closeDetails()
    return
  }
  selectedWorkspace.value = ws
  editingName.value = false
  fetchMembers(ws)
}

function closeDetails() {
  selectedWorkspace.value = null
  members.value = []
  editingName.value = false
}

async function handleAddMember() {
  if (!selectedWorkspace.value || !newMemberId.value.trim()) return
  addingMember.value = true
  try {
    await addWorkspaceMember(selectedWorkspace.value.id, {
      member_id: newMemberId.value.trim(),
      member_type: newMemberType.value,
      role: newMemberRole.value,
    })
    toast.success('Member added')
    newMemberId.value = ''
    newMemberType.value = 'user'
    newMemberRole.value = 'member'
    await fetchMembers(selectedWorkspace.value)
  } catch (err) {
    toast.error('Failed to add member', {
      description: extractErrorMessage(err),
    })
  } finally {
    addingMember.value = false
  }
}

function confirmRemoveMember(member: WorkspaceMemberResponse) {
  memberToRemove.value = member
  showRemoveMemberDialog.value = true
}

async function handleRemoveMember() {
  if (!selectedWorkspace.value || !memberToRemove.value) return
  removingMember.value = true
  try {
    await removeWorkspaceMember(
      selectedWorkspace.value.id,
      memberToRemove.value.member_id,
      memberToRemove.value.member_type,
    )
    toast.success('Member removed')
    await fetchMembers(selectedWorkspace.value)
  } catch (err) {
    toast.error('Failed to remove member', {
      description: extractErrorMessage(err),
    })
  } finally {
    showRemoveMemberDialog.value = false
    memberToRemove.value = null
    removingMember.value = false
  }
}

async function handleRename() {
  if (!selectedWorkspace.value || !editNameValue.value.trim()) return
  if (editNameValue.value.trim() === selectedWorkspace.value.name) {
    editingName.value = false
    return
  }
  savingName.value = true
  try {
    const updated = await updateWorkspace(selectedWorkspace.value.id, {
      name: editNameValue.value.trim(),
    })
    selectedWorkspace.value = updated
    const idx = workspaces.value.findIndex(ws => ws.id === updated.id)
    if (idx !== -1) workspaces.value[idx] = updated
    toast.success('Workspace renamed')
    editingName.value = false
  } catch (err) {
    toast.error('Failed to rename workspace', {
      description: extractErrorMessage(err),
    })
  } finally {
    savingName.value = false
  }
}

function startRename() {
  if (!selectedWorkspace.value) return
  editNameValue.value = selectedWorkspace.value.name
  editingName.value = true
}

function cancelRename() {
  editingName.value = false
  editNameValue.value = ''
}

async function handleRoleChange(member: WorkspaceMemberResponse, newRole: WorkspaceRole) {
  if (!selectedWorkspace.value || newRole === member.role) return
  updatingRoleFor.value = member.member_id
  try {
    await updateWorkspaceMemberRole(
      selectedWorkspace.value.id,
      member.member_id,
      member.member_type,
      newRole,
    )
    toast.success('Role updated')
    await fetchMembers(selectedWorkspace.value)
  } catch (err) {
    toast.error('Failed to update role', {
      description: extractErrorMessage(err),
    })
  } finally {
    updatingRoleFor.value = null
  }
}

onMounted(() => {
  if (hasTenant.value) fetchWorkspaces()
})

watch(tenantVersion, () => {
  if (hasTenant.value) {
    closeDetails()
    fetchWorkspaces()
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <FolderTree class="size-6 text-muted-foreground" />
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Workspaces</h1>
          <p class="text-sm text-muted-foreground">Organize resources with hierarchical workspaces</p>
        </div>
      </div>
      <Button :disabled="!hasTenant" @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Create Workspace
      </Button>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view workspaces.</p>
    </div>

    <template v-else>

    <!-- Search filter -->
    <div v-if="!loading && workspaces.length > 0" class="relative">
      <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        v-model="searchQuery"
        placeholder="Filter workspaces..."
        class="pl-9"
      />
    </div>

    <!-- Main content: list + optional desktop detail panel -->
    <div
      class="grid gap-6"
      :class="selectedWorkspace && isDesktop ? 'lg:grid-cols-[1fr_minmax(400px,480px)]' : ''"
    >
      <!-- Tree view -->
      <div class="min-w-0 rounded-md border">
        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading workspaces...
        </div>

        <!-- Empty (no workspaces) -->
        <div v-else-if="workspaces.length === 0" class="py-12 text-center text-muted-foreground">
          <FolderTree class="mx-auto size-12 text-muted-foreground/50" />
          <h3 class="mt-4 text-lg font-semibold">No workspaces found</h3>
          <p class="mt-1 text-sm">
            Create a workspace to organize your resources.
          </p>
          <Button variant="outline" size="sm" class="mt-4" @click="openCreateDialog">
            <Plus class="mr-2 size-4" />
            Create Workspace
          </Button>
        </div>

        <!-- Empty (search has no results) -->
        <div v-else-if="filteredFlatNodes.length === 0" class="py-12 text-center text-muted-foreground">
          <Search class="mx-auto size-12 text-muted-foreground/50" />
          <h3 class="mt-4 text-lg font-semibold">No matching workspaces</h3>
          <p class="mt-1 text-sm">No workspaces match "{{ searchQuery }}".</p>
        </div>

        <!-- Tree rows -->
        <div v-else role="list" aria-label="Workspaces" class="divide-y">
          <div
            v-for="node in filteredFlatNodes"
            :key="node.workspace.id"
            role="listitem"
            class="relative flex items-center gap-2 px-4 py-2.5 transition-colors hover:bg-muted/50 cursor-pointer"
            :class="[
              selectedWorkspace?.id === node.workspace.id ? 'bg-muted' : '',
            ]"
            :style="{ paddingLeft: `${node.depth * 24 + 16}px` }"
            :aria-label="`Select workspace ${node.workspace.name}`"
            :aria-selected="selectedWorkspace?.id === node.workspace.id"
            @click="selectWorkspace(node.workspace)"
          >
            <!-- Tree guide lines -->
            <span
              v-if="node.depth > 0"
              class="absolute top-0 bottom-0 border-l border-border"
              :style="{ left: `${(node.depth - 1) * 24 + 28}px` }"
              aria-hidden="true"
            />

            <!-- Expand/collapse toggle -->
            <button
              v-if="node.children.length > 0"
              class="relative z-10 flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground"
              :aria-label="expandedIds.has(node.workspace.id) ? `Collapse ${node.workspace.name}` : `Expand ${node.workspace.name}`"
              @click.stop="toggleExpand(node.workspace.id)"
            >
              <ChevronDown v-if="expandedIds.has(node.workspace.id)" class="size-4" />
              <ChevronRight v-else class="size-4" />
            </button>
            <div v-else class="size-5 shrink-0" />

            <!-- Workspace info -->
            <FolderTree class="size-4 shrink-0 text-muted-foreground" />
            <span class="flex-1 truncate text-sm font-medium">{{ node.workspace.name }}</span>
            <Badge v-if="node.workspace.is_root" variant="outline" class="text-[10px]">
              Root
            </Badge>

            <!-- Actions -->
            <Button
              v-if="!node.workspace.is_root"
              variant="ghost"
              size="icon"
              class="size-7 shrink-0 text-destructive hover:text-destructive"
              title="Delete workspace"
              :aria-label="`Delete workspace ${node.workspace.name}`"
              @click.stop="confirmDelete(node.workspace)"
            >
              <Trash2 class="size-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <!-- Desktop detail panel (right side of grid) -->
      <Card v-if="selectedWorkspace && isDesktop" class="sticky top-6 self-start overflow-y-auto max-h-[calc(100vh-8rem)]">
        <CardContent class="pt-6">
          <SettingsWorkspaceDetailPanel
            :workspace="selectedWorkspace"
            :members="members"
            :members-loading="membersLoading"
            :editing-name="editingName"
            :edit-name-value="editNameValue"
            :saving-name="savingName"
            :adding-member="addingMember"
            :new-member-id="newMemberId"
            :new-member-type="newMemberType"
            :new-member-role="newMemberRole"
            :updating-role-for="updatingRoleFor"
            show-close
            @close="closeDetails"
            @start-rename="startRename"
            @cancel-rename="cancelRename"
            @update:edit-name-value="editNameValue = $event"
            @rename="handleRename"
            @update:new-member-id="newMemberId = $event"
            @update:new-member-type="newMemberType = $event"
            @update:new-member-role="newMemberRole = $event"
            @add-member="handleAddMember"
            @remove-member="confirmRemoveMember"
            @role-change="handleRoleChange"
          />
        </CardContent>
      </Card>
    </div>

    <!-- Mobile detail sheet -->
    <Sheet v-model:open="sheetOpen">
      <SheetContent side="right" class="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Workspace Details</SheetTitle>
          <SheetDescription>Manage workspace settings and members</SheetDescription>
        </SheetHeader>
        <div v-if="selectedWorkspace" class="mt-6">
          <SettingsWorkspaceDetailPanel
            :workspace="selectedWorkspace"
            :members="members"
            :members-loading="membersLoading"
            :editing-name="editingName"
            :edit-name-value="editNameValue"
            :saving-name="savingName"
            :adding-member="addingMember"
            :new-member-id="newMemberId"
            :new-member-type="newMemberType"
            :new-member-role="newMemberRole"
            :updating-role-for="updatingRoleFor"
            @close="closeDetails"
            @start-rename="startRename"
            @cancel-rename="cancelRename"
            @update:edit-name-value="editNameValue = $event"
            @rename="handleRename"
            @update:new-member-id="newMemberId = $event"
            @update:new-member-type="newMemberType = $event"
            @update:new-member-role="newMemberRole = $event"
            @add-member="handleAddMember"
            @remove-member="confirmRemoveMember"
            @role-change="handleRoleChange"
          />
        </div>
      </SheetContent>
    </Sheet>

    </template>

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
            <Label for="workspace-name">Name <span class="text-destructive">*</span></Label>
            <Input
              id="workspace-name"
              v-model="createName"
              placeholder="My Workspace"
              @keydown.enter="handleCreate"
              @input="createNameError = ''"
            />
            <p v-if="createNameError" class="text-sm text-destructive">{{ createNameError }}</p>
          </div>
          <div class="space-y-1.5">
            <Label>Parent Workspace <span class="text-destructive">*</span></Label>
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
            <p v-if="createParentError" class="text-sm text-destructive">{{ createParentError }}</p>
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

    <!-- Delete workspace dialog -->
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

    <!-- Remove member confirmation dialog -->
    <Dialog v-model:open="showRemoveMemberDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Remove Member</DialogTitle>
          <DialogDescription>
            Are you sure you want to remove {{ memberToRemove?.member_type }} "{{ memberToRemove?.member_id }}" from "{{ selectedWorkspace?.name }}"?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button variant="destructive" :disabled="removingMember" @click="handleRemoveMember">
            <Loader2 v-if="removingMember" class="mr-2 size-4 animate-spin" />
            Remove
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
