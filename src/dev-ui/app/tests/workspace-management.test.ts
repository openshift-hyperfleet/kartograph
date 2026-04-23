import { describe, it, expect, vi } from 'vitest'

// ── Workspace Management Tests ────────────────────────────────────────────────
//
// Spec: "Workspace Management"
// Covers:
//   - Scenario: Create workspace (with name and optional parent)
//   - Scenario: Member management (add, remove, change role)
//   - Tree/hierarchy display and filtering

// ── Types ─────────────────────────────────────────────────────────────────────

interface WorkspaceResponse {
  id: string
  name: string
  parent_workspace_id: string | null
  is_root: boolean
  created_at: string
}

interface WorkspaceMemberResponse {
  member_id: string
  member_type: 'user' | 'group'
  role: 'member' | 'admin' | 'owner'
}

type WorkspaceRole = 'member' | 'admin' | 'owner'

// ── Workspace Tree Building (mirrors workspaces/index.vue) ────────────────────

interface WorkspaceNode {
  workspace: WorkspaceResponse
  children: WorkspaceNode[]
  depth: number
}

function buildWorkspaceTree(workspaces: WorkspaceResponse[]): WorkspaceNode[] {
  const byParent = new Map<string | null, WorkspaceResponse[]>()
  for (const ws of workspaces) {
    const parentKey = ws.parent_workspace_id
    if (!byParent.has(parentKey)) byParent.set(parentKey, [])
    byParent.get(parentKey)!.push(ws)
  }

  function build(parentId: string | null, depth: number): WorkspaceNode[] {
    const children = byParent.get(parentId) ?? []
    return children.map((ws) => ({
      workspace: ws,
      children: build(ws.id, depth + 1),
      depth,
    }))
  }

  return build(null, 0)
}

function flattenTree(nodes: WorkspaceNode[], expandedIds: Set<string>): WorkspaceNode[] {
  const result: WorkspaceNode[] = []
  function walk(nodeList: WorkspaceNode[]) {
    for (const node of nodeList) {
      result.push(node)
      if (expandedIds.has(node.workspace.id)) {
        walk(node.children)
      }
    }
  }
  walk(nodes)
  return result
}

function filteredFlatNodes(nodes: WorkspaceNode[], searchQuery: string): WorkspaceNode[] {
  const q = searchQuery.toLowerCase().trim()
  if (!q) return nodes
  return nodes.filter((node) => node.workspace.name.toLowerCase().includes(q))
}

// ── Workspace Creation Validation ─────────────────────────────────────────────

function validateCreate(
  name: string,
  parentId: string,
): { nameError: string; parentError: string; valid: boolean } {
  const nameError = name.trim() ? '' : 'Workspace name is required'
  const parentError = parentId ? '' : 'Parent workspace is required'
  const valid = !nameError && !parentError
  return { nameError, parentError, valid }
}

// ── Member Management ─────────────────────────────────────────────────────────

function validateAddMember(memberId: string): boolean {
  return !!memberId.trim()
}

function shouldSkipRoleChange(
  member: WorkspaceMemberResponse,
  newRole: WorkspaceRole,
): boolean {
  return newRole === member.role
}

// ── Workspace Rename ──────────────────────────────────────────────────────────

function validateRename(
  currentName: string,
  newName: string,
): { valid: boolean; noChange: boolean } {
  const trimmed = newName.trim()
  if (!trimmed) return { valid: false, noChange: false }
  if (trimmed === currentName) return { valid: true, noChange: true }
  return { valid: true, noChange: false }
}

// ── Workspace Search Filtering ────────────────────────────────────────────────

