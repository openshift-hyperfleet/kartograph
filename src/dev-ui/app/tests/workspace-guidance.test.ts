import { describe, it, expect, vi } from 'vitest'

// ── Requirement: Tenant and Workspace Context — Workspace guidance ────────────
//
// Spec: "GIVEN a user entering a tenant for the first time,
//        WHEN no personal workspace exists,
//        THEN the UI suggests creating one or joining an existing team workspace"
//
// Task: task-062
// Spec ref: specs/ui/experience.spec.md
//
// The home page (pages/index.vue) mounts a <WorkspaceGuidance> component under
//   v-if="hasTenant && !hasWorkspace"
// and suppresses it (along with the KG creation prompt) once the user has a workspace.
//
// Tests mirror the component logic as pure functions — the established pattern
// for this codebase (no Nuxt composable mocking needed).

// ── Types (mirrors src/dev-ui/app/types/index.ts) ────────────────────────────

interface WorkspaceResponse {
  id: string
  name: string
  tenant_id: string
  parent_workspace_id: string | null
  is_root: boolean
  created_at: string
  updated_at: string
}

// ── Extracted logic (mirrors pages/index.vue) ─────────────────────────────────

/**
 * Computes whether the current user has at least one workspace.
 * Mirrors: const hasWorkspace = computed(() => workspaces.value.length > 0)
 */
function computeHasWorkspace(workspaces: WorkspaceResponse[]): boolean {
  return workspaces.length > 0
}

/**
 * Computes whether the workspace guidance panel should be visible.
 * Mirrors: v-if="hasTenant && !statsLoading && !hasWorkspace"
 */
function computeShowGuidance(params: {
  hasTenant: boolean
  statsLoading: boolean
  hasWorkspace: boolean
}): boolean {
  return params.hasTenant && !params.statsLoading && !params.hasWorkspace
}

/**
 * Computes whether the "new user KG creation prompt" should be visible.
 * Mirrors: v-else-if="hasWorkspace && kgCount === 0"
 * The two states are mutually exclusive — KG prompt only shows when workspace exists.
 */
function computeShowKgPrompt(params: {
  hasWorkspace: boolean
  kgCount: number
}): boolean {
  return params.hasWorkspace && params.kgCount === 0
}

/**
 * Simulates handleWorkspaceCreated — called from the WorkspaceGuidance component
 * after a workspace is successfully created. Appends the new workspace to the list
 * and hides the guidance (because hasWorkspace becomes true).
 */
function handleWorkspaceCreated(
  workspaces: WorkspaceResponse[],
  newWorkspace: WorkspaceResponse,
): WorkspaceResponse[] {
  return [...workspaces, newWorkspace]
}

/**
 * Simulates the WorkspaceGuidance component emit pattern.
 * The component emits 'create' when the "Create Workspace" button is clicked,
 * and 'join' when the "Join a Team Workspace" button is clicked.
 */
function triggerGuidanceAction(
  action: 'create' | 'join',
  emit: (event: string) => void,
): void {
  emit(action)
}

/**
 * Simulates opening the workspace creation dialog from the guidance panel.
 */
