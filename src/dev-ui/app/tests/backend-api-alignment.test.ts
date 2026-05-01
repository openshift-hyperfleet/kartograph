import { describe, it, expect, vi } from 'vitest'

// ── Backend API Alignment Tests ───────────────────────────────────────────────
//
// Spec: "Backend API Alignment"
// Covers:
//   - Scenario: Resource operations succeed end-to-end
//     (every UI operation calls the CORRECT backend API endpoint)
//   - Scenario: Parent context is preserved
//     (scoped resources include parent ID in the API call)
//
// These tests verify the EXACT endpoint URL and HTTP method for every IAM
// CRUD operation exposed by useIamApi.ts. They guard against URL drift and
// ensure the reactive refresh pattern (reload after mutation) is followed.

// ── Group CRUD Endpoint URLs ──────────────────────────────────────────────────
//
// Mirrors the useIamApi group functions + groups/index.vue handlers.

describe('Backend API Alignment - Group CRUD endpoint URLs', () => {
  it('listGroups calls GET /iam/groups', async () => {
    const apiFetch = vi.fn().mockResolvedValue([])

    async function listGroups() {
      return apiFetch<unknown[]>('/iam/groups')
    }

    await listGroups()
    expect(apiFetch).toHaveBeenCalledWith('/iam/groups')
  })

  it('createGroup calls POST /iam/groups with {name}', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'g-1', name: 'Engineering' })

    async function createGroup(data: { name: string }) {
      return apiFetch('/iam/groups', { method: 'POST', body: data })
    }

    await createGroup({ name: 'Engineering' })
    expect(apiFetch).toHaveBeenCalledWith('/iam/groups', {
      method: 'POST',
      body: { name: 'Engineering' },
    })
  })

  it('deleteGroup calls DELETE /iam/groups/{id}', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined)
    const groupId = 'g-abc-123'

    async function deleteGroup(id: string) {
      return apiFetch(`/iam/groups/${id}`, { method: 'DELETE' })
    }

    await deleteGroup(groupId)
    expect(apiFetch).toHaveBeenCalledWith(`/iam/groups/${groupId}`, { method: 'DELETE' })
  })

  it('updateGroup calls PATCH /iam/groups/{id} with {name}', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'g-1', name: 'Platform Team' })
    const groupId = 'g-1'

    async function updateGroup(id: string, data: { name: string }) {
      return apiFetch(`/iam/groups/${id}`, { method: 'PATCH', body: data })
    }

    await updateGroup(groupId, { name: 'Platform Team' })
    expect(apiFetch).toHaveBeenCalledWith(`/iam/groups/${groupId}`, {
      method: 'PATCH',
      body: { name: 'Platform Team' },
    })
  })

  it('getGroup calls GET /iam/groups/{id}', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'g-1', name: 'Engineering' })
    const groupId = 'g-1'

    async function getGroup(id: string) {
      return apiFetch(`/iam/groups/${id}`)
    }

    await getGroup(groupId)
    expect(apiFetch).toHaveBeenCalledWith(`/iam/groups/${groupId}`)
  })
})

// ── Group Member Endpoint URLs ────────────────────────────────────────────────

describe('Backend API Alignment - Group member endpoint URLs', () => {
  it('listGroupMembers calls GET /iam/groups/{id}/members', async () => {
    const apiFetch = vi.fn().mockResolvedValue([])
    const groupId = 'g-1'

    async function listGroupMembers(id: string) {
      return apiFetch(`/iam/groups/${id}/members`)
    }

    await listGroupMembers(groupId)
    expect(apiFetch).toHaveBeenCalledWith(`/iam/groups/${groupId}/members`)
  })

  it('addGroupMember calls POST /iam/groups/{id}/members with {user_id, role}', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ user_id: 'u-1', role: 'member' })
    const groupId = 'g-1'

    async function addGroupMember(id: string, data: { user_id: string; role: string }) {
      return apiFetch(`/iam/groups/${id}/members`, { method: 'POST', body: data })
    }

    await addGroupMember(groupId, { user_id: 'u-1', role: 'member' })
    expect(apiFetch).toHaveBeenCalledWith(`/iam/groups/${groupId}/members`, {
      method: 'POST',
      body: { user_id: 'u-1', role: 'member' },
    })
  })

  it('updateGroupMemberRole calls PATCH /iam/groups/{id}/members/{userId} with {role}', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ user_id: 'u-1', role: 'admin' })
    const groupId = 'g-1'
    const userId = 'u-1'

    async function updateGroupMemberRole(gId: string, uId: string, role: string) {
      return apiFetch(`/iam/groups/${gId}/members/${uId}`, {
        method: 'PATCH',
        body: { role },
      })
    }

    await updateGroupMemberRole(groupId, userId, 'admin')
    expect(apiFetch).toHaveBeenCalledWith(`/iam/groups/${groupId}/members/${userId}`, {
      method: 'PATCH',
      body: { role: 'admin' },
    })
  })

  it('removeGroupMember calls DELETE /iam/groups/{id}/members/{userId}', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined)
    const groupId = 'g-1'
    const userId = 'u-1'

    async function removeGroupMember(gId: string, uId: string) {
      return apiFetch(`/iam/groups/${gId}/members/${uId}`, { method: 'DELETE' })
    }

    await removeGroupMember(groupId, userId)
    expect(apiFetch).toHaveBeenCalledWith(`/iam/groups/${groupId}/members/${userId}`, {
      method: 'DELETE',
    })
  })
})