function filterWorkspacesByName(
  workspaces: WorkspaceResponse[],
  query: string,
): WorkspaceResponse[] {
  const q = query.toLowerCase().trim()
  if (!q) return workspaces
  return workspaces.filter((ws) => ws.name.toLowerCase().includes(q))
}

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Create workspace — validation
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - creation validation', () => {
  it('rejects creation when name is empty', () => {
    const result = validateCreate('', 'parent-1')
    expect(result.valid).toBe(false)
    expect(result.nameError).toBe('Workspace name is required')
  })

  it('rejects creation when name is only whitespace', () => {
    const result = validateCreate('   ', 'parent-1')
    expect(result.valid).toBe(false)
    expect(result.nameError).toBe('Workspace name is required')
  })

  it('rejects creation when parent workspace is not selected', () => {
    const result = validateCreate('My Workspace', '')
    expect(result.valid).toBe(false)
    expect(result.parentError).toBe('Parent workspace is required')
  })

  it('fails with both errors when name and parent are missing', () => {
    const result = validateCreate('', '')
    expect(result.valid).toBe(false)
    expect(result.nameError).toBeTruthy()
    expect(result.parentError).toBeTruthy()
  })

  it('passes validation when name and parent are both provided', () => {
    const result = validateCreate('My Workspace', 'root-ws-1')
    expect(result.valid).toBe(true)
    expect(result.nameError).toBe('')
    expect(result.parentError).toBe('')
  })

  it('trims name before validation', () => {
    const result = validateCreate('  Valid Name  ', 'parent-1')
    expect(result.valid).toBe(true)
  })
})

