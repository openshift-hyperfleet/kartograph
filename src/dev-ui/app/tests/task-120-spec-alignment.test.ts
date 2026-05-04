import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

// ── Task-120 Spec Alignment: UI Workspace & Tenant Management Pages ───────────
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-120 — UI Workspace & Tenant Management Pages
//
// Verifies that the workspace management page and ambient tenant selector
// satisfy the spec requirements:
//
//   Requirement: Tenant and Workspace Context
//     - Scenario: Tenant selector
//     - Scenario: Workspace guidance
//
//   Requirement: Workspace Management
//     - Scenario: Create workspace
//     - Scenario: Member management
//
//   Requirement: Backend API Alignment
//     - Scenario: Resource operations succeed end-to-end
//     - Scenario: Parent context is preserved
//
// Testing approach: source-level inspection via readFileSync.
// This follows the established pattern in task-118-spec-alignment.test.ts —
// mounting the full Nuxt application in unit tests is impractical; source
// inspection is the accepted pattern for layout and composable verification.

// ── Source paths ──────────────────────────────────────────────────────────────

const root = resolve(__dirname, '../..')
const appDir = resolve(__dirname, '..')

const workspacesPagePath = resolve(appDir, 'pages/workspaces/index.vue')
const workspacesPage = readFileSync(workspacesPagePath, 'utf-8')

const layoutPath = resolve(appDir, 'layouts/default.vue')
const layoutContent = readFileSync(layoutPath, 'utf-8')

const useTenantPath = resolve(appDir, 'composables/useTenant.ts')
const useTenantContent = readFileSync(useTenantPath, 'utf-8')

const useIamApiPath = resolve(appDir, 'composables/api/useIamApi.ts')
const useIamApiContent = readFileSync(useIamApiPath, 'utf-8')

const workspaceDetailPanelPath = resolve(appDir, 'components/settings/WorkspaceDetailPanel.vue')
const workspaceDetailPanel = readFileSync(workspaceDetailPanelPath, 'utf-8')

const workspaceGuidancePath = resolve(appDir, 'components/workspaces/WorkspaceGuidance.vue')
const workspaceGuidance = readFileSync(workspaceGuidancePath, 'utf-8')

const indexPagePath = resolve(appDir, 'pages/index.vue')
const indexPage = readFileSync(indexPagePath, 'utf-8')

// ── Requirement: Tenant and Workspace Context ─────────────────────────────────

describe('Scenario: Tenant selector — sidebar provides multi-tenant picker', () => {
  it('layout includes tenant selector region with aria-label', () => {
    expect(layoutContent).toContain('tenantAriaLabel')
  })

  it('tenant selector shows DropdownMenu when multiple tenants exist (isMultiTenant)', () => {
    expect(layoutContent).toContain('isMultiTenant')
    expect(layoutContent).toContain('DropdownMenu')
  })

  it('tenant selector is in BOTH desktop sidebar and mobile sidebar', () => {
    // Desktop: hidden md:flex sidebar
    // Mobile: Sheet content
    const desktopTenantCount = (layoutContent.match(/tenantAriaLabel/g) || []).length
    // At minimum 2 regions (desktop + mobile), each with role="region"
    expect(desktopTenantCount).toBeGreaterThanOrEqual(2)
  })

  it('switchTenant() is called when user picks a different tenant', () => {
    // Layout calls handleTenantChange which calls switchTenant
    expect(layoutContent).toContain('handleTenantChange')
    expect(layoutContent).toContain('switchTenant')
  })

  it('single-tenant state shows static display (not a dropdown)', () => {
    expect(layoutContent).toContain('isSingleTenant')
    // The dropdown trigger is only rendered in the v-else branch
    expect(layoutContent).toContain('v-else-if="isSingleTenant"')
  })

  it('useTenant exports switchTenant that bumps tenantVersion', () => {
    expect(useTenantContent).toContain('function switchTenant')
    expect(useTenantContent).toContain('tenantVersion.value++')
  })

  it('useTenant exports tenantVersion as shared state', () => {
    expect(useTenantContent).toContain('tenantVersion')
    expect(useTenantContent).toContain('useState')
  })

  it('switching tenant persists selection to localStorage', () => {
    expect(useTenantContent).toContain('persistToStorage')
    expect(useTenantContent).toContain('localStorage')
  })
})