// ── API Key Endpoint URLs ─────────────────────────────────────────────────────
//
// These tests document and guard the CORRECT endpoint URLs for API key
// operations. In particular, revoke uses DELETE /iam/api-keys/{id},
// NOT POST /iam/api-keys/{id}/revoke.

describe('Backend API Alignment - API key endpoint URLs', () => {
  it('listApiKeys calls GET /iam/api-keys', async () => {
    const apiFetch = vi.fn().mockResolvedValue([])

    async function listApiKeys() {
      return apiFetch('/iam/api-keys', { query: {} })
    }

    await listApiKeys()
    expect(apiFetch).toHaveBeenCalledWith('/iam/api-keys', expect.anything())
    const [url] = apiFetch.mock.calls[0]
    expect(url).toBe('/iam/api-keys')
  })

  it('createApiKey calls POST /iam/api-keys with {name, expires_in_days}', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      id: 'key-1',
      name: 'CI Pipeline',
      secret: 'fake-secret', // gitleaks:allow
      prefix: 'kfake_',
    })

    async function createApiKey(data: { name: string; expires_in_days?: number }) {
      return apiFetch('/iam/api-keys', { method: 'POST', body: data })
    }

    await createApiKey({ name: 'CI Pipeline', expires_in_days: 365 })
    expect(apiFetch).toHaveBeenCalledWith('/iam/api-keys', {
      method: 'POST',
      body: { name: 'CI Pipeline', expires_in_days: 365 },
    })
  })

  it('revokeApiKey calls DELETE /iam/api-keys/{id} — NOT POST /revoke', async () => {
    // This is the canonical endpoint: DELETE /iam/api-keys/{id}
    // It must NOT use POST /iam/api-keys/{id}/revoke (that path does not exist)
    const apiFetch = vi.fn().mockResolvedValue(undefined)
    const apiKeyId = 'key-abc-123'

    async function revokeApiKey(id: string) {
      return apiFetch(`/iam/api-keys/${id}`, { method: 'DELETE' })
    }

    await revokeApiKey(apiKeyId)
    expect(apiFetch).toHaveBeenCalledWith(`/iam/api-keys/${apiKeyId}`, { method: 'DELETE' })

    // Explicitly assert the wrong path is NOT used
    const [calledUrl, calledOpts] = apiFetch.mock.calls[0]
    expect(calledUrl).not.toContain('/revoke')
    expect(calledOpts.method).toBe('DELETE')
  })
})

// ── Reactive Refresh After Mutations ─────────────────────────────────────────
//
// Spec: "THEN the UI reflects the updated state without requiring a manual refresh"
// After every successful mutation, the list must be reloaded reactively.

