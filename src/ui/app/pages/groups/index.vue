<script setup lang="ts">
import { Users, Plus, Search, Trash2, ChevronDown, ChevronRight, UserCircle } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { ref, reactive } from 'vue'
import type { GroupResponse } from '~/types'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

const { createGroup, getGroup, deleteGroup } = useIamApi()
const { extractErrorMessage } = useErrorHandler()

// ── State ──────────────────────────────────────────────────────────────────

const groups = ref<GroupResponse[]>([])
const expandedGroupIds = ref<Set<string>>(new Set())

const createDialogOpen = ref(false)
const createForm = reactive({ name: '' })
const isCreating = ref(false)

const lookupId = ref('')
const isLookingUp = ref(false)

const deleteDialogOpen = ref(false)
const groupToDelete = ref<GroupResponse | null>(null)
const isDeleting = ref(false)

// ── Helpers ────────────────────────────────────────────────────────────────

function toggleExpand(groupId: string) {
  if (expandedGroupIds.value.has(groupId)) {
    expandedGroupIds.value.delete(groupId)
  } else {
    expandedGroupIds.value.add(groupId)
  }
}

function isExpanded(groupId: string): boolean {
  return expandedGroupIds.value.has(groupId)
}

// ── Create ─────────────────────────────────────────────────────────────────

async function handleCreate() {
  if (!createForm.name.trim()) {
    toast.error('Group name is required')
    return
  }
  isCreating.value = true
  try {
    const group = await createGroup({ name: createForm.name.trim() })
    groups.value.unshift(group)
    createForm.name = ''
    toast.success(`Group "${group.name}" created`)
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
    groups.value = groups.value.filter((g) => g.id !== groupToDelete.value!.id)
    expandedGroupIds.value.delete(groupToDelete.value.id)
    toast.success(`Group "${name}" deleted`)
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

// ── Refresh a single group ─────────────────────────────────────────────────

async function refreshGroup(groupId: string) {
  try {
    const updated = await getGroup(groupId)
    const idx = groups.value.findIndex((g) => g.id === groupId)
    if (idx !== -1) {
      groups.value[idx] = updated
    }
  } catch {
    toast.error('Failed to refresh group')
  }
}
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
        <DialogTrigger as-child>
          <Button>
            <Plus class="mr-2 size-4" />
            Create Group
          </Button>
        </DialogTrigger>
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create Group</DialogTitle>
            <DialogDescription>
              Create a new group to organize users and manage permissions.
            </DialogDescription>
          </DialogHeader>
          <form @submit.prevent="handleCreate" class="space-y-4">
            <div class="space-y-2">
              <Label for="group-name">Name</Label>
              <Input
                id="group-name"
                v-model="createForm.name"
                placeholder="e.g. Engineering Team"
                :disabled="isCreating"
              />
            </div>
            <DialogFooter>
              <DialogClose as-child>
                <Button type="button" variant="outline" :disabled="isCreating">Cancel</Button>
              </DialogClose>
              <Button type="submit" :disabled="isCreating || !createForm.name.trim()">
                {{ isCreating ? 'Creating...' : 'Create' }}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>

    <Separator />

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

    <!-- Groups List -->
    <div v-if="groups.length === 0" class="py-12 text-center">
      <Users class="mx-auto size-12 text-muted-foreground/50" />
      <h3 class="mt-4 text-lg font-semibold">No groups loaded</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        Create a new group or look up an existing one by ID.
      </p>
      <p class="mt-2 text-xs text-muted-foreground/70">
        The API does not provide a list endpoint for groups. Use the lookup above to fetch a group by its ID.
      </p>
    </div>

    <div v-else class="space-y-4">
      <Card v-for="group in groups" :key="group.id">
        <CardHeader class="cursor-pointer" @click="toggleExpand(group.id)">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <component
                :is="isExpanded(group.id) ? ChevronDown : ChevronRight"
                class="size-4 text-muted-foreground"
              />
              <div>
                <CardTitle class="text-base">{{ group.name }}</CardTitle>
                <p class="mt-0.5 font-mono text-xs text-muted-foreground">{{ group.id }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Badge variant="secondary">
                {{ group.members.length }} {{ group.members.length === 1 ? 'member' : 'members' }}
              </Badge>
              <Button
                variant="ghost"
                size="icon"
                class="text-destructive hover:bg-destructive/10 hover:text-destructive"
                @click.stop="confirmDelete(group)"
              >
                <Trash2 class="size-4" />
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent v-if="isExpanded(group.id)">
          <Separator class="mb-4" />
          <div v-if="group.members.length === 0" class="py-4 text-center text-sm text-muted-foreground">
            No members in this group yet.
          </div>
          <Table v-else>
            <TableHeader>
              <TableRow>
                <TableHead>User ID</TableHead>
                <TableHead>Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="member in group.members" :key="member.user_id">
                <TableCell class="font-mono text-sm">
                  <div class="flex items-center gap-2">
                    <UserCircle class="size-4 text-muted-foreground" />
                    {{ member.user_id }}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge :variant="member.role === 'admin' ? 'default' : 'secondary'">
                    {{ member.role }}
                  </Badge>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>

        <CardFooter v-if="isExpanded(group.id)" class="justify-end">
          <Button variant="ghost" size="sm" @click="refreshGroup(group.id)">
            Refresh
          </Button>
        </CardFooter>
      </Card>
    </div>

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
  </div>
</template>
