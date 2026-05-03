---
id: task-127
title: "UI: Workspace Management"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add workspace management UI with creation and member management"
pr_description: |
  ## What & Why

  Implements the Workspace Management pages under the "Settings" navigation group.
  Users with appropriate permissions can create workspaces, and workspace admins can
  manage members (users and groups) without leaving to a separate edit page.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Workspace Management** — both scenarios: create workspace (name +
    optional parent), member management (add/remove users and groups, change roles)
  - **Requirement: Interaction Principles** (as applied to workspace management):
    inline/side-panel editing — no navigation to a separate edit page for workspace
    name or member roles

  ## Workspaces List Page (`/settings/workspaces`)

  - Fetches the user's workspaces from `GET /iam/workspaces`
  - Tree or flat list view showing workspace name, parent (if any), member count
  - "Create workspace" button in the page header (only visible when user has
    `create_child` permission)

  ## Create Workspace

  Side panel (Sheet) slides in:
  - Name field (required; validated — no empty, no duplicate within parent)
  - Parent workspace selector (optional dropdown populated with accessible workspaces)
  - "Create" button → `POST /iam/workspaces`
  - On success: sheet closes; new workspace appears in list immediately (optimistic
    update or re-fetch)

  ## Member Management

  Clicking a workspace opens its detail view (inline expand or dedicated route
  `/settings/workspaces/{id}`):

  ### Member list
  - Table: Member (user display name or group name), Type (user / group), Role,
    Actions (Change Role, Remove)

  ### Add member
  - "Add member" button → side panel with:
    - Type selector: User or Group
    - Search/autocomplete for users (`GET /iam/users?q=…`) or groups
      (`GET /iam/groups?q=…`)
    - Role dropdown (viewer, editor, admin — or whatever roles the IAM context defines)
    - "Add" button → `POST /iam/workspaces/{id}/members`

  ### Change role
  - Inline role dropdown in the member table row; changing triggers
    `PUT /iam/workspaces/{id}/members/{member_id}` immediately (no separate save)
  - Toast confirms: "Role updated to Editor"

  ### Remove member
  - Trash icon → confirmation popover (not a full dialog; inline confirmation per the
    Interaction Principles "progressive disclosure" and "inline actions" patterns)
  - `DELETE /iam/workspaces/{id}/members/{member_id}`

  ## Backend API Integration

  | Action | Endpoint |
  |---|---|
  | List workspaces | `GET /iam/workspaces` |
  | Create workspace | `POST /iam/workspaces` |
  | Get workspace detail | `GET /iam/workspaces/{id}` |
  | List members | `GET /iam/workspaces/{id}/members` |
  | Add member | `POST /iam/workspaces/{id}/members` |
  | Update member role | `PUT /iam/workspaces/{id}/members/{member_id}` |
  | Remove member | `DELETE /iam/workspaces/{id}/members/{member_id}` |

  These endpoints are implemented in the IAM context.

  ## Files / Areas Affected

  - `src/ui/src/pages/settings/Workspaces.vue`
  - `src/ui/src/pages/settings/WorkspaceDetail.vue`
  - `src/ui/src/components/workspace/WorkspaceList.vue`
  - `src/ui/src/components/workspace/CreateWorkspaceSheet.vue`
  - `src/ui/src/components/workspace/MemberTable.vue`
  - `src/ui/src/components/workspace/AddMemberSheet.vue`

  ## How to Verify

  1. Settings → Workspaces: existing workspaces listed
  2. Click "Create workspace" → sheet opens; fill name + optional parent → Create →
     sheet closes; new workspace in list
  3. Click a workspace → detail shows member table
  4. Click "Add member" → sheet; search for a user; select role; Add → member appears
  5. Change a member's role inline → immediate API call; toast confirms
  6. Click trash icon on a member → inline confirmation → Remove → member gone

  ## Caveats / Follow-up

  - The workspace guidance shown to new users (task-119) links to the create workspace
    sheet; this task makes that link functional
  - Group management (create/edit groups) is out of scope for this task; the member
    add panel only allows selecting existing groups
---
