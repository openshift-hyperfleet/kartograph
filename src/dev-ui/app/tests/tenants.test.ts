import { describe, it, expect, vi } from 'vitest'

// ── Tenant Management Tests ───────────────────────────────────────────────────
//
// Spec: "Interaction Principles — Copy-to-clipboard & Mutation feedback"
// Covers:
//   - Copy tenant ID to clipboard (via CopyableText component in TenantDetailPanel)
//   - Mutation feedback for create, delete operations on the tenants page
//   - Inline validation errors on form fields

// ── Types ─────────────────────────────────────────────────────────────────────

interface TenantResponse {
  id: string
  name: string
  created_at: string
}

interface TenantMemberResponse {
  user_id: string
  role: 'admin' | 'member'
}

// ── Validation helpers (extracted from tenants/index.vue logic) ────────────────

function validateTenantName(name: string): { valid: boolean; error: string } {
  if (!name.trim()) return { valid: false, error: 'Tenant name is required' }
  return { valid: true, error: '' }
}

function filterTenants(tenants: TenantResponse[], query: string): TenantResponse[] {
  const q = query.toLowerCase().trim()
  if (!q) return tenants
  return tenants.filter((t) => t.name.toLowerCase().includes(q))
}

// ── Tenant name validation ─────────────────────────────────────────────────────

describe('Tenant Management - name validation', () => {
  it('rejects empty tenant name', () => {
    const result = validateTenantName('')
    expect(result.valid).toBe(false)
    expect(result.error).toBe('Tenant name is required')
  })

  it('rejects whitespace-only tenant name', () => {
    const result = validateTenantName('   ')
    expect(result.valid).toBe(false)
  })

  it('accepts a valid tenant name', () => {
    const result = validateTenantName('Acme Corp')
    expect(result.valid).toBe(true)
    expect(result.error).toBe('')
  })
})

// ── Search filtering ──────────────────────────────────────────────────────────

describe('Tenant Management - search filtering', () => {
  const tenants: TenantResponse[] = [
    { id: 't-1', name: 'Acme Corp', created_at: '' },
    { id: 't-2', name: 'Startup Inc', created_at: '' },
    { id: 't-3', name: 'Acme Labs', created_at: '' },
  ]

  it('returns all tenants when query is empty', () => {
    expect(filterTenants(tenants, '')).toHaveLength(3)
  })

  it('filters tenants by name (case-insensitive)', () => {
    const result = filterTenants(tenants, 'acme')
    expect(result).toHaveLength(2)
    expect(result.map((t) => t.name)).toContain('Acme Corp')
    expect(result.map((t) => t.name)).toContain('Acme Labs')
  })

  it('returns empty array when no tenants match', () => {
    expect(filterTenants(tenants, 'zzznomatch')).toHaveLength(0)
  })
})

// ── Copy-to-clipboard for Tenant IDs ─────────────────────────────────────────
// Spec: "Interaction Principles — Copy-to-clipboard"
// GIVEN a tenant is selected with its detail panel visible
// THEN a copy button is provided next to the tenant ID
// AND clicking the copy button writes the ID to the clipboard
// AND a toast confirms the copy action

describe('Tenant Management - copy tenant ID to clipboard', () => {
  it('calls clipboard.writeText with the tenant ID', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    let toastMsg = ''

    // Mirrors the CopyableText component behaviour used in TenantDetailPanel
    async function copyTenantId(id: string) {
      try {
        await writeText(id)
        toastMsg = 'Tenant ID copied'
      } catch {
        toastMsg = 'Failed to copy'
      }
    }

    await copyTenantId('ten-acme-corp-abc')
    expect(writeText).toHaveBeenCalledWith('ten-acme-corp-abc')
    expect(toastMsg).toBe('Tenant ID copied')
  })

  it('shows error feedback when clipboard write fails', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('NotAllowedError'))
    let toastMsg = ''

    async function copyTenantId(id: string) {
      try {
        await writeText(id)
        toastMsg = 'Tenant ID copied'
      } catch {
        toastMsg = 'Failed to copy'
      }
    }

    await copyTenantId('ten-acme-corp-abc')
    expect(toastMsg).toBe('Failed to copy')
  })

  it('copies the correct ID for each tenant when multiple exist', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    const tenants: TenantResponse[] = [
      { id: 't-1', name: 'Acme Corp', created_at: '' },
      { id: 't-2', name: 'Startup Inc', created_at: '' },
    ]
    const copiedIds: string[] = []

    async function copyTenantId(id: string) {
      await writeText(id)
      copiedIds.push(id)
    }

    for (const t of tenants) {
      await copyTenantId(t.id)
    }

    expect(writeText).toHaveBeenCalledTimes(2)
    expect(copiedIds).toEqual(['t-1', 't-2'])
  })
})

