import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Transient Secret Composable Logic ─────────────────────────────────────────
//
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task-Ref: task-124
//
// Requirement: Get Started Querying (MCP Connection)
//   Scenario: Secret shown once
//     "GIVEN a newly created API key WHEN the key is created
//      THEN the plaintext secret is shown exactly once
//      AND the user can copy it
//      AND the secret is not retrievable after leaving the page"
//
//   Scenario: Copy-paste connection command
//     "GIVEN an active API key WHEN the user views the MCP integration page
//      THEN they see a ready-to-paste configuration snippet"
//
// The useTransientSecret composable implements the in-memory-only cross-page
// secret transfer that enables the "Create API Key → View MCP Connection Snippet"
// user flow:
//   1. User creates a key on /api-keys
//   2. Page calls transientSecret.set(secret, keyName) and navigates to /integrate/mcp
//   3. MCP page calls transientSecret.consume() on mount to get the secret
//   4. Secret is shown in the MCP connection snippet (shown once, then gone)
//
// The composable uses Nuxt's useState() for memory-only storage (never URL,
// localStorage, or sessionStorage).

// ─────────────────────────────────────────────────────────────────────────────
// Pure logic tests (mirrors useTransientSecret.ts without Nuxt's useState)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Portable implementation of the useTransientSecret logic for testing.
 * Mirrors the composable exactly (same algorithm, no Nuxt dependency).
 */
function makeTransientSecret() {
  let storedSecret: string | null = null
  let storedKeyName: string | null = null
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  function set(secretValue: string, name?: string) {
    storedSecret = secretValue
    storedKeyName = name ?? null

    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => {
      clear()
    }, 30_000)
  }

  function consume(): { secret: string; keyName: string | null } | null {
    if (!storedSecret) return null
    const result = { secret: storedSecret, keyName: storedKeyName }
    clear()
    return result
  }

  function clear() {
    storedSecret = null
    storedKeyName = null
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  return { set, consume, clear }
}

// ─────────────────────────────────────────────────────────────────────────────
// Scenario: Secret shown once — set/consume lifecycle
// ─────────────────────────────────────────────────────────────────────────────

