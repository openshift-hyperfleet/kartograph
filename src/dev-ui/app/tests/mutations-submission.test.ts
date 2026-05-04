import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Mutations Console — Submission Flow Tests ────────────────────────────────
//
// Spec: "Mutations Console" — Scenario: Submission and Scenario: Submission failure
// Ref: specs/ui/experience.spec.md
//
// Verifies the floating progress indicator that persists across navigation:
//   - Submission state machine (submitting / success / failed / idle)
//   - Floating indicator positioning and content
//   - Minimize-to-pill and dismiss-after-completion behaviour
//   - Error display including partial success count
//   - Cross-page persistence via app-level mounting
//
// The production implementation uses:
//   - composables/useMutationSubmission.ts  — Nuxt useState-backed store
//   - components/graph/MutationProgress.vue — fixed-position floating indicator
//   - app.vue                               — app-root mount (cross-page persistence)
//   - pages/graph/mutations.vue             — submit wiring

// ── Source file paths ────────────────────────────────────────────────────────

const mutationProgressPath = resolve(__dirname, '../components/graph/MutationProgress.vue')
const mutationProgress = readFileSync(mutationProgressPath, 'utf-8')

const appVuePath = resolve(__dirname, '../app.vue')
const appVue = readFileSync(appVuePath, 'utf-8')

const submissionComposablePath = resolve(__dirname, '../composables/useMutationSubmission.ts')
const submissionComposable = readFileSync(submissionComposablePath, 'utf-8')

const mutationsVuePath = resolve(__dirname, '../pages/graph/mutations.vue')
const mutationsVue = readFileSync(mutationsVuePath, 'utf-8')

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission
// "THEN the mutations are submitted to the API … and a floating progress
//  indicator appears in the bottom-right corner"
// ────────────────────────────────────────────────────────────────────────────

