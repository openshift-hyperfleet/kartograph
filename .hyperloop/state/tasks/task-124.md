---
id: task-124
title: UI API Key Management & MCP Integration Page
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add API key management and MCP integration connection page"
pr_description: |
  ## What and Why

  Enables users to create and manage API keys (required for authenticating with
  the MCP server) and to copy a ready-to-paste MCP configuration snippet into
  their AI tool (e.g., Claude Code). This is the "Connect" section of the sidebar
  and is the bridge between the Kartograph knowledge graph and AI agents.

  The MCP integration page is the primary entry point for new users who want to
  start querying — it proactively guides them to create an API key if they don't
  have one.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: API Key Management** and
  **Requirement: Get Started Querying (MCP Connection)** from
  `specs/ui/experience.spec.md`.

  Specifically:
  - **Create key**: form with name and expiration date fields; requires
    `create_api_key` permission; submits to `POST /api/iam/api-keys`; the
    plaintext secret is shown exactly once in a modal with a copy button.
  - **Secret shown once**: after the create-key modal is dismissed, the secret
    is not retrievable; the modal includes an explicit warning.
  - **List keys**: table with columns: name, status (active/expired/revoked),
    creation date, last used, expiration date.
  - **Revoke key**: confirmation dialog before revoking; calls
    `DELETE /api/iam/api-keys/{id}`; revoked key shows greyed-out status.
  - **MCP integration page** (`/connect/mcp`): if the user has no active keys,
    shows inline API key creation CTA rather than a connection snippet.
  - **Copy-paste connection command**: once an active key exists, renders a
    ready-to-paste MCP config block (JSON/YAML for Claude Code mcp.json) with
    the MCP endpoint URL and key placeholder. A copy button transfers the full
    block to clipboard with a toast confirmation.

  ## Design Decisions

  - The secret-shown-once pattern uses a dedicated `<Dialog>` that renders
    the secret in a `<code>` block with a copy button. The dialog footer has
    an "I've copied it" dismiss button (no "X" close) to reduce the chance of
    accidental dismissal without copying.
  - The connection snippet is static HTML with the current user's active API key
    prefilled (the user chose to expose it); the snippet format matches the
    Claude Code `mcp.json` configuration structure.
  - Key status badges: `active` (green), `expired` (amber), `revoked` (red) —
    using the design system's semantic colors.
  - The MCP endpoint URL is derived from `import.meta.env.VITE_MCP_URL` so it
    works in all deployment environments without code changes.

  ## Backend APIs Required

  - `GET /api/iam/api-keys` — list user's API keys
  - `POST /api/iam/api-keys` — create API key (response includes plaintext secret)
  - `DELETE /api/iam/api-keys/{id}` — revoke API key

  ## Files / Areas Affected

  - `src/ui/pages/connect/ApiKeysPage.vue`
  - `src/ui/pages/connect/McpIntegrationPage.vue`
  - `src/ui/components/apikey/ApiKeyCreateForm.vue`
  - `src/ui/components/apikey/ApiKeySecretModal.vue`
  - `src/ui/components/apikey/ApiKeyTable.vue`
  - `src/ui/components/apikey/ApiKeyRevokeDialog.vue`
  - `src/ui/components/mcp/McpConnectionSnippet.vue`
  - `src/ui/composables/useApiKeys.ts`

  ## How to Verify

  1. Connect → API Keys: list renders with correct status badges
  2. Create key: modal shows plaintext secret + copy button; dismissing hides
     secret permanently (verify it's absent from component state after close)
  3. Revoke: confirmation dialog → revoke → row updates to "revoked" status
  4. Connect → MCP Integration with no active key: inline CTA to create key
  5. Connect → MCP Integration with active key: connection snippet renders with
     the MCP endpoint URL; copy button copies full block; toast confirms
  6. Users without `create_api_key` permission: create button is hidden

  ## Caveats

  The MCP endpoint URL format should match the current server routing (typically
  `/mcp`). The snippet format should be validated against Claude Code's
  `mcp.json` schema.
---
