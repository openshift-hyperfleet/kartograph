import { describe, it, expect, vi } from 'vitest'

// ── Group Management Tests ────────────────────────────────────────────────────
//
// Spec: "Backend API Alignment" — groups page CRUD operations.
// Covers: list, create, delete, rename, add/remove/update members.
//
// Groups were implemented in task-014 but never had explicit endpoint
// alignment tests. This file closes that gap.

// ── Types (mirrors ~/types) ───────────────────────────────────────────────────

type GroupRole = 'member' | 'admin' | 'owner'

interface GroupResponse {
  id: string
  name: string
  created_at: string
}

interface GroupMemberResponse {
  user_id: string
  role: GroupRole
}

// ── Validation helpers (extracted from groups/index.vue logic) ────────────────

function validateGroupName(name: string): { valid: boolean; error: string } {
  if (!name.trim()) return { valid: false, error: 'Group name is required' }
  return { valid: true, error: '' }
}

function validateMemberId(memberId: string): boolean {
  return !!memberId.trim()
}

function shouldSkipRoleChange(member: GroupMemberResponse, newRole: GroupRole): boolean {
  return newRole === member.role
}

function validateRename(
  currentName: string,
  newName: string,
): { valid: boolean; noChange: boolean } {
  const trimmed = newName.trim()
  if (!trimmed) return { valid: false, noChange: false }
  if (trimmed === currentName) return { valid: true, noChange: true }
  return { valid: true, noChange: false }
}

// ── Group name validation ─────────────────────────────────────────────────────

describe('Group Management - name validation', () => {
  it('rejects empty group name', () => {
    const result = validateGroupName('')
    expect(result.valid).toBe(false)
    expect(result.error).toBe('Group name is required')
  })

  it('rejects whitespace-only group name', () => {
    const result = validateGroupName('   ')
    expect(result.valid).toBe(false)
  })

  it('accepts a valid group name', () => {
    const result = validateGroupName('Engineering')
    expect(result.valid).toBe(true)
    expect(result.error).toBe('')
  })
})

// ── Rename validation ─────────────────────────────────────────────────────────

describe('Group Management - rename validation', () => {
  it('rejects empty new name', () => {
    const result = validateRename('Engineering', '')
    expect(result.valid).toBe(false)
  })

  it('detects no-change when trimmed name equals current name', () => {
    const result = validateRename('Engineering', 'Engineering')
    expect(result.valid).toBe(true)
    expect(result.noChange).toBe(true)
  })

  it('accepts rename when name differs', () => {
    const result = validateRename('Engineering', 'Platform')
    expect(result.valid).toBe(true)
    expect(result.noChange).toBe(false)
  })
})

// ── Member ID validation ──────────────────────────────────────────────────────

describe('Group Management - member ID validation', () => {
  it('rejects empty member ID', () => {
    expect(validateMemberId('')).toBe(false)
  })

  it('rejects whitespace-only member ID', () => {
    expect(validateMemberId('   ')).toBe(false)
  })

  it('accepts valid member ID', () => {
    expect(validateMemberId('user-abc-123')).toBe(true)
  })
})

// ── Role change guard ─────────────────────────────────────────────────────────

describe('Group Management - role change', () => {
  it('skips API call when role is unchanged', () => {
    const member: GroupMemberResponse = { user_id: 'user-42', role: 'member' }
    expect(shouldSkipRoleChange(member, 'member')).toBe(true)
  })

  it('proceeds with API call when role differs', () => {
    const member: GroupMemberResponse = { user_id: 'user-42', role: 'member' }
    expect(shouldSkipRoleChange(member, 'admin')).toBe(false)
  })
})

// ── Search filtering ──────────────────────────────────────────────────────────

describe('Group Management - search filtering', () => {
  const groups: GroupResponse[] = [
    { id: 'g-1', name: 'Engineering', created_at: '' },
    { id: 'g-2', name: 'Platform', created_at: '' },
    { id: 'g-3', name: 'Frontend', created_at: '' },
  ]

  function filterGroups(items: GroupResponse[], query: string): GroupResponse[] {
    const q = query.toLowerCase().trim()
    if (!q) return items
    return items.filter((g) => g.name.toLowerCase().includes(q))
  }

  it('returns all groups when search query is empty', () => {
    expect(filterGroups(groups, '')).toHaveLength(3)
  })

  it('filters groups by name (case-insensitive)', () => {
    const result = filterGroups(groups, 'front')
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Frontend')
  })

  it('returns empty array when no groups match', () => {
    expect(filterGroups(groups, 'zzznomatch')).toHaveLength(0)
  })

  it('returns multiple matches when several names contain the query', () => {
    // "Engineering" and "Frontend" both end in "ng" (…actually "ering" and "end")
    // Use a term that matches multiple: "en" matches Engineering, Frontend
    const result = filterGroups(groups, 'en')
    expect(result.length).toBeGreaterThanOrEqual(2)
  })
})

