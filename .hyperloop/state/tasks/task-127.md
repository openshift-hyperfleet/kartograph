---
id: task-127
title: 'UI: Workspace Management'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps:
- task-118
- task-119
round: 0
branch: hyperloop/task-127
pr: https://github.com/openshift-hyperfleet/kartograph/pull/598
pr_title: 'feat(ui): add workspace management UI with creation and member management'
pr_description: "## What & Why\n\nImplements the Workspace Management pages under\
  \ the \"Settings\" navigation group.\nUsers with appropriate permissions can create\
  \ workspaces, and workspace admins can\nmanage members (users and groups) without\
  \ leaving to a separate edit page.\n\n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n\
  - **Requirement: Workspace Management** — both scenarios: create workspace (name\
  \ +\n  optional parent), member management (add/remove users and groups, change\
  \ roles)\n- **Requirement: Interaction Principles** (as applied to workspace management):\n\
  \  inline/side-panel editing — no navigation to a separate edit page for workspace\n\
  \  name or member roles\n\n## Workspaces List Page (`/settings/workspaces`)\n\n\
  - Fetches the user's workspaces from `GET /iam/workspaces`\n- Tree or flat list\
  \ view showing workspace name, parent (if any), member count\n- \"Create workspace\"\
  \ button in the page header (only visible when user has\n  `create_child` permission)\n\
  \n## Create Workspace\n\nSide panel (Sheet) slides in:\n- Name field (required;\
  \ validated — no empty, no duplicate within parent)\n- Parent workspace selector\
  \ (optional dropdown populated with accessible workspaces)\n- \"Create\" button\
  \ → `POST /iam/workspaces`\n- On success: sheet closes; new workspace appears in\
  \ list immediately (optimistic\n  update or re-fetch)\n\n## Member Management\n\n\
  Clicking a workspace opens its detail view (inline expand or dedicated route\n`/settings/workspaces/{id}`):\n\
  \n### Member list\n- Table: Member (user display name or group name), Type (user\
  \ / group), Role,\n  Actions (Change Role, Remove)\n\n### Add member\n- \"Add member\"\
  \ button → side panel with:\n  - Type selector: User or Group\n  - Search/autocomplete\
  \ for users (`GET /iam/users?q=…`) or groups\n    (`GET /iam/groups?q=…`)\n  - Role\
  \ dropdown (viewer, editor, admin — or whatever roles the IAM context defines)\n\
  \  - \"Add\" button → `POST /iam/workspaces/{id}/members`\n\n### Change role\n-\
  \ Inline role dropdown in the member table row; changing triggers\n  `PUT /iam/workspaces/{id}/members/{member_id}`\
  \ immediately (no separate save)\n- Toast confirms: \"Role updated to Editor\"\n\
  \n### Remove member\n- Trash icon → confirmation popover (not a full dialog; inline\
  \ confirmation per the\n  Interaction Principles \"progressive disclosure\" and\
  \ \"inline actions\" patterns)\n- `DELETE /iam/workspaces/{id}/members/{member_id}`\n\
  \n## Backend API Integration\n\n| Action | Endpoint |\n|---|---|\n| List workspaces\
  \ | `GET /iam/workspaces` |\n| Create workspace | `POST /iam/workspaces` |\n| Get\
  \ workspace detail | `GET /iam/workspaces/{id}` |\n| List members | `GET /iam/workspaces/{id}/members`\
  \ |\n| Add member | `POST /iam/workspaces/{id}/members` |\n| Update member role\
  \ | `PUT /iam/workspaces/{id}/members/{member_id}` |\n| Remove member | `DELETE\
  \ /iam/workspaces/{id}/members/{member_id}` |\n\nThese endpoints are implemented\
  \ in the IAM context.\n\n## Files / Areas Affected\n\n- `src/ui/src/pages/settings/Workspaces.vue`\n\
  - `src/ui/src/pages/settings/WorkspaceDetail.vue`\n- `src/ui/src/components/workspace/WorkspaceList.vue`\n\
  - `src/ui/src/components/workspace/CreateWorkspaceSheet.vue`\n- `src/ui/src/components/workspace/MemberTable.vue`\n\
  - `src/ui/src/components/workspace/AddMemberSheet.vue`\n\n## How to Verify\n\n1.\
  \ Settings → Workspaces: existing workspaces listed\n2. Click \"Create workspace\"\
  \ → sheet opens; fill name + optional parent → Create →\n   sheet closes; new workspace\
  \ in list\n3. Click a workspace → detail shows member table\n4. Click \"Add member\"\
  \ → sheet; search for a user; select role; Add → member appears\n5. Change a member's\
  \ role inline → immediate API call; toast confirms\n6. Click trash icon on a member\
  \ → inline confirmation → Remove → member gone\n\n## Caveats / Follow-up\n\n- The\
  \ workspace guidance shown to new users (task-119) links to the create workspace\n\
  \  sheet; this task makes that link functional\n- Group management (create/edit\
  \ groups) is out of scope for this task; the member\n  add panel only allows selecting\
  \ existing groups"
---
