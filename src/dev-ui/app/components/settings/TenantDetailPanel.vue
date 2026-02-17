<script setup lang="ts">
import {
  Building2, Users, UserPlus, UserCircle, X, Trash2, Loader2,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty,
} from '@/components/ui/table'
import { Separator } from '@/components/ui/separator'
import { CopyableText } from '@/components/ui/copyable-text'
import { UserIdDisplay } from '@/components/ui/user-id'
import type { TenantResponse, TenantMemberResponse } from '~/types'

const { userId: currentUserId } = useCurrentUser()

const props = defineProps<{
  tenant: TenantResponse
  members: TenantMemberResponse[]
  membersLoading: boolean
  addingMember: boolean
  newMemberId: string
  newMemberRole: 'admin' | 'member'
  /** Whether to show the close button (hidden inside Sheet since Sheet has its own) */
  showClose?: boolean
}>()

const emit = defineEmits<{
  close: []
  'update:newMemberId': [value: string]
  'update:newMemberRole': [value: 'admin' | 'member']
  addMember: []
  removeMember: [member: TenantMemberResponse]
}>()
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h3 class="flex items-center gap-2 text-base font-semibold">
        <Building2 class="size-4" />
        {{ tenant.name }}
      </h3>
      <div class="flex items-center gap-1">
        <Button
          v-if="showClose"
          variant="ghost"
          size="icon"
          class="size-7"
          @click="emit('close')"
        >
          <X class="size-4" />
        </Button>
      </div>
    </div>

    <!-- Metadata -->
    <div class="space-y-2 text-sm">
      <div>
        <span class="text-muted-foreground">ID</span>
        <CopyableText :text="tenant.id" label="Tenant ID copied" />
      </div>
    </div>

    <Separator />

    <!-- Members section -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h4 class="flex items-center gap-2 text-sm font-semibold">
          <Users class="size-4" />
          Members
        </h4>
        <Badge v-if="members.length > 0" variant="secondary">
          {{ members.length }}
        </Badge>
      </div>

      <!-- Add member form (stacked for panel width) -->
      <div class="space-y-2 mb-4">
        <div class="space-y-1.5">
          <div class="flex items-center justify-between">
            <Label for="tenant-panel-member-id">User ID <span class="text-destructive">*</span></Label>
            <button
              v-if="currentUserId && newMemberId !== currentUserId"
              type="button"
              class="text-xs text-primary hover:underline"
              @click="emit('update:newMemberId', currentUserId)"
            >
              Add myself
            </button>
          </div>
          <Input
            id="tenant-panel-member-id"
            :model-value="newMemberId"
            placeholder="Enter user ID..."
            @update:model-value="emit('update:newMemberId', $event as string)"
          />
        </div>
        <div class="space-y-1.5">
          <Label>Role</Label>
          <Select
            :model-value="newMemberRole"
            @update:model-value="emit('update:newMemberRole', $event as 'admin' | 'member')"
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="admin">Admin</SelectItem>
              <SelectItem value="member">Member</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          class="w-full"
          :disabled="addingMember || !newMemberId.trim()"
          @click="emit('addMember')"
        >
          <Loader2 v-if="addingMember" class="mr-2 size-4 animate-spin" />
          <UserPlus v-else class="mr-2 size-4" />
          Add Member
        </Button>
      </div>

      <!-- Members table -->
      <div class="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Role</TableHead>
              <TableHead class="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="membersLoading">
              <TableCell colspan="3" class="h-16 text-center">
                <div class="flex items-center justify-center gap-2 text-muted-foreground">
                  <Loader2 class="size-4 animate-spin" />
                  Loading...
                </div>
              </TableCell>
            </TableRow>
            <TableEmpty v-else-if="members.length === 0" :colspan="3">
              No members yet.
            </TableEmpty>
            <TableRow v-for="member in members" v-else :key="member.user_id">
              <TableCell>
                <div class="flex items-center gap-1.5 min-w-0">
                  <UserCircle class="size-4 shrink-0 text-muted-foreground" />
                  <UserIdDisplay :user-id="member.user_id" label="User ID copied" />
                </div>
              </TableCell>
              <TableCell>
                <Badge :variant="member.role === 'admin' ? 'default' : 'secondary'">
                  {{ member.role }}
                </Badge>
              </TableCell>
              <TableCell class="text-right">
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-7 text-destructive hover:text-destructive"
                  title="Remove member"
                  :aria-label="`Remove user ${member.user_id}`"
                  @click="emit('removeMember', member)"
                >
                  <Trash2 class="size-3.5" />
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  </div>
</template>