describe('Scenario: Workspace guidance — first-time tenant entry prompts setup', () => {
  it('WorkspaceGuidance component exists at components/workspaces/WorkspaceGuidance.vue', () => {
    expect(existsSync(workspaceGuidancePath)).toBe(true)
  })

  it('WorkspaceGuidance emits "create" and "join" events', () => {
    expect(workspaceGuidance).toContain("emit('create')")
    expect(workspaceGuidance).toContain("emit('join')")
  })

  it('WorkspaceGuidance has a "Create Workspace" button', () => {
    expect(workspaceGuidance).toContain('Create Workspace')
  })

  it('WorkspaceGuidance has a "Join a Team Workspace" button', () => {
    expect(workspaceGuidance).toContain('Join a Team Workspace')
  })

  it('index.vue mounts WorkspaceGuidance when user has no workspaces', () => {
    // The home page uses WorkspacesWorkspaceGuidance (Nuxt auto-import)
    expect(indexPage).toContain('WorkspacesWorkspaceGuidance')
    // Gated behind hasWorkspace check
    expect(indexPage).toContain('hasWorkspace')
  })

  it('layout checks for empty workspace list and shows guidance toast', () => {
    // Layout emits a guidance toast when the tenant has 0 workspaces
    expect(layoutContent).toContain('Create or join a workspace')
  })
})

// ── Requirement: Workspace Management ────────────────────────────────────────

describe('Scenario: Create workspace — name, optional parent, submits to backend', () => {
  it('workspaces page exists at pages/workspaces/index.vue', () => {
    expect(existsSync(workspacesPagePath)).toBe(true)
  })

  it('workspaces page has a "Create Workspace" dialog', () => {
    expect(workspacesPage).toContain('Create Workspace')
    expect(workspacesPage).toContain('showCreateDialog')
  })

  it('workspace create form includes a name field', () => {
    expect(workspacesPage).toContain('createName')
    expect(workspacesPage).toContain('Workspace name is required')
  })

  it('workspace create form includes a parent workspace selector', () => {
    expect(workspacesPage).toContain('createParentId')
    expect(workspacesPage).toContain('Parent Workspace')
  })

  it('validation error shown when name is empty', () => {
    expect(workspacesPage).toContain('createNameError')
  })

  it('validation error shown when parent workspace is not selected', () => {
    expect(workspacesPage).toContain('createParentError')
    expect(workspacesPage).toContain('Parent workspace is required')
  })

  it('createWorkspace() is called with name and parent_workspace_id on submit', () => {
    expect(workspacesPage).toContain('parent_workspace_id: createParentId.value')
    expect(workspacesPage).toContain('name: createName.value.trim()')
  })

  it('success toast shown after workspace creation', () => {
    expect(workspacesPage).toContain("toast.success('Workspace created')")
  })

  it('workspace list refreshed (fetchWorkspaces) after successful creation', () => {
    // The `finally` block of handleCreate calls fetchWorkspaces after success
    expect(workspacesPage).toContain('await fetchWorkspaces()')
  })
})

describe('Scenario: Member management — add, remove, change roles', () => {
  it('WorkspaceDetailPanel exists at components/settings/WorkspaceDetailPanel.vue', () => {
    expect(existsSync(workspaceDetailPanelPath)).toBe(true)
  })

  it('WorkspaceDetailPanel shows an Add Member form', () => {
    expect(workspaceDetailPanel).toContain('Add Member')
    expect(workspaceDetailPanel).toContain('addMember')
  })

  it('WorkspaceDetailPanel allows member type selection (user / group)', () => {
    expect(workspaceDetailPanel).toContain('newMemberType')
    expect(workspaceDetailPanel).toContain('User')
    expect(workspaceDetailPanel).toContain('Group')
  })

  it('WorkspaceDetailPanel allows role selection (admin / editor / member)', () => {
    expect(workspaceDetailPanel).toContain('newMemberRole')
    expect(workspaceDetailPanel).toContain('Admin')
    expect(workspaceDetailPanel).toContain('Member')
  })

  it('WorkspaceDetailPanel renders a members table', () => {
    expect(workspaceDetailPanel).toContain('<Table')
    expect(workspaceDetailPanel).toContain('Members')
  })

  it('WorkspaceDetailPanel emits "removeMember" for the remove action', () => {
    expect(workspaceDetailPanel).toContain("emit('removeMember'")
  })

  it('WorkspaceDetailPanel emits "roleChange" when role select changes', () => {
    expect(workspaceDetailPanel).toContain("emit('roleChange'")
  })

  it('workspaces page wires remove-member into a confirmation dialog', () => {
    expect(workspacesPage).toContain('showRemoveMemberDialog')
    expect(workspacesPage).toContain('Remove Member')
  })

  it('workspaces page handles role change via updateWorkspaceMemberRole API', () => {
    expect(workspacesPage).toContain('updateWorkspaceMemberRole')
  })

  it('member changes refresh the members list (fetchMembers)', () => {
    expect(workspacesPage).toContain('await fetchMembers')
  })
})

// ── Requirement: Backend API Alignment ───────────────────────────────────────

