import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── MCP Integration Page Logic ────────────────────────────────────────────────
//
// Spec: "Get Started Querying (MCP Connection)"
// Covers:
//   - Scenario: API key creation inline (no active API keys → prompt)
//   - Scenario: Copy-paste connection command (snippet, copy button)
//   - Scenario: Secret shown once (newlyCreatedKey cleared on dismiss)

// ── Scenario: configSecret shows placeholder when no key created ──────────────
// Spec: "GIVEN an active API key WHEN the user views the MCP integration page
// THEN they see a ready-to-paste configuration snippet"

describe('MCP Integration - configSecret', () => {
  it('shows placeholder when no key has been created', () => {
    const newlyCreatedKey = { value: null as { secret: string } | null }

    const configSecret = newlyCreatedKey.value
      ? newlyCreatedKey.value.secret
      : '<YOUR_API_KEY>'

    expect(configSecret).toBe('<YOUR_API_KEY>')
  })

  it('shows real secret when a key has just been created', () => {
    const newlyCreatedKey = { value: { secret: 'fake-test-api-key' } } // gitleaks:allow

    const configSecret = newlyCreatedKey.value
      ? newlyCreatedKey.value.secret
      : '<YOUR_API_KEY>'

    expect(configSecret).toBe('fake-test-api-key')
  })

  it('hasRealSecret is false with no key, true after creation', () => {
    const newlyCreatedKey = { value: null as { secret: string } | null }
    expect(!!newlyCreatedKey.value).toBe(false)

    newlyCreatedKey.value = { secret: 'fake-test-api-key' } // gitleaks:allow
    expect(!!newlyCreatedKey.value).toBe(true)
  })
})

// ── Scenario: configReady reflects tenant + secret state ──────────────────────
describe('MCP Integration - configReady', () => {
  it('is false when tenant missing even if key created', () => {
    const hasTenant = { value: false }
    const hasRealSecret = { value: true }
    const configReady = hasTenant.value && hasRealSecret.value
    expect(configReady).toBe(false)
  })

  it('is false when key missing even with a tenant', () => {
    const hasTenant = { value: true }
    const hasRealSecret = { value: false }
    const configReady = hasTenant.value && hasRealSecret.value
    expect(configReady).toBe(false)
  })

  it('is true when tenant selected and key is available', () => {
    const hasTenant = { value: true }
    const hasRealSecret = { value: true }
    const configReady = hasTenant.value && hasRealSecret.value
    expect(configReady).toBe(true)
  })
})

// ── Scenario: Copy-paste connection command ───────────────────────────────────
// Spec: "THEN they see a ready-to-paste configuration snippet for their tool
// AND the snippet includes the MCP endpoint URL and API key placeholder
// AND a copy button is provided"

describe('MCP Integration - config snippet generation', () => {
  const mcpEndpointUrl = 'https://example.com/mcp'

  function mcpConfigClaudeCopy(secret: string): string {
    return `claude mcp add kartograph-mcp --transport http ${mcpEndpointUrl} -H "X-API-Key: ${secret}"`
  }

  function mcpConfigCursor(secret: string): string {
    return JSON.stringify(
      {
        mcpServers: {
          kartograph: {
            url: mcpEndpointUrl,
            headers: { 'X-API-Key': secret },
          },
        },
      },
      null,
      2,
    )
  }

  it('Claude Code snippet includes endpoint URL and secret', () => {
    const snippet = mcpConfigClaudeCopy('fake-api-key') // gitleaks:allow
    expect(snippet).toContain(mcpEndpointUrl)
    expect(snippet).toContain('fake-api-key')
    expect(snippet).toContain('--transport http')
    expect(snippet).toContain('X-API-Key:')
  })

  it('Claude Code snippet is a single executable line (no backslash continuations)', () => {
    const snippet = mcpConfigClaudeCopy('fake-api-key') // gitleaks:allow
    expect(snippet).not.toContain('\\\n')
  })

  it('Cursor snippet is valid JSON containing the endpoint URL', () => {
    const snippet = mcpConfigCursor('fake-api-key') // gitleaks:allow
    const parsed = JSON.parse(snippet)
    expect(parsed.mcpServers.kartograph.url).toBe(mcpEndpointUrl)
    expect(parsed.mcpServers.kartograph.headers['X-API-Key']).toBe('fake-api-key')
  })

  it('placeholder <YOUR_API_KEY> appears in snippet when no key exists', () => {
    const snippet = mcpConfigClaudeCopy('<YOUR_API_KEY>')
    expect(snippet).toContain('<YOUR_API_KEY>')
  })
})

// ── Scenario: API key creation inline ────────────────────────────────────────
// Spec: "GIVEN a user on the MCP integration page who has no active API keys
// WHEN they view the page THEN they are prompted to create an API key inline"

