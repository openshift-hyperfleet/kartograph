<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { toast } from 'vue-sonner'
import {
  Users, Plus, Trash2, Loader2, Search, Building2,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import type { GroupResponse, GroupMemberResponse, GroupRole } from '~/types'

const {
  listGroups, createGroup, deleteGroup, updateGroup,
  listGroupMembers, addGroupMember, updateGroupMemberRole, removeGroupMember,
} = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const { hasTenant, tenantVersion } = useTenant()

// ── Responsive breakpoint ──────────────────────────────────────────────────

const isDesktop = useMediaQuery('(min-width: 1024px)')

// ── State ──────────────────────────────────────────────────────────────────

const groups = ref<GroupResponse[]>([])
const loading = ref(true)

// Search / filter
const searchQuery = ref('')

// Create dialog
const createDialogOpen = ref(false)
const createFormName = ref('')
const isCreating = ref(false)

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

// Mobile sheet open state (derived from selection on mobile)
const sheetOpen = computed({
  get: () => !isDesktop.value && selectedGroup.value !== null,
  set: (val: boolean) => {
    if (!val) closeDetails()
  },
})

// ── Search filtering ───────────────────────────────────────────────────────

const filteredGroups = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return groups.value
  return groups.value.filter((group) =>
    group.name.toLowerCase().includes(q),
  )
})

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
    closeDetails()
    return
  }
  selectedGroup.value = group
  editingName.value = false
  fetchMembers(group)
}

function closeDetails() {
  selectedGroup.value = null
  members.value = []
  editingName.value = false
}

// ── Create ─────────────────────────────────────────────────────────────────

function openCreateDialog() {
  createFormName.value = ''
  createDialogOpen.value = true
}

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
      closeDetails()
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

watch(tenantVersion, () => {
  if (hasTenant.value) {
    closeDetails()
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
          <p class="text-sm text-muted-foreground">Create and manage user groups for permissions</p>
        </div>
      </div>
      <Button :disabled="!hasTenant" @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Create Group
      </Button>
    </div>

    <Separator />

    <!-- No tenant selected -->
    <div v-if="!hasTenant" class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <Building2 class="size-10" />
      <p class="font-medium">No tenant selected</p>
      <p class="text-sm">Select a tenant from the sidebar to view groups.</p>
    </div>

    <template v-else>

    <!-- Search filter -->
    <div v-if="!loading && groups.length > 0" class="relative">
      <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        v-model="searchQuery"
        placeholder="Filter groups..."
        class="pl-9"
      />
    </div>

    <!-- Main content: list + optional desktop detail panel -->
    <div
      class="grid gap-6"
      :class="selectedGroup && isDesktop ? 'lg:grid-cols-[1fr_minmax(400px,480px)]' : ''"
    >
      <!-- Group list -->
      <div class="min-w-0 rounded-md border">
        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading groups...
        </div>

        <!-- Empty (no groups) -->
        <div v-else-if="groups.length === 0" class="py-12 text-center text-muted-foreground">
          <Users class="mx-auto size-12 text-muted-foreground/50" />
          <h3 class="mt-4 text-lg font-semibold">No groups found</h3>
          <p class="mt-1 text-sm">
            Create a group to organize users and manage permissions.
          </p>
          <Button variant="outline" size="sm" class="mt-4" @click="openCreateDialog">
            <Plus class="mr-2 size-4" />
            Create Group
          </Button>
        </div>

        <!-- Empty (search has no results) -->
        <div v-else-if="filteredGroups.length === 0" class="py-12 text-center text-muted-foreground">
          <Search class="mx-auto size-12 text-muted-foreground/50" />
          <h3 class="mt-4 text-lg font-semibold">No matching groups</h3>
          <p class="mt-1 text-sm">No groups match "{{ searchQuery }}".</p>
        </div>

        <!-- Group rows -->
        <div v-else role="list" aria-label="Groups" class="divide-y">
          <div
            v-for="group in filteredGroups"
            :key="group.id"
            role="listitem"
            class="flex items-center gap-2 px-4 py-2.5 transition-colors hover:bg-muted/50 cursor-pointer"
            :class="[
              selectedGroup?.id === group.id ? 'bg-muted' : '',
            ]"
            :aria-label="`Select group ${group.name}`"
            :aria-selected="selectedGroup?.id === group.id"
            @click="selectGroup(group)"
          >
            <Users class="size-4 shrink-0 text-muted-foreground" />
            <span class="flex-1 truncate text-sm font-medium">{{ group.name }}</span>
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

      <!-- Desktop detail panel (right side of grid) -->
      <Card v-if="selectedGroup && isDesktop" class="sticky top-6 self-start overflow-y-auto max-h-[calc(100vh-8rem)]">
        <CardContent class="pt-6">
          <SettingsGroupDetailPanel
            :group="selectedGroup"
            :members="members"
            :members-loading="membersLoading"
            :editing-name="editingName"
            :edit-name-value="editNameValue"
            :saving-name="savingName"
            :adding-member="addingMember"
            :new-member-id="newMemberId"
            :new-member-role="newMemberRole"
            :updating-role-for="updatingRoleFor"
            show-close
            @close="closeDetails"
            @start-rename="startRename"
            @cancel-rename="cancelRename"
            @update:edit-name-value="editNameValue = $event"
            @rename="handleRename"
            @update:new-member-id="newMemberId = $event"
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
          <SheetTitle>Group Details</SheetTitle>
          <SheetDescription>Manage group settings and members</SheetDescription>
        </SheetHeader>
        <div v-if="selectedGroup" class="mt-6">
          <SettingsGroupDetailPanel
            :group="selectedGroup"
            :members="members"
            :members-loading="membersLoading"
            :editing-name="editingName"
            :edit-name-value="editNameValue"
            :saving-name="savingName"
            :adding-member="addingMember"
            :new-member-id="newMemberId"
            :new-member-role="newMemberRole"
            :updating-role-for="updatingRoleFor"
            @close="closeDetails"
            @start-rename="startRename"
            @cancel-rename="cancelRename"
            @update:edit-name-value="editNameValue = $event"
            @rename="handleRename"
            @update:new-member-id="newMemberId = $event"
            @update:new-member-role="newMemberRole = $event"
            @add-member="handleAddMember"
            @remove-member="confirmRemoveMember"
            @role-change="handleRoleChange"
          />
        </div>
      </SheetContent>
    </Sheet>

    </template>

    <!-- Create Group Dialog -->
    <Dialog v-model:open="createDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Group</DialogTitle>
          <DialogDescription>
            Create a new group to organize users and manage permissions.
          </DialogDescription>
        </DialogHeader>
        <form class="space-y-4" @submit.prevent="handleCreate">
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
              <Loader2 v-if="isCreating" class="mr-2 size-4 animate-spin" />
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

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
            <Loader2 v-if="isDeleting" class="mr-2 size-4 animate-spin" />
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