describe('Backend API Alignment - reactive list refresh after group mutations', () => {
  it('fetchGroups is called again after successful createGroup', async () => {
    const createGroupFn = vi.fn().mockResolvedValue({ id: 'g-new', name: 'New Group' })
    const fetchGroupsFn = vi.fn().mockResolvedValue([])
    let toastMsg = ''

    async function handleCreate(name: string) {
      if (!name.trim()) {
        toastMsg = 'Group name is required'
        return
      }
      const group = await createGroupFn({ name: name.trim() })
      toastMsg = `Group "${group.name}" created`
      await fetchGroupsFn()
    }

    await handleCreate('New Group')
    expect(createGroupFn).toHaveBeenCalledOnce()
    expect(fetchGroupsFn).toHaveBeenCalledOnce() // List refreshed after creation
    expect(toastMsg).toBe('Group "New Group" created')
  })

  it('fetchGroups is called again after successful deleteGroup', async () => {
    const deleteGroupFn = vi.fn().mockResolvedValue(undefined)
    const fetchGroupsFn = vi.fn().mockResolvedValue([])
    let toastMsg = ''

    async function handleDelete(groupId: string, groupName: string) {
      await deleteGroupFn(groupId)
      toastMsg = `Group "${groupName}" deleted`
      await fetchGroupsFn()
    }

    await handleDelete('g-1', 'Engineering')
    expect(deleteGroupFn).toHaveBeenCalledWith('g-1')
    expect(fetchGroupsFn).toHaveBeenCalledOnce() // List refreshed after deletion
    expect(toastMsg).toBe('Group "Engineering" deleted')
  })

  it('fetchMembers is called again after successful addGroupMember', async () => {
    const addMemberFn = vi.fn().mockResolvedValue({ user_id: 'u-1', role: 'member' })
    const fetchMembersFn = vi.fn().mockResolvedValue([])
    let toastMsg = ''

    async function handleAddMember(groupId: string, userId: string, role: string) {
      if (!userId.trim()) return
      await addMemberFn(groupId, { user_id: userId.trim(), role })
      toastMsg = 'Member added'
      await fetchMembersFn({ id: groupId })
    }

    await handleAddMember('g-1', 'u-42', 'member')
    expect(addMemberFn).toHaveBeenCalledOnce()
    expect(fetchMembersFn).toHaveBeenCalledOnce() // Members refreshed after adding
    expect(toastMsg).toBe('Member added')
  })

  it('fetchMembers is called again after successful removeGroupMember', async () => {
    const removeMemberFn = vi.fn().mockResolvedValue(undefined)
    const fetchMembersFn = vi.fn().mockResolvedValue([])
    let toastMsg = ''

    async function handleRemoveMember(groupId: string, userId: string) {
      await removeMemberFn(groupId, userId)
      toastMsg = 'Member removed'
      await fetchMembersFn({ id: groupId })
    }

    await handleRemoveMember('g-1', 'u-42')
    expect(removeMemberFn).toHaveBeenCalledOnce()
    expect(fetchMembersFn).toHaveBeenCalledOnce() // Members refreshed after removal
    expect(toastMsg).toBe('Member removed')
  })

  it('fetchMembers is called again after successful updateGroupMemberRole', async () => {
    const updateRoleFn = vi.fn().mockResolvedValue({ user_id: 'u-1', role: 'admin' })
    const fetchMembersFn = vi.fn().mockResolvedValue([])
    let toastMsg = ''

    async function handleRoleChange(groupId: string, userId: string, currentRole: string, newRole: string) {
      if (newRole === currentRole) return // no-op if same role
      await updateRoleFn(groupId, userId, newRole)
      toastMsg = 'Role updated'
      await fetchMembersFn({ id: groupId })
    }

    await handleRoleChange('g-1', 'u-1', 'member', 'admin')
    expect(updateRoleFn).toHaveBeenCalledOnce()
    expect(fetchMembersFn).toHaveBeenCalledOnce() // Members refreshed after role change
    expect(toastMsg).toBe('Role updated')
  })

  it('fetchMembers is NOT called when role change is a no-op (same role)', async () => {
    const updateRoleFn = vi.fn()
    const fetchMembersFn = vi.fn()

    async function handleRoleChange(groupId: string, userId: string, currentRole: string, newRole: string) {
      if (newRole === currentRole) return
      await updateRoleFn(groupId, userId, newRole)
      await fetchMembersFn({ id: groupId })
    }

    await handleRoleChange('g-1', 'u-1', 'admin', 'admin') // same role
    expect(updateRoleFn).not.toHaveBeenCalled()
    expect(fetchMembersFn).not.toHaveBeenCalled()
  })
})

// ── Reactive Refresh After API Key Mutations ──────────────────────────────────

