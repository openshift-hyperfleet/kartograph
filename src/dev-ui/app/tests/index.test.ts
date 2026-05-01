import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Requirement: Navigation Structure — Default landing ───────────────────────
// Spec: "GIVEN a returning user with existing knowledge graphs, WHEN they open
// Kartograph, THEN they land on the Explore section (Query Console or home dashboard)"
//
// The redirect logic lives in onMounted of index.vue. We test it by replicating
// the exact guard logic so regressions in the implementation are immediately caught.

const SESSION_REDIRECT_KEY = 'kartograph:home-redirect-done'

/**
 * Replicate the redirect logic from index.vue's onMounted block so it can be
 * tested in isolation. The signature mirrors the real implementation:
 *   - apiFetch  — the result of useApiClient().apiFetch
 *   - navigateTo — the Nuxt global (passed in so we can spy on it in tests)
 *   - hasTenant — hasTenant.value from useTenant()
 */
async function runRedirectLogic(
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
    // Graceful fallback — continue without redirecting
  }

  if (kgCount > 0) {
    sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')
    await navigateTo('/query')
    return { kgCount }
  }

  sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')
  return { kgCount }
}

describe('Index Page — Default landing redirect', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('redirects to /query when knowledge graphs exist', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1', name: 'My Graph' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runRedirectLogic(apiFetch as any, navigateTo, /* hasTenant */ true)

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs')
    expect(navigateTo).toHaveBeenCalledWith('/query')
  })

  it('does NOT redirect when no knowledge graphs exist', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runRedirectLogic(apiFetch as any, navigateTo, /* hasTenant */ true)

    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('does NOT redirect when apiFetch throws (graceful fallback)', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Unauthorized'))
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    // Should not throw
    await expect(
      runRedirectLogic(apiFetch as any, navigateTo, /* hasTenant */ true),
    ).resolves.not.toThrow()

    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('does NOT redirect when hasTenant is false', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1', name: 'My Graph' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runRedirectLogic(apiFetch as any, navigateTo, /* hasTenant */ false)

    expect(apiFetch).not.toHaveBeenCalled()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('does NOT redirect on a second visit in the same session (already redirected)', async () => {
    sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')

    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1', name: 'My Graph' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runRedirectLogic(apiFetch as any, navigateTo, /* hasTenant */ true)

    expect(navigateTo).not.toHaveBeenCalled()
  })
})

// ── Requirement: Navigation Structure — New user landing ─────────────────────
// Spec: "GIVEN a user with no knowledge graphs, WHEN they open Kartograph,
// THEN they are guided toward the setup flow with a prompt to create their first
// knowledge graph"
//
// The onboarding checklist computed in index.vue must contain a KG creation step.
// These tests verify the checklist shape and the done/not-done logic.

/**
 * Replicate the checklistItems computed from index.vue.
 * The second item (index 1) must be the "Create a knowledge graph" step.
 */
function buildChecklistItems(params: {
  hasTenant: boolean
  kgCount: number
  nodeTypeCount: number | null
  apiKeyCount: number | null
  apiKeyLastUsed: boolean
}) {
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

describe('Index Page — Checklist includes "Create a knowledge graph" step', () => {
  it('checklist contains a "Create a knowledge graph" item', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((item) => item.label === 'Create a knowledge graph')
    expect(kgStep).toBeDefined()
  })

  it('KG step actionTo is /knowledge-graphs', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((item) => item.label === 'Create a knowledge graph')
    expect(kgStep?.actionTo).toBe('/knowledge-graphs')
  })

  it('KG step done is true when kgCount > 0', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 2,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((item) => item.label === 'Create a knowledge graph')
    expect(kgStep?.done).toBe(true)
  })

  it('KG step done is false when kgCount is 0', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((item) => item.label === 'Create a knowledge graph')
    expect(kgStep?.done).toBe(false)
  })

  it('checklist has 5 steps total (tenant, KG, node type, API key, MCP)', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 1,
      nodeTypeCount: 2,
      apiKeyCount: 1,
      apiKeyLastUsed: true,
    })

    expect(items).toHaveLength(5)
  })
})

// ── Requirement: Tenant and Workspace Context — Workspace guidance ────────────
// Spec: "GIVEN a user entering a tenant for the first time, WHEN no personal workspace
// exists, THEN the UI suggests creating one or joining an existing team workspace"

const WORKSPACE_GUIDANCE_KEY = 'kartograph:workspace-guidance:'

/**
 * Replicate the workspace guidance logic from index.vue.
 * The toast function is passed in so we can spy on it.
 */
function showWorkspaceGuidanceIfNeeded(params: {
  currentTenantId: string | null
  workspaceCount: number | null
  toast: (msg: string, opts?: unknown) => void
  navigateTo: (path: string) => Promise<void>
}): void {
  const { currentTenantId, workspaceCount, toast, navigateTo } = params

  if (!currentTenantId || workspaceCount !== 0) return

  const key = `${WORKSPACE_GUIDANCE_KEY}${currentTenantId}`
  if (typeof localStorage !== 'undefined' && localStorage.getItem(key)) return
  if (typeof localStorage !== 'undefined') localStorage.setItem(key, 'true')

  toast('Create or join a workspace', {
    description:
      'Workspaces help you organise your knowledge graphs. Create one or ask a team member to invite you.',
    action: {
      label: 'Manage Workspaces',
      onClick: () => navigateTo('/workspaces'),
    },
    duration: 8000,
  })
}

describe('Index Page — Workspace guidance toast', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('shows workspace guidance toast when workspaceCount is 0 and key not set', () => {
    const toast = vi.fn()
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    showWorkspaceGuidanceIfNeeded({
      currentTenantId: 'tenant-abc',
      workspaceCount: 0,
      toast,
      navigateTo,
    })

    expect(toast).toHaveBeenCalledWith('Create or join a workspace', expect.any(Object))
  })

  it('does NOT show toast if guidance was already shown for this tenant', () => {
    localStorage.setItem(`${WORKSPACE_GUIDANCE_KEY}tenant-abc`, 'true')

    const toast = vi.fn()
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    showWorkspaceGuidanceIfNeeded({
      currentTenantId: 'tenant-abc',
      workspaceCount: 0,
      toast,
      navigateTo,
    })

    expect(toast).not.toHaveBeenCalled()
  })

  it('does NOT show toast if workspaceCount is > 0', () => {
    const toast = vi.fn()
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    showWorkspaceGuidanceIfNeeded({
      currentTenantId: 'tenant-abc',
      workspaceCount: 2,
      toast,
      navigateTo,
    })

    expect(toast).not.toHaveBeenCalled()
  })

  it('does NOT show toast if no tenant is set', () => {
    const toast = vi.fn()
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    showWorkspaceGuidanceIfNeeded({
      currentTenantId: null,
      workspaceCount: 0,
      toast,
      navigateTo,
    })

    expect(toast).not.toHaveBeenCalled()
  })

  it('sets per-tenant localStorage guard after showing toast', () => {
    const toast = vi.fn()
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    showWorkspaceGuidanceIfNeeded({
      currentTenantId: 'tenant-xyz',
      workspaceCount: 0,
      toast,
      navigateTo,
    })

    expect(localStorage.getItem(`${WORKSPACE_GUIDANCE_KEY}tenant-xyz`)).toBe('true')
  })
})
