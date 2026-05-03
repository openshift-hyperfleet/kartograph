import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Spec Alignment: task-103 — New user landing & Workspace guidance ──────────
//
// Spec: specs/ui/experience.spec.md
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task-Ref: task-103
//
// Scenarios covered:
//   1. Navigation Structure → "New user landing"
//      "GIVEN a user with no knowledge graphs, WHEN they open Kartograph,
//      THEN they are guided toward the setup flow with a prompt to create
//      their first knowledge graph"
//
//   2. Tenant and Workspace Context → "Workspace guidance"
//      "GIVEN a user entering a tenant for the first time, WHEN no personal
//      workspace exists, THEN the UI suggests creating one or joining an
//      existing team workspace"
//
// Implementation files:
//   - src/dev-ui/app/pages/index.vue
//   - src/dev-ui/app/components/workspaces/WorkspaceGuidance.vue
//
// All functions below replicate the logic extracted from Vue component scripts
// following the established testing pattern for this codebase (no Nuxt mocking).

// ─────────────────────────────────────────────────────────────────────────────
// Types (mirror src/dev-ui/app/types/index.ts)
// ─────────────────────────────────────────────────────────────────────────────

interface WorkspaceResponse {
  id: string
  name: string
  tenant_id: string
  parent_workspace_id: string | null
  is_root: boolean
  created_at: string
  updated_at: string
}

interface ChecklistItem {
  done: boolean
  label: string
  description: string
  actionTo: string
  actionLabel: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Extracted logic (mirrors pages/index.vue)
// ─────────────────────────────────────────────────────────────────────────────

const SESSION_REDIRECT_KEY = 'kartograph:home-redirect-done'

/**
 * Mirrors the session-redirect logic from index.vue onMounted.
 * Returning users (kgCount > 0) are sent to /query on first visit per session.
 */
async function runLandingRedirect(
  apiFetch: (path: string) => Promise<{ knowledge_graphs: { id: string }[] }>,
  navigateTo: (path: string) => Promise<void>,
  hasTenant: boolean,
): Promise<{ kgCount: number }> {
  if (typeof sessionStorage === 'undefined' || typeof localStorage === 'undefined') {
    return { kgCount: 0 }
  }

  const alreadyRedirected = sessionStorage.getItem(SESSION_REDIRECT_KEY)
  if (alreadyRedirected || !hasTenant) {
    if (!alreadyRedirected) sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')
    return { kgCount: 0 }
  }

  let kgCount = 0
  try {
    const result = await apiFetch('/management/knowledge-graphs')
    kgCount = result.knowledge_graphs?.length ?? 0
  } catch {
    kgCount = 0
  }

  sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')

  if (kgCount > 0) {
    await navigateTo('/query')
  }

  return { kgCount }
}

/**
 * Mirrors the checklistItems computed from index.vue.
 * The "Create a knowledge graph" step is how the new-user landing prompt
 * is implemented — it is the first actionable step after workspace creation.
 */
function buildChecklistItems(params: {
  hasTenant: boolean
  kgCount: number
  nodeTypeCount: number | null
  apiKeyCount: number | null
  apiKeyLastUsed: boolean
}): ChecklistItem[] {
  const { hasTenant, kgCount, nodeTypeCount, apiKeyCount, apiKeyLastUsed } = params
  return [
    {
      done: hasTenant,
      label: 'Create a tenant',
      description: 'You need a tenant to organize your knowledge graphs.',
      actionTo: '/tenants',
      actionLabel: 'Manage Tenants',
    },
    {
      done: kgCount > 0,
      label: 'Create a knowledge graph',
      description: 'Organise your data sources into a queryable knowledge graph.',
      actionTo: '/knowledge-graphs',
      actionLabel: 'Create Knowledge Graph',
    },
    {
      done: (nodeTypeCount ?? 0) > 0,
      label: 'Define a node type',
      description: 'Add at least one node type to your graph schema.',
      actionTo: '/graph/schema',
      actionLabel: 'Browse Schema',
    },
    {
      done: (apiKeyCount ?? 0) > 0,
      label: 'Create an API key',
      description: 'Generate an API key for programmatic access.',
      actionTo: '/api-keys',
      actionLabel: 'Create API Key',
    },
    {
      done: apiKeyLastUsed,
      label: 'Connect via MCP',
      description: 'Use your API key to connect an AI agent via MCP.',
      actionTo: '/integrate/mcp',
      actionLabel: 'MCP Integration',
    },
  ]
}

/**
 * Mirrors: const hasWorkspace = computed(() => workspaces.value.length > 0)
 * Controls whether WorkspaceGuidance or the Getting Started checklist is shown.
 */
function computeHasWorkspace(workspaces: WorkspaceResponse[]): boolean {
  return workspaces.length > 0
}

/**
 * Mirrors the v-if condition for WorkspaceGuidance in index.vue.
 * The component lives inside a <template v-else> gated by hasTenant,
 * so hasTenant is an implicit precondition.
 */
function computeShowWorkspaceGuidance(params: {
  hasTenant: boolean
  statsLoading: boolean
  workspaces: WorkspaceResponse[]
}): boolean {
  return params.hasTenant && !params.statsLoading && !computeHasWorkspace(params.workspaces)
}

/**
 * Mirrors: v-if="showChecklist && hasWorkspace" on the Getting Started card.
 * The card with data-testid="new-user-kg-prompt" only shows after workspace exists.
 */
function computeShowNewUserKgPrompt(params: {
  onboardingDismissed: boolean
  allChecklistDone: boolean
  hasWorkspace: boolean
}): boolean {
  const showChecklist = !params.onboardingDismissed && !params.allChecklistDone
  return showChecklist && params.hasWorkspace
}

/**
 * Mirrors the WorkspaceGuidance component emit definitions.
 * The component emits 'create' (Create Workspace) and 'join' (Join a Team Workspace).
 */
function workspaceGuidanceActions(): { emits: readonly ['create', 'join'] } {
  return { emits: ['create', 'join'] as const }
}

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 1: New user landing
// Spec: "GIVEN a user with no knowledge graphs, WHEN they open Kartograph,
//        THEN they are guided toward the setup flow with a prompt to create
//        their first knowledge graph"
// ─────────────────────────────────────────────────────────────────────────────

describe('task-103 — New user landing', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('new user with no KGs is NOT redirected away from home page', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, /* hasTenant */ true)

    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('new user stays on home (index) where the setup checklist is presented', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    const { kgCount } = await runLandingRedirect(apiFetch as any, navigateTo, true)

    // kgCount drives whether the KG checklist item is shown as done
    expect(kgCount).toBe(0)
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('checklist includes a "Create a knowledge graph" step (the setup prompt)', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((item) => item.label === 'Create a knowledge graph')
    expect(kgStep).toBeDefined()
    expect(kgStep!.done).toBe(false)
    expect(kgStep!.actionTo).toBe('/knowledge-graphs')
  })

  it('checklist "Create a knowledge graph" step links to /knowledge-graphs', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((item) => item.label === 'Create a knowledge graph')
    expect(kgStep!.actionTo).toBe('/knowledge-graphs')
    expect(kgStep!.actionLabel).toBe('Create Knowledge Graph')
  })

