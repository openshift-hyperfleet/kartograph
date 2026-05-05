---
id: task-150
title: UI API Key Management and MCP Integration page
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps:
- task-140
round: 5
branch: hyperloop/task-150
pr: https://github.com/openshift-hyperfleet/kartograph/pull/628
pr_title: 'feat(ui): add API key management and MCP integration configuration page'
pr_description: "## What and Why\n\nAPI keys are the primary mechanism for AI agents\
  \ to authenticate with the\nKartograph MCP server. The API Key Management page handles\
  \ key lifecycle (create,\nlist, revoke). The MCP Integration page bridges the gap\
  \ from \"I have a key\" to\n\"my AI tool is connected\" by providing ready-to-paste\
  \ configuration snippets and\nwalking users through key creation inline if they\
  \ have none.\n\nBoth pages correspond to the `Connect` section of the sidebar introduced\
  \ in task-140.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: API Key Management — Scenario: Create key**\n  \"create with\
  \ name and expiration; secret shown exactly once\"\n\n- **Requirement: API Key Management\
  \ — Scenario: List keys**\n  \"keys listed with status (active, expired, revoked),\
  \ creation date, last used,\n  expiration\"\n\n- **Requirement: API Key Management\
  \ — Scenario: Revoke key**\n  \"active or expired key revoked; can no longer authenticate\"\
  \n\n- **Requirement: Get Started Querying (MCP Connection) — Scenario: API key creation\
  \ inline**\n  \"user with no active API keys sees prompt to create one inline on\
  \ MCP page\"\n\n- **Requirement: Get Started Querying (MCP Connection) — Scenario:\
  \ Copy-paste connection command**\n  \"ready-to-paste config snippet for Claude\
  \ Code (MCP endpoint URL + API key placeholder);\n  copy button provided\"\n\n-\
  \ **Requirement: Get Started Querying (MCP Connection) — Scenario: Secret shown\
  \ once**\n  \"newly created API key's plaintext secret is shown exactly once; copyable;\n\
  \  not retrievable after leaving the page\"\n\n- **Requirement: Backend API Alignment\
  \ — Scenario: Resource operations succeed end-to-end**\n  List keys: `GET /api-keys`\n\
  \  Create key: `POST /api-keys`\n  Revoke key: `DELETE /api-keys/{id}`\n\n- **Requirement:\
  \ Interaction Principles — Scenario: Copy-to-clipboard**\n  API key secret and MCP\
  \ config snippet both have copy buttons with toast confirmation.\n\n## Key Design\
  \ Decisions\n\n- **API Key list** (`/connect/api-keys`): A table with columns: Name,\
  \ Status badge\n  (active/expired/revoked), Created, Last Used, Expires. A \"Create\
  \ API Key\" button\n  opens `ApiKeyCreateSheet`. A \"Revoke\" button per row (with\
  \ AlertDialog confirmation).\n- **ApiKeyCreateSheet**: Name field + expiration date\
  \ picker. On submit, `POST /api-keys`.\n  On success: show the `SecretRevealModal`\
  \ with the plaintext secret. Sheet closes.\n- **SecretRevealModal**: Full-screen\
  \ overlay (not dismissable by clicking outside).\n  Shows the secret in a monospace\
  \ box with a copy button and a countdown. A checkbox\n  \"I have saved this key\"\
  \ enables the \"Close\" button. After closing, the secret is\n  gone from state.\n\
  - **MCP Integration page** (`/connect/mcp`): Two-panel layout:\n  - Left: \"Connect\
  \ your AI agent\" instructions with numbered steps.\n  - Right: If no active keys\
  \ → inline `ApiKeyCreateForm` (condensed). If keys exist →\n    a dropdown \"Select\
  \ API Key\" (just the key name; key ID used in config) + the\n    ready-to-paste\
  \ MCP config JSON snippet.\n- **Config snippet**: Formatted JSON block for the Claude\
  \ Code `~/.claude/settings.json`\n  MCP server entry. Includes the MCP endpoint\
  \ URL (from `NUXT_PUBLIC_API_BASE_URL`)\n  and a placeholder (or the actual key\
  \ ID/name). Copy button copies the full block.\n\n## What Files Are Affected\n\n\
  - **New**: `src/ui/pages/connect/api-keys.vue`\n- **New**: `src/ui/pages/connect/mcp.vue`\n\
  - **New**: `src/ui/components/apikeys/ApiKeyTable.vue`\n- **New**: `src/ui/components/apikeys/ApiKeyCreateSheet.vue`\n\
  - **New**: `src/ui/components/apikeys/SecretRevealModal.vue`\n- **New**: `src/ui/components/mcp/McpConfigSnippet.vue`\n\
  - **New**: `src/ui/composables/useApiKeys.ts`\n- **New**: `src/ui/tests/unit/ApiKeyTable.test.ts`\n\
  - **New**: `src/ui/tests/unit/SecretRevealModal.test.ts`\n- **New**: `src/ui/tests/unit/McpConfigSnippet.test.ts`\n\
  \n## How to Verify\n\n```bash\nmake instance-up\nsource .instances/$(basename $(pwd))/.env.instance\n\
  cd src/ui && npm run dev\n# 1. Navigate to /connect/api-keys — table shows existing\
  \ keys with status\n# 2. Click \"Create API Key\" — sheet opens; fill name + expiry;\
  \ submit\n# 3. SecretRevealModal appears — copy button works; close button locked\
  \ until\n#    \"I have saved this key\" checkbox is checked\n# 4. Return to /connect/api-keys\
  \ — new key listed as \"active\"\n# 5. Click \"Revoke\" on the key — confirmation\
  \ dialog; key becomes revoked\n# 6. Navigate to /connect/mcp — if no active keys:\
  \ inline creation prompt\n# 7. With active keys: dropdown of key names; select one\
  \ → config snippet appears\n# 8. Copy button on snippet — toast confirms copy\n\
  ```\n\nUnit tests:\n```bash\ncd src/ui && npm run test:unit -- apikeys mcp\n# SecretRevealModal:\
  \ close button disabled until checkbox; secret cleared on close\n# McpConfigSnippet:\
  \ correct URL interpolated; copy button fires clipboard write\n# useApiKeys: list,\
  \ create, revoke all call correct endpoints\n```\n\n## Caveats\n\n- The `POST /api-keys`\
  \ response includes the `secret` field only once (at creation).\n  The UI must capture\
  \ it from the response and display it immediately in\n  `SecretRevealModal`. It\
  \ must not be stored in any persistent state (no Pinia\n  persistence, no localStorage).\n\
  - The MCP config snippet format must match what Claude Code expects. At time of\n\
  \  writing, the format is:\n  ```json\n  {\n    \"mcpServers\": {\n      \"kartograph\"\
  : {\n        \"type\": \"http\",\n        \"url\": \"<KARTOGRAPH_MCP_URL>\",\n \
  \       \"headers\": { \"X-API-Key\": \"<YOUR_API_KEY>\" }\n      }\n    }\n  }\n\
  \  ```\n  Update the snippet format if the MCP protocol changes.\n- Key status (active/expired/revoked)\
  \ is determined server-side. Poll\n  `GET /api-keys` on page load only; do not poll\
  \ for status changes."
---
