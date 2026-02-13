<script setup lang="ts">
import {
  FolderTree, Users, UserPlus, UserCircle, Pencil, Check, X, Trash2, Loader2,
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
import type { WorkspaceResponse, WorkspaceMemberResponse, WorkspaceMemberType, WorkspaceRole } from '~/types'

const props = defineProps<{
  workspace: WorkspaceResponse
  members: WorkspaceMemberResponse[]
  membersLoading: boolean
  editingName: boolean
  editNameValue: string
  savingName: boolean
  addingMember: boolean
  newMemberId: string
  newMemberType: WorkspaceMemberType
  newMemberRole: WorkspaceRole
  updatingRoleFor: string | null
  /** Whether to show the close button (hidden inside Sheet since Sheet has its own) */
  showClose?: boolean
}>()

const emit = defineEmits<{
  close: []
  startRename: []
  cancelRename: []
  'update:editNameValue': [value: string]
  rename: []
  'update:newMemberId': [value: string]
  'update:newMemberType': [value: WorkspaceMemberType]
  'update:newMemberRole': [value: WorkspaceRole]
  addMember: []
  removeMember: [member: WorkspaceMemberResponse]
  roleChange: [member: WorkspaceMemberResponse, role: WorkspaceRole]
}>()

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h3 class="flex items-center gap-2 text-base font-semibold">
        <FolderTree class="size-4" />
        {{ workspace.name }}
      </h3>
      <div class="flex items-center gap-1">
        <Button
          v-if="!editingName"
          variant="ghost"
          size="icon"
          class="size-7 text-muted-foreground hover:text-foreground"
          title="Rename workspace"
          @click="emit('startRename')"
        >
          <Pencil class="size-3.5" />
        </Button>
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

    <!-- Rename inline -->
    <div v-if="editingName" class="flex items-center gap-2">
      <Input
        :model-value="editNameValue"
        class="h-8 text-sm"
        @update:model-value="emit('update:editNameValue', $event as string)"
        @keydown.enter="emit('rename')"
        @keydown.escape="emit('cancelRename')"
      />
      <Button
        variant="ghost"
        size="icon"
        class="size-7 shrink-0 text-green-600 hover:text-green-700"
        :disabled="savingName || !editNameValue.trim()"
        @click="emit('rename')"
      >
        <Loader2 v-if="savingName" class="size-3.5 animate-spin" />
        <Check v-else class="size-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        class="size-7 shrink-0"
        :disabled="savingName"
        @click="emit('cancelRename')"
      >
        <X class="size-3.5" />
      </Button>
    </div>

    <!-- Metadata -->
    <div class="space-y-2 text-sm">
      <div>
        <span class="text-muted-foreground">ID</span>
        <CopyableText :text="workspace.id" label="Workspace ID copied" />
      </div>
      <div>
        <span class="text-muted-foreground">Tenant ID</span>
        <CopyableText :text="workspace.tenant_id" label="Tenant ID copied" />
      </div>
      <div>
        <span class="text-muted-foreground">Parent</span>
        <CopyableText v-if="workspace.parent_workspace_id" :text="workspace.parent_workspace_id" label="Parent ID copied" />
        <p v-else class="font-mono text-xs">None (root)</p>
      </div>
      <div class="flex items-center gap-4">
        <div>
          <span class="text-muted-foreground">Root</span>
          <p>
            <Badge :variant="workspace.is_root ? 'default' : 'secondary'" class="text-[10px]">
              {{ workspace.is_root ? 'Yes' : 'No' }}
            </Badge>
          </p>
        </div>
      </div>
      <div>
        <span class="text-muted-foreground">Created</span>
        <p>{{ formatDate(workspace.created_at) }}</p>
      </div>
      <div>
        <span class="text-muted-foreground">Updated</span>
        <p>{{ formatDate(workspace.updated_at) }}</p>
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
          <Label for="ws-panel-member-id">Member ID <span class="text-destructive">*</span></Label>
          <Input
            id="ws-panel-member-id"
            :model-value="newMemberId"
            placeholder="User or group ID..."
            @update:model-value="emit('update:newMemberId', $event as string)"
          />
        </div>
        <div class="flex gap-2">
          <div class="flex-1 space-y-1.5">
            <Label>Type</Label>
            <Select
              :model-value="newMemberType"
              @update:model-value="emit('update:newMemberType', $event as WorkspaceMemberType)"
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="group">Group</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="flex-1 space-y-1.5">
            <Label>Role</Label>
            <Select
              :model-value="newMemberRole"
              @update:model-value="emit('update:newMemberRole', $event as WorkspaceRole)"
            >
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
              <TableHead>Member</TableHead>
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
            <TableRow v-for="member in members" v-else :key="`${member.member_type}-${member.member_id}`">
              <TableCell>
                <div class="flex items-center gap-1.5 min-w-0">
                  <UserCircle class="size-4 shrink-0 text-muted-foreground" />
                  <CopyableText :text="member.member_id" label="Member ID copied" />
                  <Badge variant="outline" class="shrink-0 text-[10px]">
                    {{ member.member_type }}
                  </Badge>
                </div>
              </TableCell>
              <TableCell>
                <Select
                  :model-value="member.role"
                  :disabled="updatingRoleFor === member.member_id"
                  @update:model-value="(val: WorkspaceRole) => emit('roleChange', member, val)"
                >
                  <SelectTrigger class="h-8 w-[100px] text-sm">
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
                  class="size-7 text-destructive hover:text-destructive"
                  title="Remove member"
                  :aria-label="`Remove ${member.member_type} ${member.member_id}`"
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