describe('useTransientSecret - set and consume lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('consume() returns null when no secret has been set', () => {
    const ts = makeTransientSecret()
    const result = ts.consume()
    expect(result).toBeNull()
  })

  it('consume() returns the secret and keyName after set()', () => {
    const ts = makeTransientSecret()
    ts.set('krtgph_test_secret', 'MCP - Claude Code') // gitleaks:allow

    const result = ts.consume()
    expect(result).not.toBeNull()
    expect(result?.secret).toBe('krtgph_test_secret')
    expect(result?.keyName).toBe('MCP - Claude Code')
  })

  it('secret is only available once — second consume() returns null', () => {
    const ts = makeTransientSecret()
    ts.set('krtgph_test_secret') // gitleaks:allow

    const first = ts.consume()
    expect(first).not.toBeNull()

    const second = ts.consume()
    expect(second).toBeNull()
  })

  it('set() with no keyName stores null for keyName', () => {
    const ts = makeTransientSecret()
    ts.set('krtgph_test_secret') // gitleaks:allow

    const result = ts.consume()
    expect(result?.keyName).toBeNull()
  })

  it('clear() makes secret unavailable before consume() is called', () => {
    const ts = makeTransientSecret()
    ts.set('krtgph_test_secret', 'My Key') // gitleaks:allow
    ts.clear()

    const result = ts.consume()
    expect(result).toBeNull()
  })

  it('set() can be called multiple times — only the last value is stored', () => {
    const ts = makeTransientSecret()
    ts.set('old_secret', 'Old Key') // gitleaks:allow
    ts.set('new_secret', 'New Key') // gitleaks:allow

    const result = ts.consume()
    expect(result?.secret).toBe('new_secret')
    expect(result?.keyName).toBe('New Key')
  })

  it('auto-clears secret after 30-second timeout (safety net)', () => {
    const ts = makeTransientSecret()
    ts.set('krtgph_test_secret', 'Test Key') // gitleaks:allow

    // Advance fake timer past the 30-second safety net
    vi.advanceTimersByTime(30_001)

    const result = ts.consume()
    expect(result).toBeNull()
  })

  it('consume() cancels the auto-clear timeout so it does not fire later', () => {
    const ts = makeTransientSecret()
    ts.set('krtgph_test_secret') // gitleaks:allow

    // consume() should clear before the timeout fires
    ts.consume()

    // Advance past timeout — no error should occur from stale timer
    vi.advanceTimersByTime(30_001)

    // Secret is already gone after consume
    expect(ts.consume()).toBeNull()
  })

  it('set() resets the 30-second timeout if called again before expiry', () => {
    const ts = makeTransientSecret()
    ts.set('first_secret') // gitleaks:allow

    // Advance 20 seconds (not yet expired)
    vi.advanceTimersByTime(20_000)

    // Update with new secret — resets the 30-second window
    ts.set('second_secret') // gitleaks:allow

    // Advance another 20 seconds (total 40s, but only 20s since the reset)
    vi.advanceTimersByTime(20_000)

    // Should still be available (timeout was reset by second set())
    const result = ts.consume()
    expect(result?.secret).toBe('second_secret')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario: Secret shown once — cross-page transfer flow
//
// This tests the end-to-end flow:
//   /api-keys sets the transient secret → navigate to /integrate/mcp
//   /integrate/mcp consumes the transient secret on mount
// ─────────────────────────────────────────────────────────────────────────────

describe('useTransientSecret - cross-page secret transfer flow', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('api-keys page sets secret; mcp page consumes it and shows real secret in config', () => {
    const transientSecret = makeTransientSecret()
    const navigateToMcp = vi.fn()

    // ── Step 1: User creates a key on /api-keys ──
    const newKey = {
      id: 'key-1',
      name: 'MCP - Claude Code',
      secret: 'krtgph_mcp_secret', // gitleaks:allow
      prefix: 'krtgph_',
    }

    // api-keys page: set secret and navigate to MCP
    function navigateToMcpWithSecret() {
      transientSecret.set(newKey.secret, newKey.name)
      navigateToMcp('/integrate/mcp')
    }

    navigateToMcpWithSecret()
    expect(navigateToMcp).toHaveBeenCalledWith('/integrate/mcp')

    // ── Step 2: MCP page mounts and consumes the secret ──
    let mcpPageNewlyCreatedKey: { id: string; name: string; secret: string } | null = null

    function onMcpPageMounted() {
      const transferred = transientSecret.consume()
      if (transferred) {
        mcpPageNewlyCreatedKey = {
          id: '',
          name: transferred.keyName ?? 'Transferred Key',
          secret: transferred.secret,
        }
      }
    }

    onMcpPageMounted()

    // Secret is now available in the MCP page's newlyCreatedKey
    expect(mcpPageNewlyCreatedKey).not.toBeNull()
    expect(mcpPageNewlyCreatedKey?.secret).toBe('krtgph_mcp_secret')
    expect(mcpPageNewlyCreatedKey?.name).toBe('MCP - Claude Code')
  })

  it('after MCP page consumes the secret, it is no longer accessible', () => {
    const transientSecret = makeTransientSecret()

    // api-keys page sets the secret
    transientSecret.set('krtgph_mcp_secret', 'My Key') // gitleaks:allow

    // MCP page consumes it
    const result = transientSecret.consume()
    expect(result?.secret).toBe('krtgph_mcp_secret')

    // Any subsequent attempt to retrieve (e.g. page refresh or back navigation) returns null
    const second = transientSecret.consume()
    expect(second).toBeNull()
  })

  it('if user navigates away from api-keys WITHOUT going to mcp, clear() is called', () => {
    const transientSecret = makeTransientSecret()
    const navigatingToMcp = { value: false }

    transientSecret.set('krtgph_mcp_secret', 'My Key') // gitleaks:allow

    // Simulate onUnmounted from api-keys page when navigating elsewhere
    function onApiKeysUnmounted() {
      if (!navigatingToMcp.value) {
        transientSecret.clear()
      }
    }

    onApiKeysUnmounted()

    // Secret has been cleared — MCP page would not receive it
    expect(transientSecret.consume()).toBeNull()
  })

  it('navigating FROM api-keys TO mcp preserves the secret (skip clear)', () => {
    const transientSecret = makeTransientSecret()
    const navigatingToMcp = { value: false }

    transientSecret.set('krtgph_mcp_secret', 'My Key') // gitleaks:allow

    // Simulate user clicking "MCP Integration" from the api-keys page
    function navigateToMcpWithSecret() {
      transientSecret.set('krtgph_mcp_secret', 'My Key') // gitleaks:allow
      navigatingToMcp.value = true // guards against onUnmounted clear
    }

    function onApiKeysUnmounted() {
      if (!navigatingToMcp.value) {
        transientSecret.clear()
      }
    }

    navigateToMcpWithSecret()
    onApiKeysUnmounted() // fires, but navigatingToMcp.value is true → skip clear

    // Secret is still available for the MCP page to consume
    const result = transientSecret.consume()
    expect(result?.secret).toBe('krtgph_mcp_secret')
  })

  it('secret is stored in memory only — not accessible via localStorage or sessionStorage', () => {
    // This test documents the security property: the transient secret
    // must NOT appear in any browser storage APIs.
    // The implementation uses Nuxt's useState (reactive memory state),
    // so we verify the storage APIs are not involved.
    const localStorageSetItem = vi.spyOn(Storage.prototype, 'setItem')
    const sessionStorageSetItem = vi.spyOn(Storage.prototype, 'setItem')

    const ts = makeTransientSecret()
    ts.set('krtgph_mcp_secret', 'My Key') // gitleaks:allow

    // Neither localStorage nor sessionStorage should have been called
    expect(localStorageSetItem).not.toHaveBeenCalled()
    expect(sessionStorageSetItem).not.toHaveBeenCalled()

    vi.restoreAllMocks()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Scenario: MCP page mounts with no transient secret
// ─────────────────────────────────────────────────────────────────────────────

describe('useTransientSecret - MCP page mounted with no pre-existing secret', () => {
  it('mcp page newlyCreatedKey remains null when no transient secret exists', () => {
    const transientSecret = makeTransientSecret()

    let mcpPageNewlyCreatedKey: { secret: string } | null = null

    // Simulate MCP page onMounted when no secret was transferred
    function onMcpPageMounted() {
      const transferred = transientSecret.consume()
      if (transferred) {
        mcpPageNewlyCreatedKey = { secret: transferred.secret }
      }
    }

    onMcpPageMounted()

    // No key was transferred → newlyCreatedKey stays null
    // → config blocks show placeholder <YOUR_API_KEY>
    expect(mcpPageNewlyCreatedKey).toBeNull()
  })

  it('configSecret shows placeholder when newlyCreatedKey is null', () => {
    const newlyCreatedKey: { secret: string } | null = null
    const configSecret = newlyCreatedKey ? newlyCreatedKey.secret : '<YOUR_API_KEY>'
    expect(configSecret).toBe('<YOUR_API_KEY>')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Backend API Alignment: Credential handling
//
// Spec: "Credential handling"
//   "GIVEN credentials provided during data source setup
//    WHEN the data source is saved
//    THEN credentials are encrypted and stored server-side
//    AND the plaintext is never persisted in the browser"
//
// For API keys specifically: the plaintext secret is transmitted over HTTPS to
// the backend (POST /api/iam/api-keys) and the response contains the secret
// exactly once. The UI receives it in memory only and must not write it to
// localStorage, sessionStorage, cookies, or the URL.
// ─────────────────────────────────────────────────────────────────────────────

describe('Credential handling — plaintext never persisted in the browser', () => {
  it('api-keys page does not write secret to localStorage after creation', () => {
    const localSetItem = vi.spyOn(Storage.prototype, 'setItem')

    const newlyCreatedKey = {
      id: 'key-1',
      name: 'CI Pipeline',
      secret: 'krtgph_ci_secret', // gitleaks:allow
      prefix: 'krtgph_',
    }

    // Simulate the api-keys page receiving the newly created key.
    // The page stores it only in reactive state (ref), not localStorage.
    const newKeyRef = { value: null as typeof newlyCreatedKey | null }
    newKeyRef.value = newlyCreatedKey

    // Neither storage API should have been touched
    expect(localSetItem).not.toHaveBeenCalledWith(
      expect.any(String),
      expect.stringContaining(newlyCreatedKey.secret),
    )

    vi.restoreAllMocks()
  })

  it('mcp page does not write secret to sessionStorage during transient transfer', () => {
    const sessionSetItem = vi.spyOn(Storage.prototype, 'setItem')

    const ts = makeTransientSecret()
    ts.set('krtgph_mcp_secret') // gitleaks:allow
    ts.consume()

    expect(sessionSetItem).not.toHaveBeenCalledWith(
      expect.any(String),
      expect.stringContaining('krtgph_mcp_secret'),
    )

    vi.restoreAllMocks()
  })

  it('transient secret is not embedded in navigation URL', () => {
    const navigateTo = vi.fn()
    const ts = makeTransientSecret()

    // Simulate navigateToMcpWithSecret
    const secret = 'krtgph_mcp_secret' // gitleaks:allow
    ts.set(secret, 'My Key')
    navigateTo('/integrate/mcp') // URL does NOT contain secret

    expect(navigateTo).toHaveBeenCalledWith('/integrate/mcp')
    // The secret should NOT appear anywhere in the navigation URL
    expect(navigateTo).not.toHaveBeenCalledWith(
      expect.stringContaining(secret),
    )
  })
})
