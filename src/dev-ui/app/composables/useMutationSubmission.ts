import type { MutationResult } from '~/types'

export type MutationSubmissionStatus = 'idle' | 'submitting' | 'success' | 'failed'

export interface MutationSubmissionState {
  status: MutationSubmissionStatus
  operationCount: number
  result: MutationResult | null
  error: string | null
  /** Timestamp when submission started (for computing elapsed time locally) */
  startedAt: number | null
  /** Timestamp when submission completed (for displaying final elapsed time) */
  completedAt: number | null
}

/**
 * Cross-component mutation submission state.
 *
 * Uses Nuxt `useState` so the reactive state persists across page
 * navigations (e.g. the user can leave the mutations page and still
 * see a floating progress indicator).
 *
 * Elapsed time is NOT stored in reactive state — it was causing the
 * entire app to re-render every second via Vue's reactivity system.
 * Instead, `startedAt` / `completedAt` timestamps are stored, and
 * consuming components compute elapsed time locally with their own
 * `setInterval`.
 */
export function useMutationSubmission() {
  const state = useState<MutationSubmissionState>('mutation-submission', () => ({
    status: 'idle',
    operationCount: 0,
    result: null,
    error: null,
    startedAt: null,
    completedAt: null,
  }))

  const { applyMutations } = useGraphApi()
  const { extractErrorMessage } = useErrorHandler()

  async function submit(jsonlContent: string, opCount: number) {
    if (state.value.status === 'submitting') return

    state.value = {
      status: 'submitting',
      operationCount: opCount,
      result: null,
      error: null,
      startedAt: Date.now(),
      completedAt: null,
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 300_000) // 5 min

    try {
      const result = await applyMutations(jsonlContent, { signal: controller.signal })
      clearTimeout(timeoutId)
      state.value.completedAt = Date.now()
      state.value.result = result
      state.value.status = result.success ? 'success' : 'failed'
      if (!result.success && result.errors.length > 0) {
        state.value.error = result.errors.join('; ')
      }
    } catch (err) {
      clearTimeout(timeoutId)
      state.value.completedAt = Date.now()
      state.value.status = 'failed'
      if (err instanceof Error && err.name === 'AbortError') {
        state.value.error = 'Request timed out after 5 minutes'
      } else {
        state.value.error = extractErrorMessage(err)
      }
    }
  }

  function dismiss() {
    state.value = {
      status: 'idle',
      operationCount: 0,
      result: null,
      error: null,
      startedAt: null,
      completedAt: null,
    }
  }

  return {
    state,
    submit,
    dismiss,
  }
}