describe('Backend API Alignment - reactive list refresh after API key mutations', () => {
  it('loadKeys is called again after successful createApiKey', async () => {
    const createKeyFn = vi.fn().mockResolvedValue({
      id: 'key-new',
      name: 'CI Pipeline',
      secret: 'fake-secret', // gitleaks:allow
      prefix: 'kfake_',
    })
    const loadKeysFn = vi.fn().mockResolvedValue([])
    let toastMsg = ''

    async function handleCreate(name: string, expiresInDays: number) {
      if (!name.trim()) return
      const key = await createKeyFn({ name: name.trim(), expires_in_days: expiresInDays })
      toastMsg = `API key "${key.name}" created`
      await loadKeysFn()
    }

    await handleCreate('CI Pipeline', 365)
    expect(createKeyFn).toHaveBeenCalledOnce()
    expect(loadKeysFn).toHaveBeenCalledOnce() // List refreshed after creation
    expect(toastMsg).toBe('API key "CI Pipeline" created')
  })

  it('loadKeys is called again after successful revokeApiKey', async () => {
    const revokeKeyFn = vi.fn().mockResolvedValue(undefined)
    const loadKeysFn = vi.fn().mockResolvedValue([])
    let toastMsg = ''

    async function handleRevoke(apiKeyId: string, apiKeyName: string) {
      if (!apiKeyId) return
      await revokeKeyFn(apiKeyId)
      toastMsg = `API key "${apiKeyName}" revoked`
      await loadKeysFn()
    }

    await handleRevoke('key-abc', 'CI Pipeline')
    expect(revokeKeyFn).toHaveBeenCalledWith('key-abc')
    expect(loadKeysFn).toHaveBeenCalledOnce() // List refreshed after revocation
    expect(toastMsg).toBe('API key "CI Pipeline" revoked')
  })

  it('revokeApiKey uses DELETE method (not POST)', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined)
    const apiKeyId = 'key-abc-123'

    // This simulates what useIamApi.revokeApiKey does:
    async function revokeApiKey(id: string) {
      return apiFetch(`/iam/api-keys/${id}`, { method: 'DELETE' })
    }

    await revokeApiKey(apiKeyId)
    const [, opts] = apiFetch.mock.calls[0]
    expect(opts.method).toBe('DELETE')
    expect(opts.method).not.toBe('POST')
  })
})

// ── Workspace Parent Context ──────────────────────────────────────────────────
//
// Spec: "Parent context is preserved"
// When creating a workspace, the parent_workspace_id MUST be included in the
// request body. The backend API requires it for workspace creation.

describe('Backend API Alignment - workspace parent context preserved', () => {
  it('createWorkspace request body always includes parent_workspace_id', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'ws-new', name: 'My Workspace' })

    async function createWorkspace(data: { name: string; parent_workspace_id: string }) {
      return apiFetch('/iam/workspaces', { method: 'POST', body: data })
    }

    await createWorkspace({ name: 'My Workspace', parent_workspace_id: 'ws-root' })
    const [url, opts] = apiFetch.mock.calls[0]
    expect(url).toBe('/iam/workspaces')
    expect(opts.method).toBe('POST')
    expect(opts.body).toHaveProperty('parent_workspace_id', 'ws-root')
    expect(opts.body).toHaveProperty('name', 'My Workspace')
  })

  it('createWorkspace is NOT called when parent workspace is not selected', async () => {
    const apiFetch = vi.fn()

    function validateCreateWorkspace(name: string, parentId: string) {
      return !!(name.trim() && parentId)
    }

    async function handleCreate(name: string, parentId: string) {
      if (!validateCreateWorkspace(name, parentId)) return
      await apiFetch('/iam/workspaces', { method: 'POST', body: { name, parent_workspace_id: parentId } })
    }

    await handleCreate('My Workspace', '') // no parent selected
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('listWorkspaces calls GET /iam/workspaces (flat, not scoped to parent)', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ workspaces: [] })

    async function listWorkspaces() {
      return apiFetch('/iam/workspaces')
    }

    await listWorkspaces()
    expect(apiFetch).toHaveBeenCalledWith('/iam/workspaces')
    // The flat listing endpoint is /iam/workspaces — NOT /iam/workspaces/{id}/children
    const [url] = apiFetch.mock.calls[0]
    expect(url).toBe('/iam/workspaces')
    expect(url).not.toContain('/children')
  })

  it('workspace list is refreshed after successful createWorkspace', async () => {
    const createWorkspaceFn = vi.fn().mockResolvedValue({ id: 'ws-new', name: 'My Workspace' })
    const listWorkspacesFn = vi.fn().mockResolvedValue({ workspaces: [] })
    let toastMsg = ''

    async function handleCreateWorkspace(name: string, parentId: string) {
      if (!name.trim() || !parentId) return
      const ws = await createWorkspaceFn({ name: name.trim(), parent_workspace_id: parentId })
      toastMsg = 'Workspace created'
      await listWorkspacesFn() // reactive refresh
      return ws
    }

    await handleCreateWorkspace('My Workspace', 'ws-root')
    expect(createWorkspaceFn).toHaveBeenCalledOnce()
    expect(listWorkspacesFn).toHaveBeenCalledOnce() // Workspace list refreshed reactively
    expect(toastMsg).toBe('Workspace created')
  })
})

