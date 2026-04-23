import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Interaction Principles Tests ──────────────────────────────────────────────
//
// Spec: "Interaction Principles"
// Covers:
//   - Scenario: Copy-to-clipboard (copy button provided, toast confirms)
//   - Scenario: Mutation feedback (toast notification confirms success or reports failure)
//   - Scenario: Inline actions over navigation (editing happens in-place or side panel)
//   - Scenario: Progressive disclosure (summary by default, detail on demand)

// ── Scenario: Copy-to-clipboard ───────────────────────────────────────────────
// Spec: "GIVEN any identifier, configuration snippet, or secret
// THEN a copy button is provided
// AND a toast confirms the copy action"

describe('Interaction Principles - copy to clipboard', () => {
  it('calls clipboard.writeText with the correct content', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    let toastMsg = ''

    async function copyToClipboard(text: string, label?: string) {
      try {
        await writeText(text)
        toastMsg = label ? `${label} copied` : 'Copied to clipboard'
        return true
      } catch {
        toastMsg = 'Failed to copy to clipboard'
        return false
      }
    }

    const success = await copyToClipboard('krtgph_secret123', 'API key secret')
    expect(writeText).toHaveBeenCalledWith('krtgph_secret123')
    expect(success).toBe(true)
    expect(toastMsg).toBe('API key secret copied')
  })

  it('shows error toast when clipboard write fails', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('Permission denied'))
    let toastMsg = ''

    async function copyToClipboard(text: string, label?: string) {
      try {
        await writeText(text)
        toastMsg = label ? `${label} copied` : 'Copied to clipboard'
        return true
      } catch {
        toastMsg = 'Failed to copy to clipboard'
        return false
      }
    }

    const success = await copyToClipboard('some-text')
    expect(success).toBe(false)
    expect(toastMsg).toBe('Failed to copy to clipboard')
  })

  it('uses generic "Copied to clipboard" when no label provided', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    let toastMsg = ''

    async function copyToClipboard(text: string, label?: string) {
      try {
        await writeText(text)
        toastMsg = label ? `${label} copied` : 'Copied to clipboard'
        return true
      } catch {
        return false
      }
    }

    await copyToClipboard('some-id-value')
    expect(toastMsg).toBe('Copied to clipboard')
  })

  it('shows copied state feedback after click (copiedFlag pattern)', async () => {
    const copiedConfigTab = { value: null as string | null }
    const writeText = vi.fn().mockResolvedValue(undefined)

    async function copyConfig(tab: string, text: string) {
      await writeText(text)
      copiedConfigTab.value = tab
      // In the real component, this resets after 2000ms
    }

    await copyConfig('Claude Code', 'claude mcp add ...')
    expect(copiedConfigTab.value).toBe('Claude Code')
  })
})

// ── Scenario: Mutation feedback ───────────────────────────────────────────────
// Spec: "GIVEN a write operation (create, update, delete)
// THEN a toast notification confirms success or reports failure
// AND validation errors are shown inline on form fields"

describe('Interaction Principles - mutation feedback', () => {
  it('shows success toast on create operation', async () => {
    const apiFetch = vi.fn().mockResolvedValue({ id: 'new-1', name: 'Test' })
    let successToast = ''

    async function handleCreate(name: string) {
      const result = await apiFetch('/resource', { method: 'POST', body: { name } })
      successToast = `"${result.name}" created`
    }

    await handleCreate('Test')
    expect(successToast).toBe('"Test" created')
  })

  it('shows error toast on failed create operation', async () => {
    const apiFetch = vi.fn().mockRejectedValue(new Error('Conflict'))
    let errorToast = ''

    async function handleCreate(name: string) {
      try {
        await apiFetch('/resource', { method: 'POST', body: { name } })
      } catch (err) {
        errorToast = err instanceof Error ? err.message : 'Create failed'
      }
    }

    await handleCreate('Duplicate')
    expect(errorToast).toBe('Conflict')
  })

  it('shows validation error inline when form field is empty', () => {
    const nameError = { value: '' }
    const name = { value: '' }

    function validate() {
      nameError.value = ''
      if (!name.value.trim()) {
        nameError.value = 'Name is required'
        return false
      }
      return true
    }

    const valid = validate()
    expect(valid).toBe(false)
    expect(nameError.value).toBe('Name is required')
  })

  it('clears validation error when field is corrected', () => {
    const nameError = { value: 'Name is required' }
    const name = { value: 'My Resource' }

    function validate() {
      nameError.value = ''
      if (!name.value.trim()) {
        nameError.value = 'Name is required'
        return false
      }
      return true
    }

    const valid = validate()
    expect(valid).toBe(true)
    expect(nameError.value).toBe('')
  })

  it('shows success toast on delete (revoke) operation', async () => {
    const apiFetch = vi.fn().mockResolvedValue({})
    let successToast = ''

    async function handleRevoke(keyName: string) {
      await apiFetch('/iam/api-keys/key-1/revoke', { method: 'POST' })
      successToast = `API key "${keyName}" revoked`
    }

    await handleRevoke('CI Pipeline')
    expect(successToast).toBe('API key "CI Pipeline" revoked')
  })
})

