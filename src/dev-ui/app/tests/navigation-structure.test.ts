import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Task: task-119 — UI Navigation Structure & Routing ────────────────────────
//
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task-Ref: task-119
//
// Requirement: Navigation Structure
//   Scenario: Primary navigation
//     "GIVEN an authenticated user, THEN the sidebar presents navigation
//     grouped as: Explore, Data, Connect, Settings"
//
//   Scenario: Default landing
//     "GIVEN a returning user with existing knowledge graphs, WHEN they open
//     Kartograph, THEN they land on the Explore section (Query Console or
//     home dashboard)"
//
//   Scenario: New user landing
//     "GIVEN a user with no knowledge graphs, WHEN they open Kartograph,
//     THEN they are guided toward the setup flow with a prompt to create
//     their first knowledge graph"
//
// Implementation files:
//   - src/dev-ui/app/layouts/default.vue   (navSections computed ref)
//   - src/dev-ui/app/pages/index.vue       (landing redirect + checklist)
//   - src/dev-ui/app/middleware/auth.global.ts (auth guard)

// ─────────────────────────────────────────────────────────────────────────────
// Shared types
// ─────────────────────────────────────────────────────────────────────────────

interface NavItem {
  label: string
  to: string
  badge?: string
  ariaLabel?: string
}

interface NavSection {
  title: string
  items: NavItem[]
}