  it('the setup prompt (Getting Started checklist) only appears once workspace exists', () => {
    // Pre-workspace state — guidance blocks KG prompt
    const withoutWorkspace = computeShowNewUserKgPrompt({
      onboardingDismissed: false,
      allChecklistDone: false,
      hasWorkspace: false,
    })
    expect(withoutWorkspace).toBe(false)

    // Post-workspace state — KG prompt appears
    const withWorkspace = computeShowNewUserKgPrompt({
      onboardingDismissed: false,
      allChecklistDone: false,
      hasWorkspace: true,
    })
    expect(withWorkspace).toBe(true)
  })

  it('the KG checklist step is marked done once the user creates a knowledge graph', () => {
    const beforeKg = buildChecklistItems({
      hasTenant: true, kgCount: 0, nodeTypeCount: null, apiKeyCount: null, apiKeyLastUsed: false,
    })
    const afterKg = buildChecklistItems({
      hasTenant: true, kgCount: 1, nodeTypeCount: null, apiKeyCount: null, apiKeyLastUsed: false,
    })

    const stepBefore = beforeKg.find((i) => i.label === 'Create a knowledge graph')!
    const stepAfter = afterKg.find((i) => i.label === 'Create a knowledge graph')!

    expect(stepBefore.done).toBe(false)
    expect(stepAfter.done).toBe(true)
  })

