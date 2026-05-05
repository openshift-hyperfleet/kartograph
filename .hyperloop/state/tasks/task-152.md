---
id: task-152
title: 'UI: IAM, Tenant Context & Connect (API Keys, Workspaces, MCP Integration)'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-151
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add IAM pages — API keys, workspaces, tenant selector, MCP integration'
pr_description: "## What and Why\n\nThis task implements the **Settings** and **Connect**\
  \ sections of the\nKartograph UI: tenant switching, workspace management, API key\
  \ lifecycle,\nand the MCP integration \"get started\" page. These are the first\
  \ fully-wired\nfeature pages (reading from and writing to the existing IAM REST\
  \ API).\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\n\
  \n### Requirement: Tenant and Workspace Context\n- Tenant selector in the sidebar:\
  \ lists all tenants the user belongs to;\n  switching a tenant refreshes all data\
  \ in the UI (clears relevant Pinia\n  stores and re-fetches)\n- Workspace guidance:\
  \ on first visit to a tenant where the user has no\n  personal workspace, a prompt\
  \ suggests creating or joining one\n\n### Requirement: Workspace Management\n- **Create\
  \ workspace** page: form with name field and optional parent\n  workspace selector;\
  \ calls `POST /iam/workspaces`; shown only to users\n  with `create_child` permission\
  \ on the parent\n- **Member management** panel: for workspaces where the user has\
  \ `manage`\n  permission — add members (user or group), change roles, remove members;\n\
  \  operates on `POST/DELETE /iam/workspaces/{id}/members`\n\n### Requirement: API\
  \ Key Management\n- **API Keys** list page: table showing key name, status (active/expired/\n\
  \  revoked), creation date, last-used date, expiration date; calls\n  `GET /iam/api-keys`\n\
  - **Create key** flow: modal with name + expiration inputs; calls\n  `POST /iam/api-keys`;\
  \ on success, plaintext secret is shown in a one-time\n  reveal panel with a copy\
  \ button; secret is not shown again after dismissal\n- **Revoke key** action: confirmation\
  \ dialog → `DELETE /iam/api-keys/{id}`;\n  key transitions to `revoked` status in\
  \ the table immediately\n\n### Requirement: Get Started Querying (MCP Connection)\n\
  - **MCP Integration** page (`/connect/mcp`):\n  - If user has no active API keys:\
  \ inline prompt to create one (opens the\n    create-key modal)\n  - If at least\
  \ one active key exists: shows a ready-to-paste config\n    snippet for Claude Code\
  \ (MCP endpoint URL + key placeholder) with a\n    copy button\n- **Secret shown\
  \ once**: the plaintext secret from key creation is shown\n  exactly once in a dismissible\
  \ reveal panel with a copy button and a\n  warning (\"you cannot retrieve this again\"\
  )\n\n### Requirement: Backend API Alignment\n- All reads and writes use the REST\
  \ API; 2xx responses update UI state\n  without a manual page refresh\n- Workspace-scoped\
  \ resources include the workspace ID in the request\n  (e.g., `workspace_id` query\
  \ param or path segment as required by the API)\n- Auth header is set from the Pinia\
  \ auth store (wired here for the first\n  time if not done in task-151)\n\n### Requirement:\
  \ Interaction Principles\n- Workspace name editing happens in-place (not on a separate\
  \ edit page)\n- Copy buttons on the MCP snippet and API key secret show toast confirmation\n\
  - Create/update/delete operations show success or failure toasts\n- Form validation\
  \ errors appear inline on fields\n\n## Key Design Decisions\n\n- The API key secret\
  \ is stored only in component-local state (not Pinia,\n  not localStorage) and is\
  \ cleared when the reveal panel is dismissed.\n- Tenant switching is implemented\
  \ by updating the `X-Tenant-ID` header in\n  the API client and invalidating/refetching\
  \ all active Pinia stores.\n- The workspace member table uses a sheet overlay for\
  \ adding/editing\n  members (no separate route).\n\n## Files / Areas Affected\n\n\
  - `src/ui/src/pages/settings/WorkspacesPage.vue`\n- `src/ui/src/pages/settings/WorkspaceMembersPanel.vue`\n\
  - `src/ui/src/pages/connect/ApiKeysPage.vue`\n- `src/ui/src/pages/connect/McpIntegrationPage.vue`\n\
  - `src/ui/src/components/ApiKeyCreateModal.vue`\n- `src/ui/src/components/ApiKeySecretReveal.vue`\n\
  - `src/ui/src/components/TenantSelector.vue` (replace stub from task-151)\n- `src/ui/src/stores/tenant.ts`\
  \ (tenant switching logic)\n- `src/ui/src/stores/apiKeys.ts`\n- `src/ui/src/stores/workspaces.ts`\n\
  - `src/ui/src/lib/api/iam.ts` (typed API wrappers)\n\n## How to Verify\n\n```bash\n\
  make instance-up\nsource .instances/$(basename $(pwd))/.env.instance\ncd src/ui\
  \ && npm run dev\n```\n\n1. Log in as Alice → sidebar tenant selector shows Alice's\
  \ tenants\n2. Create a workspace → workspace appears in the list; no page reload\
  \ needed\n3. Open workspace → add Bob as a member; Bob appears in the member table\n\
  4. Navigate to Connect → API Keys → Create: provide name + expiry\n5. Secret is\
  \ shown once in the reveal panel with a copy button\n6. Dismiss the reveal → secret\
  \ is gone; key appears in the list as \"active\"\n7. Navigate to Connect → MCP Integration\
  \ → snippet shows endpoint + key\n   placeholder with a copy button\n8. Revoke the\
  \ key → status changes to \"revoked\" in the list immediately\n9. MCP Integration\
  \ page now shows the \"create API key\" inline prompt\n\n## Caveats\n\n- Groups\
  \ management (adding groups as workspace members) requires the\n  groups API; if\
  \ not yet implemented, the member-add flow should accept\n  users only, with groups\
  \ as a deferred enhancement.\n- Tenant creation (if needed) is an admin operation;\
  \ the tenant list in\n  the selector comes from `GET /iam/tenants` scoped to the\
  \ current user."
---
