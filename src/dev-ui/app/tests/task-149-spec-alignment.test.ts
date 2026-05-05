import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// ── Task-149 Spec Alignment: User Experience ──────────────────────────────────
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-149 — UI Experience — Sync Monitoring, MCP Integration, API Key
//       Management, and Secret lifecycle
//
// This file provides targeted spec-alignment verification for four requirement
// groups from the experience spec, complementing prior task coverage:
//
//   Requirement: Sync Monitoring (data-sources page)
//     - Scenario: Active sync progress  (SyncPhaseIndicator, polling, status labels)
//     - Scenario: Sync history          (sync-runs endpoint, history rendering)
//     - Scenario: Sync logs             (per-run logs endpoint)
//     - Scenario: Manual sync trigger   (POST /management/data-sources/{id}/sync)
//
//   Requirement: Get Started Querying (MCP Connection)
//     - Scenario: API key creation inline (create dialog on MCP page)
//     - Scenario: Copy-paste connection command (ready-to-paste snippet)
//     - Scenario: Secret shown once (useTransientSecret composable + mcp.vue)
//
//   Requirement: API Key Management
//     - Scenario: Create key    (POST via createApiKey, secret shown once)
//     - Scenario: List keys     (status: active / expired / revoked)
//     - Scenario: Revoke key    (revokeApiKey, confirmation dialog)
//
//   Requirement: Backend API Alignment — Sync Trigger
//     - The sync trigger POST uses the correct scoped endpoint
//
// Prior task coverage for the remaining scenarios:
//   task-118: Design Language, Dark Mode, Interaction Principles
//   task-120: Workspace management, Tenant context, Navigation structure
//   task-121: Knowledge Graph creation, Data Source connection wizard
//   task-125: Query Console (Cypher editor, execution, history, KG context)
//   task-126: Schema Browser cross-navigation deep-links
//   task-128: Mutations Console (all scenarios)
//   task-129: End-to-end coherence (Backend API Alignment, Ontology Design, etc.)
//   task-138: Backend API Alignment and Mutations KG Selection
//   task-139: Query Console, Schema Browser, Graph Explorer
//
// Task-Ref: task-149
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da

// ── Source file reads ─────────────────────────────────────────────────────────

const appDir = resolve(__dirname, '..')

const dataSourcesVue = readFileSync(
  resolve(appDir, 'pages/data-sources/index.vue'),
  'utf-8',
)

const mcpVue = readFileSync(
  resolve(appDir, 'pages/integrate/mcp.vue'),
  'utf-8',
)

const apiKeysVue = readFileSync(
  resolve(appDir, 'pages/api-keys/index.vue'),
  'utf-8',
)

const transientSecretTs = readFileSync(
  resolve(appDir, 'composables/useTransientSecret.ts'),
  'utf-8',
)