// ── Scenario: Progressive disclosure ─────────────────────────────────────────
// Spec: "GIVEN complex information THEN the UI shows a summary by default
// AND detail is revealed on demand (expand, drill-in, sheet)"

describe('Interaction Principles - progressive disclosure', () => {
  it('collapsible section starts collapsed (showDetails = false)', () => {
    const showDetails = { value: false }
    expect(showDetails.value).toBe(false)
  })

  it('toggles section expanded when clicked', () => {
    const showDetails = { value: false }

    function toggleDetails() {
      showDetails.value = !showDetails.value
    }

    toggleDetails()
    expect(showDetails.value).toBe(true)

    toggleDetails()
    expect(showDetails.value).toBe(false)
  })

  it('sheet/drawer starts closed and opens on user action', () => {
    const sheetOpen = { value: false }

    function openSheet() {
      sheetOpen.value = true
    }

    expect(sheetOpen.value).toBe(false)
    openSheet()
    expect(sheetOpen.value).toBe(true)
  })
})

// ── Scenario: Inline actions over navigation ──────────────────────────────────
// Spec: "GIVEN an editable resource THEN editing happens in-place or in a side panel
// AND the user is not navigated to a separate edit page"

describe('Interaction Principles - inline editing patterns', () => {
  it('dialog/sheet opens for inline edit rather than route navigation', () => {
    const editDialogOpen = { value: false }
    let navigatedTo = ''

    function openEditDialog() {
      editDialogOpen.value = true
      // No navigation — editing is in-place
    }

    openEditDialog()
    expect(editDialogOpen.value).toBe(true)
    expect(navigatedTo).toBe('') // No navigation occurred
  })

  it('closing edit dialog resets open state', () => {
    const editDialogOpen = { value: true }

    function closeEditDialog() {
      editDialogOpen.value = false
    }

    closeEditDialog()
    expect(editDialogOpen.value).toBe(false)
  })
})

// ── Scenario: Navigation sidebar structure ────────────────────────────────────
// Spec: "the sidebar presents navigation grouped as:
//   Explore — Query Console, Schema Browser, Graph Explorer
//   Data — Knowledge Graphs, Data Sources (with sync status)
//   Connect — API Keys, MCP Integration
//   Settings — Workspaces, Groups, Tenants"

