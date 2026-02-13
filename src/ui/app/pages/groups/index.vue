<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { toast } from 'vue-sonner'
import {
  Users, Plus, Trash2, Loader2, Search, Info,
  UserPlus, X, Pencil, Check, Building2, UserCircle,
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
import type { GroupResponse, GroupMemberResponse, GroupRole } from '~/types'

const {
  listGroups, createGroup, getGroup, deleteGroup, updateGroup,
  listGroupMembers, addGroupMember, updateGroupMemberRole, removeGroupMember,
} = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── State ──────────────────────────────────────────────────────────────────

const groups = ref<GroupResponse[]>([])
const loading = ref(true)

// Create dialog
const createDialogOpen = ref(false)
const createFormName = ref('')
const isCreating = ref(false)

// Lookup
const lookupId = ref('')
const isLookingUp = ref(false)

// Delete dialog
const deleteDialogOpen = ref(false)
const groupToDelete = ref<GroupResponse | null>(null)
const isDeleting = ref(false)

// Details / selection
const selectedGroup = ref<GroupResponse | null>(null)

// Members
const members = ref<GroupMemberResponse[]>([])
const membersLoading = ref(false)
const newMemberId = ref('')
const newMemberRole = ref<GroupRole>('member')
const addingMember = ref(false)

// Rename
const editingName = ref(false)
const editNameValue = ref('')
const savingName = ref(false)

// Role editing
const updatingRoleFor = ref<string | null>(null)

// Remove member dialog
const showRemoveMemberDialog = ref(false)
const memberToRemove = ref<GroupMemberResponse | null>(null)
const removingMember = ref(false)

// ── Data loading ───────────────────────────────────────────────────────────

async function fetchGroups() {
  loading.value = true
  try {
    groups.value = await listGroups()
  } catch (err) {
    toast.error('Failed to load groups', {
      description: extractErrorMessage(err),
    })
  } finally {
    loading.value = false
  }
}

async function fetchMembers(group: GroupResponse) {
  membersLoading.value = true
  try {
    members.value = await listGroupMembers(group.id)
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

function selectGroup(group: GroupResponse) {
  if (selectedGroup.value?.id === group.id) {
    selectedGroup.value = null
    members.value = []
    return
  }
  selectedGroup.value = group
  editingName.value = false
  fetchMembers(group)
}

// ── Create ─────────────────────────────────────────────────────────────────

async function handleCreate() {
  if (!createFormName.value.trim()) {
    toast.error('Group name is required')
    return
  }
  isCreating.value = true
  try {
    const group = await createGroup({ name: createFormName.value.trim() })
    createFormName.value = ''
    toast.success(`Group "${group.name}" created`)
    await fetchGroups()
  } catch (err: unknown) {
    toast.error('Failed to create group', {
      description: extractErrorMessage(err),
    })
  } finally {
    createDialogOpen.value = false
    isCreating.value = false
  }
}

// ── Look Up ────────────────────────────────────────────────────────────────

async function handleLookup() {
  const id = lookupId.value.trim()
  if (!id) {
    toast.error('Please enter a Group ID')
    return
  }
  if (groups.value.some((g) => g.id === id)) {
    toast.info('Group is already displayed')
    return
  }
  isLookingUp.value = true
  try {
    const group = await getGroup(id)
    groups.value.unshift(group)
    lookupId.value = ''
    toast.success(`Found group "${group.name}"`)
  } catch (err: unknown) {
    toast.error('Group not found', {
      description: extractErrorMessage(err),
    })
  } finally {
    isLookingUp.value = false
  }
}

// ── Delete ─────────────────────────────────────────────────────────────────

function confirmDelete(group: GroupResponse) {
  groupToDelete.value = group
  deleteDialogOpen.value = true
}

async function handleDelete() {
  if (!groupToDelete.value) return
  isDeleting.value = true
  try {
    await deleteGroup(groupToDelete.value.id)
    const name = groupToDelete.value.name
    if (selectedGroup.value?.id === groupToDelete.value.id) {
      selectedGroup.value = null
      members.value = []
    }
    toast.success(`Group "${name}" deleted`)
    await fetchGroups()
  } catch (err: unknown) {
    toast.error('Failed to delete group', {
      description: extractErrorMessage(err),
    })
  } finally {
    deleteDialogOpen.value = false
    groupToDelete.value = null
    isDeleting.value = false
  }
}

// ── Rename ─────────────────────────────────────────────────────────────────

function startRename() {
  if (!selectedGroup.value) return
  editNameValue.value = selectedGroup.value.name
  editingName.value = true
}

function cancelRename() {
  editingName.value = false
  editNameValue.value = ''
}

async function handleRename() {
  if (!selectedGroup.value || !editNameValue.value.trim()) return
  if (editNameValue.value.trim() === selectedGroup.value.name) {
    editingName.value = false
    return
  }
  savingName.value = true
  try {
    const updated = await updateGroup(selectedGroup.value.id, {
      name: editNameValue.value.trim(),
    })
    selectedGroup.value = updated
    // Update in the list too
    const idx = groups.value.findIndex(g => g.id === updated.id)
    if (idx !== -1) groups.value[idx] = updated
    toast.success('Group renamed')
    editingName.value = false
  } catch (err) {
    toast.error('Failed to rename group', {
      description: extractErrorMessage(err),
    })
  } finally {
    savingName.value = false
  }
}

// ── Members ────────────────────────────────────────────────────────────────

async function handleAddMember() {
  if (!selectedGroup.value || !newMemberId.value.trim()) return
  addingMember.value = true
  try {
    await addGroupMember(selectedGroup.value.id, {
      user_id: newMemberId.value.trim(),
      role: newMemberRole.value,
    })
    toast.success('Member added')
    newMemberId.value = ''
    newMemberRole.value = 'member'
    await fetchMembers(selectedGroup.value)
  } catch (err) {
    toast.error('Failed to add member', {
      description: extractErrorMessage(err),
    })
  } finally {
    addingMember.value = false
  }
}

function confirmRemoveMember(member: GroupMemberResponse) {
  memberToRemove.value = member
  showRemoveMemberDialog.value = true
}

async function handleRemoveMember() {
  if (!selectedGroup.value || !memberToRemove.value) return
  removingMember.value = true
  try {
    await removeGroupMember(
      selectedGroup.value.id,
      memberToRemove.value.user_id,
    )
    toast.success('Member removed')
    await fetchMembers(selectedGroup.value)
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

async function handleRoleChange(member: GroupMemberResponse, newRole: GroupRole) {
  if (!selectedGroup.value || newRole === member.role) return
  updatingRoleFor.value = member.user_id
  try {
    await updateGroupMemberRole(
      selectedGroup.value.id,
      member.user_id,
      newRole,
    )
    toast.success('Role updated')
    await fetchMembers(selectedGroup.value)
  } catch (err) {
    toast.error('Failed to update role', {
      description: extractErrorMessage(err),
    })
  } finally {
    updatingRoleFor.value = null
  }
}

onMounted(() => {
  if (hasTenant.value) fetchGroups()
})

// Re-fetch when tenant changes
watch(tenantVersion, () => {
  if (hasTenant.value) {
    selectedGroup.value = null
    members.value = []
    editingName.value = false
    fetchGroups()
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Users class="size-6 text-muted-foreground" />
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Groups</h1>
          <p class="text-sm text-muted-foreground">Create and manage user groups</p>
        </div>
      </div>

      <!-- Create Group Dialog -->
      <Dialog v-model:open="createDialogOpen">
        <Button :disabled="!hasTenant" @click="createDialogOpen = true">
          <Plus class="mr-2 size-4" />
          Create Group
        </Button>
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create Group</DialogTitle>
            <DialogDescription>
              Create a new group to organize users and manage permissions.
            </DialogDescription>
          </DialogHeader>
          <form @submit.prevent="handleCreate" class="space-y-4">
            <div class="space-y-2">
              <Label for="group-name">Name <span class="text-destructive">*</span></Label>
              <Input
                id="group-name"
                v-model="createFormName"
                placeholder="e.g. Engineering Team"
                :disabled="isCreating"
                @keydown.enter="handleCreate"
              />
            </div>
            <DialogFooter>
              <DialogClose as-child>
                <Button type="button" variant="outline" :disabled="isCreating">Cancel</Button>
              </DialogClose>
              <Button type="submit" :disabled="isCreating || !createFormName.trim()">
                {{ isCreating ? 'Creating...' : 'Create' }}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the header to view groups.</p>
    </div>

    <template v-else>

    <!-- Lookup by ID -->
    <Card>
      <CardHeader>
        <CardTitle class="text-base">Look Up Group</CardTitle>
      </CardHeader>
      <CardContent>
        <form @submit.prevent="handleLookup" class="flex gap-3">
          <Input
            v-model="lookupId"
            placeholder="Enter Group ID"
            class="max-w-sm font-mono text-sm"
            :disabled="isLookingUp"
            @keydown.enter="handleLookup"
          />
          <Button type="submit" variant="secondary" :disabled="isLookingUp || !lookupId.trim()" @click="handleLookup">
            <Search class="mr-2 size-4" />
            {{ isLookingUp ? 'Searching...' : 'Look Up' }}
          </Button>
        </form>
      </CardContent>
    </Card>

    <!-- Groups grid: list + details sidebar -->
    <div class="grid gap-6" :class="selectedGroup ? 'lg:grid-cols-[1fr_320px]' : ''">
      <!-- Group list -->
      <div class="rounded-md border">
        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading groups...
        </div>

        <!-- Empty -->
        <div v-else-if="groups.length === 0" class="py-12 text-center text-muted-foreground">
          <Users class="mx-auto size-12 text-muted-foreground/50" />
          <h3 class="mt-4 text-lg font-semibold">No groups found</h3>
          <p class="mt-1 text-sm">
            Create a new group or look up an existing one by ID.
          </p>
          <Button variant="outline" size="sm" class="mt-4" @click="createDialogOpen = true">
            <Plus class="mr-2 size-4" />
            Create Group
          </Button>
        </div>

        <!-- Group rows -->
        <div v-else class="divide-y">
          <div
            v-for="group in groups"
            :key="group.id"
            class="flex items-center gap-2 px-4 py-2.5 transition-colors hover:bg-muted/50 cursor-pointer"
            :class="[
              selectedGroup?.id === group.id ? 'bg-muted' : '',
            ]"
            @click="selectGroup(group)"
          >
            <Users class="size-4 shrink-0 text-muted-foreground" />
            <span class="flex-1 text-sm font-medium">{{ group.name }}</span>
            <Badge variant="secondary">
              {{ group.members.length }} {{ group.members.length === 1 ? 'member' : 'members' }}
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              class="size-7 shrink-0 text-destructive hover:text-destructive"
              title="Delete group"
              :aria-label="`Delete group ${group.name}`"
              @click.stop="confirmDelete(group)"
            >
              <Trash2 class="size-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <!-- Details sidebar -->
      <Card v-if="selectedGroup" class="self-start">
        <CardHeader class="pb-3">
          <div class="flex items-center justify-between">
            <CardTitle class="flex items-center gap-2 text-base">
              <Info class="size-4" />
              Group Details
            </CardTitle>
            <Button variant="ghost" size="icon" class="size-7" @click="selectedGroup = null; members = []">
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
              <p class="font-medium">{{ selectedGroup.name }}</p>
              <Button
                variant="ghost"
                size="icon"
                class="size-6 shrink-0 text-muted-foreground hover:text-foreground"
                title="Rename group"
                @click="startRename"
              >
                <Pencil class="size-3" />
              </Button>
            </div>
          </div>
          <div>
            <span class="text-muted-foreground">ID</span>
            <CopyableText :text="selectedGroup.id" :truncate="false" label="Group ID copied" />
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Members panel (full-width, below grid) -->
    <Card v-if="selectedGroup">
      <CardHeader>
        <div class="flex items-center justify-between">
          <CardTitle class="flex items-center gap-2 text-lg">
            <Users class="size-5" />
            Members of "{{ selectedGroup.name }}"
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
            <Label for="grp-member-id">User ID <span class="text-destructive">*</span></Label>
            <Input
              id="grp-member-id"
              v-model="newMemberId"
              placeholder="Enter user ID..."
            />
          </div>
          <div class="w-32 space-y-1.5">
            <Label>Role</Label>
            <Select v-model="newMemberRole">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="admin">Admin</SelectItem>
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
                <TableHead>User ID</TableHead>
                <TableHead>Role</TableHead>
                <TableHead class="w-[80px] text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="membersLoading">
                <TableCell colspan="3" class="h-16 text-center">
                  <div class="flex items-center justify-center gap-2 text-muted-foreground">
                    <Loader2 class="size-4 animate-spin" />
                    Loading members...
                  </div>
                </TableCell>
              </TableRow>
              <TableEmpty v-else-if="members.length === 0" :colspan="3">
                No members in this group.
              </TableEmpty>
              <TableRow v-for="member in members" v-else :key="member.user_id">
                <TableCell>
                  <div class="flex items-center gap-2">
                    <UserCircle class="size-4 text-muted-foreground" />
                    <CopyableText :text="member.user_id" label="User ID copied" :truncate="false" />
                  </div>
                </TableCell>
                <TableCell>
                  <Select
                    :model-value="member.role"
                    :disabled="updatingRoleFor === member.user_id"
                    @update:model-value="(val: GroupRole) => handleRoleChange(member, val)"
                  >
                    <SelectTrigger class="h-8 w-[120px] text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">Admin</SelectItem>
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
                    :aria-label="`Remove user ${member.user_id}`"
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

    <!-- Delete Confirmation Dialog -->
    <Dialog v-model:open="deleteDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete Group</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete
            <span class="font-semibold">{{ groupToDelete?.name }}</span>? This action cannot be
            undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline" :disabled="isDeleting">Cancel</Button>
          </DialogClose>
          <Button variant="destructive" :disabled="isDeleting" @click="handleDelete">
            {{ isDeleting ? 'Deleting...' : 'Delete' }}
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
            Are you sure you want to remove user "{{ memberToRemove?.user_id }}" from "{{ selectedGroup?.name }}"?
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