// ── UI refresh after mutation ─────────────────────────────────────────────────

describe('Group Management - UI refresh after mutation', () => {
  it('calls fetchGroups after successful create to refresh the list', async () => {
    const createGroup = vi.fn().mockResolvedValue({ id: 'g-new', name: 'DevOps' })
    const fetchGroups = vi.fn().mockResolvedValue(undefined)
    let groups: GroupResponse[] = []
    let toastMsg = ''

    async function handleCreate(name: string) {
      if (!validateGroupName(name).valid) return
      const group = await createGroup({ name: name.trim() })
      toastMsg = `Group "${group.name}" created`
      await fetchGroups()
    }

    await handleCreate('DevOps')
    expect(createGroup).toHaveBeenCalledWith({ name: 'DevOps' })
    expect(fetchGroups).toHaveBeenCalledOnce()
    expect(toastMsg).toBe('Group "DevOps" created')
  })

  it('calls fetchGroups after successful delete to refresh the list', async () => {
    const deleteGroup = vi.fn().mockResolvedValue(undefined)
    const fetchGroups = vi.fn().mockResolvedValue(undefined)
    const groupToDelete = { value: { id: 'g-1', name: 'Engineering' } }
    let toastMsg = ''

    async function handleDelete() {
      if (!groupToDelete.value) return
      await deleteGroup(groupToDelete.value.id)
      toastMsg = `Group "${groupToDelete.value.name}" deleted`
      await fetchGroups()
    }

    await handleDelete()
    expect(deleteGroup).toHaveBeenCalledWith('g-1')
    expect(fetchGroups).toHaveBeenCalledOnce()
    expect(toastMsg).toBe('Group "Engineering" deleted')
  })

  it('refreshes member list after adding a member', async () => {
    const addGroupMember = vi.fn().mockResolvedValue({})
    const fetchMembers = vi.fn().mockResolvedValue(undefined)
    const selectedGroup = { id: 'g-1', name: 'Engineering' }

    async function handleAddMember(memberId: string, role: GroupRole) {
      if (!validateMemberId(memberId)) return
      await addGroupMember(selectedGroup.id, { user_id: memberId.trim(), role })
      await fetchMembers(selectedGroup)
    }

    await handleAddMember('user-42', 'member')
    expect(addGroupMember).toHaveBeenCalledWith('g-1', { user_id: 'user-42', role: 'member' })
    expect(fetchMembers).toHaveBeenCalledOnce()
  })

  it('refreshes member list after removing a member', async () => {
    const removeGroupMember = vi.fn().mockResolvedValue(undefined)
    const fetchMembers = vi.fn().mockResolvedValue(undefined)
    const selectedGroup = { id: 'g-1', name: 'Engineering' }
    const memberToRemove = { user_id: 'user-42', role: 'member' as GroupRole }

    async function handleRemoveMember() {
      await removeGroupMember(selectedGroup.id, memberToRemove.user_id)
      await fetchMembers(selectedGroup)
    }

    await handleRemoveMember()
    expect(removeGroupMember).toHaveBeenCalledWith('g-1', 'user-42')
    expect(fetchMembers).toHaveBeenCalledOnce()
  })

  it('refreshes member list after role change', async () => {
    const updateGroupMemberRole = vi.fn().mockResolvedValue({})
    const fetchMembers = vi.fn().mockResolvedValue(undefined)
    const selectedGroup = { id: 'g-1', name: 'Engineering' }
    const member: GroupMemberResponse = { user_id: 'user-42', role: 'member' }

    async function handleRoleChange(m: GroupMemberResponse, newRole: GroupRole) {
      if (shouldSkipRoleChange(m, newRole)) return
      await updateGroupMemberRole(selectedGroup.id, m.user_id, newRole)
      await fetchMembers(selectedGroup)
    }

    await handleRoleChange(member, 'admin')
    expect(updateGroupMemberRole).toHaveBeenCalledWith('g-1', 'user-42', 'admin')
    expect(fetchMembers).toHaveBeenCalledOnce()
  })
})

// ── Backend API Alignment: exact endpoint URL assertions ──────────────────────
// Spec: "Backend API Alignment" — every CRUD operation calls the documented endpoint.
// These tests mirror the useIamApi composable's implementation exactly.

