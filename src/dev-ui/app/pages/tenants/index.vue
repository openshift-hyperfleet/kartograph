<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import { toast } from 'vue-sonner'
import {
  Building2, Plus, Trash2, Loader2, Search,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose,
} from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import type { TenantResponse, TenantMemberResponse } from '~/types'

const {
  listTenants, createTenant, deleteTenant,
  listTenantMembers, addTenantMember, removeTenantMember,
} = useIamApi()
const { extractErrorMessage } = useErrorHandler()
const {
  currentTenantId,
  hasTenant,
  syncTenantList,
  switchTenant,
  handleCurrentTenantDeleted,
} = useTenant()

// ── Responsive breakpoint ──────────────────────────────────────────────────

const isDesktop = useMediaQuery('(min-width: 1024px)')

// ── State ──────────────────────────────────────────────────────────────────

const tenants = ref<TenantResponse[]>([])
const loading = ref(true)

// Search / filter
const searchQuery = ref('')

// Create dialog
const createDialogOpen = ref(false)
const createFormName = ref('')
const creating = ref(false)

// Delete dialog
const deleteDialogOpen = ref(false)
const tenantToDelete = ref<TenantResponse | null>(null)
const deleting = ref(false)

// Details / selection
const selectedTenant = ref<TenantResponse | null>(null)

// Members
const members = ref<TenantMemberResponse[]>([])
const membersLoading = ref(false)
const newMemberId = ref('')
const newMemberRole = ref<'admin' | 'member'>('member')
const addingMember = ref(false)

// Remove member dialog
const showRemoveMemberDialog = ref(false)
const memberToRemove = ref<TenantMemberResponse | null>(null)
const removingMember = ref(false)

// Mobile sheet open state (derived from selection on mobile)
const sheetOpen = computed({
  get: () => !isDesktop.value && selectedTenant.value !== null,
  set: (val: boolean) => {
    if (!val) closeDetails()
  },
})

// ── Search filtering ───────────────────────────────────────────────────────

const filteredTenants = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return tenants.value
  return tenants.value.filter((tenant) =>
    tenant.name.toLowerCase().includes(q),
  )
})

// ── Data loading ───────────────────────────────────────────────────────────

async function fetchTenants() {
  loading.value = true
  try {
    tenants.value = await listTenants()
    // Keep the shared tenant list (used by the header selector) in sync
    syncTenantList(tenants.value)
  } catch (err) {
    toast.error('Failed to load tenants', {
      description: extractErrorMessage(err),
    })
  } finally {
    loading.value = false
  }
}

