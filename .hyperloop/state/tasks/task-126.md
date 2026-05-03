---
id: task-126
title: "UI: API Key Management & MCP Integration"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add API key management and MCP integration pages"
pr_description: |
  ## What & Why

  Implements two tightly related pages in the "Connect" navigation group: API Key
  Management (full lifecycle: create, list, revoke) and the MCP Integration page
  (helps users connect AI agents to their knowledge graph via copy-paste config).

  The "secret shown once" pattern is the most security-sensitive UX element and must
  be carefully implemented so the plaintext key is displayed only at creation time and
  is not retrievable afterward.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: API Key Management** — all three scenarios: create key (name +
    expiration; secret shown once), list keys (status, dates, last used), revoke key
  - **Requirement: Get Started Querying (MCP Connection)** — all three scenarios:
    inline API key creation if none active, copy-paste connection snippet with endpoint
    URL + API key placeholder, "secret shown once" guarantee

  ## API Keys Page (`/connect/api-keys`)

  ### List view

  Table with columns: Name, Status (active / expired / revoked badge), Created,
  Last Used, Expires, Actions (Revoke button).

  Status badges:
  - `active` → green
  - `expired` → gray
  - `revoked` → red/destructive

  ### Create key

  Side panel (Sheet) slides in from the right with:
  - Name field (required)
  - Expiration date picker (optional; no expiration = never expires)
  - "Create" button → `POST /iam/api-keys`
  - On success: the sheet transforms to a **Secret Reveal** state:
    - Large monospace display of the full API key secret
    - Copy button (copies to clipboard, toast confirms)
    - Warning banner: "This secret will not be shown again. Copy it now."
    - "Done" button closes the sheet (secret is NOT stored anywhere in the UI)

  ### Revoke key

  Confirmation dialog before revoking: "Revoke {key name}? This cannot be undone."
  → `DELETE /iam/api-keys/{id}` (or `POST /iam/api-keys/{id}/revoke`)
  → key status updates to "revoked" in the list

  ## MCP Integration Page (`/connect/mcp`)

  ### No active API keys

  Full-page empty state with:
  - "You need an API key to connect agents" heading
  - Inline mini-form to create an API key (name only, no expiration) — same backend
    call as the API Keys page
  - On success: shows the secret once (same reveal pattern) then transitions to the
    connection snippet

  ### Connection snippet

  Once an active API key exists:
  - Shows the MCP endpoint URL: `https://{api_host}/mcp`
  - Shows a ready-to-paste JSON snippet for Claude Code:
    ```json
    {
      "mcpServers": {
        "kartograph": {
          "type": "http",
          "url": "https://{api_host}/mcp",
          "headers": {
            "x-api-key": "<YOUR_API_KEY>"
          }
        }
      }
    }
    ```
  - Copy button for the entire snippet (one-click)
  - Instruction text noting that the user should replace `<YOUR_API_KEY>` with
    their actual secret key

  ## Backend API Integration

  | Action | Endpoint |
  |---|---|
  | List API keys | `GET /iam/api-keys` |
  | Create API key | `POST /iam/api-keys` |
  | Revoke API key | `POST /iam/api-keys/{id}/revoke` |

  These endpoints exist in the IAM context.

  ## Files / Areas Affected

  - `src/ui/src/pages/connect/ApiKeys.vue`
  - `src/ui/src/pages/connect/McpIntegration.vue`
  - `src/ui/src/components/api-keys/ApiKeyTable.vue`
  - `src/ui/src/components/api-keys/CreateKeySheet.vue`
  - `src/ui/src/components/api-keys/SecretReveal.vue`
  - `src/ui/src/components/mcp/ConnectionSnippet.vue`
  - `src/ui/src/api/iam.ts` — typed API client for IAM context

  ## How to Verify

  1. API Keys page: table renders with status badges; "Create" button opens sheet
  2. Fill name → Create → sheet shows monospace secret + copy button + warning;
     clicking "Done" closes sheet; secret no longer visible; key appears in list
  3. Revoke an active key → confirmation dialog → key status changes to "revoked"
  4. MCP Integration with no active keys → empty state with inline creation form
  5. After creating a key → snippet with copy button; clicking copy → clipboard updated
     (toast confirms); snippet shows `<YOUR_API_KEY>` placeholder (not the real secret)

  ## Caveats / Follow-up

  - The plaintext secret MUST NOT be stored in Pinia/Vuex state or localStorage;
    it is only held in a local `ref` within the `CreateKeySheet` component and cleared
    when the sheet closes
---