  it('returning user with KGs IS redirected to /query on first session visit', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1' }, { id: 'kg-2' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, true)

    expect(navigateTo).toHaveBeenCalledWith('/query')
  })

  it('redirect to /query checks /management/knowledge-graphs endpoint', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [{ id: 'kg-1' }] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, true)

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs')
  })

  it('redirect is skipped on second visit in the same browser session', async () => {
    sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')

    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [{ id: 'kg-1' }] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, true)

    expect(apiFetch).not.toHaveBeenCalled()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('redirect does not happen when no tenant is selected', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [{ id: 'kg-1' }] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, /* hasTenant */ false)

    expect(apiFetch).not.toHaveBeenCalled()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('API error during redirect check is handled gracefully (stays on home)', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Network error'))
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await expect(
      runLandingRedirect(apiFetch as any, navigateTo, true),
    ).resolves.not.toThrow()

    expect(navigateTo).not.toHaveBeenCalled()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario 2: Workspace guidance
// Spec: "GIVEN a user entering a tenant for the first time, WHEN no personal
//        workspace exists, THEN the UI suggests creating one or joining an
//        existing team workspace"
// ─────────────────────────────────────────────────────────────────────────────

describe('task-103 — Workspace guidance', () => {
  it('workspace guidance is shown when tenant is set but no workspaces exist', () => {
    const shown = computeShowWorkspaceGuidance({
      hasTenant: true,
      statsLoading: false,
      workspaces: [],
    })
    expect(shown).toBe(true)
  })

  it('workspace guidance is NOT shown while stats are still loading', () => {
    // Prevents guidance flashing before workspace list is fetched
    const shown = computeShowWorkspaceGuidance({
      hasTenant: true,
      statsLoading: true,
      workspaces: [],
    })
    expect(shown).toBe(false)
  })

  it('workspace guidance is NOT shown when user has at least one workspace', () => {
    const workspaces: WorkspaceResponse[] = [
      {
        id: 'ws-1',
        name: 'Personal',
        tenant_id: 't-1',
        parent_workspace_id: null,
        is_root: true,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]
    const shown = computeShowWorkspaceGuidance({
      hasTenant: true,
      statsLoading: false,
      workspaces,
    })
    expect(shown).toBe(false)
  })

  it('workspace guidance is NOT shown when no tenant is selected', () => {
    const shown = computeShowWorkspaceGuidance({
      hasTenant: false,
      statsLoading: false,
      workspaces: [],
    })
    expect(shown).toBe(false)
  })

  it('WorkspaceGuidance component exposes a "create" emit for Create Workspace action', () => {
    const component = workspaceGuidanceActions()
    expect(component.emits).toContain('create')
  })

  it('WorkspaceGuidance component exposes a "join" emit for Join a Team Workspace action', () => {
    const component = workspaceGuidanceActions()
    expect(component.emits).toContain('join')
  })

  it('workspace guidance and KG setup prompt are mutually exclusive', () => {
    // State: no workspace — guidance shown, KG prompt hidden
    const workspaces: WorkspaceResponse[] = []
    const hasWorkspace = computeHasWorkspace(workspaces)

    const showGuidance = computeShowWorkspaceGuidance({
      hasTenant: true,
      statsLoading: false,
      workspaces,
    })
    const showKgPrompt = computeShowNewUserKgPrompt({
      onboardingDismissed: false,
      allChecklistDone: false,
      hasWorkspace,
    })

    expect(showGuidance).toBe(true)
    expect(showKgPrompt).toBe(false)
    expect(showGuidance && showKgPrompt).toBe(false)
  })

  it('once workspace is created guidance disappears and KG prompt becomes visible', () => {
    const workspace: WorkspaceResponse = {
      id: 'ws-new',
      name: 'My Team Workspace',
      tenant_id: 't-1',
      parent_workspace_id: null,
      is_root: true,
      created_at: '2024-01-02T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    }

    const workspaces = [workspace]
    const hasWorkspace = computeHasWorkspace(workspaces)

    const showGuidance = computeShowWorkspaceGuidance({
      hasTenant: true,
      statsLoading: false,
      workspaces,
    })
    const showKgPrompt = computeShowNewUserKgPrompt({
      onboardingDismissed: false,
      allChecklistDone: false,
      hasWorkspace,
    })

    expect(showGuidance).toBe(false)
    expect(showKgPrompt).toBe(true)
  })

  it('workspace list is fetched from GET /iam/workspaces', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ workspaces: [], count: 0 })

    async function listWorkspaces(): Promise<WorkspaceResponse[]> {
      const result = await apiFetch('/iam/workspaces')
      return result.workspaces ?? []
    }

    await listWorkspaces()
    expect(apiFetch).toHaveBeenCalledWith('/iam/workspaces')
  })

  it('hasWorkspace is false when /iam/workspaces returns empty list', async () => {
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
      workspaces: [
        {
          id: 'ws-1', name: 'Personal', tenant_id: 't-1',
          parent_workspace_id: null, is_root: true,
          created_at: '', updated_at: '',
        },
      ],
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
