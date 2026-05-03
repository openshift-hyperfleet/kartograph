---
id: task-120
title: UI Workspace & Tenant Management Pages
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add workspace management and tenant context selector"
pr_description: |
  ## What and Why

  Implements the Workspaces page under Settings and the ambient tenant selector in
  the sidebar. Workspaces and tenants are the top-level organizational units in
  Kartograph — users must be able to create and manage them before doing anything
  else. The tenant selector is also required by several downstream pages (KG
  creation, query scoping) so it must land before those tasks.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Workspace Management** and
  **Requirement: Tenant and Workspace Context** from `specs/ui/experience.spec.md`.

  Specifically:
  - **Tenant selector**: visible in sidebar for users who belong to multiple tenants;
    switching tenant calls the tenant-switch API and triggers a full data refresh
    (all reactive state dependent on tenant is reset).
  - **Workspace guidance**: first-time tenant entry (no personal workspace) shows a
    prompt to create one or join an existing team workspace.
  - **Create workspace**: form with name field and optional parent workspace selector;
    submits to `POST /api/iam/workspaces`; requires `create_child` permission.
  - **Member management**: table of current members (users and groups) with role
    selector; add member (search by user/group), remove, change role; operations
    use `PUT/DELETE /api/iam/workspaces/{id}/members`.
  - All operations use the **Backend API Alignment** contract: 2xx confirmed before
    UI state updates; parent workspace ID is always included in creation calls.

  ## Design Decisions

  - The tenant selector is a `<Select>` dropdown in the sidebar footer area, visible
    only when `user.tenants.length > 1`.
  - Workspace editing (name, description) is inline — no separate edit page —
    consistent with the "inline actions over navigation" interaction principle.
  - Member management opens in a side panel (Sheet) rather than a full-page route.
  - SpiceDB permission checks (`create_child`, `manage`) gate the UI controls; the
    backend enforces them authoritatively.

  ## Backend APIs Required

  - `GET /api/iam/tenants` — list user's tenants for tenant selector
  - `GET /api/iam/workspaces` — list workspaces
  - `POST /api/iam/workspaces` — create workspace
  - `PUT /api/iam/workspaces/{id}` — update workspace
  - `GET/POST/DELETE /api/iam/workspaces/{id}/members` — member management

  ## Files / Areas Affected

  - `src/ui/pages/settings/WorkspacesPage.vue`
  - `src/ui/pages/settings/WorkspaceDetailPage.vue`
  - `src/ui/components/workspace/WorkspaceCreateForm.vue`
  - `src/ui/components/workspace/WorkspaceMemberTable.vue`
  - `src/ui/components/AppSidebar.vue` — tenant selector addition
  - `src/ui/composables/useTenant.ts` — active tenant state + switch logic
  - `src/ui/composables/useWorkspaces.ts` — workspace CRUD + member ops

  ## How to Verify

  1. Multi-tenant user sees tenant dropdown in sidebar; switching refreshes all data
  2. Settings → Workspaces lists all workspaces the user can see
  3. Create workspace form submits successfully and new item appears in list
  4. Member management panel adds/removes/role-changes members with toast feedback
  5. First-time tenant entry (no workspace) shows onboarding guidance
  6. Users without `create_child` cannot see the Create button

  ## Caveats

  Groups page (also under Settings) is out of scope for this task. Tenant creation
  is an admin-level operation handled separately.
---