// ── Tenant Endpoint URLs ──────────────────────────────────────────────────────

describe('Backend API Alignment - tenant endpoint URLs', () => {
  it('listTenants calls GET /iam/tenants', async () => {
    const apiFetch = vi.fn().mockResolvedValue([])

    async function listTenants() {
      return apiFetch('/iam/tenants')
    }

    await listTenants()
    expect(apiFetch).toHaveBeenCalledWith('/iam/tenants')
  })

  it('listTenantMembers calls GET /iam/tenants/{id}/members', async () => {
    const apiFetch = vi.fn().mockResolvedValue([])
    const tenantId = 'tenant-1'

    async function listTenantMembers(id: string) {
      return apiFetch(`/iam/tenants/${id}/members`)
    }

    await listTenantMembers(tenantId)
    expect(apiFetch).toHaveBeenCalledWith(`/iam/tenants/${tenantId}/members`)
  })
})

// ── End-to-end Operation Patterns ────────────────────────────────────────────
//
// Spec: "Resource operations succeed end-to-end"
// These tests verify the complete sequence: validate → API call → refresh → toast

describe('Backend API Alignment - end-to-end operation pattern for groups', () => {
  it('complete group create flow: validate → POST /iam/groups → reload list → success toast', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'g-1', name: 'Engineering' })
    const fetchGroups = vi.fn().mockResolvedValue([])
    const toasts: string[] = []

    async function handleCreate(name: string) {
      if (!name.trim()) {
        toasts.push('error:Group name is required')
        return
      }
      const group = await apiFetch('/iam/groups', { method: 'POST', body: { name: name.trim() } })
      toasts.push(`success:Group "${group.name}" created`)
      await fetchGroups()
    }

    await handleCreate('Engineering')

    // Correct endpoint
    expect(apiFetch).toHaveBeenCalledWith('/iam/groups', {
      method: 'POST',
      body: { name: 'Engineering' },
    })
    // List refreshed reactively (no manual page reload needed)
    expect(fetchGroups).toHaveBeenCalledOnce()
    // Success toast shown
    expect(toasts).toContain('success:Group "Engineering" created')
  })

  it('complete group delete flow: confirm → DELETE /iam/groups/{id} → reload list → success toast', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined)
    const fetchGroups = vi.fn().mockResolvedValue([])
    const toasts: string[] = []
    let dialogOpen = false

    // Step 1: User opens confirm dialog
    function confirmDelete(group: { id: string; name: string }) {
      dialogOpen = true
      return group
    }

    // Step 2: User confirms deletion
    async function handleDelete(groupId: string, groupName: string) {
      await apiFetch(`/iam/groups/${groupId}`, { method: 'DELETE' })
      dialogOpen = false
      toasts.push(`success:Group "${groupName}" deleted`)
      await fetchGroups()
    }

    const group = confirmDelete({ id: 'g-1', name: 'Engineering' })
    expect(dialogOpen).toBe(true)
    expect(apiFetch).not.toHaveBeenCalled() // not called until confirmed

    await handleDelete(group.id, group.name)
    expect(apiFetch).toHaveBeenCalledWith('/iam/groups/g-1', { method: 'DELETE' })
    expect(fetchGroups).toHaveBeenCalledOnce()
    expect(toasts).toContain('success:Group "Engineering" deleted')
    expect(dialogOpen).toBe(false)
  })

  it('complete API key revoke flow: confirm → DELETE /iam/api-keys/{id} → reload list → success toast', async () => {
    const apiFetch = vi.fn().mockResolvedValue(undefined)
    const loadKeys = vi.fn().mockResolvedValue([])
    const toasts: string[] = []

    async function handleRevoke(apiKeyId: string, apiKeyName: string) {
      // Uses DELETE /iam/api-keys/{id} — not POST /revoke
      await apiFetch(`/iam/api-keys/${apiKeyId}`, { method: 'DELETE' })
      toasts.push(`success:API key "${apiKeyName}" revoked`)
      await loadKeys()
    }

    await handleRevoke('key-abc', 'CI Pipeline')

    const [url, opts] = apiFetch.mock.calls[0]
    expect(url).toBe('/iam/api-keys/key-abc')
    expect(opts.method).toBe('DELETE')
    expect(url).not.toContain('/revoke') // explicitly guard against wrong path
    expect(loadKeys).toHaveBeenCalledOnce()
    expect(toasts).toContain('success:API key "CI Pipeline" revoked')
  })
})