interface ChecklistItem {
  done: boolean
  label: string
  description: string
  actionTo: string
  actionLabel: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Extracted logic — mirrors layouts/default.vue navSections computed ref
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Mirrors the navSections computed ref from layouts/default.vue.
 * The four goal-oriented groups are the canonical navigation structure.
 */
function buildNavSections(activeSyncCount: number = 0): NavSection[] {
  const badge = activeSyncCount > 0 ? String(activeSyncCount) : undefined
  const dsAriaLabel = badge
    ? `Data Sources — ${activeSyncCount} active sync${activeSyncCount === 1 ? '' : 's'}`
    : undefined

  return [
    {
      title: 'Explore',
      items: [
        { label: 'Query Console', to: '/query' },
        { label: 'Schema Browser', to: '/graph/schema' },
        { label: 'Graph Explorer', to: '/graph/explorer' },
        { label: 'Mutations Console', to: '/graph/mutations' },
      ],
    },
    {
      title: 'Data',
      items: [
        { label: 'Knowledge Graphs', to: '/knowledge-graphs' },
        {
          label: 'Data Sources',
          to: '/data-sources',
          badge,
          ariaLabel: dsAriaLabel,
        },
      ],
    },
    {
      title: 'Connect',
      items: [
        { label: 'API Keys', to: '/api-keys' },
        { label: 'MCP Integration', to: '/integrate/mcp' },
      ],
    },
    {
      title: 'Settings',
      items: [
        { label: 'Workspaces', to: '/workspaces' },
        { label: 'Groups', to: '/groups' },
        { label: 'Tenants', to: '/tenants' },
      ],
    },
  ]
}

// ─────────────────────────────────────────────────────────────────────────────
// Extracted logic — mirrors pages/index.vue landing redirect (onMounted)
// ─────────────────────────────────────────────────────────────────────────────

const SESSION_REDIRECT_KEY = 'kartograph:home-redirect-done'

/**
 * Mirrors the redirect guard from pages/index.vue onMounted.
 * Returning users (kgCount > 0) are sent to /query on first visit per session.
 * New users (kgCount === 0) stay on the home page where the setup checklist
 * is shown.
 */
async function runLandingRedirect(
  apiFetch: (path: string) => Promise<{ knowledge_graphs: { id: string }[] }>,
  navigateTo: (path: string) => Promise<void>,
  hasTenant: boolean,
): Promise<{ kgCount: number }> {
  if (typeof sessionStorage === 'undefined') return { kgCount: 0 }

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

// ─────────────────────────────────────────────────────────────────────────────
// Extracted logic — mirrors pages/index.vue checklistItems computed ref
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Mirrors the checklistItems computed ref from pages/index.vue.
 * The list drives the "Getting Started" onboarding checklist shown to
 * new users. Each item has a done flag, a label, and an actionTo route.
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

// ─────────────────────────────────────────────────────────────────────────────
// Extracted logic — isActive helper from layouts/default.vue
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Mirrors the isActive() helper from layouts/default.vue.
 * Determines whether a nav item should render with the active highlight.
 */
function isActive(currentPath: string, to: string): boolean {
  if (to === '/') return currentPath === '/'
  if (to === '#') return false
  return currentPath === to || currentPath.startsWith(to + '/')
}

// ─────────────────────────────────────────────────────────────────────────────
// Extracted logic — auth guard from middleware/auth.global.ts
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Mirrors the route guard logic from middleware/auth.global.ts.
 * Unauthenticated users (except on /auth/callback) are redirected to login.
 */
function shouldRedirectToLogin(params: {
  path: string
  isAuthenticated: boolean
}): boolean {
  if (params.path === '/auth/callback') return false
  return !params.isAuthenticated
}

// ─────────────────────────────────────────────────────────────────────────────
// Scenario: Primary navigation
// Spec: "GIVEN an authenticated user, THEN the sidebar presents navigation
//        grouped as: Explore — Query Console, Schema Browser, Graph Explorer,
//        Mutations Console; Data — Knowledge Graphs, Data Sources (with sync
//        status); Connect — API Keys, MCP Integration;
//        Settings — Workspaces, Groups, Tenants"
// ─────────────────────────────────────────────────────────────────────────────

describe('task-119 — Primary navigation', () => {
  const sections = buildNavSections()

  it('sidebar presents exactly four navigation groups', () => {
    expect(sections).toHaveLength(4)
  })

  it('groups appear in the required order: Explore, Data, Connect, Settings', () => {
    const titles = sections.map((s) => s.title)
    expect(titles).toEqual(['Explore', 'Data', 'Connect', 'Settings'])
  })

  it('Explore group contains Query Console, Schema Browser, Graph Explorer, Mutations Console', () => {
    const explore = sections.find((s) => s.title === 'Explore')!
    const labels = explore.items.map((i) => i.label)
    expect(labels).toEqual([
      'Query Console',
      'Schema Browser',
      'Graph Explorer',
      'Mutations Console',
    ])
  })

  it('Explore → Query Console routes to /query', () => {
    const explore = sections.find((s) => s.title === 'Explore')!
    const qc = explore.items.find((i) => i.label === 'Query Console')!
    expect(qc.to).toBe('/query')
  })

  it('Explore → Schema Browser routes to /graph/schema', () => {
    const explore = sections.find((s) => s.title === 'Explore')!
    const sb = explore.items.find((i) => i.label === 'Schema Browser')!
    expect(sb.to).toBe('/graph/schema')
  })

  it('Explore → Graph Explorer routes to /graph/explorer', () => {
    const explore = sections.find((s) => s.title === 'Explore')!
    const ge = explore.items.find((i) => i.label === 'Graph Explorer')!
    expect(ge.to).toBe('/graph/explorer')
  })

  it('Explore → Mutations Console routes to /graph/mutations', () => {
    const explore = sections.find((s) => s.title === 'Explore')!
    const mc = explore.items.find((i) => i.label === 'Mutations Console')!
    expect(mc.to).toBe('/graph/mutations')
  })

  it('Data group contains Knowledge Graphs and Data Sources', () => {
    const data = sections.find((s) => s.title === 'Data')!
    const labels = data.items.map((i) => i.label)
    expect(labels).toContain('Knowledge Graphs')
    expect(labels).toContain('Data Sources')
  })

  it('Data → Knowledge Graphs routes to /knowledge-graphs', () => {
    const data = sections.find((s) => s.title === 'Data')!
    const kg = data.items.find((i) => i.label === 'Knowledge Graphs')!
    expect(kg.to).toBe('/knowledge-graphs')
  })

  it('Data → Data Sources routes to /data-sources', () => {
    const data = sections.find((s) => s.title === 'Data')!
    const ds = data.items.find((i) => i.label === 'Data Sources')!
    expect(ds.to).toBe('/data-sources')
  })

  it('Data Sources shows a numeric badge when syncs are active', () => {
    const sectionsWithBadge = buildNavSections(3)
    const data = sectionsWithBadge.find((s) => s.title === 'Data')!
    const ds = data.items.find((i) => i.label === 'Data Sources')!
    expect(ds.badge).toBe('3')
    expect(ds.ariaLabel).toContain('3 active syncs')
  })

  it('Data Sources badge is absent when no syncs are active', () => {
    const ds = sections.find((s) => s.title === 'Data')!.items.find(
      (i) => i.label === 'Data Sources',
    )!
    expect(ds.badge).toBeUndefined()
  })

  it('Connect group contains API Keys and MCP Integration', () => {
    const connect = sections.find((s) => s.title === 'Connect')!
    const labels = connect.items.map((i) => i.label)
    expect(labels).toEqual(['API Keys', 'MCP Integration'])
  })

  it('Connect → API Keys routes to /api-keys', () => {
    const connect = sections.find((s) => s.title === 'Connect')!
    const ak = connect.items.find((i) => i.label === 'API Keys')!
    expect(ak.to).toBe('/api-keys')
  })

  it('Connect → MCP Integration routes to /integrate/mcp', () => {
    const connect = sections.find((s) => s.title === 'Connect')!
    const mcp = connect.items.find((i) => i.label === 'MCP Integration')!
    expect(mcp.to).toBe('/integrate/mcp')
  })

  it('Settings group contains Workspaces, Groups, and Tenants', () => {
    const settings = sections.find((s) => s.title === 'Settings')!
    const labels = settings.items.map((i) => i.label)
    expect(labels).toEqual(['Workspaces', 'Groups', 'Tenants'])
  })

  it('Settings → Workspaces routes to /workspaces', () => {
    const settings = sections.find((s) => s.title === 'Settings')!
    const ws = settings.items.find((i) => i.label === 'Workspaces')!
    expect(ws.to).toBe('/workspaces')
  })

  it('Settings → Groups routes to /groups', () => {
    const settings = sections.find((s) => s.title === 'Settings')!
    const gr = settings.items.find((i) => i.label === 'Groups')!
    expect(gr.to).toBe('/groups')
  })

  it('Settings → Tenants routes to /tenants', () => {
    const settings = sections.find((s) => s.title === 'Settings')!
    const tn = settings.items.find((i) => i.label === 'Tenants')!
    expect(tn.to).toBe('/tenants')
  })

  it('all nav items across all sections have non-empty labels and routes', () => {
    for (const section of sections) {
      for (const item of section.items) {
        expect(item.label).toBeTruthy()
        expect(item.to).toMatch(/^\//)
      }
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario: Default landing
// Spec: "GIVEN a returning user with existing knowledge graphs, WHEN they open
//        Kartograph, THEN they land on the Explore section (Query Console or
//        home dashboard)"
// ─────────────────────────────────────────────────────────────────────────────

describe('task-119 — Default landing', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('returning user with existing KGs is redirected to /query', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1' }, { id: 'kg-2' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, /* hasTenant */ true)

    expect(navigateTo).toHaveBeenCalledWith('/query')
  })

  it('redirect checks /management/knowledge-graphs to determine returning status', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, true)

    expect(apiFetch).toHaveBeenCalledWith('/management/knowledge-graphs')
  })

  it('redirect to Query Console (/query) satisfies "Explore section" landing', () => {
    // /query is within the Explore group — landing there satisfies the spec.
    const sections = buildNavSections()
    const explore = sections.find((s) => s.title === 'Explore')!
    const qcItem = explore.items.find((i) => i.to === '/query')
    expect(qcItem).toBeDefined()
    expect(qcItem!.label).toBe('Query Console')
  })

  it('redirect is NOT performed for users with no knowledge graphs', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, true)

    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('redirect only fires once per session (sessionStorage guard)', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    // First visit — redirect fires.
    await runLandingRedirect(apiFetch as any, navigateTo, true)
    expect(navigateTo).toHaveBeenCalledTimes(1)

    // Second visit in same session — guard is set; no redirect.
    await runLandingRedirect(apiFetch as any, navigateTo, true)
    expect(navigateTo).toHaveBeenCalledTimes(1)
  })

  it('redirect is skipped when no tenant is selected', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, /* hasTenant */ false)

    expect(apiFetch).not.toHaveBeenCalled()
    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('API error during KG fetch is handled gracefully — user stays on home', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Network error'))
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await expect(
      runLandingRedirect(apiFetch as any, navigateTo, true),
    ).resolves.not.toThrow()

    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('kgCount returned from redirect is the correct count', async () => {
    const apiFetch = vi.fn().mockResolvedValue({
      knowledge_graphs: [{ id: 'kg-1' }, { id: 'kg-2' }, { id: 'kg-3' }],
    })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    const { kgCount } = await runLandingRedirect(apiFetch as any, navigateTo, true)

    expect(kgCount).toBe(3)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario: New user landing
// Spec: "GIVEN a user with no knowledge graphs, WHEN they open Kartograph,
//        THEN they are guided toward the setup flow with a prompt to create
//        their first knowledge graph"
// ─────────────────────────────────────────────────────────────────────────────

describe('task-119 — New user landing', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('new user with no KGs stays on the home page (no redirect)', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ knowledge_graphs: [] })
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    await runLandingRedirect(apiFetch as any, navigateTo, true)

    expect(navigateTo).not.toHaveBeenCalled()
  })

  it('the setup checklist includes a "Create a knowledge graph" step', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((i) => i.label === 'Create a knowledge graph')
    expect(kgStep).toBeDefined()
  })

  it('"Create a knowledge graph" step is not done when kgCount is 0', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((i) => i.label === 'Create a knowledge graph')!
    expect(kgStep.done).toBe(false)
  })

  it('"Create a knowledge graph" step links to /knowledge-graphs', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((i) => i.label === 'Create a knowledge graph')!
    expect(kgStep.actionTo).toBe('/knowledge-graphs')
  })

  it('"Create a knowledge graph" step is done once the user creates one', () => {
    const items = buildChecklistItems({
      hasTenant: true,
      kgCount: 1,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    const kgStep = items.find((i) => i.label === 'Create a knowledge graph')!
    expect(kgStep.done).toBe(true)
  })

  it('setup checklist has 5 steps that guide the user through the full setup flow', () => {
    const items = buildChecklistItems({
      hasTenant: false,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    expect(items).toHaveLength(5)
    const labels = items.map((i) => i.label)
    expect(labels).toContain('Create a tenant')
    expect(labels).toContain('Create a knowledge graph')
    expect(labels).toContain('Define a node type')
    expect(labels).toContain('Create an API key')
    expect(labels).toContain('Connect via MCP')
  })

  it('each checklist step has a route to navigate to for action', () => {
    const items = buildChecklistItems({
      hasTenant: false,
      kgCount: 0,
      nodeTypeCount: null,
      apiKeyCount: null,
      apiKeyLastUsed: false,
    })

    for (const item of items) {
      expect(item.actionTo).toMatch(/^\//)
      expect(item.actionLabel).toBeTruthy()
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Route guard — auth guard verifies every navigation
// ─────────────────────────────────────────────────────────────────────────────

describe('task-119 — Auth route guard', () => {
  it('unauthenticated user is redirected to login on protected routes', () => {
    expect(
      shouldRedirectToLogin({ path: '/query', isAuthenticated: false }),
    ).toBe(true)
  })

  it('authenticated user is NOT redirected to login', () => {
    expect(
      shouldRedirectToLogin({ path: '/query', isAuthenticated: true }),
    ).toBe(false)
  })

  it('auth/callback page is exempt from the auth guard (allows OIDC code exchange)', () => {
    expect(
      shouldRedirectToLogin({ path: '/auth/callback', isAuthenticated: false }),
    ).toBe(false)
  })

  it('guard applies to all non-callback routes', () => {
    const protectedRoutes = [
      '/',
      '/query',
      '/graph/schema',
      '/graph/explorer',
      '/graph/mutations',
      '/knowledge-graphs',
      '/data-sources',
      '/api-keys',
      '/integrate/mcp',
      '/workspaces',
      '/groups',
      '/tenants',
    ]

    for (const route of protectedRoutes) {
      expect(
        shouldRedirectToLogin({ path: route, isAuthenticated: false }),
      ).toBe(true)
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Active state detection — sidebar highlights the current route
// ─────────────────────────────────────────────────────────────────────────────

describe('task-119 — Sidebar active state', () => {
  it('nav item at exact current path is active', () => {
    expect(isActive('/query', '/query')).toBe(true)
  })

  it('nav item is active for sub-paths (e.g. /query?kg=abc)', () => {
    // The isActive function checks startsWith(to + '/') — direct sub-routes match.
    // NB: query params are not part of route.path; the path itself triggers this.
    expect(isActive('/graph/schema/node', '/graph/schema')).toBe(true)
  })

  it('home nav item is only active on exact / path', () => {
    expect(isActive('/', '/')).toBe(true)
    expect(isActive('/query', '/')).toBe(false)
  })

  it('nav item is NOT active when on a different route', () => {
    expect(isActive('/graph/schema', '/query')).toBe(false)
    expect(isActive('/workspaces', '/api-keys')).toBe(false)
  })

  it('disabled nav items (to="#") are never marked active', () => {
    expect(isActive('/query', '#')).toBe(false)
    expect(isActive('/', '#')).toBe(false)
  })
})