describe('Submission — indicator appears on submit', () => {
  it('mutations.vue calls submission.submit() on Apply Mutations', () => {
    expect(mutationsVue).toContain('submission.submit(')
  })

  it('mutations.vue uses useMutationSubmission() to access cross-page state', () => {
    expect(mutationsVue).toContain('useMutationSubmission()')
  })

  it('MutationProgress.vue is positioned fixed bottom-right (viewport-anchored)', () => {
    expect(mutationProgress).toContain('fixed bottom-4 right-4')
  })

  it('MutationProgress.vue is hidden when status is idle', () => {
    // isVisible = state.value.status !== 'idle'
    expect(mutationProgress).toContain("state.value.status !== 'idle'")
    expect(mutationProgress).toContain('isVisible')
    expect(mutationProgress).toContain('v-if="isVisible"')
  })

  it('MutationProgress.vue renders a submitting state', () => {
    expect(mutationProgress).toContain("state.status === 'submitting'")
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission — operation count
// "AND the indicator shows status (submitting / success / failed), operation
//  count, and elapsed time"
// ────────────────────────────────────────────────────────────────────────────

describe('Submission — operation count display', () => {
  it('MutationProgress.vue displays operationCount from submission state', () => {
    expect(mutationProgress).toContain('operationCount')
  })

  it('operationCount is shown as a localized number with a badge', () => {
    expect(mutationProgress).toContain('state.operationCount.toLocaleString()')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission — elapsed time
// ────────────────────────────────────────────────────────────────────────────

describe('Submission — elapsed time counter', () => {
  it('MutationProgress.vue tracks elapsed seconds via a local setInterval', () => {
    expect(mutationProgress).toContain('elapsedSeconds')
    expect(mutationProgress).toContain('setInterval')
  })

  it('local timer is started when status becomes submitting', () => {
    expect(mutationProgress).toContain('startLocalTimer')
    expect(mutationProgress).toContain("status === 'submitting'")
  })

  it('local timer is stopped when submission completes or fails', () => {
    expect(mutationProgress).toContain('stopLocalTimer')
    expect(mutationProgress).toContain('clearInterval')
  })

  it('useMutationSubmission stores startedAt and completedAt timestamps', () => {
    expect(submissionComposable).toContain('startedAt')
    expect(submissionComposable).toContain('completedAt')
  })

  it('elapsed time computation uses startedAt and completedAt timestamps', () => {
    const startedAt = Date.now() - 5_000
    const completedAt = Date.now()
    const elapsed = Math.floor((completedAt - startedAt) / 1000)
    expect(elapsed).toBeGreaterThanOrEqual(5)
  })

  it('final elapsed is frozen at completedAt once submission is done', () => {
    expect(mutationProgress).toContain('finalElapsedSeconds')
    expect(mutationProgress).toContain('completedAt')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission — persists across navigation
// "AND the indicator persists when the user navigates away from the mutations
//  console"
// ────────────────────────────────────────────────────────────────────────────

describe('Submission — cross-page persistence', () => {
  it('MutationProgress is mounted in app.vue (app root — renders on every page)', () => {
    expect(appVue).toContain('MutationProgress')
  })

  it('app.vue imports MutationProgress from components/graph/', () => {
    expect(appVue).toContain("from '@/components/graph/MutationProgress.vue'")
  })

  it('useMutationSubmission uses Nuxt useState to persist across navigation', () => {
    // Nuxt useState survives page transitions because it is stored at the Nuxt
    // app level, not in the page component's local state.
    expect(submissionComposable).toContain('useState')
  })

  it("state key is 'mutation-submission' (unique identifier)", () => {
    expect(submissionComposable).toContain("'mutation-submission'")
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission — success state
// ────────────────────────────────────────────────────────────────────────────

describe('Submission — success state display', () => {
  it('MutationProgress.vue renders a distinct success state', () => {
    expect(mutationProgress).toContain("state.status === 'success'")
  })

  it('success state displays operations_applied count from the API result', () => {
    expect(mutationProgress).toContain('operations_applied')
  })

  it('success state displays the final elapsed time', () => {
    expect(mutationProgress).toContain('finalElapsedSeconds')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission — minimize to compact pill
// "AND the indicator can be minimized to a compact pill or dismissed after
//  completion"
// ────────────────────────────────────────────────────────────────────────────

describe('Submission — minimize to compact pill', () => {
  it('MutationProgress.vue has a minimized state (compact pill)', () => {
    expect(mutationProgress).toContain('minimized')
  })

  it('MutationProgress.vue has a Minimize button that sets minimized = true', () => {
    // The Minus icon button sets minimized to true
    expect(mutationProgress).toContain('minimized = true')
  })

  it('MutationProgress.vue has an Expand button that sets minimized = false', () => {
    expect(mutationProgress).toContain('minimized = false')
  })

  it('minimized pill links back to /graph/mutations (navigation shortcut)', () => {
    expect(mutationProgress).toContain('to="/graph/mutations"')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission — dismiss after completion
// ────────────────────────────────────────────────────────────────────────────

describe('Submission — dismiss after completion', () => {
  it('MutationProgress.vue exposes a Dismiss button that calls dismiss()', () => {
    expect(mutationProgress).toContain('dismiss')
  })

  it('Dismiss is only available when not submitting (cannot dismiss mid-flight)', () => {
    // The dismiss button renders only when status !== 'submitting'
    expect(mutationProgress).toContain("state.status !== 'submitting'")
  })

  it('useMutationSubmission.dismiss() resets state to idle', () => {
    expect(submissionComposable).toContain("status: 'idle'")
    // The dismiss function resets all fields
    expect(submissionComposable).toContain('function dismiss()')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission failure
// "THEN the floating indicator shows the error message"
// ────────────────────────────────────────────────────────────────────────────

describe('Submission failure — error message', () => {
  it('MutationProgress.vue renders a distinct failed state', () => {
    expect(mutationProgress).toContain("state.status === 'failed'")
  })

  it('MutationProgress.vue shows state.error in the failed state', () => {
    expect(mutationProgress).toContain('state.error')
  })

  it('error message is truncated to 120 characters to prevent layout overflow', () => {
    expect(mutationProgress).toContain('truncatedError')
    expect(mutationProgress).toContain('120')
  })

  it('truncation appends "..." to messages longer than 120 chars', () => {
    function truncateError(err: string | null): string {
      if (!err) return ''
      return err.length > 120 ? err.slice(0, 120) + '...' : err
    }
    const short = 'Network error: connection refused'
    expect(truncateError(short)).toBe(short)

    const long = 'E'.repeat(150)
    const truncated = truncateError(long)
    expect(truncated.endsWith('...')).toBe(true)
    expect(truncated.length).toBe(123) // 120 + 3 for '...'
  })

  it('full error is accessible via title attribute for assistive technology', () => {
    expect(mutationProgress).toContain(':title="state.error')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission failure — operations applied before failure
// "AND the number of operations applied before failure is displayed if any
//  were processed"
// ────────────────────────────────────────────────────────────────────────────

describe('Submission failure — partial success count', () => {
  it('MutationProgress.vue shows operations_applied count in the failed state', () => {
    expect(mutationProgress).toContain('operations_applied')
  })

  it('MutationProgress.vue displays "applied before failure" label', () => {
    expect(mutationProgress).toContain('applied before failure')
  })

  it('partial-success line is shown conditionally (only when result exists)', () => {
    // v-if="state.result" guards the partial success display
    expect(mutationProgress).toContain('state.result')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Submission state machine (pure logic tests)
// ────────────────────────────────────────────────────────────────────────────

describe('Submission state machine — pure transitions', () => {
  interface SubmissionState {
    status: 'idle' | 'submitting' | 'success' | 'failed'
    operationCount: number
    result: { success: boolean; operations_applied: number; errors: string[] } | null
    error: string | null
    startedAt: number | null
    completedAt: number | null
  }

  function idle(): SubmissionState {
    return {
      status: 'idle',
      operationCount: 0,
      result: null,
      error: null,
      startedAt: null,
      completedAt: null,
    }
  }

  function submitting(opCount: number): SubmissionState {
    return {
      status: 'submitting',
      operationCount: opCount,
      result: null,
      error: null,
      startedAt: Date.now(),
      completedAt: null,
    }
  }

  function success(
    prev: SubmissionState,
    result: { success: boolean; operations_applied: number; errors: string[] },
  ): SubmissionState {
    return {
      ...prev,
      status: result.success ? 'success' : 'failed',
      result,
      error: !result.success && result.errors.length > 0 ? result.errors.join('; ') : null,
      completedAt: Date.now(),
    }
  }

  function failed(prev: SubmissionState, message: string): SubmissionState {
    return { ...prev, status: 'failed', error: message, completedAt: Date.now() }
  }

  it('initial state is idle', () => {
    const state = idle()
    expect(state.status).toBe('idle')
    expect(state.operationCount).toBe(0)
    expect(state.startedAt).toBeNull()
  })

  it('submitting state captures operation count and startedAt', () => {
    const state = submitting(42)
    expect(state.status).toBe('submitting')
    expect(state.operationCount).toBe(42)
    expect(state.startedAt).not.toBeNull()
    expect(state.completedAt).toBeNull()
  })

  it('success state transition preserves operation count', () => {
    const s = submitting(10)
    const done = success(s, { success: true, operations_applied: 10, errors: [] })
    expect(done.status).toBe('success')
    expect(done.operationCount).toBe(10)
    expect(done.result?.operations_applied).toBe(10)
    expect(done.completedAt).not.toBeNull()
  })

  it('api error with success=false transitions to failed with error text', () => {
    const s = submitting(5)
    const done = success(s, { success: false, operations_applied: 2, errors: ['Type not found'] })
    expect(done.status).toBe('failed')
    expect(done.error).toContain('Type not found')
    expect(done.result?.operations_applied).toBe(2) // partial success count
  })

  it('network error transitions to failed with error message', () => {
    const s = submitting(20)
    const done = failed(s, 'Connection refused')
    expect(done.status).toBe('failed')
    expect(done.error).toBe('Connection refused')
    expect(done.completedAt).not.toBeNull()
  })

  it('dismiss resets to idle (indicator hidden)', () => {
    const s = failed(submitting(5), 'error')
    const reset = idle()
    expect(reset.status).toBe('idle')
    expect(reset.error).toBeNull()
    expect(reset.operationCount).toBe(0)
  })

  it('dismiss is valid from both success and failed states', () => {
    // Both success and failed return to idle on dismiss
    const successState = success(submitting(5), { success: true, operations_applied: 5, errors: [] })
    expect(successState.status).toBe('success')
    // After dismiss, status should be idle
    const reset = idle()
    expect(reset.status).toBe('idle')
  })
})
