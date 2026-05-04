---
id: task-126
title: 'UI: API Key Management & MCP Integration'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps:
- task-118
- task-119
round: 0
branch: hyperloop/task-126
pr: https://github.com/openshift-hyperfleet/kartograph/pull/597
pr_title: 'feat(ui): add API key management and MCP integration pages'
pr_description: "## What & Why\n\nImplements two tightly related pages in the \"Connect\"\
  \ navigation group: API Key\nManagement (full lifecycle: create, list, revoke) and\
  \ the MCP Integration page\n(helps users connect AI agents to their knowledge graph\
  \ via copy-paste config).\n\nThe \"secret shown once\" pattern is the most security-sensitive\
  \ UX element and must\nbe carefully implemented so the plaintext key is displayed\
  \ only at creation time and\nis not retrievable afterward.\n\n## Spec Requirements\
  \ Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n- **Requirement: API Key Management**\
  \ — all three scenarios: create key (name +\n  expiration; secret shown once), list\
  \ keys (status, dates, last used), revoke key\n- **Requirement: Get Started Querying\
  \ (MCP Connection)** — all three scenarios:\n  inline API key creation if none active,\
  \ copy-paste connection snippet with endpoint\n  URL + API key placeholder, \"secret\
  \ shown once\" guarantee\n\n## API Keys Page (`/connect/api-keys`)\n\n### List view\n\
  \nTable with columns: Name, Status (active / expired / revoked badge), Created,\n\
  Last Used, Expires, Actions (Revoke button).\n\nStatus badges:\n- `active` → green\n\
  - `expired` → gray\n- `revoked` → red/destructive\n\n### Create key\n\nSide panel\
  \ (Sheet) slides in from the right with:\n- Name field (required)\n- Expiration\
  \ date picker (optional; no expiration = never expires)\n- \"Create\" button → `POST\
  \ /iam/api-keys`\n- On success: the sheet transforms to a **Secret Reveal** state:\n\
  \  - Large monospace display of the full API key secret\n  - Copy button (copies\
  \ to clipboard, toast confirms)\n  - Warning banner: \"This secret will not be shown\
  \ again. Copy it now.\"\n  - \"Done\" button closes the sheet (secret is NOT stored\
  \ anywhere in the UI)\n\n### Revoke key\n\nConfirmation dialog before revoking:\
  \ \"Revoke {key name}? This cannot be undone.\"\n→ `DELETE /iam/api-keys/{id}` (or\
  \ `POST /iam/api-keys/{id}/revoke`)\n→ key status updates to \"revoked\" in the\
  \ list\n\n## MCP Integration Page (`/connect/mcp`)\n\n### No active API keys\n\n\
  Full-page empty state with:\n- \"You need an API key to connect agents\" heading\n\
  - Inline mini-form to create an API key (name only, no expiration) — same backend\n\
  \  call as the API Keys page\n- On success: shows the secret once (same reveal pattern)\
  \ then transitions to the\n  connection snippet\n\n### Connection snippet\n\nOnce\
  \ an active API key exists:\n- Shows the MCP endpoint URL: `https://{api_host}/mcp`\n\
  - Shows a ready-to-paste JSON snippet for Claude Code:\n  ```json\n  {\n    \"mcpServers\"\
  : {\n      \"kartograph\": {\n        \"type\": \"http\",\n        \"url\": \"https://{api_host}/mcp\"\
  ,\n        \"headers\": {\n          \"x-api-key\": \"<YOUR_API_KEY>\"\n       \
  \ }\n      }\n    }\n  }\n  ```\n- Copy button for the entire snippet (one-click)\n\
  - Instruction text noting that the user should replace `<YOUR_API_KEY>` with\n \
  \ their actual secret key\n\n## Backend API Integration\n\n| Action | Endpoint |\n\
  |---|---|\n| List API keys | `GET /iam/api-keys` |\n| Create API key | `POST /iam/api-keys`\
  \ |\n| Revoke API key | `POST /iam/api-keys/{id}/revoke` |\n\nThese endpoints exist\
  \ in the IAM context.\n\n## Files / Areas Affected\n\n- `src/ui/src/pages/connect/ApiKeys.vue`\n\
  - `src/ui/src/pages/connect/McpIntegration.vue`\n- `src/ui/src/components/api-keys/ApiKeyTable.vue`\n\
  - `src/ui/src/components/api-keys/CreateKeySheet.vue`\n- `src/ui/src/components/api-keys/SecretReveal.vue`\n\
  - `src/ui/src/components/mcp/ConnectionSnippet.vue`\n- `src/ui/src/api/iam.ts` —\
  \ typed API client for IAM context\n\n## How to Verify\n\n1. API Keys page: table\
  \ renders with status badges; \"Create\" button opens sheet\n2. Fill name → Create\
  \ → sheet shows monospace secret + copy button + warning;\n   clicking \"Done\"\
  \ closes sheet; secret no longer visible; key appears in list\n3. Revoke an active\
  \ key → confirmation dialog → key status changes to \"revoked\"\n4. MCP Integration\
  \ with no active keys → empty state with inline creation form\n5. After creating\
  \ a key → snippet with copy button; clicking copy → clipboard updated\n   (toast\
  \ confirms); snippet shows `<YOUR_API_KEY>` placeholder (not the real secret)\n\n\
  ## Caveats / Follow-up\n\n- The plaintext secret MUST NOT be stored in Pinia/Vuex\
  \ state or localStorage;\n  it is only held in a local `ref` within the `CreateKeySheet`\
  \ component and cleared\n  when the sheet closes"
---