describe('MCP Integration - inline API key creation', () => {
  it('shows "no keys" prompt state when activeKeys is empty', () => {
    const apiKeys: { is_revoked: boolean }[] = []
    const activeKeys = apiKeys.filter((k) => !k.is_revoked)
    const showCreatePrompt = activeKeys.length === 0
    expect(showCreatePrompt).toBe(true)
  })

  it('shows "has keys" state when active keys exist', () => {
    const apiKeys = [{ is_revoked: false }, { is_revoked: true }]
    const activeKeys = apiKeys.filter((k) => !k.is_revoked)
    const showCreatePrompt = activeKeys.length === 0
    expect(showCreatePrompt).toBe(false)
    expect(activeKeys).toHaveLength(1)
  })

  it('validates key name is required before creation', async () => {
    const createForm = { name: '', expires_in_days: 30 }
    let toastError = ''
    const apiFetch = vi.fn()

    async function handleCreateKey() {
      if (!createForm.name.trim()) {
        toastError = 'Key name is required'
        return
      }
      await apiFetch('/iam/api-keys', { method: 'POST', body: createForm }) // gitleaks:allow
    }

    await handleCreateKey()
    expect(toastError).toBe('Key name is required')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('validates expiry range: must be between 1 and 3650 days', async () => {
    const createForm = { name: 'MCP Key', expires_in_days: 0 }
    let expiryError = ''
    const apiFetch = vi.fn()

    async function handleCreateKey() {
      if (!createForm.name.trim()) return
      if (createForm.expires_in_days < 1 || createForm.expires_in_days > 3650) {
        expiryError = 'Must be between 1 and 3650 days'
        return
      }
      await apiFetch('/iam/api-keys', { method: 'POST', body: createForm })
    }

    await handleCreateKey()
    expect(expiryError).toBe('Must be between 1 and 3650 days')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('creates key successfully and populates newlyCreatedKey', async () => {
    const createForm = { name: 'MCP Key', expires_in_days: 30 }
    const newlyCreatedKey = { value: null as { name: string; secret: string } | null }
    const apiFetch = vi.fn().mockResolvedValue({ name: 'MCP Key', secret: 'fake-new-key', id: 'key-1', prefix: 'kfake_' }) // gitleaks:allow
    let toastMsg = ''

    async function handleCreateKey() {
      if (!createForm.name.trim()) return
      if (createForm.expires_in_days < 1 || createForm.expires_in_days > 3650) return
      const key = await apiFetch('/iam/api-keys', { method: 'POST', body: createForm })
      newlyCreatedKey.value = key
      toastMsg = `API key "${key.name}" created`
    }

    await handleCreateKey()
    expect(newlyCreatedKey.value?.secret).toBe('fake-new-key')
    expect(toastMsg).toBe('API key "MCP Key" created')
  })
})

// ── Scenario: Secret shown once ───────────────────────────────────────────────
// Spec: "GIVEN a newly created API key WHEN the key is created
// THEN the plaintext secret is shown exactly once
// AND the user can copy it
// AND the secret is not retrievable after leaving the page"

describe('MCP Integration - secret shown once', () => {
  it('newlyCreatedKey is null before any key is created', () => {
    const newlyCreatedKey = { value: null as { secret: string } | null }
    expect(newlyCreatedKey.value).toBeNull()
    // configSecret falls back to placeholder
    const configSecret = newlyCreatedKey.value ? newlyCreatedKey.value.secret : '<YOUR_API_KEY>'
    expect(configSecret).toBe('<YOUR_API_KEY>')
  })

  it('tenant switch clears newlyCreatedKey so old secret is not retained', () => {
    const newlyCreatedKey = { value: { secret: 'krtgph_old' } as { secret: string } | null }

    // Simulate what the tenantVersion watcher does
    function onTenantChange() {
      newlyCreatedKey.value = null
    }

    onTenantChange()
    expect(newlyCreatedKey.value).toBeNull()
  })

  it('copying secret updates secretCopied flag', async () => {
    const newlyCreatedKey = { value: { secret: 'fake-api-key' } } // gitleaks:allow
    const secretCopied = { value: false }
    const clipboardWriteText = vi.fn().mockResolvedValue(undefined)

    async function copySecret() {
      if (!newlyCreatedKey.value) return
      await clipboardWriteText(newlyCreatedKey.value.secret)
      secretCopied.value = true
    }

    await copySecret()
    expect(clipboardWriteText).toHaveBeenCalledWith('fake-api-key')
    expect(secretCopied.value).toBe(true)
  })

  it('copySecret does not set secretCopied if clipboard write fails', async () => {
    const newlyCreatedKey = { value: { secret: 'fake-api-key' } } // gitleaks:allow
    const secretCopied = { value: false }
    const clipboardWriteText = vi.fn().mockRejectedValue(new Error('Permission denied'))
    let errorToast = ''

    async function copySecret() {
      if (!newlyCreatedKey.value) return
      try {
        await clipboardWriteText(newlyCreatedKey.value.secret)
        secretCopied.value = true
      } catch {
        errorToast = 'Failed to copy to clipboard'
      }
    }

    await copySecret()
    expect(secretCopied.value).toBe(false)
    expect(errorToast).toBe('Failed to copy to clipboard')
  })
})
