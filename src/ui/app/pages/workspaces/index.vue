<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  FolderTree, Plus, Trash2, Loader2, ChevronRight, ChevronDown, Info,
  Users, UserPlus, X, Pencil, Check, Building2,
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

import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty,
} from '@/components/ui/table'
import { Separator } from '@/components/ui/separator'
import { CopyableText } from '@/components/ui/copyable-text'
import type { WorkspaceResponse, WorkspaceMemberResponse, WorkspaceMemberType, WorkspaceRole } from '~/types'

const {
  listWorkspaces, createWorkspace, deleteWorkspace, updateWorkspace,
  listWorkspaceMembers, addWorkspaceMember, removeWorkspaceMember, updateWorkspaceMemberRole,
} = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── State ──────────────────────────────────────────────────────────────────

const workspaces = ref<WorkspaceResponse[]>([])
const loading = ref(true)

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
      selectedWorkspace.value = null
      members.value = []
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
    selectedWorkspace.value = null
    members.value = []
    return
  }
  selectedWorkspace.value = ws
  fetchMembers(ws)
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
    // Update in the tree list too
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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

onMounted(() => {
  if (hasTenant.value) fetchWorkspaces()
})

// Re-fetch when tenant changes
watch(tenantVersion, () => {
  if (hasTenant.value) {
    selectedWorkspace.value = null
    members.value = []
    editingName.value = false
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
        <h1 class="text-2xl font-bold tracking-tight">Workspaces</h1>
      </div>
      <Button :disabled="!hasTenant" @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Create Workspace
      </Button>
    </div>

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the header to view workspaces.</p>
    </div>

    <template v-else>

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
              :aria-label="expandedIds.has(node.workspace.id) ? `Collapse ${node.workspace.name}` : `Expand ${node.workspace.name}`"
              @click="toggleExpand(node.workspace.id)"
            >
              <ChevronDown v-if="expandedIds.has(node.workspace.id)" class="size-4" />
              <ChevronRight v-else class="size-4" />
            </button>
            <div v-else class="size-5 shrink-0" />

            <!-- Workspace info -->
            <button
              class="flex flex-1 items-center gap-2 text-left"
              :aria-label="`Select workspace ${node.workspace.name}`"
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
              :aria-label="`Delete workspace ${node.workspace.name}`"
              @click.stop="confirmDelete(node.workspace)"
            >
              <Trash2 class="size-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <!-- Details panel (sidebar) -->
      <Card v-if="selectedWorkspace" class="self-start">
        <CardHeader class="pb-3">
          <div class="flex items-center justify-between">
            <CardTitle class="flex items-center gap-2 text-base">
              <Info class="size-4" />
              Workspace Details
            </CardTitle>
            <Button variant="ghost" size="icon" class="size-7" @click="selectedWorkspace = null; members = []">
              <X class="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent class="space-y-3 text-sm">
          <div>
            <span class="text-muted-foreground">Name</span>
            <div v-if="editingName" class="mt-1 flex items-center gap-1.5">
              <Input
                v-model="editNameValue"
                class="h-8 text-sm"
                @keydown.enter="handleRename"
                @keydown.escape="cancelRename"
              />
              <Button
                variant="ghost"
                size="icon"
                class="size-7 shrink-0 text-green-600 hover:text-green-700"
                :disabled="savingName || !editNameValue.trim()"
                @click="handleRename"
              >
                <Loader2 v-if="savingName" class="size-3.5 animate-spin" />
                <Check v-else class="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                class="size-7 shrink-0"
                :disabled="savingName"
                @click="cancelRename"
              >
                <X class="size-3.5" />
              </Button>
            </div>
            <div v-else class="flex items-center gap-1.5">
              <p class="font-medium">{{ selectedWorkspace.name }}</p>
              <Button
                variant="ghost"
                size="icon"
                class="size-6 shrink-0 text-muted-foreground hover:text-foreground"
                title="Rename workspace"
                @click="startRename"
              >
                <Pencil class="size-3" />
              </Button>
            </div>
          </div>
          <div>
            <span class="text-muted-foreground">ID</span>
            <CopyableText :text="selectedWorkspace.id" :truncate="false" label="Workspace ID copied" />
          </div>
          <div>
            <span class="text-muted-foreground">Tenant ID</span>
            <CopyableText :text="selectedWorkspace.tenant_id" :truncate="false" label="Tenant ID copied" />
          </div>
          <div>
            <span class="text-muted-foreground">Parent Workspace</span>
            <CopyableText v-if="selectedWorkspace.parent_workspace_id" :text="selectedWorkspace.parent_workspace_id" :truncate="false" label="Parent Workspace ID copied" />
            <p v-else class="font-mono text-xs">None (root)</p>
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

    <!-- Members panel (full-width, below grid) -->
    <Card v-if="selectedWorkspace">
      <CardHeader>
        <div class="flex items-center justify-between">
          <CardTitle class="flex items-center gap-2 text-lg">
            <Users class="size-5" />
            Members of "{{ selectedWorkspace.name }}"
          </CardTitle>
          <Badge v-if="members.length > 0" variant="secondary">
            {{ members.length }} {{ members.length === 1 ? 'member' : 'members' }}
          </Badge>
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <!-- Add member form -->
        <div class="flex items-end gap-3">
          <div class="flex-1 space-y-1.5">
            <Label for="ws-member-id">Member ID <span class="text-destructive">*</span></Label>
            <Input
              id="ws-member-id"
              v-model="newMemberId"
              placeholder="Enter user or group ID..."
            />
          </div>
          <div class="w-32 space-y-1.5">
            <Label>Type</Label>
            <Select v-model="newMemberType">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="group">Group</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="w-32 space-y-1.5">
            <Label>Role</Label>
            <Select v-model="newMemberRole">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="editor">Editor</SelectItem>
                <SelectItem value="member">Member</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button :disabled="addingMember || !newMemberId.trim()" @click="handleAddMember">
            <Loader2 v-if="addingMember" class="mr-2 size-4 animate-spin" />
            <UserPlus v-else class="mr-2 size-4" />
            Add
          </Button>
        </div>

        <Separator />

        <!-- Members table -->
        <div class="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Member ID</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Role</TableHead>
                <TableHead class="w-[80px] text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="membersLoading">
                <TableCell colspan="4" class="h-16 text-center">
                  <div class="flex items-center justify-center gap-2 text-muted-foreground">
                    <Loader2 class="size-4 animate-spin" />
                    Loading members...
                  </div>
                </TableCell>
              </TableRow>
              <TableEmpty v-else-if="members.length === 0" :colspan="4">
                No members in this workspace.
              </TableEmpty>
              <TableRow v-for="member in members" v-else :key="`${member.member_type}-${member.member_id}`">
                <TableCell>
                  <CopyableText :text="member.member_id" label="Member ID copied" />
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {{ member.member_type }}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Select
                    :model-value="member.role"
                    :disabled="updatingRoleFor === member.member_id"
                    @update:model-value="(val: WorkspaceRole) => handleRoleChange(member, val)"
                  >
                    <SelectTrigger class="h-8 w-[120px] text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="editor">Editor</SelectItem>
                      <SelectItem value="member">Member</SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell class="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="text-destructive hover:text-destructive"
                    title="Remove member"
                    :aria-label="`Remove ${member.member_type} ${member.member_id}`"
                    @click="confirmRemoveMember(member)"
                  >
                    <Trash2 class="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>

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