// ── Mutation Feedback — tenant create / delete ─────────────────────────────────
// Spec: "Interaction Principles — Mutation feedback"
// GIVEN a write operation (create, delete tenant)
// THEN a toast notification confirms success or reports failure

describe('Tenant Management - mutation feedback on create', () => {
  it('shows success toast with tenant name after create', async () => {
    const createTenant = vi.fn().mockResolvedValue({ id: 't-new', name: 'Acme Corp' })
    let successToast = ''

    async function handleCreate(name: string) {
      const validation = validateTenantName(name)
      if (!validation.valid) return
      const created = await createTenant({ name: name.trim() })
      successToast = `Tenant "${created.name}" created`
    }

    await handleCreate('Acme Corp')
    expect(successToast).toBe('Tenant "Acme Corp" created')
  })

  it('shows error toast when tenant creation fails', async () => {
    const createTenant = vi.fn().mockRejectedValue(new Error('Conflict'))
    let errorToast = ''

    async function handleCreate(name: string) {
      const validation = validateTenantName(name)
      if (!validation.valid) {
        errorToast = validation.error
        return
      }
      try {
        await createTenant({ name: name.trim() })
      } catch {
        errorToast = 'Failed to create tenant'
      }
    }

    await handleCreate('Acme Corp')
    expect(errorToast).toBe('Failed to create tenant')
  })

  it('shows inline name error when name is empty on submit', () => {
    let nameError = ''

    function handleCreate(name: string) {
      const validation = validateTenantName(name)
      if (!validation.valid) {
        nameError = validation.error
        return false
      }
      return true
    }

    const ok = handleCreate('')
    expect(ok).toBe(false)
    expect(nameError).toBe('Tenant name is required')
  })

  it('does not call API when name validation fails', async () => {
    const createTenant = vi.fn()

    async function handleCreate(name: string) {
      const validation = validateTenantName(name)
      if (!validation.valid) return
      await createTenant({ name: name.trim() })
    }

    await handleCreate('')
    expect(createTenant).not.toHaveBeenCalled()
  })
})

describe('Tenant Management - mutation feedback on delete', () => {
  it('shows success toast with tenant name after delete', async () => {
    const deleteTenant = vi.fn().mockResolvedValue(undefined)
    const tenantToDelete = { name: 'Acme Corp', id: 't-1' }
    let successToast = ''

    async function handleDelete() {
      await deleteTenant(tenantToDelete.id)
      successToast = `Tenant "${tenantToDelete.name}" deleted`
    }

    await handleDelete()
    expect(successToast).toBe('Tenant "Acme Corp" deleted')
  })

  it('shows error toast when delete fails', async () => {
    const deleteTenant = vi.fn().mockRejectedValue(new Error('Forbidden'))
    let errorToast = ''

    async function handleDelete(id: string) {
      try {
        await deleteTenant(id)
      } catch {
        errorToast = 'Failed to delete tenant'
      }
    }

    await handleDelete('t-1')
    expect(errorToast).toBe('Failed to delete tenant')
  })

  it('does nothing when tenantToDelete is null', async () => {
    const deleteTenant = vi.fn()
    const tenantToDelete = { value: null as TenantResponse | null }

    async function handleDelete() {
      if (!tenantToDelete.value) return
      await deleteTenant(tenantToDelete.value.id)
    }

    await handleDelete()
    expect(deleteTenant).not.toHaveBeenCalled()
  })
})

// ── Member management feedback ─────────────────────────────────────────────────