describe('Scenario: Resource operations succeed end-to-end — useIamApi workspace methods', () => {
  it('useIamApi provides listWorkspaces → GET /iam/workspaces', () => {
    expect(useIamApiContent).toContain("'/iam/workspaces'")
    expect(useIamApiContent).toContain('listWorkspaces')
  })

  it('useIamApi provides createWorkspace → POST /iam/workspaces', () => {
    expect(useIamApiContent).toContain("method: 'POST'")
    expect(useIamApiContent).toContain('createWorkspace')
  })

  it('useIamApi provides deleteWorkspace → DELETE /iam/workspaces/{id}', () => {
    expect(useIamApiContent).toContain("method: 'DELETE'")
    expect(useIamApiContent).toContain('deleteWorkspace')
  })

  it('useIamApi provides updateWorkspace → PATCH /iam/workspaces/{id}', () => {
    expect(useIamApiContent).toContain("method: 'PATCH'")
    expect(useIamApiContent).toContain('updateWorkspace')
  })

  it('useIamApi provides listWorkspaceMembers, addWorkspaceMember, removeWorkspaceMember, updateWorkspaceMemberRole', () => {
    expect(useIamApiContent).toContain('listWorkspaceMembers')
    expect(useIamApiContent).toContain('addWorkspaceMember')
    expect(useIamApiContent).toContain('removeWorkspaceMember')
    expect(useIamApiContent).toContain('updateWorkspaceMemberRole')
  })

  it('listWorkspaces is called on mount and after tenant switch', () => {
    expect(workspacesPage).toContain('onMounted')
    expect(workspacesPage).toContain('fetchWorkspaces')
    // Tenant switch watcher
    expect(workspacesPage).toContain('watch(tenantVersion')
  })
})

describe('Scenario: Parent context is preserved — parent_workspace_id in creation call', () => {
  it('createWorkspace API call includes parent_workspace_id in body', () => {
    expect(useIamApiContent).toContain('parent_workspace_id')
    // Typed as required in the function signature
    expect(useIamApiContent).toContain('parent_workspace_id: string')
  })

  it('workspaces page form validates that parent is always selected before submit', () => {
    expect(workspacesPage).toContain("createParentError.value = 'Parent workspace is required'")
  })

  it('removeWorkspaceMember sends member_type as query param for correct scoping', () => {
    expect(useIamApiContent).toContain("query: { member_type: memberType }")
  })
})

// ── Interaction: Inline Actions over Navigation ───────────────────────────────

describe('Scenario: Inline actions over navigation — workspace editing in-place', () => {
  it('workspaces page has an inline rename form (no separate edit page)', () => {
    expect(workspacesPage).toContain('editingName')
    expect(workspacesPage).toContain('editNameValue')
    // Rename confirmed inline via a button, not a router.push to /edit
    expect(workspacesPage).toContain('handleRename')
  })

  it('WorkspaceDetailPanel shows inline rename controls', () => {
    expect(workspaceDetailPanel).toContain('editingName')
    expect(workspaceDetailPanel).toContain("emit('startRename')")
    expect(workspaceDetailPanel).toContain("emit('cancelRename')")
    expect(workspaceDetailPanel).toContain("emit('rename')")
  })

  it('member detail opens in a side panel (Sheet on mobile) not a separate page', () => {
    // On mobile, a Sheet is used (not navigateTo('/workspaces/:id'))
    expect(workspacesPage).toContain('<Sheet')
    expect(workspacesPage).toContain('SheetContent')
  })
})

// ── Progressive Disclosure ────────────────────────────────────────────────────

describe('Scenario: Progressive disclosure — workspace detail shown on demand', () => {
  it('workspace detail (members) only fetched when workspace row is clicked', () => {
    // selectWorkspace triggers fetchMembers lazily
    expect(workspacesPage).toContain('function selectWorkspace')
    expect(workspacesPage).toContain('fetchMembers(ws)')
  })

  it('workspace list shows compact rows (name + root badge only, no inline members)', () => {
    // The flat list renders name and Root badge — members are NOT in list rows
    expect(workspacesPage).toContain('node.workspace.name')
    expect(workspacesPage).toContain('is_root')
    // The member table is only in the detail panel, not the list row
    expect(workspaceDetailPanel).toContain('<Table')
  })

  it('closing the detail panel resets selectedWorkspace to null', () => {
    expect(workspacesPage).toContain('function closeDetails')
    expect(workspacesPage).toContain('selectedWorkspace.value = null')
  })
})

// ── Responsive Design: Workspace Page ────────────────────────────────────────

describe('Scenario: Desktop layout — detail panel beside list; Scenario: Tablet/mobile — Sheet overlay', () => {
  it('workspace page uses isDesktop media query for layout switching', () => {
    expect(workspacesPage).toContain('isDesktop')
    expect(workspacesPage).toContain('useMediaQuery')
  })

  it('desktop shows detail in a sticky right panel (lg:grid-cols)', () => {
    expect(workspacesPage).toContain('lg:grid-cols-')
  })

  it('mobile shows detail in a Sheet overlay', () => {
    expect(workspacesPage).toContain('<Sheet')
    expect(workspacesPage).toContain('side="right"')
  })

  it('sheetOpen is derived from !isDesktop && selectedWorkspace !== null', () => {
    expect(workspacesPage).toContain('!isDesktop.value && selectedWorkspace.value !== null')
  })
})
