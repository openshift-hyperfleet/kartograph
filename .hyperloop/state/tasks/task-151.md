---
id: task-151
title: "UI Workspace Management — create workspaces and manage members"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-140]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add workspace management with creation and member management"
pr_description: |
  ## What and Why

  Workspaces are the multi-tenancy boundary within a tenant, grouping related
  knowledge graphs and controlling who can access them. This task adds the
  Workspace management page (Settings → Workspaces): create a workspace with an
  optional parent, and manage membership (add, remove, change roles for users
  and groups). The Workspace creation guidance shown to first-time tenant members
  (task-140) links here.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Workspace Management — Scenario: Create workspace**
    "user with create_child permission creates a workspace with name and optional parent;
    workspace is created"

  - **Requirement: Workspace Management — Scenario: Member management**
    "workspace with manage permission: add, remove, change roles for members (users and groups)"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    List workspaces: `GET /workspaces`
    Create workspace: `POST /workspaces`
    List members: `GET /workspaces/{id}/members`
    Add member: `POST /workspaces/{id}/members`
    Remove member: `DELETE /workspaces/{id}/members/{member_id}`
    Update role: `PATCH /workspaces/{id}/members/{member_id}`

  - **Requirement: Interaction Principles — Scenario: Inline actions over navigation**
    Member role changes happen inline in the member table (select dropdown); no
    separate edit page.

  - **Requirement: Interaction Principles — Scenario: Mutation feedback**
    Toast for workspace creation, member add, member remove, role update.

  ## Key Design Decisions

  - **Workspace list** (`/settings/workspaces`): A tree view (since workspaces are
    hierarchical with optional parent) showing the workspace hierarchy for the active
    tenant. Each node shows workspace name, member count, and action buttons (Manage,
    Delete — permission-gated).
  - **Workspace creation**: A Sheet with:
    - Name field (required)
    - Parent workspace selector (optional; shows workspace tree for selection)
    - Submit calls `POST /workspaces` with `name` and optional `parent_id`.
  - **Workspace detail / member management** (`/settings/workspaces/{id}`): A page
    (or full-height Sheet) showing:
    - Workspace name (inline editable for users with manage permission)
    - Members table: columns: Member (user or group name/email), Role badge, Actions
      (role dropdown inline, Remove button with confirmation)
    - "Add Member" button: opens a search-and-select panel; search users/groups by
      name; select role; add.
  - **Role model**: The roles available in the dropdown are derived from the
    workspace role enum (from `iam/presentation/workspaces/models.py` — e.g.,
    `viewer`, `editor`, `manager`, `admin`).
  - **Permission gating**: "Add Member" and role change controls only render for
    users with `manage` permission (check the `can_manage` flag from the workspace
    list response, or derive from the user's own role).

  ## What Files Are Affected

  - **New**: `src/ui/pages/settings/workspaces/index.vue`
  - **New**: `src/ui/pages/settings/workspaces/[id].vue`
  - **New**: `src/ui/components/workspace/WorkspaceTree.vue`
  - **New**: `src/ui/components/workspace/WorkspaceCreateSheet.vue`
  - **New**: `src/ui/components/workspace/MemberTable.vue`
  - **New**: `src/ui/components/workspace/AddMemberPanel.vue`
  - **New**: `src/ui/composables/useWorkspaces.ts`
  - **New**: `src/ui/tests/unit/WorkspaceTree.test.ts`
  - **New**: `src/ui/tests/unit/MemberTable.test.ts`
  - **New**: `src/ui/tests/unit/useWorkspaces.test.ts`

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/ui && npm run dev
  # 1. Navigate to /settings/workspaces — workspace tree shown
  # 2. Click "Create Workspace" — Sheet opens; enter name; optional parent selection
  # 3. Submit — new workspace appears in tree; toast confirms
  # 4. Click "Manage" on a workspace — member table shown
  # 5. Click "Add Member" — search panel opens; search by name; select role; submit
  # 6. Change member role — inline dropdown; save on change; toast confirms
  # 7. Remove member — confirmation dialog; member disappears from table
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- workspace
  # WorkspaceTree: renders hierarchy; create button permission-gated
  # MemberTable: role dropdown inline edit; remove with confirmation
  # useWorkspaces: create, list, add/remove/update members all hit correct endpoints
  ```

  ## Caveats

  - The workspace hierarchy can be arbitrarily deep. The `WorkspaceTree` must handle
    deep nesting gracefully (collapsible tree nodes, not flat list).
  - Groups can be members too (not just users). The "Add Member" panel must allow
    searching both users and groups. The API returns a `member_type` field
    (`user` or `group`) to distinguish them in the table.
  - If the user has no `manage` permission on a workspace, the member table is still
    visible (read-only) but the "Add Member" and role-change controls are hidden.
  - The root workspace (is_root=true) cannot be deleted. Hide or disable the Delete
    button for root workspaces.
---