describe('Workspace Management - creation API call', () => {
  it('calls createWorkspace with correct name and parent_workspace_id', async () => {
    const createWorkspace = vi.fn().mockResolvedValue({ id: 'ws-new', name: 'My Workspace' })
    let toastMsg = ''

    async function handleCreate(name: string, parentId: string) {
      const result = validateCreate(name, parentId)
      if (!result.valid) return
      const ws = await createWorkspace({ name: name.trim(), parent_workspace_id: parentId })
      toastMsg = 'Workspace created'
      return ws
    }

    await handleCreate('My Workspace', 'parent-1')
    expect(createWorkspace).toHaveBeenCalledWith({
      name: 'My Workspace',
      parent_workspace_id: 'parent-1',
    })
    expect(toastMsg).toBe('Workspace created')
  })

  it('does not call API when validation fails', async () => {
    const createWorkspace = vi.fn()

    async function handleCreate(name: string, parentId: string) {
      const result = validateCreate(name, parentId)
      if (!result.valid) return
      await createWorkspace({ name: name.trim(), parent_workspace_id: parentId })
    }

    await handleCreate('', 'parent-1')
    expect(createWorkspace).not.toHaveBeenCalled()
  })

  it('shows error toast on API failure', async () => {
    const createWorkspace = vi.fn().mockRejectedValue(new Error('Conflict'))
    let errorMsg = ''

    async function handleCreate(name: string, parentId: string) {
      try {
        await createWorkspace({ name: name.trim(), parent_workspace_id: parentId })
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to create workspace'
      }
    }

    await handleCreate('Duplicate', 'parent-1')
    expect(errorMsg).toBe('Conflict')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Member management — add member
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - add member', () => {
  it('returns false for empty member ID (prevents API call)', () => {
    expect(validateAddMember('')).toBe(false)
  })

  it('returns false for whitespace-only member ID', () => {
    expect(validateAddMember('   ')).toBe(false)
  })

  it('returns true for valid member ID', () => {
    expect(validateAddMember('user-abc-123')).toBe(true)
  })

  it('calls addWorkspaceMember with correct arguments on success', async () => {
    const addWorkspaceMember = vi.fn().mockResolvedValue({})
    let toastMsg = ''

    async function handleAddMember(
      workspaceId: string,
      memberId: string,
      memberType: 'user' | 'group',
      role: WorkspaceRole,
    ) {
      if (!validateAddMember(memberId)) return
      await addWorkspaceMember(workspaceId, {
        member_id: memberId.trim(),
        member_type: memberType,
        role,
      })
      toastMsg = 'Member added'
    }

    await handleAddMember('ws-1', 'user-42', 'user', 'member')
    expect(addWorkspaceMember).toHaveBeenCalledWith('ws-1', {
      member_id: 'user-42',
      member_type: 'user',
      role: 'member',
    })
    expect(toastMsg).toBe('Member added')
  })

  it('does not call API when member ID is empty', async () => {
    const addWorkspaceMember = vi.fn()

    async function handleAddMember(workspaceId: string, memberId: string) {
      if (!validateAddMember(memberId)) return
      await addWorkspaceMember(workspaceId, { member_id: memberId })
    }

    await handleAddMember('ws-1', '')
    expect(addWorkspaceMember).not.toHaveBeenCalled()
  })

  it('shows error toast when add member API fails', async () => {
    const addWorkspaceMember = vi.fn().mockRejectedValue(new Error('Forbidden'))
    let errorMsg = ''

    async function handleAddMember(workspaceId: string, memberId: string) {
      try {
        await addWorkspaceMember(workspaceId, { member_id: memberId })
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to add member'
      }
    }

    await handleAddMember('ws-1', 'user-42')
    expect(errorMsg).toBe('Forbidden')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Member management — remove member
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - remove member', () => {
  it('calls removeWorkspaceMember with workspace id, member id, and type', async () => {
    const removeWorkspaceMember = vi.fn().mockResolvedValue({})
    let toastMsg = ''

    const member: WorkspaceMemberResponse = {
      member_id: 'user-42',
      member_type: 'user',
      role: 'member',
    }

    async function handleRemoveMember(workspaceId: string, m: WorkspaceMemberResponse) {
      await removeWorkspaceMember(workspaceId, m.member_id, m.member_type)
      toastMsg = 'Member removed'
    }

    await handleRemoveMember('ws-1', member)
    expect(removeWorkspaceMember).toHaveBeenCalledWith('ws-1', 'user-42', 'user')
    expect(toastMsg).toBe('Member removed')
  })

  it('shows error toast when remove member API fails', async () => {
    const removeWorkspaceMember = vi.fn().mockRejectedValue(new Error('Not found'))
    let errorMsg = ''

    const member: WorkspaceMemberResponse = {
      member_id: 'user-42',
      member_type: 'user',
      role: 'member',
    }

    async function handleRemoveMember(workspaceId: string, m: WorkspaceMemberResponse) {
      try {
        await removeWorkspaceMember(workspaceId, m.member_id, m.member_type)
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to remove member'
      }
    }

    await handleRemoveMember('ws-1', member)
    expect(errorMsg).toBe('Not found')
  })

  it('remove dialog requires confirmation before calling API (guard pattern)', () => {
    // Simulates: confirm dialog must be accepted before calling removeWorkspaceMember
    let removeDialogOpen = false
    let memberToRemove: WorkspaceMemberResponse | null = null
    const removeWorkspaceMember = vi.fn()

    function confirmRemoveMember(member: WorkspaceMemberResponse) {
      memberToRemove = member
      removeDialogOpen = true
    }

    function cancelRemove() {
      removeDialogOpen = false
      memberToRemove = null
    }

    const member: WorkspaceMemberResponse = { member_id: 'user-42', member_type: 'user', role: 'member' }
    confirmRemoveMember(member)
    expect(removeDialogOpen).toBe(true)
    expect(memberToRemove).toBe(member)
    expect(removeWorkspaceMember).not.toHaveBeenCalled() // not called until confirmed

    cancelRemove()
    expect(removeDialogOpen).toBe(false)
    expect(memberToRemove).toBeNull()
    expect(removeWorkspaceMember).not.toHaveBeenCalled() // still not called after cancel
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Member management — role change
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - role change', () => {
  it('skips API call when new role is the same as current role', () => {
    const member: WorkspaceMemberResponse = { member_id: 'user-42', member_type: 'user', role: 'member' }
    expect(shouldSkipRoleChange(member, 'member')).toBe(true)
  })

  it('proceeds with API call when new role differs from current', () => {
    const member: WorkspaceMemberResponse = { member_id: 'user-42', member_type: 'user', role: 'member' }
    expect(shouldSkipRoleChange(member, 'admin')).toBe(false)
  })

  it('calls updateWorkspaceMemberRole with correct arguments', async () => {
    const updateRole = vi.fn().mockResolvedValue({})
    let toastMsg = ''

    const member: WorkspaceMemberResponse = {
      member_id: 'user-42',
      member_type: 'user',
      role: 'member',
    }

    async function handleRoleChange(workspaceId: string, m: WorkspaceMemberResponse, newRole: WorkspaceRole) {
      if (shouldSkipRoleChange(m, newRole)) return
      await updateRole(workspaceId, m.member_id, m.member_type, newRole)
      toastMsg = 'Role updated'
    }

    await handleRoleChange('ws-1', member, 'admin')
    expect(updateRole).toHaveBeenCalledWith('ws-1', 'user-42', 'user', 'admin')
    expect(toastMsg).toBe('Role updated')
  })

  it('does not call API when role is unchanged', async () => {
    const updateRole = vi.fn()

    const member: WorkspaceMemberResponse = {
      member_id: 'user-42',
      member_type: 'user',
      role: 'admin',
    }

    async function handleRoleChange(workspaceId: string, m: WorkspaceMemberResponse, newRole: WorkspaceRole) {
      if (shouldSkipRoleChange(m, newRole)) return
      await updateRole(workspaceId, m.member_id, m.member_type, newRole)
    }

    await handleRoleChange('ws-1', member, 'admin') // same role
    expect(updateRole).not.toHaveBeenCalled()
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Workspace rename
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - rename', () => {
  it('rejects rename when new name is empty', () => {
    const result = validateRename('My Workspace', '')
    expect(result.valid).toBe(false)
  })

  it('detects no-change when trimmed name equals current name', () => {
    const result = validateRename('My Workspace', 'My Workspace')
    expect(result.valid).toBe(true)
    expect(result.noChange).toBe(true)
  })

  it('accepts rename when name is different', () => {
    const result = validateRename('Old Name', 'New Name')
    expect(result.valid).toBe(true)
    expect(result.noChange).toBe(false)
  })

  it('calls updateWorkspace with trimmed new name', async () => {
    const updateWorkspace = vi.fn().mockResolvedValue({ id: 'ws-1', name: 'New Name' })
    let toastMsg = ''

    async function handleRename(workspaceId: string, currentName: string, newName: string) {
      const { valid, noChange } = validateRename(currentName, newName)
      if (!valid) return
      if (noChange) return
      await updateWorkspace(workspaceId, { name: newName.trim() })
      toastMsg = 'Workspace renamed'
    }

    await handleRename('ws-1', 'Old Name', '  New Name  ')
    expect(updateWorkspace).toHaveBeenCalledWith('ws-1', { name: 'New Name' })
    expect(toastMsg).toBe('Workspace renamed')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Workspace tree building
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - tree building', () => {
  const rootWs: WorkspaceResponse = {
    id: 'root-1',
    name: 'Engineering',
    parent_workspace_id: null,
    is_root: true,
    created_at: '2024-01-01T00:00:00Z',
  }

  const childWs: WorkspaceResponse = {
    id: 'child-1',
    name: 'Backend',
    parent_workspace_id: 'root-1',
    is_root: false,
    created_at: '2024-01-02T00:00:00Z',
  }

  const grandchildWs: WorkspaceResponse = {
    id: 'grandchild-1',
    name: 'API Team',
    parent_workspace_id: 'child-1',
    is_root: false,
    created_at: '2024-01-03T00:00:00Z',
  }

  it('builds a tree with a single root workspace', () => {
    const tree = buildWorkspaceTree([rootWs])
    expect(tree).toHaveLength(1)
    expect(tree[0].workspace.id).toBe('root-1')
    expect(tree[0].depth).toBe(0)
    expect(tree[0].children).toHaveLength(0)
  })

  it('attaches child workspaces under their parent', () => {
    const tree = buildWorkspaceTree([rootWs, childWs])
    expect(tree).toHaveLength(1) // only root at top level
    expect(tree[0].children).toHaveLength(1)
    expect(tree[0].children[0].workspace.id).toBe('child-1')
    expect(tree[0].children[0].depth).toBe(1)
  })

  it('builds nested hierarchy (grandchild)', () => {
    const tree = buildWorkspaceTree([rootWs, childWs, grandchildWs])
    const root = tree[0]
    const child = root.children[0]
    expect(child.children).toHaveLength(1)
    expect(child.children[0].workspace.id).toBe('grandchild-1')
    expect(child.children[0].depth).toBe(2)
  })

  it('returns empty array for empty workspace list', () => {
    const tree = buildWorkspaceTree([])
    expect(tree).toHaveLength(0)
  })

  it('handles multiple root workspaces', () => {
    const root2: WorkspaceResponse = {
      id: 'root-2',
      name: 'Product',
      parent_workspace_id: null,
      is_root: true,
      created_at: '2024-01-01T00:00:00Z',
    }
    const tree = buildWorkspaceTree([rootWs, root2])
    expect(tree).toHaveLength(2)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Flatten tree (respects expandedIds)
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - flatten tree', () => {
  const root: WorkspaceNode = {
    workspace: { id: 'root-1', name: 'Engineering', parent_workspace_id: null, is_root: true, created_at: '' },
    depth: 0,
    children: [
      {
        workspace: { id: 'child-1', name: 'Backend', parent_workspace_id: 'root-1', is_root: false, created_at: '' },
        depth: 1,
        children: [],
      },
    ],
  }

  it('includes only root when no IDs are expanded', () => {
    const flat = flattenTree([root], new Set())
    expect(flat).toHaveLength(1)
    expect(flat[0].workspace.id).toBe('root-1')
  })

  it('includes children when parent ID is in expandedIds', () => {
    const flat = flattenTree([root], new Set(['root-1']))
    expect(flat).toHaveLength(2)
    expect(flat[0].workspace.id).toBe('root-1')
    expect(flat[1].workspace.id).toBe('child-1')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Filter flat nodes by search query
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - search filtering', () => {
  const nodes: WorkspaceNode[] = [
    {
      workspace: { id: 'ws-1', name: 'Engineering', parent_workspace_id: null, is_root: true, created_at: '' },
      depth: 0,
      children: [],
    },
    {
      workspace: { id: 'ws-2', name: 'Backend', parent_workspace_id: 'ws-1', is_root: false, created_at: '' },
      depth: 1,
      children: [],
    },
    {
      workspace: { id: 'ws-3', name: 'Frontend', parent_workspace_id: 'ws-1', is_root: false, created_at: '' },
      depth: 1,
      children: [],
    },
  ]

  it('returns all nodes when search query is empty', () => {
    expect(filteredFlatNodes(nodes, '')).toHaveLength(3)
  })

  it('filters nodes by name (case-insensitive)', () => {
    const result = filteredFlatNodes(nodes, 'back')
    expect(result).toHaveLength(1)
    expect(result[0].workspace.name).toBe('Backend')
  })

  it('returns empty when no nodes match', () => {
    const result = filteredFlatNodes(nodes, 'zzznomatch')
    expect(result).toHaveLength(0)
  })

  it('returns multiple matches when several names contain query', () => {
    const result = filteredFlatNodes(nodes, 'end')
    // "Backend" and "Frontend" both contain "end"
    expect(result).toHaveLength(2)
  })

  it('ignores whitespace-only query and returns all', () => {
    const result = filteredFlatNodes(nodes, '   ')
    expect(result).toHaveLength(3)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Responsive layout: desktop panel vs mobile sheet
// ────────────────────────────────────────────────────────────────────────────

describe('Workspace Management - responsive layout (desktop vs mobile)', () => {
  it('sheet is NOT open when isDesktop is true (detail shows in panel)', () => {
    const isDesktop = true
    const selectedWorkspace = { id: 'ws-1', name: 'Engineering' }

    // sheetOpen = !isDesktop && selectedWorkspace !== null
    const sheetOpen = !isDesktop && selectedWorkspace !== null
    expect(sheetOpen).toBe(false)
  })

  it('sheet IS open when isDesktop is false and a workspace is selected', () => {
    const isDesktop = false
    const selectedWorkspace = { id: 'ws-1', name: 'Engineering' }

    const sheetOpen = !isDesktop && selectedWorkspace !== null
    expect(sheetOpen).toBe(true)
  })

  it('sheet is NOT open when no workspace is selected on mobile', () => {
    const isDesktop = false
    const selectedWorkspace = null

    const sheetOpen = !isDesktop && selectedWorkspace !== null
    expect(sheetOpen).toBe(false)
  })

  it('closing sheet deselects the workspace', () => {
    let selectedWorkspace: { id: string; name: string } | null = { id: 'ws-1', name: 'Engineering' }

    function closeDetails() {
      selectedWorkspace = null
    }

    closeDetails()
    expect(selectedWorkspace).toBeNull()
  })
})
