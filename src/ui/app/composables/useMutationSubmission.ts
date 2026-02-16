import type { MutationResult } from '~/types'

export type MutationSubmissionStatus = 'idle' | 'submitting' | 'success' | 'failed'

export interface MutationSubmissionState {
  status: MutationSubmissionStatus
  operationCount: number
  elapsedSeconds: number
  result: MutationResult | null
  error: string | null
  startedAt: number | null
}

/**
 * Cross-component mutation submission state.
 *
 * Uses Nuxt `useState` so the reactive state persists across page
 * navigations (e.g. the user can leave the mutations page and still
 * see a floating progress indicator).
 */
export function useMutationSubmission() {
  const state = useState<MutationSubmissionState>('mutation-submission', () => ({
    status: 'idle',
    operationCount: 0,
    elapsedSeconds: 0,
    result: null,
    error: null,
    startedAt: null,
  }))

  const { applyMutations } = useGraphApi()
  const { extractErrorMessage } = useErrorHandler()

  let elapsedInterval: ReturnType<typeof setInterval> | null = null

  function startTimer() {
    stopTimer()
    state.value.elapsedSeconds = 0
    elapsedInterval = setInterval(() => {
      state.value.elapsedSeconds++
    }, 1000)
  }

  function stopTimer() {
    if (elapsedInterval) {
      clearInterval(elapsedInterval)
      elapsedInterval = null
    }
  }

  async function submit(jsonlContent: string, opCount: number) {
    if (state.value.status === 'submitting') return

    state.value = {
      status: 'submitting',
      operationCount: opCount,
      elapsedSeconds: 0,
      result: null,
      error: null,
      startedAt: Date.now(),
    }
    startTimer()

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 300_000) // 5 min

    try {
      const result = await applyMutations(jsonlContent, { signal: controller.signal })
      clearTimeout(timeoutId)
      stopTimer()
      state.value.result = result
      state.value.status = result.success ? 'success' : 'failed'
      if (!result.success && result.errors.length > 0) {
        state.value.error = result.errors.join('; ')
      }
    } catch (err) {
      clearTimeout(timeoutId)
      stopTimer()
      state.value.status = 'failed'
      if (err instanceof Error && err.name === 'AbortError') {
        state.value.error = 'Request timed out after 5 minutes'
      } else {
        state.value.error = extractErrorMessage(err)
      }
    }
  }

  function dismiss() {
    stopTimer()
    state.value = {
      status: 'idle',
      operationCount: 0,
      elapsedSeconds: 0,
      result: null,
      error: null,
      startedAt: null,
    }
  }

  return {
    state,
    submit,
    dismiss,
  }
}