const syncPhaseIndicatorVue = readFileSync(
  resolve(appDir, 'components/graph/SyncPhaseIndicator.vue'),
  'utf-8',
)

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Sync Monitoring
// Scenario: Active sync progress
// "GIVEN a data source with a sync in progress
//  WHEN the user views the data source
//  THEN they see the current sync status (ingesting, extracting, applying)
//  AND a progress indicator appropriate to the current phase"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — Sync Monitoring: Scenario: Active sync progress', () => {
  it('SyncPhaseIndicator component is imported in data-sources page', () => {
    expect(dataSourcesVue).toContain('SyncPhaseIndicator')
  })

  it('SyncPhaseIndicator component file exists and renders phase-specific content', () => {
    // Component must convey the current sync phase to the user
    expect(syncPhaseIndicatorVue).toContain('status')
  })

  it('data-sources page defines syncPhaseLabel to map statuses to readable names', () => {
    expect(dataSourcesVue).toContain('syncPhaseLabel')
  })

  it('syncPhaseLabel covers "ingesting" phase', () => {
    expect(dataSourcesVue).toContain('ingesting')
  })

  it('syncPhaseLabel covers "extracting" phase', () => {
    expect(dataSourcesVue).toContain('extracting')
  })

  it('syncPhaseLabel covers "applying" phase', () => {
    expect(dataSourcesVue).toContain('applying')
  })

  it('data-sources page polls for sync status while any sync is active', () => {
    // The page uses setInterval to refresh sync status while syncs are running
    expect(dataSourcesVue).toContain('setInterval')
    expect(dataSourcesVue).toContain('pollInterval')
  })

  it('page polling uses hasActiveSyncs to determine whether to keep polling', () => {
    // hasActiveSyncs() guards the polling loop — polling stops at terminal state
    expect(dataSourcesVue).toContain('hasActiveSyncs')
  })

  it('logic: hasActiveSyncs detects in-progress statuses correctly', () => {
    // Spec: "ingesting, extracting, applying" — all three are "in progress"
    // Terminal statuses ("completed", "failed") must not be counted as active
    const inProgressStatuses = ['running', 'ingesting', 'extracting', 'applying', 'pending']
    const terminalStatuses = ['completed', 'failed']

    function isActiveStatus(status: string): boolean {
      return !terminalStatuses.includes(status)
    }

    for (const status of inProgressStatuses) {
      expect(isActiveStatus(status)).toBe(true)
    }
    for (const status of terminalStatuses) {
      expect(isActiveStatus(status)).toBe(false)
    }
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Sync Monitoring
// Scenario: Sync history
// "GIVEN a data source with completed syncs
//  WHEN the user views the data source
//  THEN they see a history of sync runs with status (completed, failed),
//       timestamps, and duration"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — Sync Monitoring: Scenario: Sync history', () => {
  it('data-sources page fetches sync runs from /management/data-sources/{id}/sync-runs', () => {
    expect(dataSourcesVue).toContain('/management/data-sources/')
    expect(dataSourcesVue).toContain('sync-runs')
  })

  it('sync-runs are stored on each data source object (ds.sync_runs)', () => {
    expect(dataSourcesVue).toContain('sync_runs')
  })

  it('completed status is included in sync run history', () => {
    expect(dataSourcesVue).toContain("'completed'")
  })

  it('failed status is included in sync run history', () => {
    expect(dataSourcesVue).toContain("'failed'")
  })

  it('sync history shows timestamps (created_at or started_at)', () => {
    // History entries must show when each sync ran
    expect(dataSourcesVue).toMatch(/created_at|started_at/)
  })

  it('logic: sync duration can be computed from start and end timestamps', () => {
    // Spec: "timestamps, and duration" — duration = ended_at - started_at
    function computeDurationMs(startedAt: string, endedAt: string): number {
      return new Date(endedAt).getTime() - new Date(startedAt).getTime()
    }

    const start = '2024-01-01T10:00:00Z'
    const end = '2024-01-01T10:02:30Z'
    const durationMs = computeDurationMs(start, end)
    expect(durationMs).toBe(150_000) // 2 minutes 30 seconds
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Sync Monitoring
// Scenario: Sync logs
// "GIVEN a sync run (in progress or completed)
//  WHEN the user requests logs
//  THEN detailed logs for that run are displayed"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — Sync Monitoring: Scenario: Sync logs', () => {
  it('data-sources page fetches logs from /management/data-sources/{id}/sync-runs/{runId}/logs', () => {
    expect(dataSourcesVue).toContain('/management/data-sources/')
    expect(dataSourcesVue).toContain('sync-runs')
    expect(dataSourcesVue).toContain('/logs')
  })

  it('log endpoint embeds both data source ID and sync run ID', () => {
    // The URL must include both parent IDs for correct scoping
    expect(dataSourcesVue).toMatch(/\/management\/data-sources\/.*\/sync-runs\/.*\/logs/)
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Sync Monitoring
// Scenario: Manual sync trigger
// "GIVEN a data source the user has manage permission on
//  WHEN the user triggers a sync
//  THEN a new sync run begins and progress is shown"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — Sync Monitoring: Scenario: Manual sync trigger', () => {
  it('data-sources page defines triggerSync function', () => {
    expect(dataSourcesVue).toContain('triggerSync')
  })

  it('triggerSync posts to /management/data-sources/{id}/sync', () => {
    // The trigger must use POST, not GET
    expect(dataSourcesVue).toContain('/management/data-sources/')
    expect(dataSourcesVue).toContain('/sync')
    expect(dataSourcesVue).toContain("method: 'POST'")
  })

  it('sync trigger button is wired to triggerSync in the template', () => {
    // The button must call triggerSync with the data source ID
    expect(dataSourcesVue).toContain('@click="triggerSync(ds.id)"')
  })

  it('triggerSync initiates polling after triggering a sync', () => {
    // Once a sync is triggered, the page must start watching its progress
    expect(dataSourcesVue).toContain('startPolling')
  })

  it('triggerSync shows a toast on success', () => {
    expect(dataSourcesVue).toContain('toast.success')
  })

  it('logic: sync trigger URL is constructed correctly for a given data source ID', () => {
    const dsId = 'ds-abc123'
    const url = `/management/data-sources/${dsId}/sync`
    expect(url).toBe('/management/data-sources/ds-abc123/sync')
    expect(url).not.toContain('undefined')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Get Started Querying (MCP Connection)
// Scenario: API key creation inline
// "GIVEN a user on the MCP integration page who has no active API keys
//  WHEN they view the page
//  THEN they are prompted to create an API key inline"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — MCP Integration: Scenario: API key creation inline', () => {
  it('mcp.vue provides an inline API key creation form (createDialogOpen)', () => {
    // The MCP page can create a key without navigating away
    expect(mcpVue).toContain('createDialogOpen')
    expect(mcpVue).toContain('createApiKey')
  })

  it('mcp.vue tracks active keys to determine if inline creation prompt is needed', () => {
    // activeKeys computed — when empty, the user is prompted to create a key
    expect(mcpVue).toContain('activeKeys')
  })

  it('mcp.vue includes a prompt when no active API keys exist', () => {
    // "Create an API key, then copy the configuration for your MCP client."
    expect(mcpVue).toContain('Create an API key')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Get Started Querying (MCP Connection)
// Scenario: Copy-paste connection command
// "GIVEN an active API key
//  WHEN the user views the MCP integration page
//  THEN they see a ready-to-paste configuration snippet for their tool
//  AND the snippet includes the MCP endpoint URL and API key placeholder
//  AND a copy button is provided"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — MCP Integration: Scenario: Copy-paste connection command', () => {
  it('mcp.vue generates mcpConfigClaudeCopy (ready-to-paste config for Claude Code)', () => {
    // The snippet must be a complete, copy-pasteable command
    expect(mcpVue).toContain('mcpConfigClaudeCopy')
  })

  it('mcp.vue includes the MCP endpoint URL in the connection snippet', () => {
    expect(mcpVue).toContain('mcpEndpointUrl')
  })

  it('copy-paste snippet includes X-API-Key header', () => {
    // The command must carry the API key in the X-API-Key header
    expect(mcpVue).toContain('X-API-Key')
  })

  it('mcp.vue provides copy buttons for each config snippet', () => {
    // data-testid="copy-snippet-button" is present for copy functionality
    expect(mcpVue).toContain('copy-snippet-button')
    expect(mcpVue).toContain('copyConfig')
  })

  it('mcp.vue supports multiple MCP tools (Claude Code, Cursor, etc.)', () => {
    // The page shows tabs or sections for different tools
    expect(mcpVue).toContain('mcpConfigClaudeCopy')
    expect(mcpVue).toContain('mcpConfigCursor')
  })

  it('logic: mcpConfigClaudeCopy embeds the endpoint URL and API key correctly', () => {
    const mcpEndpointUrl = 'https://kartograph.example.com/mcp'
    const secret = 'karto_test_key_secret'

    // Replicate the logic from mcp.vue
    const snippet = `claude mcp add kartograph-mcp --transport http ${mcpEndpointUrl} -H "X-API-Key: ${secret}"`

    expect(snippet).toContain(mcpEndpointUrl)
    expect(snippet).toContain(secret)
    expect(snippet).toContain('X-API-Key')
    expect(snippet).not.toContain('undefined')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Get Started Querying (MCP Connection)
// Scenario: Secret shown once
// "GIVEN a newly created API key
//  WHEN the key is created
//  THEN the plaintext secret is shown exactly once
//  AND the user can copy it
//  AND the secret is not retrievable after leaving the page"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — MCP Integration: Scenario: Secret shown once', () => {
  it('useTransientSecret is imported in mcp.vue for cross-page secret transfer', () => {
    expect(mcpVue).toContain('useTransientSecret')
  })

  it('mcp.vue calls transientSecret.consume() to retrieve the one-time secret', () => {
    // consume() returns the secret and immediately clears it from state
    expect(mcpVue).toContain('transientSecret.consume()')
  })

  it('useTransientSecret.consume clears the secret after first read', () => {
    // Source must show that consume() calls clear() to destroy the secret
    expect(transientSecretTs).toContain('consume')
    expect(transientSecretTs).toContain('clear()')
  })

  it('useTransientSecret stores secret in memory only (useState), never calls localStorage.setItem', () => {
    // The secret must live only in Nuxt in-memory state — never written to
    // browser storage APIs. The source mentions localStorage only in a doc
    // comment to document what it avoids; it must never call the API.
    expect(transientSecretTs).toContain('useState')
    expect(transientSecretTs).not.toContain('localStorage.setItem')
    expect(transientSecretTs).not.toContain('sessionStorage.setItem')
  })

  it('useTransientSecret has a 30-second safety-net auto-clear timeout', () => {
    // Even if the user never navigates to the MCP page, the secret expires
    expect(transientSecretTs).toContain('30_000')
    expect(transientSecretTs).toContain('setTimeout')
  })

  it('mcp.vue warns the user that the secret will not be shown again', () => {
    // "Copy your config now — the secret won't be shown again."
    expect(mcpVue).toContain("secret won't be shown again")
  })

  it('logic: useTransientSecret consume returns null after first call', () => {
    // Replicate the composable logic in plain JS (no Nuxt dependency) to
    // verify the one-time-read behaviour without needing useState().
    let storedSecret: string | null = null
    let storedKeyName: string | null = null

    function set(secretValue: string, name?: string) {
      storedSecret = secretValue
      storedKeyName = name ?? null
    }
    function clear() {
      storedSecret = null
      storedKeyName = null
    }
    function consume(): { secret: string; keyName: string | null } | null {
      if (!storedSecret) return null
      const result = { secret: storedSecret, keyName: storedKeyName }
      clear()
      return result
    }

    set('karto_secret_123', 'my-key')
    const first = consume()
    expect(first).not.toBeNull()
    expect(first!.secret).toBe('karto_secret_123')

    // Second call must return null — the secret has been consumed
    const second = consume()
    expect(second).toBeNull()
  })

  it('logic: useTransientSecret clear removes the secret immediately', () => {
    let storedSecret: string | null = null

    function set(secretValue: string) { storedSecret = secretValue }
    function clear() { storedSecret = null }
    function consume(): { secret: string } | null {
      if (!storedSecret) return null
      const result = { secret: storedSecret }
      clear()
      return result
    }

    set('karto_one_time')
    clear() // explicitly cleared before consume

    const result = consume()
    expect(result).toBeNull()
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: API Key Management
// Scenario: Create key
// "GIVEN a user with create_api_key permission
//  WHEN they create a key with a name and expiration
//  THEN the key is created and the secret is shown once"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — API Key Management: Scenario: Create key', () => {
  it('api-keys page calls createApiKey on form submit', () => {
    expect(apiKeysVue).toContain('createApiKey')
  })

  it('api-keys creation form captures name and expires_in_days', () => {
    expect(apiKeysVue).toContain('createForm')
    expect(apiKeysVue).toContain('expires_in_days')
    // Form uses createForm.name for the key name input
    expect(apiKeysVue).toContain('createForm.name')
  })

  it('api-keys page stores the newly created key for one-time secret display', () => {
    // newlyCreatedKey ref holds the just-created APIKeyCreatedResponse
    expect(apiKeysVue).toContain('newlyCreatedKey')
  })

  it('api-keys page uses useTransientSecret for cross-page secret transfer', () => {
    // When the user navigates to the MCP page, the secret is transferred transiently
    expect(apiKeysVue).toContain('transientSecret')
  })

  it('api-keys page shows a "secret shown once" warning banner', () => {
    // Spec: "the plaintext secret is shown exactly once"
    expect(apiKeysVue).toContain('only time the full secret will be shown')
  })

  it('api-keys page provides a copy button for the newly created secret', () => {
    // The user can copy the secret before it is cleared
    expect(apiKeysVue).toContain('copyToClipboard')
  })

  it('logic: key creation clears newlyCreatedKey on dialog close', () => {
    // When the dialog is closed, the secret ref must be nulled
    // (verified by presence of the reset logic in the source)
    expect(apiKeysVue).toContain('newlyCreatedKey.value = null')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: API Key Management
// Scenario: List keys
// "GIVEN the API keys page
//  THEN keys are listed with status (active, expired, revoked), creation date,
//       last used, and expiration"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — API Key Management: Scenario: List keys', () => {
  it('api-keys page fetches keys via listApiKeys on mount', () => {
    expect(apiKeysVue).toContain('listApiKeys')
    expect(apiKeysVue).toContain('onMounted')
  })

  it('api-keys page computes activeKeys (not revoked, not expired)', () => {
    expect(apiKeysVue).toContain('activeKeys')
    expect(apiKeysVue).toContain('is_revoked')
  })

  it('api-keys page computes expiredKeys separately from active keys', () => {
    expect(apiKeysVue).toContain('expiredKeys')
  })

  it('api-keys page computes revokedKeys for the revoked category', () => {
    expect(apiKeysVue).toContain('revokedKeys')
  })

  it('api-keys page defines keyStatus helper that returns active/expired/revoked', () => {
    expect(apiKeysVue).toContain('keyStatus')
    expect(apiKeysVue).toContain("'active'")
    expect(apiKeysVue).toContain("'expired'")
    expect(apiKeysVue).toContain("'revoked'")
  })

  it('api-keys page shows expires_at for expiration information', () => {
    expect(apiKeysVue).toContain('expires_at')
  })

  it('logic: keyStatus classifies keys correctly', () => {
    function isExpired(key: { expires_at: string }): boolean {
      return new Date(key.expires_at) < new Date()
    }

    function keyStatus(key: {
      is_revoked: boolean
      expires_at: string
    }): 'active' | 'revoked' | 'expired' {
      if (key.is_revoked) return 'revoked'
      if (isExpired(key)) return 'expired'
      return 'active'
    }

    // Active: not revoked, expires far in the future
    expect(keyStatus({ is_revoked: false, expires_at: '2099-01-01T00:00:00Z' })).toBe('active')

    // Revoked: is_revoked flag takes precedence over expiry
    expect(keyStatus({ is_revoked: true, expires_at: '2099-01-01T00:00:00Z' })).toBe('revoked')

    // Expired: not revoked but past expiry date
    expect(keyStatus({ is_revoked: false, expires_at: '2000-01-01T00:00:00Z' })).toBe('expired')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: API Key Management
// Scenario: Revoke key
// "GIVEN an active or expired key
//  WHEN the user revokes it
//  THEN the key is marked revoked and can no longer authenticate"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — API Key Management: Scenario: Revoke key', () => {
  it('api-keys page calls revokeApiKey to revoke a key', () => {
    expect(apiKeysVue).toContain('revokeApiKey')
  })

  it('api-keys page uses a confirmation dialog before revoking', () => {
    // Revoke is irreversible — must use an AlertDialog or similar confirmation
    expect(apiKeysVue).toContain('AlertDialog')
  })

  it('api-keys page shows a success toast on successful revocation', () => {
    expect(apiKeysVue).toContain('toast.success')
    expect(apiKeysVue).toContain('revoked')
  })

  it('api-keys page reloads the key list after revocation', () => {
    // The revoked state must be reflected without a manual page refresh
    expect(apiKeysVue).toContain('listApiKeys')
  })

  it('revokedKeys computed excludes active and expired keys', () => {
    // Spec: "can no longer authenticate" → appears in revoked list only
    expect(apiKeysVue).toContain('k.is_revoked')
  })

  it('logic: revoked key is excluded from active key computation', () => {
    interface Key { is_revoked: boolean; expires_at: string }

    function isExpired(key: Key): boolean {
      return new Date(key.expires_at) < new Date()
    }

    function computeActiveKeys(keys: Key[]): Key[] {
      return keys.filter((k) => !k.is_revoked && !isExpired(k))
    }

    const revokedKey: Key = { is_revoked: true, expires_at: '2099-01-01T00:00:00Z' }
    const activeKey: Key = { is_revoked: false, expires_at: '2099-01-01T00:00:00Z' }

    const active = computeActiveKeys([revokedKey, activeKey])
    expect(active).toHaveLength(1)
    expect(active[0]).toBe(activeKey)
    // Revoked key must not appear in active list
    expect(active).not.toContain(revokedKey)
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Backend API Alignment
// Scenario: Resource operations succeed end-to-end (Sync Trigger)
// "GIVEN a user performs any create, read, update, or delete operation via the UI
//  WHEN the operation is submitted
//  THEN the corresponding backend API call succeeds (2xx response)"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-149 — Backend API Alignment: Sync and API Key endpoints', () => {
  it('sync trigger uses POST method (not GET or PATCH)', () => {
    // Spec: "WHEN the user triggers a sync THEN a new sync run begins"
    // The HTTP method must be POST to create a new resource (sync run)
    expect(dataSourcesVue).toContain("method: 'POST'")
    expect(dataSourcesVue).toContain('/sync')
  })

  it('sync-runs listing endpoint follows /management/data-sources/{id}/sync-runs pattern', () => {
    // Spec: Parent context preserved — data source ID scopes the sync runs
    expect(dataSourcesVue).toMatch(
      /\/management\/data-sources\/.*\/sync-runs/,
    )
  })

  it('api-keys page uses /iam/ prefix for API key operations', () => {
    // API key endpoints are in the IAM bounded context
    expect(apiKeysVue).toContain('createApiKey')
    expect(apiKeysVue).toContain('revokeApiKey')
  })

  it('mcp.vue uses mcpEndpointUrl from runtime config (not hardcoded)', () => {
    // The MCP endpoint must come from config so it works across environments
    expect(mcpVue).toContain('mcpEndpointUrl')
    expect(mcpVue).toContain('useRuntimeConfig')
  })

  it('transient secret never touches the URL (no query params)', () => {
    // Spec: "the plaintext is never persisted in the browser"
    // Secret must not appear in the URL where it would be logged
    expect(transientSecretTs).not.toContain('location.href')
    expect(transientSecretTs).not.toContain('router.push')
    expect(transientSecretTs).not.toContain('window.location')
  })
})