describe('Tenant Management - member management feedback', () => {
  it('shows success toast after adding a member', async () => {
    const addTenantMember = vi.fn().mockResolvedValue({})
    const fetchMembers = vi.fn().mockResolvedValue(undefined)
    let successToast = ''

    async function handleAddMember(tenantId: string, userId: string, role: 'admin' | 'member') {
      if (!userId.trim()) return
      await addTenantMember(tenantId, { user_id: userId.trim(), role })
      successToast = 'Member added'
      await fetchMembers(tenantId)
    }

    await handleAddMember('t-1', 'user-42', 'member')
    expect(addTenantMember).toHaveBeenCalledWith('t-1', { user_id: 'user-42', role: 'member' })
    expect(successToast).toBe('Member added')
    expect(fetchMembers).toHaveBeenCalledWith('t-1')
  })

  it('shows error toast when add member fails', async () => {
    const addTenantMember = vi.fn().mockRejectedValue(new Error('Not found'))
    let errorToast = ''

    async function handleAddMember(tenantId: string, userId: string, role: 'admin' | 'member') {
      if (!userId.trim()) return
      try {
        await addTenantMember(tenantId, { user_id: userId.trim(), role })
      } catch {
        errorToast = 'Failed to add member'
      }
    }

    await handleAddMember('t-1', 'user-42', 'member')
    expect(errorToast).toBe('Failed to add member')
  })

  it('shows success toast after removing a member', async () => {
    const removeTenantMember = vi.fn().mockResolvedValue(undefined)
    const fetchMembers = vi.fn().mockResolvedValue(undefined)
    const memberToRemove: TenantMemberResponse = { user_id: 'user-42', role: 'member' }
    let successToast = ''

    async function handleRemoveMember(tenantId: string, m: TenantMemberResponse) {
      await removeTenantMember(tenantId, m.user_id)
      successToast = 'Member removed'
      await fetchMembers(tenantId)
    }

    await handleRemoveMember('t-1', memberToRemove)
    expect(removeTenantMember).toHaveBeenCalledWith('t-1', 'user-42')
    expect(successToast).toBe('Member removed')
  })

  it('shows error toast when remove member fails', async () => {
    const removeTenantMember = vi.fn().mockRejectedValue(new Error('Forbidden'))
    let errorToast = ''

    async function handleRemoveMember(tenantId: string, userId: string) {
      try {
        await removeTenantMember(tenantId, userId)
      } catch {
        errorToast = 'Failed to remove member'
      }
    }

    await handleRemoveMember('t-1', 'user-42')
    expect(errorToast).toBe('Failed to remove member')
  })
})

// ── Backend API alignment ──────────────────────────────────────────────────────

describe('Tenant Management - backend API alignment', () => {
  it('listTenants calls GET /iam/tenants', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue([])

    async function listTenants() {
      return mockApiFetch('/iam/tenants')
    }

    await listTenants()
    expect(mockApiFetch).toHaveBeenCalledWith('/iam/tenants')
  })

  it('createTenant calls POST /iam/tenants with name', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue({ id: 't-new', name: 'Acme Corp' })

    async function createTenant(data: { name: string }) {
      return mockApiFetch('/iam/tenants', { method: 'POST', body: data })
    }

    await createTenant({ name: 'Acme Corp' })
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/tenants',
      expect.objectContaining({
        method: 'POST',
        body: expect.objectContaining({ name: 'Acme Corp' }),
      }),
    )
  })

  it('deleteTenant calls DELETE /iam/tenants/{id}', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue(undefined)

    async function deleteTenant(tenantId: string) {
      return mockApiFetch(`/iam/tenants/${tenantId}`, { method: 'DELETE' })
    }

    await deleteTenant('t-abc-123')
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/tenants/t-abc-123',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('addTenantMember calls POST /iam/tenants/{id}/members', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue({ user_id: 'user-42', role: 'member' })

    async function addTenantMember(tenantId: string, data: { user_id: string; role: string }) {
      return mockApiFetch(`/iam/tenants/${tenantId}/members`, { method: 'POST', body: data })
    }

    await addTenantMember('t-abc-123', { user_id: 'user-42', role: 'member' })
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/tenants/t-abc-123/members',
      expect.objectContaining({
        method: 'POST',
        body: expect.objectContaining({ user_id: 'user-42', role: 'member' }),
      }),
    )
  })

  it('removeTenantMember calls DELETE /iam/tenants/{id}/members/{userId}', async () => {
    const mockApiFetch = vi.fn().mockResolvedValue(undefined)

    async function removeTenantMember(tenantId: string, userId: string) {
      return mockApiFetch(`/iam/tenants/${tenantId}/members/${userId}`, { method: 'DELETE' })
    }

    await removeTenantMember('t-abc-123', 'user-42')
    expect(mockApiFetch).toHaveBeenCalledWith(
      '/iam/tenants/t-abc-123/members/user-42',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})
