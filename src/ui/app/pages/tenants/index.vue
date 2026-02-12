<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { toast } from 'vue-sonner'
import { Building2, Plus, Users, Trash2, Loader2, UserPlus, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty,
} from '@/components/ui/table'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import type { TenantResponse, TenantMemberResponse } from '~/types'

const {
  listTenants, createTenant, deleteTenant,
  listTenantMembers, addTenantMember, removeTenantMember,
} = useIamApi()
const { extractErrorMessage } = useErrorHandler()

// ── State ──────────────────────────────────────────────────────────────────

const tenants = ref<TenantResponse[]>([])
const loading = ref(true)

// Create dialog
const showCreateDialog = ref(false)
const createName = ref('')
const creating = ref(false)

// Delete dialog
const showDeleteDialog = ref(false)
const tenantToDelete = ref<TenantResponse | null>(null)
const deleting = ref(false)

// Members panel
const selectedTenant = ref<TenantResponse | null>(null)
const members = ref<TenantMemberResponse[]>([])
const membersLoading = ref(false)
const newMemberUserId = ref('')
const newMemberRole = ref<'admin' | 'member'>('member')
const addingMember = ref(false)

// ── Data loading ───────────────────────────────────────────────────────────

async function fetchTenants() {
  loading.value = true
  try {
    tenants.value = await listTenants()
  } catch (err) {
    toast.error('Failed to load tenants', {
      description: extractErrorMessage(err),
    })
  } finally {
    loading.value = false
  }
}

async function fetchMembers(tenant: TenantResponse) {
  selectedTenant.value = tenant
  membersLoading.value = true
  try {
    members.value = await listTenantMembers(tenant.id)
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

async function handleCreate() {
  if (!createName.value.trim()) return
  creating.value = true
  try {
    await createTenant({ name: createName.value.trim() })
    toast.success('Tenant created')
    createName.value = ''
    await fetchTenants()
  } catch (err) {
    toast.error('Failed to create tenant', {
      description: extractErrorMessage(err),
    })
  } finally {
    showCreateDialog.value = false
    creating.value = false
  }
}

function confirmDelete(tenant: TenantResponse) {
  tenantToDelete.value = tenant
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!tenantToDelete.value) return
  deleting.value = true
  try {
    await deleteTenant(tenantToDelete.value.id)
    toast.success('Tenant deleted')
    if (selectedTenant.value?.id === tenantToDelete.value?.id) {
      selectedTenant.value = null
      members.value = []
    }
    await fetchTenants()
  } catch (err) {
    toast.error('Failed to delete tenant', {
      description: extractErrorMessage(err),
    })
  } finally {
    showDeleteDialog.value = false
    tenantToDelete.value = null
    deleting.value = false
  }
}

async function handleAddMember() {
  if (!selectedTenant.value || !newMemberUserId.value.trim()) return
  addingMember.value = true
  try {
    await addTenantMember(selectedTenant.value.id, {
      user_id: newMemberUserId.value.trim(),
      role: newMemberRole.value,
    })
    toast.success('Member added')
    newMemberUserId.value = ''
    newMemberRole.value = 'member'
    await fetchMembers(selectedTenant.value)
  } catch (err) {
    toast.error('Failed to add member', {
      description: extractErrorMessage(err),
    })
  } finally {
    addingMember.value = false
  }
}

async function handleRemoveMember(userId: string) {
  if (!selectedTenant.value) return
  try {
    await removeTenantMember(selectedTenant.value.id, userId)
    toast.success('Member removed')
    await fetchMembers(selectedTenant.value)
  } catch (err) {
    toast.error('Failed to remove member', {
      description: extractErrorMessage(err),
    })
  }
}

function closeMembers() {
  selectedTenant.value = null
  members.value = []
}

onMounted(fetchTenants)

</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Building2 class="size-6 text-muted-foreground" />
        <h1 class="text-2xl font-bold tracking-tight">Tenants</h1>
      </div>
      <Button @click="showCreateDialog = true">
        <Plus class="mr-2 size-4" />
        Create Tenant
      </Button>
    </div>

    <!-- Tenants table -->
    <div class="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Name</TableHead>
            <TableHead class="w-[140px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <!-- Loading state -->
          <TableRow v-if="loading">
            <TableCell colspan="3" class="h-24 text-center">
              <div class="flex items-center justify-center gap-2 text-muted-foreground">
                <Loader2 class="size-4 animate-spin" />
                Loading tenants...
              </div>
            </TableCell>
          </TableRow>

          <!-- Empty state -->
          <TableEmpty v-else-if="tenants.length === 0" :colspan="3">
            No tenants found. Create one to get started.
          </TableEmpty>

          <!-- Data rows -->
          <TableRow v-for="tenant in tenants" v-else :key="tenant.id">
            <TableCell class="font-mono text-xs text-muted-foreground">
              {{ tenant.id }}
            </TableCell>
            <TableCell class="font-medium">{{ tenant.name }}</TableCell>
            <TableCell class="text-right">
              <div class="flex items-center justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  title="View Members"
                  @click="fetchMembers(tenant)"
                >
                  <Users class="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  title="Delete"
                  class="text-destructive hover:text-destructive"
                  @click="confirmDelete(tenant)"
                >
                  <Trash2 class="size-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <!-- Members panel -->
    <Card v-if="selectedTenant">
      <CardHeader>
        <div class="flex items-center justify-between">
          <CardTitle class="flex items-center gap-2 text-lg">
            <Users class="size-5" />
            Members of "{{ selectedTenant.name }}"
          </CardTitle>
          <Button variant="ghost" size="icon" @click="closeMembers">
            <X class="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <!-- Add member form -->
        <div class="flex items-end gap-3">
          <div class="flex-1 space-y-1.5">
            <Label for="member-user-id">User ID</Label>
            <Input
              id="member-user-id"
              v-model="newMemberUserId"
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
          <Button :disabled="addingMember || !newMemberUserId.trim()" @click="handleAddMember">
            <UserPlus class="mr-2 size-4" />
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
                No members in this tenant.
              </TableEmpty>
              <TableRow v-for="member in members" v-else :key="member.user_id">
                <TableCell class="font-mono text-xs">{{ member.user_id }}</TableCell>
                <TableCell>
                  <Badge :variant="member.role === 'admin' ? 'default' : 'secondary'">
                    {{ member.role }}
                  </Badge>
                </TableCell>
                <TableCell class="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="text-destructive hover:text-destructive"
                    title="Remove member"
                    @click="handleRemoveMember(member.user_id)"
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

    <!-- Create tenant dialog -->
    <Dialog v-model:open="showCreateDialog">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Tenant</DialogTitle>
          <DialogDescription>
            Enter a name for the new tenant.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-1.5">
            <Label for="tenant-name">Name</Label>
            <Input
              id="tenant-name"
              v-model="createName"
              placeholder="My Tenant"
              @keydown.enter="handleCreate"
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button :disabled="creating || !createName.trim()" @click="handleCreate">
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
          <DialogTitle>Delete Tenant</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete "{{ tenantToDelete?.name }}"? This action cannot be undone.
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
