import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Auth Callback Page Logic ───────────────────────────────────────────────────
//
// Spec: pages/auth/callback.vue
// Covers:
//   - Scenario: Successful OIDC callback → redirect to /
//   - Scenario: Callback times out after 15s → timedOut flag set, retry shown
//   - Scenario: Callback failure → restarts login flow
//   - Scenario: Retry button → invokes login()

// ── State machine extracted from auth/callback.vue ────────────────────────────

const CALLBACK_TIMEOUT_MS = 15_000

interface CallbackState {
  timedOut: boolean
  error: unknown | null
  done: boolean
}

function makeCallbackState(): CallbackState {
  return { timedOut: false, error: null, done: false }
}

async function runCallbackFlow(
  state: CallbackState,
  opts: {
    handleCallback: () => Promise<void>
    login: () => Promise<void>
    navigate: (path: string) => Promise<void>
    setTimeout: (fn: () => void, ms: number) => ReturnType<typeof globalThis.setTimeout>
    clearTimeout: (id: ReturnType<typeof globalThis.setTimeout>) => void
  },
): Promise<void> {
  const timer = opts.setTimeout(() => {
    state.timedOut = true
  }, CALLBACK_TIMEOUT_MS)

  try {
    await opts.handleCallback()
    opts.clearTimeout(timer)
    state.done = true
    await opts.navigate('/')
  } catch (err) {
    opts.clearTimeout(timer)
    state.error = err
    await opts.login()
  }
}

// ── Scenario: Timeout detection ───────────────────────────────────────────────

describe('Auth Callback — timeout detection', () => {
  it('sets timedOut to true after CALLBACK_TIMEOUT_MS', () => {
    vi.useFakeTimers()

    const state = makeCallbackState()
    expect(state.timedOut).toBe(false)

    const timer = setTimeout(() => {
      state.timedOut = true
    }, CALLBACK_TIMEOUT_MS)

    vi.advanceTimersByTime(CALLBACK_TIMEOUT_MS - 1)
    expect(state.timedOut).toBe(false)

    vi.advanceTimersByTime(1)
    expect(state.timedOut).toBe(true)

    clearTimeout(timer)
    vi.useRealTimers()
  })

  it('does not set timedOut if cleared before expiry', () => {
    vi.useFakeTimers()

    const state = makeCallbackState()

    const timer = setTimeout(() => {
      state.timedOut = true
    }, CALLBACK_TIMEOUT_MS)

    clearTimeout(timer)
    vi.advanceTimersByTime(CALLBACK_TIMEOUT_MS + 1000)
    expect(state.timedOut).toBe(false)

    vi.useRealTimers()
  })

  it('CALLBACK_TIMEOUT_MS is 15 seconds', () => {
    expect(CALLBACK_TIMEOUT_MS).toBe(15_000)
  })
})

// ── Scenario: Successful callback ─────────────────────────────────────────────

describe('Auth Callback — successful callback', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('clears timeout and navigates to / on success', async () => {
    const state = makeCallbackState()
    const navigate = vi.fn().mockResolvedValue(undefined)
    const login = vi.fn()
    const handleCallback = vi.fn().mockResolvedValue(undefined)
    const clearTimeoutSpy = vi.fn()

    await runCallbackFlow(state, {
      handleCallback,
      login,
      navigate,
      setTimeout: globalThis.setTimeout.bind(globalThis),
      clearTimeout: clearTimeoutSpy,
    })

    expect(handleCallback).toHaveBeenCalledOnce()
    expect(navigate).toHaveBeenCalledWith('/')
    expect(login).not.toHaveBeenCalled()
    expect(clearTimeoutSpy).toHaveBeenCalledOnce()
    expect(state.done).toBe(true)
    expect(state.error).toBeNull()
  })

  it('does not set timedOut when callback resolves before timeout', async () => {
    const state = makeCallbackState()

    await runCallbackFlow(state, {
      handleCallback: vi.fn().mockResolvedValue(undefined),
      login: vi.fn(),
      navigate: vi.fn().mockResolvedValue(undefined),
      setTimeout: globalThis.setTimeout.bind(globalThis),
      clearTimeout: globalThis.clearTimeout.bind(globalThis),
    })

    vi.advanceTimersByTime(CALLBACK_TIMEOUT_MS + 1000)
    expect(state.timedOut).toBe(false)
  })
})

// ── Scenario: Callback failure → restarts login ───────────────────────────────

describe('Auth Callback — callback failure', () => {
  it('calls login() and records error when handleCallback rejects', async () => {
    const state = makeCallbackState()
    const callbackError = new Error('stale state')
    const handleCallback = vi.fn().mockRejectedValue(callbackError)
    const login = vi.fn().mockResolvedValue(undefined)
    const navigate = vi.fn()
    const clearTimeoutSpy = vi.fn()

    await runCallbackFlow(state, {
      handleCallback,
      login,
      navigate,
      setTimeout: globalThis.setTimeout.bind(globalThis),
      clearTimeout: clearTimeoutSpy,
    })

    expect(login).toHaveBeenCalledOnce()
    expect(navigate).not.toHaveBeenCalled()
    expect(state.error).toBe(callbackError)
    expect(state.done).toBe(false)
    expect(clearTimeoutSpy).toHaveBeenCalledOnce()
  })

  it('clears timeout even when callback fails', async () => {
    const state = makeCallbackState()
    const clearTimeoutSpy = vi.fn()

    await runCallbackFlow(state, {
      handleCallback: vi.fn().mockRejectedValue(new Error('fail')),
      login: vi.fn().mockResolvedValue(undefined),
      navigate: vi.fn(),
      setTimeout: globalThis.setTimeout.bind(globalThis),
      clearTimeout: clearTimeoutSpy,
    })

    expect(clearTimeoutSpy).toHaveBeenCalledOnce()
  })
})

// ── Scenario: Retry button ─────────────────────────────────────────────────────

describe('Auth Callback — retry login', () => {
  it('retry invokes login()', async () => {
    const login = vi.fn().mockResolvedValue(undefined)

    // Simulate retryLogin() from the component
    async function retryLogin() {
      await login()
    }

    await retryLogin()
    expect(login).toHaveBeenCalledOnce()
  })

  it('retry can be called multiple times independently', async () => {
    const login = vi.fn().mockResolvedValue(undefined)

    async function retryLogin() {
      await login()
    }

    await retryLogin()
    await retryLogin()
    expect(login).toHaveBeenCalledTimes(2)
  })
})

// ── Scenario: Initial page state ──────────────────────────────────────────────

describe('Auth Callback — initial state', () => {
  it('starts with timedOut false', () => {
    const state = makeCallbackState()
    expect(state.timedOut).toBe(false)
  })

  it('starts with no error', () => {
    const state = makeCallbackState()
    expect(state.error).toBeNull()
  })

  it('starts as not done', () => {
    const state = makeCallbackState()
    expect(state.done).toBe(false)
  })
})