async function fetchMembers(tenant: TenantResponse) {
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

function selectTenant(tenant: TenantResponse) {
  if (selectedTenant.value?.id === tenant.id) {
    closeDetails()
    return
  }
  selectedTenant.value = tenant
  newMemberId.value = ''
  newMemberRole.value = 'member'
  fetchMembers(tenant)
}

function closeDetails() {
  selectedTenant.value = null
  members.value = []
  newMemberId.value = ''
  newMemberRole.value = 'member'
}

// ── Create ─────────────────────────────────────────────────────────────────

function openCreateDialog() {
  createFormName.value = ''
  createDialogOpen.value = true
}

async function handleCreate() {
  if (!createFormName.value.trim()) {
    toast.error('Tenant name is required')
    return
  }
  creating.value = true
  try {
    const created = await createTenant({ name: createFormName.value.trim() })
    createFormName.value = ''
    toast.success(`Tenant "${created.name}" created`)
    await fetchTenants()
    // Auto-select the newly created tenant if none is currently selected
    if (!hasTenant.value) {
      switchTenant(created.id, created.name)
    }
  } catch (err: unknown) {
    toast.error('Failed to create tenant', {
      description: extractErrorMessage(err),
    })
  } finally {
    createDialogOpen.value = false
    creating.value = false
  }
}

// ── Delete ─────────────────────────────────────────────────────────────────

function confirmDelete(tenant: TenantResponse) {
  tenantToDelete.value = tenant
  deleteDialogOpen.value = true
}

async function handleDelete() {
  if (!tenantToDelete.value) return
  deleting.value = true
  const deletedId = tenantToDelete.value.id
  const wasCurrentTenant = deletedId === currentTenantId.value
  try {
    await deleteTenant(deletedId)
    const name = tenantToDelete.value.name
    if (selectedTenant.value?.id === deletedId) {
      closeDetails()
    }
    toast.success(`Tenant "${name}" deleted`)
    await fetchTenants()
    // If the deleted tenant was the currently-selected one, fall back
    if (wasCurrentTenant) {
      handleCurrentTenantDeleted()
    }
  } catch (err: unknown) {
    toast.error('Failed to delete tenant', {
      description: extractErrorMessage(err),
    })
  } finally {
    deleteDialogOpen.value = false
    tenantToDelete.value = null
    deleting.value = false
  }
}

// ── Members ────────────────────────────────────────────────────────────────

async function handleAddMember() {
  if (!selectedTenant.value || !newMemberId.value.trim()) return
  addingMember.value = true
  try {
    await addTenantMember(selectedTenant.value.id, {
      user_id: newMemberId.value.trim(),
      role: newMemberRole.value,
    })
    toast.success('Member added')
    newMemberId.value = ''
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

function confirmRemoveMember(member: TenantMemberResponse) {
  memberToRemove.value = member
  showRemoveMemberDialog.value = true
}

async function handleRemoveMember() {
  if (!selectedTenant.value || !memberToRemove.value) return
  removingMember.value = true
  try {
    await removeTenantMember(selectedTenant.value.id, memberToRemove.value.user_id)
    toast.success('Member removed')
    await fetchMembers(selectedTenant.value)
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

onMounted(fetchTenants)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Building2 class="size-6 text-muted-foreground" />
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Tenants</h1>
          <p class="text-sm text-muted-foreground">Manage tenant organizations and membership</p>
        </div>
      </div>
      <Button @click="openCreateDialog">
        <Plus class="mr-2 size-4" />
        Create Tenant
      </Button>
    </div>

    <Separator />

    <!-- Search filter -->
    <div v-if="!loading && tenants.length > 0" class="relative">
      <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        v-model="searchQuery"
        placeholder="Filter tenants..."
        class="pl-9"
      />
    </div>

    <!-- Main content: list + optional desktop detail panel -->
    <div
      class="grid gap-6"
      :class="selectedTenant && isDesktop ? 'lg:grid-cols-[1fr_minmax(580px,640px)]' : ''"
    >
      <!-- Tenant list -->
      <div class="min-w-0 rounded-md border">
        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center gap-2 py-12 text-muted-foreground">
          <Loader2 class="size-4 animate-spin" />
          Loading tenants...
        </div>

        <!-- Empty (no tenants) -->
        <div v-else-if="tenants.length === 0" class="py-12 text-center text-muted-foreground">
          <Building2 class="mx-auto size-12 text-muted-foreground/50" />
          <h3 class="mt-4 text-lg font-semibold">No tenants found</h3>
          <p class="mt-1 text-sm">
            Create a tenant to organize your workspaces and teams.
          </p>
          <Button variant="outline" size="sm" class="mt-4" @click="openCreateDialog">
            <Plus class="mr-2 size-4" />
            Create Tenant
          </Button>
        </div>

        <!-- Empty (search has no results) -->
        <div v-else-if="filteredTenants.length === 0" class="py-12 text-center text-muted-foreground">
          <Search class="mx-auto size-12 text-muted-foreground/50" />
          <h3 class="mt-4 text-lg font-semibold">No matching tenants</h3>
          <p class="mt-1 text-sm">No tenants match "{{ searchQuery }}".</p>
        </div>

        <!-- Tenant rows -->
        <div v-else role="list" aria-label="Tenants" class="divide-y">
          <div
            v-for="tenant in filteredTenants"
            :key="tenant.id"
            role="listitem"
            class="flex items-center gap-2 px-4 py-2.5 transition-colors hover:bg-muted/50 cursor-pointer"
            :class="[
              selectedTenant?.id === tenant.id ? 'bg-muted' : '',
            ]"
            :aria-label="`Select tenant ${tenant.name}`"
            :aria-selected="selectedTenant?.id === tenant.id"
            @click="selectTenant(tenant)"
          >
            <Building2 class="size-4 shrink-0 text-muted-foreground" />
            <span class="flex-1 truncate text-sm font-medium">{{ tenant.name }}</span>
            <Button
              variant="ghost"
              size="icon"
              class="size-7 shrink-0 text-destructive hover:text-destructive"
              title="Delete tenant"
              :aria-label="`Delete tenant ${tenant.name}`"
              @click.stop="confirmDelete(tenant)"
            >
              <Trash2 class="size-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <!-- Desktop detail panel (right side of grid) -->
      <Card v-if="selectedTenant && isDesktop" class="sticky top-6 self-start overflow-y-auto max-h-[calc(100vh-8rem)]">
        <CardContent class="pt-6">
          <SettingsTenantDetailPanel
            :tenant="selectedTenant"
            :members="members"
            :members-loading="membersLoading"
            :adding-member="addingMember"
            :new-member-id="newMemberId"
            :new-member-role="newMemberRole"
            show-close
            @close="closeDetails"
            @update:new-member-id="newMemberId = $event"
            @update:new-member-role="newMemberRole = $event"
            @add-member="handleAddMember"
            @remove-member="confirmRemoveMember"
          />
        </CardContent>
      </Card>
    </div>

    <!-- Mobile detail sheet -->
    <Sheet v-model:open="sheetOpen">
      <SheetContent side="right" class="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Tenant Details</SheetTitle>
          <SheetDescription>Manage tenant members</SheetDescription>
        </SheetHeader>
        <div v-if="selectedTenant" class="mt-6">
          <SettingsTenantDetailPanel
            :tenant="selectedTenant"
            :members="members"
            :members-loading="membersLoading"
            :adding-member="addingMember"
            :new-member-id="newMemberId"
            :new-member-role="newMemberRole"
            @close="closeDetails"
            @update:new-member-id="newMemberId = $event"
            @update:new-member-role="newMemberRole = $event"
            @add-member="handleAddMember"
            @remove-member="confirmRemoveMember"
          />
        </div>
      </SheetContent>
    </Sheet>

    <!-- Create Tenant Dialog -->
    <Dialog v-model:open="createDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Tenant</DialogTitle>
          <DialogDescription>
            Enter a name for the new tenant.
          </DialogDescription>
        </DialogHeader>
        <form class="space-y-4" @submit.prevent="handleCreate">
          <div class="space-y-2">
            <Label for="tenant-name">Name <span class="text-destructive">*</span></Label>
            <Input
              id="tenant-name"
              v-model="createFormName"
              placeholder="e.g. Acme Corp"
              :disabled="creating"
            />
          </div>
          <DialogFooter>
            <DialogClose as-child>
              <Button type="button" variant="outline" :disabled="creating">Cancel</Button>
            </DialogClose>
            <Button type="submit" :disabled="creating || !createFormName.trim()">
              <Loader2 v-if="creating" class="mr-2 size-4 animate-spin" />
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
          <DialogTitle>Delete Tenant</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete
            <span class="font-semibold">{{ tenantToDelete?.name }}</span>? This action cannot be
            undone. All workspaces, groups, and API keys within this tenant will also be permanently deleted.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline" :disabled="deleting">Cancel</Button>
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
            Are you sure you want to remove user "{{ memberToRemove?.user_id }}" from "{{ selectedTenant?.name }}"?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose as-child>
            <Button variant="outline" :disabled="removingMember">Cancel</Button>
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