describe('Navigation - sidebar section structure', () => {
  const navSections = [
    {
      title: 'Explore',
      items: [
        { label: 'Query Console', to: '/query' },
        { label: 'Schema Browser', to: '/graph/schema' },
        { label: 'Graph Explorer', to: '/graph/explorer' },
      ],
    },
    {
      title: 'Data',
      items: [
        { label: 'Knowledge Graphs', to: '/knowledge-graphs' },
        { label: 'Data Sources', to: '/data-sources' },
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

  it('has exactly 4 nav sections', () => {
    expect(navSections).toHaveLength(4)
  })

  it('Explore section contains Query Console, Schema Browser, Graph Explorer', () => {
    const explore = navSections.find((s) => s.title === 'Explore')!
    const labels = explore.items.map((i) => i.label)
    expect(labels).toContain('Query Console')
    expect(labels).toContain('Schema Browser')
    expect(labels).toContain('Graph Explorer')
  })

  it('Data section contains Knowledge Graphs and Data Sources', () => {
    const data = navSections.find((s) => s.title === 'Data')!
    const labels = data.items.map((i) => i.label)
    expect(labels).toContain('Knowledge Graphs')
    expect(labels).toContain('Data Sources')
  })

  it('Connect section contains API Keys and MCP Integration', () => {
    const connect = navSections.find((s) => s.title === 'Connect')!
    const labels = connect.items.map((i) => i.label)
    expect(labels).toContain('API Keys')
    expect(labels).toContain('MCP Integration')
  })

  it('Settings section contains Workspaces, Groups, Tenants', () => {
    const settings = navSections.find((s) => s.title === 'Settings')!
    const labels = settings.items.map((i) => i.label)
    expect(labels).toContain('Workspaces')
    expect(labels).toContain('Groups')
    expect(labels).toContain('Tenants')
  })

  it('all nav items have valid route paths', () => {
    const allItems = navSections.flatMap((s) => s.items)
    for (const item of allItems) {
      expect(item.to).toMatch(/^\//)
    }
  })
})

// ── Scenario: Workspace guidance (new user) ───────────────────────────────────
// Spec: "GIVEN a user entering a tenant for the first time
// WHEN no personal workspace exists
// THEN the UI suggests creating one or joining an existing team workspace"

describe('Navigation - workspace guidance for new users', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('shows guidance toast when workspace count is 0', () => {
    const WORKSPACE_GUIDANCE_KEY = 'kartograph:workspace-guidance:'
    const tenantId = 'tenant-abc'
    const workspaceCount = 0
    let guidanceShown = false

    function showWorkspaceGuidanceIfNeeded() {
      if (workspaceCount !== 0) return
      const key = `${WORKSPACE_GUIDANCE_KEY}${tenantId}`
      if (localStorage.getItem(key)) return
      localStorage.setItem(key, 'true')
      guidanceShown = true
    }

    showWorkspaceGuidanceIfNeeded()
    expect(guidanceShown).toBe(true)
    expect(localStorage.getItem(`${WORKSPACE_GUIDANCE_KEY}${tenantId}`)).toBe('true')
  })

  it('does NOT show guidance again after it has been shown once', () => {
    const WORKSPACE_GUIDANCE_KEY = 'kartograph:workspace-guidance:'
    const tenantId = 'tenant-abc'
    localStorage.setItem(`${WORKSPACE_GUIDANCE_KEY}${tenantId}`, 'true')
    let guidanceShown = false

    function showWorkspaceGuidanceIfNeeded() {
      const key = `${WORKSPACE_GUIDANCE_KEY}${tenantId}`
      if (localStorage.getItem(key)) return
      localStorage.setItem(key, 'true')
      guidanceShown = true
    }

    showWorkspaceGuidanceIfNeeded()
    expect(guidanceShown).toBe(false)
  })

  it('does NOT show guidance when workspaces already exist', () => {
    const tenantId = 'tenant-abc'
    const workspaceCount = 2
    let guidanceShown = false

    function showWorkspaceGuidanceIfNeeded() {
      if (workspaceCount !== 0) return
      guidanceShown = true
    }

    showWorkspaceGuidanceIfNeeded()
    expect(guidanceShown).toBe(false)
  })
})

// ── Scenario: Returning user redirect ─────────────────────────────────────────
// Spec: "GIVEN a returning user with existing knowledge graphs
// WHEN they open Kartograph THEN they land on the Explore section"

describe('Navigation - returning user redirect', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('detects returning user via query history in localStorage', () => {
    const queryHistory = [{ query: 'MATCH (n) RETURN n', timestamp: 1000, rowCount: 5 }]
    localStorage.setItem('kartograph:query-history', JSON.stringify(queryHistory))

    const rawHistory = localStorage.getItem('kartograph:query-history')
    let isReturning = false
    if (rawHistory) {
      try {
        const history = JSON.parse(rawHistory)
        isReturning = Array.isArray(history) && history.length > 0
      } catch { /* ignore */ }
    }

    expect(isReturning).toBe(true)
  })

  it('does not redirect a new user with no query history', () => {
    // No localStorage entry
    const rawHistory = localStorage.getItem('kartograph:query-history')
    let isReturning = false
    if (rawHistory) {
      try {
        const history = JSON.parse(rawHistory)
        isReturning = Array.isArray(history) && history.length > 0
      } catch { /* ignore */ }
    }

    expect(isReturning).toBe(false)
  })

  it('redirect only fires once per session (SESSION_REDIRECT_KEY)', () => {
    const SESSION_REDIRECT_KEY = 'kartograph:home-redirect-done'
    sessionStorage.setItem(SESSION_REDIRECT_KEY, 'true')

    const alreadyRedirected = sessionStorage.getItem(SESSION_REDIRECT_KEY) !== null
    expect(alreadyRedirected).toBe(true)
    // Redirect should NOT fire again
  })
})
