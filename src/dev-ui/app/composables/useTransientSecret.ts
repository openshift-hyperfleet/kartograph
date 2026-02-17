/**
 * Manages a transient API key secret for cross-page transfer.
 *
 * The secret lives only in memory (Nuxt useState) — never in the URL,
 * localStorage, sessionStorage, or any persistent storage.
 *
 * It is auto-cleared after first read (`consume`) or after a 30-second
 * safety-net timeout, whichever comes first.
 */
export function useTransientSecret() {
  const secret = useState<string | null>('transient-api-secret', () => null)
  const keyName = useState<string | null>('transient-api-key-name', () => null)

  let timeoutId: ReturnType<typeof setTimeout> | null = null

  /** Store a secret for one-time retrieval on another page. */
  function set(secretValue: string, name?: string) {
    secret.value = secretValue
    keyName.value = name ?? null

    // Auto-clear after 30 seconds as safety net
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => {
      clear()
    }, 30_000)
  }

  /** Read and immediately clear the secret (one-time use). Returns null if already consumed or expired. */
  function consume(): { secret: string; keyName: string | null } | null {
    if (!secret.value) return null
    const result = { secret: secret.value, keyName: keyName.value }
    clear()
    return result
  }

  /** Manually clear the secret and cancel any pending timeout. */
  function clear() {
    secret.value = null
    keyName.value = null
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  return { set, consume, clear }
}
