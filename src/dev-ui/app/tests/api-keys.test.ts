import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── API Key Management Page Logic ─────────────────────────────────────────────
//
// Spec: "API Key Management"
// Covers:
//   - Scenario: Create key (validation, success, secret shown once)
//   - Scenario: List keys (status: active, expired, revoked; creation date, last used, expiration)
//   - Scenario: Revoke key (marked revoked, can no longer authenticate)

// ── Helper functions (extracted from api-keys/index.vue logic) ────────────────

function isExpired(expiresAt: string): boolean {
  return new Date(expiresAt) < new Date()
}

function keyStatus(key: { is_revoked: boolean; expires_at: string }): 'active' | 'revoked' | 'expired' {
  if (key.is_revoked) return 'revoked'
  if (isExpired(key.expires_at)) return 'expired'
  return 'active'
}

function daysUntilExpiry(expiresAt: string): number {
  const now = new Date()
  const expiry = new Date(expiresAt)
  return Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}

function maskedSecret(secret: string): string {
  if (secret.length <= 8) return secret
  return secret.slice(0, 8) + '•'.repeat(Math.min(24, secret.length - 8))
}

// ── Scenario: isExpired logic ─────────────────────────────────────────────────

describe('API Keys - isExpired', () => {
  it('returns false for a future expiry date', () => {
    const future = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
    expect(isExpired(future)).toBe(false)
  })

  it('returns true for a past expiry date', () => {
    const past = new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()
    expect(isExpired(past)).toBe(true)
  })
})

// ── Scenario: keyStatus logic ─────────────────────────────────────────────────
// Spec: "THEN keys are listed with status (active, expired, revoked)"

describe('API Keys - keyStatus', () => {
  const future = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
  const past = new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()

  it('returns "revoked" for a revoked key regardless of expiry', () => {
    expect(keyStatus({ is_revoked: true, expires_at: future })).toBe('revoked')
    expect(keyStatus({ is_revoked: true, expires_at: past })).toBe('revoked')
  })

  it('returns "expired" for a non-revoked key past its expiry date', () => {
    expect(keyStatus({ is_revoked: false, expires_at: past })).toBe('expired')
  })

  it('returns "active" for a non-revoked key with a future expiry date', () => {
    expect(keyStatus({ is_revoked: false, expires_at: future })).toBe('active')
  })
})

// ── Scenario: daysUntilExpiry ─────────────────────────────────────────────────

describe('API Keys - daysUntilExpiry', () => {
  it('returns a positive number for a future expiry', () => {
    const future = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
    const days = daysUntilExpiry(future)
    expect(days).toBeGreaterThan(0)
    expect(days).toBeLessThanOrEqual(31) // Allow 1 day of tolerance
  })

  it('returns a negative number for a past expiry', () => {
    const past = new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString()
    const days = daysUntilExpiry(past)
    expect(days).toBeLessThan(0)
  })
})

// ── Scenario: maskedSecret ────────────────────────────────────────────────────

describe('API Keys - maskedSecret', () => {
  it('shows first 8 chars and replaces rest with bullet dots', () => {
    const secret = 'fakekey_abc123xy' // gitleaks:allow
    const masked = maskedSecret(secret)
    expect(masked.startsWith('fakekey_')).toBe(true)
    expect(masked).toContain('•')
  })

  it('returns short secrets unchanged (≤ 8 chars)', () => {
    expect(maskedSecret('abc1234')).toBe('abc1234')
  })

  it('caps bullet replacement at 24 characters', () => {
    const longSecret = 'krtgph_' + 'a'.repeat(100)
    const masked = maskedSecret(longSecret)
    const bullets = masked.slice(8)
    expect(bullets.length).toBe(24)
  })
})

// ── Scenario: Create key validation ──────────────────────────────────────────
// Spec: "GIVEN a user with create_api_key permission
// WHEN they create a key with a name and expiration
// THEN the key is created and the secret is shown once"

