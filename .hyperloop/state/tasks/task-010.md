---
id: task-010
title: "UI — IAM management and MCP integration pages"
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: [task-006]
round: 0
branch: null
pr: null
---

## Summary

Implements the Settings and Connect sections of the UI: workspace management, group management, tenant management, API key lifecycle, and the MCP integration page. All backend APIs for these features are already implemented. Depends only on `task-006` (navigation shell).

## Scope

### Workspace Management (`/settings/workspaces`)

**Workspace tree view**:
- List workspaces in the current tenant (hierarchical display: root → children)
- Create workspace: sheet form with name field + parent workspace selector (defaults to root)
  - Requires `create_child` permission on selected parent
- Rename workspace: inline edit (pencil icon → editable label)
- Delete workspace: confirmation dialog; disabled if workspace has children or is root

**Member management** (workspace detail / side panel):
- List current members (users + groups) with their roles
- Add member: search for user or group, assign role (Admin / Editor / Member)
- Change role: inline role selector dropdown
- Remove member: with confirmation
- Guard: prevent demoting/removing last admin (show error toast if API returns 409)

### Group Management (`/settings/groups`)

- List groups in tenant (all visible to tenant members)
- Create group: inline form with name field
- Rename group: inline edit
- Delete group: confirmation dialog
- **Member management** (group detail):
  - List members with Admin / Member roles
  - Add / remove members; change roles
  - Guard: block last admin demotion/removal

### Tenant Management (`/settings/tenants`)

- List tenants the user belongs to (shows in sidebar tenant selector too)
- Create tenant (multi-tenant mode only): sheet form with name field
- **Member management** (tenant detail):
  - List members with Admin / Member roles
  - Add / remove; change roles
  - Guard: block last admin demotion/removal
- Delete tenant (Admin only): confirmation dialog with cascade warning

### API Key Management (`/connect/api-keys`)

- List API keys: columns — name, prefix, status badge (active/expired/revoked), created_at, expires_at, last_used_at
- Create key: inline form — name, expiration (days, default 30, max 3650)
  - On success: show plaintext secret exactly once in a modal with copy button and warning ("This is the only time you'll see this key")
- Revoke key: confirmation dialog; disabled if already revoked
- **Secret shown once**: after creating, secret is cleared from component state on modal close

### MCP Integration Page (`/connect/mcp`)

**When user has no active API keys**:
- Prompt to create an API key inline (same form as API Key Management page)

**When user has active API keys**:
- Display ready-to-paste MCP configuration snippet for Claude Code:
  ```json
  {
    "mcpServers": {
      "kartograph": {
        "url": "https://{api-host}/mcp/sse",
        "headers": { "X-API-Key": "{selected-key-prefix}..." }
      }
    }
  }
  ```
- Key selector dropdown (choose which API key to use in the snippet)
- Copy button for the full snippet (with toast confirmation)
- Note: "Replace the API key placeholder with your actual key (shown once at creation)"

### API Client Layer

Add typed clients for IAM endpoints already implemented in the backend:
- Tenants CRUD + member management
- Workspaces CRUD + member management
- Groups CRUD + member management
- API Keys CRUD + revoke

## TDD Notes

Component tests using Vitest + Vue Test Utils with MSW:
- API key secret modal: copy button fires clipboard write; close clears secret from state
- Revoke button: disabled for already-revoked keys
- Workspace create form: name length validation (1–512 chars)
- Last-admin guard: role change to member shows error toast when API returns 409
- MCP snippet: key selector updates snippet content; copy button confirmed by toast
- Tenant selector (from task-006): switching tenants refreshes workspace list
