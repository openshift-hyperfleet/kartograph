---
id: task-150
title: "UI API Key Management and MCP Integration page"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-140]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add API key management and MCP integration configuration page"
pr_description: |
  ## What and Why

  API keys are the primary mechanism for AI agents to authenticate with the
  Kartograph MCP server. The API Key Management page handles key lifecycle (create,
  list, revoke). The MCP Integration page bridges the gap from "I have a key" to
  "my AI tool is connected" by providing ready-to-paste configuration snippets and
  walking users through key creation inline if they have none.

  Both pages correspond to the `Connect` section of the sidebar introduced in task-140.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: API Key Management — Scenario: Create key**
    "create with name and expiration; secret shown exactly once"

  - **Requirement: API Key Management — Scenario: List keys**
    "keys listed with status (active, expired, revoked), creation date, last used,
    expiration"

  - **Requirement: API Key Management — Scenario: Revoke key**
    "active or expired key revoked; can no longer authenticate"

  - **Requirement: Get Started Querying (MCP Connection) — Scenario: API key creation inline**
    "user with no active API keys sees prompt to create one inline on MCP page"

  - **Requirement: Get Started Querying (MCP Connection) — Scenario: Copy-paste connection command**
    "ready-to-paste config snippet for Claude Code (MCP endpoint URL + API key placeholder);
    copy button provided"

  - **Requirement: Get Started Querying (MCP Connection) — Scenario: Secret shown once**
    "newly created API key's plaintext secret is shown exactly once; copyable;
    not retrievable after leaving the page"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    List keys: `GET /api-keys`
    Create key: `POST /api-keys`
    Revoke key: `DELETE /api-keys/{id}`

  - **Requirement: Interaction Principles — Scenario: Copy-to-clipboard**
    API key secret and MCP config snippet both have copy buttons with toast confirmation.

  ## Key Design Decisions

  - **API Key list** (`/connect/api-keys`): A table with columns: Name, Status badge
    (active/expired/revoked), Created, Last Used, Expires. A "Create API Key" button
    opens `ApiKeyCreateSheet`. A "Revoke" button per row (with AlertDialog confirmation).
  - **ApiKeyCreateSheet**: Name field + expiration date picker. On submit, `POST /api-keys`.
    On success: show the `SecretRevealModal` with the plaintext secret. Sheet closes.
  - **SecretRevealModal**: Full-screen overlay (not dismissable by clicking outside).
    Shows the secret in a monospace box with a copy button and a countdown. A checkbox
    "I have saved this key" enables the "Close" button. After closing, the secret is
    gone from state.
  - **MCP Integration page** (`/connect/mcp`): Two-panel layout:
    - Left: "Connect your AI agent" instructions with numbered steps.
    - Right: If no active keys → inline `ApiKeyCreateForm` (condensed). If keys exist →
      a dropdown "Select API Key" (just the key name; key ID used in config) + the
      ready-to-paste MCP config JSON snippet.
  - **Config snippet**: Formatted JSON block for the Claude Code `~/.claude/settings.json`
    MCP server entry. Includes the MCP endpoint URL (from `NUXT_PUBLIC_API_BASE_URL`)
    and a placeholder (or the actual key ID/name). Copy button copies the full block.

  ## What Files Are Affected

  - **New**: `src/ui/pages/connect/api-keys.vue`
  - **New**: `src/ui/pages/connect/mcp.vue`
  - **New**: `src/ui/components/apikeys/ApiKeyTable.vue`
  - **New**: `src/ui/components/apikeys/ApiKeyCreateSheet.vue`
  - **New**: `src/ui/components/apikeys/SecretRevealModal.vue`
  - **New**: `src/ui/components/mcp/McpConfigSnippet.vue`
  - **New**: `src/ui/composables/useApiKeys.ts`
  - **New**: `src/ui/tests/unit/ApiKeyTable.test.ts`
  - **New**: `src/ui/tests/unit/SecretRevealModal.test.ts`
  - **New**: `src/ui/tests/unit/McpConfigSnippet.test.ts`

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/ui && npm run dev
  # 1. Navigate to /connect/api-keys — table shows existing keys with status
  # 2. Click "Create API Key" — sheet opens; fill name + expiry; submit
  # 3. SecretRevealModal appears — copy button works; close button locked until
  #    "I have saved this key" checkbox is checked
  # 4. Return to /connect/api-keys — new key listed as "active"
  # 5. Click "Revoke" on the key — confirmation dialog; key becomes revoked
  # 6. Navigate to /connect/mcp — if no active keys: inline creation prompt
  # 7. With active keys: dropdown of key names; select one → config snippet appears
  # 8. Copy button on snippet — toast confirms copy
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- apikeys mcp
  # SecretRevealModal: close button disabled until checkbox; secret cleared on close
  # McpConfigSnippet: correct URL interpolated; copy button fires clipboard write
  # useApiKeys: list, create, revoke all call correct endpoints
  ```

  ## Caveats

  - The `POST /api-keys` response includes the `secret` field only once (at creation).
    The UI must capture it from the response and display it immediately in
    `SecretRevealModal`. It must not be stored in any persistent state (no Pinia
    persistence, no localStorage).
  - The MCP config snippet format must match what Claude Code expects. At time of
    writing, the format is:
    ```json
    {
      "mcpServers": {
        "kartograph": {
          "type": "http",
          "url": "<KARTOGRAPH_MCP_URL>",
          "headers": { "X-API-Key": "<YOUR_API_KEY>" }
        }
      }
    }
    ```
    Update the snippet format if the MCP protocol changes.
  - Key status (active/expired/revoked) is determined server-side. Poll
    `GET /api-keys` on page load only; do not poll for status changes.
---