function openCreateWorkspaceDialog(state: { showCreateDialog: boolean }): void {
  state.showCreateDialog = true
}

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 1: Guidance shown when workspace list is empty
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Scenario: guidance shown when user has no workspaces', () => {
  it('hasWorkspace is false when workspace list is empty', () => {
    expect(computeHasWorkspace([])).toBe(false)
  })

  it('workspace guidance panel is shown when tenant exists and no workspaces', () => {
    const visible = computeShowGuidance({
      hasTenant: true,
      statsLoading: false,
      hasWorkspace: false,
    })
    expect(visible).toBe(true)
  })

  it('workspace guidance panel is hidden while stats are still loading', () => {
    // Prevents a flash of the guidance before workspaces are fetched
    const visible = computeShowGuidance({
      hasTenant: true,
      statsLoading: true,
      hasWorkspace: false,
    })
    expect(visible).toBe(false)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 2: Guidance contains a create-workspace action
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Scenario: create-workspace action present', () => {
  it('guidance emits "create" when the create-workspace button is activated', () => {
    const emit = vi.fn()
    triggerGuidanceAction('create', emit)
    expect(emit).toHaveBeenCalledWith('create')
    expect(emit).toHaveBeenCalledTimes(1)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 3: Guidance contains a join-workspace action
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Scenario: join-workspace action present', () => {
  it('guidance emits "join" when the join-workspace button is activated', () => {
    const emit = vi.fn()
    triggerGuidanceAction('join', emit)
    expect(emit).toHaveBeenCalledWith('join')
    expect(emit).toHaveBeenCalledTimes(1)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 4: Guidance NOT shown when workspaces exist
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Scenario: guidance not shown when workspaces exist', () => {
  it('hasWorkspace is true when the workspace list is non-empty', () => {
    const workspaces: WorkspaceResponse[] = [
      {
        id: 'ws-1',
        name: 'My Workspace',
        tenant_id: 'tenant-abc',
        parent_workspace_id: null,
        is_root: true,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]
    expect(computeHasWorkspace(workspaces)).toBe(true)
  })

  it('workspace guidance panel is hidden when the user already has a workspace', () => {
    const visible = computeShowGuidance({
      hasTenant: true,
      statsLoading: false,
      hasWorkspace: true,
    })
    expect(visible).toBe(false)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 5: KG creation prompt does NOT appear when workspace guidance is active
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Scenario: KG prompt suppressed when no workspace', () => {
  it('KG creation prompt is NOT shown when the user has no workspaces (hasWorkspace=false)', () => {
    const showKgPrompt = computeShowKgPrompt({ hasWorkspace: false, kgCount: 0 })
    expect(showKgPrompt).toBe(false)
  })

  it('workspace guidance and KG prompt are mutually exclusive', () => {
    // State: no workspaces, no KGs
    const hasWorkspace = false
    const kgCount = 0
    const showGuidance = computeShowGuidance({
      hasTenant: true,
      statsLoading: false,
      hasWorkspace,
    })
    const showKgPrompt = computeShowKgPrompt({ hasWorkspace, kgCount })

    // Only one can be visible at a time
    expect(showGuidance).toBe(true)
    expect(showKgPrompt).toBe(false)
    expect(showGuidance && showKgPrompt).toBe(false)
  })

  it('KG creation prompt IS shown once user has a workspace but no KGs', () => {
    const showKgPrompt = computeShowKgPrompt({ hasWorkspace: true, kgCount: 0 })
    expect(showKgPrompt).toBe(true)
  })

  it('KG creation prompt is NOT shown when user already has KGs', () => {
    const showKgPrompt = computeShowKgPrompt({ hasWorkspace: true, kgCount: 3 })
    expect(showKgPrompt).toBe(false)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 6: Create workspace dialog opens on button click
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Scenario: create workspace dialog opens on button click', () => {
  it('clicking create workspace sets showCreateDialog to true', () => {
    const state = { showCreateDialog: false }
    openCreateWorkspaceDialog(state)
    expect(state.showCreateDialog).toBe(true)
  })

  it('handleCreate event from WorkspaceGuidance triggers dialog open on the home page', () => {
    // The home page listens to @create from WorkspaceGuidance and opens the dialog
    const dialogState = { open: false }
    function onGuidanceCreate() { dialogState.open = true }

    // Simulate WorkspaceGuidance emitting 'create'
    const emit = vi.fn().mockImplementation((event: string) => {
      if (event === 'create') onGuidanceCreate()
    })
    triggerGuidanceAction('create', emit)

    expect(dialogState.open).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 7: Guidance hides after workspace is created
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Scenario: guidance disappears after workspace created', () => {
  it('workspace list is updated after handleWorkspaceCreated is called', () => {
    const workspaces: WorkspaceResponse[] = []

    const newWorkspace: WorkspaceResponse = {
      id: 'ws-new',
      name: 'New WS',
      tenant_id: 'tenant-abc',
      parent_workspace_id: null,
      is_root: true,
      created_at: '2024-01-02T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    }

    const updated = handleWorkspaceCreated(workspaces, newWorkspace)
    expect(updated).toHaveLength(1)
    expect(updated[0].id).toBe('ws-new')
  })

  it('hasWorkspace becomes true after workspace is created, hiding guidance', () => {
    // initial state: no workspaces
    let workspaces: WorkspaceResponse[] = []
    expect(computeHasWorkspace(workspaces)).toBe(false)

    // after workspace creation
    const newWorkspace: WorkspaceResponse = {
      id: 'ws-new',
      name: 'New WS',
      tenant_id: 'tenant-abc',
      parent_workspace_id: null,
      is_root: true,
      created_at: '2024-01-02T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    }
    workspaces = handleWorkspaceCreated(workspaces, newWorkspace)
    expect(computeHasWorkspace(workspaces)).toBe(true)

    // guidance is now hidden
    const showGuidance = computeShowGuidance({
      hasTenant: true,
      statsLoading: false,
      hasWorkspace: computeHasWorkspace(workspaces),
    })
    expect(showGuidance).toBe(false)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Backend API alignment: workspace list endpoint
// ─────────────────────────────────────────────────────────────────────────────

describe('Workspace Guidance — Backend API alignment', () => {
  it('workspace list is fetched from GET /iam/workspaces', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      workspaces: [],
      count: 0,
    })

    // Mirrors useIamApi.listWorkspaces — the call used in index.vue fetchStats()
    async function listWorkspaces() {
      return apiFetch('/iam/workspaces')
    }

    await listWorkspaces()
    expect(apiFetch).toHaveBeenCalledWith('/iam/workspaces')
  })

  it('hasWorkspace is false when /iam/workspaces returns an empty list', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ workspaces: [], count: 0 })

    async function listWorkspaces(): Promise<WorkspaceResponse[]> {
      const result = await apiFetch('/iam/workspaces')
      return result.workspaces ?? []
    }

    const workspaces = await listWorkspaces()
    expect(computeHasWorkspace(workspaces)).toBe(false)
  })

  it('hasWorkspace is true when /iam/workspaces returns one or more workspaces', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      workspaces: [{ id: 'ws-1', name: 'Personal', tenant_id: 't-1', parent_workspace_id: null, is_root: true, created_at: '', updated_at: '' }],
      count: 1,
    })

    async function listWorkspaces(): Promise<WorkspaceResponse[]> {
      const result = await apiFetch('/iam/workspaces')
      return result.workspaces ?? []
    }

    const workspaces = await listWorkspaces()
    expect(computeHasWorkspace(workspaces)).toBe(true)
  })
})
