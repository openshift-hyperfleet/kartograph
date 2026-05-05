---
id: task-151
title: UI Workspace Management — create workspaces and manage members
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps:
- task-140
round: 10
branch: hyperloop/task-151
pr: https://github.com/openshift-hyperfleet/kartograph/pull/619
pr_title: 'feat(ui): add workspace management with creation and member management'
pr_description: "## What and Why\n\nWorkspaces are the multi-tenancy boundary within\
  \ a tenant, grouping related\nknowledge graphs and controlling who can access them.\
  \ This task adds the\nWorkspace management page (Settings → Workspaces): create\
  \ a workspace with an\noptional parent, and manage membership (add, remove, change\
  \ roles for users\nand groups). The Workspace creation guidance shown to first-time\
  \ tenant members\n(task-140) links here.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Workspace Management — Scenario: Create workspace**\n  \"user\
  \ with create_child permission creates a workspace with name and optional parent;\n\
  \  workspace is created\"\n\n- **Requirement: Workspace Management — Scenario: Member\
  \ management**\n  \"workspace with manage permission: add, remove, change roles\
  \ for members (users and groups)\"\n\n- **Requirement: Backend API Alignment — Scenario:\
  \ Resource operations succeed end-to-end**\n  List workspaces: `GET /workspaces`\n\
  \  Create workspace: `POST /workspaces`\n  List members: `GET /workspaces/{id}/members`\n\
  \  Add member: `POST /workspaces/{id}/members`\n  Remove member: `DELETE /workspaces/{id}/members/{member_id}`\n\
  \  Update role: `PATCH /workspaces/{id}/members/{member_id}`\n\n- **Requirement:\
  \ Interaction Principles — Scenario: Inline actions over navigation**\n  Member\
  \ role changes happen inline in the member table (select dropdown); no\n  separate\
  \ edit page.\n\n- **Requirement: Interaction Principles — Scenario: Mutation feedback**\n\
  \  Toast for workspace creation, member add, member remove, role update.\n\n## Key\
  \ Design Decisions\n\n- **Workspace list** (`/settings/workspaces`): A tree view\
  \ (since workspaces are\n  hierarchical with optional parent) showing the workspace\
  \ hierarchy for the active\n  tenant. Each node shows workspace name, member count,\
  \ and action buttons (Manage,\n  Delete — permission-gated).\n- **Workspace creation**:\
  \ A Sheet with:\n  - Name field (required)\n  - Parent workspace selector (optional;\
  \ shows workspace tree for selection)\n  - Submit calls `POST /workspaces` with\
  \ `name` and optional `parent_id`.\n- **Workspace detail / member management** (`/settings/workspaces/{id}`):\
  \ A page\n  (or full-height Sheet) showing:\n  - Workspace name (inline editable\
  \ for users with manage permission)\n  - Members table: columns: Member (user or\
  \ group name/email), Role badge, Actions\n    (role dropdown inline, Remove button\
  \ with confirmation)\n  - \"Add Member\" button: opens a search-and-select panel;\
  \ search users/groups by\n    name; select role; add.\n- **Role model**: The roles\
  \ available in the dropdown are derived from the\n  workspace role enum (from `iam/presentation/workspaces/models.py`\
  \ — e.g.,\n  `viewer`, `editor`, `manager`, `admin`).\n- **Permission gating**:\
  \ \"Add Member\" and role change controls only render for\n  users with `manage`\
  \ permission (check the `can_manage` flag from the workspace\n  list response, or\
  \ derive from the user's own role).\n\n## What Files Are Affected\n\n- **New**:\
  \ `src/ui/pages/settings/workspaces/index.vue`\n- **New**: `src/ui/pages/settings/workspaces/[id].vue`\n\
  - **New**: `src/ui/components/workspace/WorkspaceTree.vue`\n- **New**: `src/ui/components/workspace/WorkspaceCreateSheet.vue`\n\
  - **New**: `src/ui/components/workspace/MemberTable.vue`\n- **New**: `src/ui/components/workspace/AddMemberPanel.vue`\n\
  - **New**: `src/ui/composables/useWorkspaces.ts`\n- **New**: `src/ui/tests/unit/WorkspaceTree.test.ts`\n\
  - **New**: `src/ui/tests/unit/MemberTable.test.ts`\n- **New**: `src/ui/tests/unit/useWorkspaces.test.ts`\n\
  \n## How to Verify\n\n```bash\nmake instance-up\nsource .instances/$(basename $(pwd))/.env.instance\n\
  cd src/ui && npm run dev\n# 1. Navigate to /settings/workspaces — workspace tree\
  \ shown\n# 2. Click \"Create Workspace\" — Sheet opens; enter name; optional parent\
  \ selection\n# 3. Submit — new workspace appears in tree; toast confirms\n# 4. Click\
  \ \"Manage\" on a workspace — member table shown\n# 5. Click \"Add Member\" — search\
  \ panel opens; search by name; select role; submit\n# 6. Change member role — inline\
  \ dropdown; save on change; toast confirms\n# 7. Remove member — confirmation dialog;\
  \ member disappears from table\n```\n\nUnit tests:\n```bash\ncd src/ui && npm run\
  \ test:unit -- workspace\n# WorkspaceTree: renders hierarchy; create button permission-gated\n\
  # MemberTable: role dropdown inline edit; remove with confirmation\n# useWorkspaces:\
  \ create, list, add/remove/update members all hit correct endpoints\n```\n\n## Caveats\n\
  \n- The workspace hierarchy can be arbitrarily deep. The `WorkspaceTree` must handle\n\
  \  deep nesting gracefully (collapsible tree nodes, not flat list).\n- Groups can\
  \ be members too (not just users). The \"Add Member\" panel must allow\n  searching\
  \ both users and groups. The API returns a `member_type` field\n  (`user` or `group`)\
  \ to distinguish them in the table.\n- If the user has no `manage` permission on\
  \ a workspace, the member table is still\n  visible (read-only) but the \"Add Member\"\
  \ and role-change controls are hidden.\n- The root workspace (is_root=true) cannot\
  \ be deleted. Hide or disable the Delete\n  button for root workspaces."
---