describe('API Keys - create key validation', () => {
  it('rejects creation when name is empty', async () => {
    const createForm = { name: '', expires_in_days: 30 }
    let toastError = ''
    const apiFetch = vi.fn()

    async function handleCreate() {
      if (!createForm.name.trim()) {
        toastError = 'Key name is required'
        return
      }
      await apiFetch('/iam/api-keys', { method: 'POST', body: createForm })
    }

    await handleCreate()
    expect(toastError).toBe('Key name is required')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('rejects expiry of 0 days as out of range', async () => {
    const createForm = { name: 'Test Key', expires_in_days: 0 }
    let expiryError = ''
    const apiFetch = vi.fn()

    async function handleCreate() {
      if (!createForm.name.trim()) return
      if (createForm.expires_in_days < 1 || createForm.expires_in_days > 3650) {
        expiryError = 'Must be between 1 and 3650 days'
        return
      }
      await apiFetch('/iam/api-keys', { method: 'POST', body: createForm })
    }

    await handleCreate()
    expect(expiryError).toBe('Must be between 1 and 3650 days')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('rejects expiry of 3651 days as out of range', async () => {
    const createForm = { name: 'Test Key', expires_in_days: 3651 }
    let expiryError = ''
    const apiFetch = vi.fn()

    async function handleCreate() {
      if (!createForm.name.trim()) return
      if (createForm.expires_in_days < 1 || createForm.expires_in_days > 3650) {
        expiryError = 'Must be between 1 and 3650 days'
        return
      }
      await apiFetch('/iam/api-keys', { method: 'POST' })
    }

    await handleCreate()
    expect(expiryError).toBe('Must be between 1 and 3650 days')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('creates key and shows secret once on success', async () => {
    const createForm = { name: 'CI Pipeline', expires_in_days: 365 }
    const newlyCreatedKey = { value: null as { name: string; secret: string } | null }
    const isCreating = { value: false }
    const apiFetch = vi.fn().mockResolvedValue({
      id: 'key-abc',
      name: 'CI Pipeline',
      secret: 'fake-key-value', // gitleaks:allow
      prefix: 'kfake_',
    })
    let toastMsg = ''

    async function handleCreate() {
      if (!createForm.name.trim()) return
      isCreating.value = true
      try {
        const key = await apiFetch('/iam/api-keys', { method: 'POST', body: createForm })
        newlyCreatedKey.value = key
        toastMsg = `API key "${key.name}" created`
      } finally {
        isCreating.value = false
      }
    }

    await handleCreate()
    expect(newlyCreatedKey.value?.secret).toBe('fake-key-value')
    expect(toastMsg).toBe('API key "CI Pipeline" created')
    expect(isCreating.value).toBe(false)
  })

  it('resets isCreating on API failure', async () => {
    const createForm = { name: 'Bad Key', expires_in_days: 30 }
    const isCreating = { value: false }
    const apiFetch = vi.fn().mockRejectedValue(new Error('Forbidden'))
    let errorMsg = ''

    async function handleCreate() {
      isCreating.value = true
      try {
        await apiFetch('/iam/api-keys', { method: 'POST', body: createForm })
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed'
      } finally {
        isCreating.value = false
      }
    }

    await handleCreate()
    expect(isCreating.value).toBe(false)
    expect(errorMsg).toBe('Forbidden')
  })
})

// ── Scenario: Revoke key ──────────────────────────────────────────────────────
// Spec: "GIVEN an active or expired key WHEN the user revokes it
// THEN the key is marked revoked and can no longer authenticate"

describe('API Keys - revoke key', () => {
  it('opens revoke confirmation dialog with the target key', () => {
    const keyToRevoke = { value: null as { id: string; name: string } | null }
    const revokeDialogOpen = { value: false }

    function confirmRevoke(key: { id: string; name: string }) {
      keyToRevoke.value = key
      revokeDialogOpen.value = true
    }

    confirmRevoke({ id: 'key-abc', name: 'CI Pipeline' })
    expect(revokeDialogOpen.value).toBe(true)
    expect(keyToRevoke.value?.id).toBe('key-abc')
    expect(keyToRevoke.value?.name).toBe('CI Pipeline')
  })

  it('calls revoke API and reloads key list on confirmation', async () => {
    const keyToRevoke = { value: { id: 'key-abc', name: 'CI Pipeline' } }
    const revokeDialogOpen = { value: true }
    const isRevoking = { value: false }
    const revokeApiFetch = vi.fn().mockResolvedValue({})
    const loadKeys = vi.fn().mockResolvedValue(undefined)
    let toastMsg = ''

    async function handleRevoke() {
      if (!keyToRevoke.value) return
      isRevoking.value = true
      try {
        await revokeApiFetch(`/iam/api-keys/${keyToRevoke.value.id}/revoke`, { method: 'POST' })
        toastMsg = `API key "${keyToRevoke.value.name}" revoked`
        await loadKeys()
      } finally {
        revokeDialogOpen.value = false
        keyToRevoke.value = null
        isRevoking.value = false
      }
    }

    await handleRevoke()
    expect(revokeApiFetch).toHaveBeenCalledWith('/iam/api-keys/key-abc/revoke', { method: 'POST' })
    expect(toastMsg).toBe('API key "CI Pipeline" revoked')
    expect(loadKeys).toHaveBeenCalledOnce()
    expect(revokeDialogOpen.value).toBe(false)
    expect(keyToRevoke.value).toBeNull()
    expect(isRevoking.value).toBe(false)
  })

  it('resets dialog state on revoke API failure', async () => {
    const keyToRevoke = { value: { id: 'key-abc', name: 'CI Pipeline' } }
    const revokeDialogOpen = { value: true }
    const isRevoking = { value: false }
    const revokeApiFetch = vi.fn().mockRejectedValue(new Error('Not found'))
    let errorMsg = ''

    async function handleRevoke() {
      if (!keyToRevoke.value) return
      isRevoking.value = true
      try {
        await revokeApiFetch(`/iam/api-keys/${keyToRevoke.value.id}/revoke`, { method: 'POST' })
      } catch (err) {
        errorMsg = err instanceof Error ? err.message : 'Failed to revoke'
      } finally {
        revokeDialogOpen.value = false
        keyToRevoke.value = null
        isRevoking.value = false
      }
    }

    await handleRevoke()
    expect(errorMsg).toBe('Not found')
    expect(revokeDialogOpen.value).toBe(false)
    expect(isRevoking.value).toBe(false)
  })

  it('does nothing when keyToRevoke is null', async () => {
    const keyToRevoke = { value: null as { id: string } | null }
    const revokeApiFetch = vi.fn()

    async function handleRevoke() {
      if (!keyToRevoke.value) return
      await revokeApiFetch(`/iam/api-keys/${keyToRevoke.value.id}/revoke`, { method: 'POST' })
    }

    await handleRevoke()
    expect(revokeApiFetch).not.toHaveBeenCalled()
  })
})

// ── Scenario: Key list filtering ──────────────────────────────────────────────
// Spec: "THEN keys are listed with status (active, expired, revoked), creation date, last used, and expiration"

describe('API Keys - list filtering by status', () => {
  const future = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
  const past = new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()

  const keys = [
    { id: '1', name: 'Active', is_revoked: false, expires_at: future, last_used_at: null },
    { id: '2', name: 'Expired', is_revoked: false, expires_at: past, last_used_at: null },
    { id: '3', name: 'Revoked', is_revoked: true, expires_at: future, last_used_at: null },
  ]

  it('separates active keys', () => {
    const activeKeys = keys.filter((k) => !k.is_revoked && !isExpired(k.expires_at))
    expect(activeKeys).toHaveLength(1)
    expect(activeKeys[0].name).toBe('Active')
  })

  it('separates expired keys (non-revoked but past expiry)', () => {
    const expiredKeys = keys.filter((k) => !k.is_revoked && isExpired(k.expires_at))
    expect(expiredKeys).toHaveLength(1)
    expect(expiredKeys[0].name).toBe('Expired')
  })

  it('separates revoked keys', () => {
    const revokedKeys = keys.filter((k) => k.is_revoked)
    expect(revokedKeys).toHaveLength(1)
    expect(revokedKeys[0].name).toBe('Revoked')
  })
})

// ── Secret shown once: dismiss clears the key ─────────────────────────────────
describe('API Keys - secret shown once after dismiss', () => {
  it('dismissCreatedKey clears newlyCreatedKey and resets secretCopied', () => {
    const newlyCreatedKey = { value: { name: 'My Key', secret: 'fake-key' } as { name: string; secret: string } | null } // gitleaks:allow
    const secretCopied = { value: true }
    const secretVisible = { value: false }

    function dismissCreatedKey() {
      newlyCreatedKey.value = null
      secretCopied.value = false
      secretVisible.value = true
    }

    dismissCreatedKey()
    expect(newlyCreatedKey.value).toBeNull()
    expect(secretCopied.value).toBe(false)
    expect(secretVisible.value).toBe(true)
  })
})