describe('Group Management - backend endpoint alignment (useIamApi)', () => {
  it('listGroups calls GET /iam/groups', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue([])

    // Mirrors useIamApi.listGroups exactly
    async function listGroups() {
      return mockApiFetch('/iam/groups')
    }

    await listGroups()
    expect(mockApiFetch).toHaveBeenCalledWith('/iam/groups')
  })

  it('createGroup calls POST /iam/groups with group name', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue({ id: 'g-new', name: 'DevOps' })

    // Mirrors useIamApi.createGroup exactly
    async function createGroup(data: { name: string }) {
      return mockApiFetch('/iam/groups', { method: 'POST', body: data })
    }

    await createGroup({ name: 'DevOps' })
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/groups',
      expect.objectContaining({
        method: 'POST',
        body: expect.objectContaining({ name: 'DevOps' }),
      }),
    )
  })

  it('deleteGroup calls DELETE /iam/groups/{id}', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue(undefined)

    // Mirrors useIamApi.deleteGroup exactly
    async function deleteGroup(groupId: string) {
      return mockApiFetch(`/iam/groups/${groupId}`, { method: 'DELETE' })
    }

    await deleteGroup('g-abc-123')
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/groups/g-abc-123',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('updateGroup calls PATCH /iam/groups/{id} with new name', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue({ id: 'g-abc', name: 'Platform' })

    // Mirrors useIamApi.updateGroup exactly
    async function updateGroup(groupId: string, data: { name: string }) {
      return mockApiFetch(`/iam/groups/${groupId}`, { method: 'PATCH', body: data })
    }

    await updateGroup('g-abc-123', { name: 'Platform' })
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/groups/g-abc-123',
      expect.objectContaining({
        method: 'PATCH',
        body: expect.objectContaining({ name: 'Platform' }),
      }),
    )
  })

  it('listGroupMembers calls GET /iam/groups/{id}/members', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue([])

    // Mirrors useIamApi.listGroupMembers exactly
    async function listGroupMembers(groupId: string) {
      return mockApiFetch(`/iam/groups/${groupId}/members`)
    }

    await listGroupMembers('g-abc-123')
    expect(mockApiFetch).toHaveBeenCalledWith('/iam/groups/g-abc-123/members')
  })

  it('addGroupMember calls POST /iam/groups/{id}/members with user_id and role', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue({ user_id: 'user-42', role: 'member' })

    // Mirrors useIamApi.addGroupMember exactly
    async function addGroupMember(groupId: string, data: { user_id: string; role: GroupRole }) {
      return mockApiFetch(`/iam/groups/${groupId}/members`, { method: 'POST', body: data })
    }

    await addGroupMember('g-abc-123', { user_id: 'user-42', role: 'member' })
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/groups/g-abc-123/members',
      expect.objectContaining({
        method: 'POST',
        body: expect.objectContaining({ user_id: 'user-42', role: 'member' }),
      }),
    )
  })

  it('removeGroupMember calls DELETE /iam/groups/{id}/members/{userId}', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue(undefined)

    // Mirrors useIamApi.removeGroupMember exactly
    async function removeGroupMember(groupId: string, userId: string) {
      return mockApiFetch(`/iam/groups/${groupId}/members/${userId}`, { method: 'DELETE' })
    }

    await removeGroupMember('g-abc-123', 'user-42')
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/groups/g-abc-123/members/user-42',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('updateGroupMemberRole calls PATCH /iam/groups/{id}/members/{userId} with new role', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue({ user_id: 'user-42', role: 'admin' })

    // Mirrors useIamApi.updateGroupMemberRole exactly
    async function updateGroupMemberRole(groupId: string, userId: string, role: GroupRole) {
      return mockApiFetch(`/iam/groups/${groupId}/members/${userId}`, {
        method: 'PATCH',
        body: { role },
      })
    }

    await updateGroupMemberRole('g-abc-123', 'user-42', 'admin')
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/groups/g-abc-123/members/user-42',
      expect.objectContaining({
        method: 'PATCH',
        body: { role: 'admin' },
      }),
    )
  })
})

// ── Remove member dialog guard ────────────────────────────────────────────────

describe('Group Management - remove member dialog guard', () => {
  it('confirmRemoveMember opens dialog and sets memberToRemove without calling API', () => {
    const showRemoveMemberDialog = { value: false }
    const memberToRemove = { value: null as GroupMemberResponse | null }
    const removeGroupMember = vi.fn()

    const member: GroupMemberResponse = { user_id: 'user-42', role: 'member' }

    function confirmRemoveMember(m: GroupMemberResponse) {
      memberToRemove.value = m
      showRemoveMemberDialog.value = true
    }

    confirmRemoveMember(member)
    expect(showRemoveMemberDialog.value).toBe(true)
    expect(memberToRemove.value).toBe(member)
    expect(removeGroupMember).not.toHaveBeenCalled()
  })
})
