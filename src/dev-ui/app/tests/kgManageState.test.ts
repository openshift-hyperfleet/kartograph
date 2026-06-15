import { describe, it, expect, vi } from 'vitest'
import {
  SECTION_STATE_MESSAGES,
  appendLocalChatMessage,
  buildTransitionRestrictionReason,
  handleActivatableKeydown,
  handleChatInputKeydown,
  isForbiddenHttpError,
  isNotFoundHttpError,
  resolveForbiddenReason,
  resolveSectionState,
  shouldApplyMutationResult,
} from '../utils/kgManageState'

describe('KG-MANAGE-017 - chat input keyboard contract', () => {
  it('sends on Enter without Shift', () => {
    const onSend = vi.fn()
    const preventDefault = vi.fn()
    const result = handleChatInputKeydown(
      { key: 'Enter', shiftKey: false, preventDefault },
      onSend,
    )

    expect(result).toBe('send')
    expect(preventDefault).toHaveBeenCalledOnce()
    expect(onSend).toHaveBeenCalledOnce()
  })

  it('inserts newline on Shift+Enter without sending', () => {
    const onSend = vi.fn()
    const preventDefault = vi.fn()
    const result = handleChatInputKeydown(
      { key: 'Enter', shiftKey: true, preventDefault },
      onSend,
    )

    expect(result).toBe('newline')
    expect(preventDefault).not.toHaveBeenCalled()
    expect(onSend).not.toHaveBeenCalled()
  })

  it('ignores non-Enter keys', () => {
    const onSend = vi.fn()
    const preventDefault = vi.fn()
    const result = handleChatInputKeydown(
      { key: 'a', shiftKey: false, preventDefault },
      onSend,
    )

    expect(result).toBe('ignored')
    expect(onSend).not.toHaveBeenCalled()
  })
})

describe('KG-MANAGE-018 - keyboard operable step and rail actions', () => {
  it('activates step actions on Enter', () => {
    const onActivate = vi.fn()
    const preventDefault = vi.fn()
    const handled = handleActivatableKeydown(
      { key: 'Enter', preventDefault },
      onActivate,
    )

    expect(handled).toBe(true)
    expect(preventDefault).toHaveBeenCalledOnce()
    expect(onActivate).toHaveBeenCalledOnce()
  })

  it('activates step actions on Space', () => {
    const onActivate = vi.fn()
    const preventDefault = vi.fn()
    const handled = handleActivatableKeydown(
      { key: ' ', preventDefault },
      onActivate,
    )

    expect(handled).toBe(true)
    expect(onActivate).toHaveBeenCalledOnce()
  })

  it('ignores unrelated keys for activatable controls', () => {
    const onActivate = vi.fn()
    const handled = handleActivatableKeydown(
      { key: 'Tab', preventDefault: vi.fn() },
      onActivate,
    )

    expect(handled).toBe(false)
    expect(onActivate).not.toHaveBeenCalled()
  })
})

describe('KG-MANAGE-019 - section-specific loading, empty, and error states', () => {
  it('uses step-specific loading messages', () => {
    const overview = resolveSectionState({
      section: 'workspace-overview',
      loading: true,
    })
    const mutationLogs = resolveSectionState({
      section: 'mutation-logs',
      loading: true,
    })

    expect(overview.message).toBe(SECTION_STATE_MESSAGES['workspace-overview'].loading)
    expect(mutationLogs.message).toBe(SECTION_STATE_MESSAGES['mutation-logs'].loading)
    expect(overview.message).not.toBe(mutationLogs.message)
  })

  it('returns actionable empty states with optional next-step labels', () => {
    const state = resolveSectionState({
      section: 'mutation-logs',
      empty: true,
      emptyActionLabel: 'Refresh runs',
    })

    expect(state.phase).toBe('empty')
    expect(state.message).toBe(SECTION_STATE_MESSAGES['mutation-logs'].empty)
    expect(state.actionLabel).toBe('Refresh runs')
  })

  it('surfaces section-specific error messaging', () => {
    const state = resolveSectionState({
      section: 'graph-management',
      error: 'Session service unavailable',
    })

    expect(state.phase).toBe('error')
    expect(state.message).toBe('Session service unavailable')
  })
})

describe('KG-MANAGE-020 - forbidden and disabled action restrictions', () => {
  it('detects forbidden HTTP errors', () => {
    expect(isForbiddenHttpError({ statusCode: 403 })).toBe(true)
    expect(isForbiddenHttpError(new Error('Forbidden'))).toBe(true)
    expect(isForbiddenHttpError({ statusCode: 404 })).toBe(false)
  })

  it('detects not-found HTTP errors without treating them as failures', () => {
    expect(isNotFoundHttpError({ statusCode: 404 })).toBe(true)
    expect(isNotFoundHttpError(new Error('Not Found'))).toBe(true)
    expect(isNotFoundHttpError({ statusCode: 403 })).toBe(false)
  })

  it('builds explicit forbidden section messaging', () => {
    const state = resolveSectionState({
      section: 'graph-management',
      forbidden: true,
      forbiddenReason: 'You do not have permission to perform this action',
    })

    expect(state.phase).toBe('forbidden')
    expect(state.message).toBe('You do not have permission to perform this action')
  })

  it('explains why transition is disabled', () => {
    expect(
      buildTransitionRestrictionReason(false, ['Missing entity types']),
    ).toBe('Transition blocked: Missing entity types')
    expect(buildTransitionRestrictionReason(true, [])).toBeNull()
  })

  it('blocks mutation result application when forbidden', () => {
    expect(shouldApplyMutationResult(true)).toBe(false)
    expect(shouldApplyMutationResult(false)).toBe(true)
  })

  it('extracts forbidden reasons from API errors', () => {
    expect(
      resolveForbiddenReason(
        { data: { detail: 'You do not have permission to perform this action' } },
        'Access restricted',
      ),
    ).toBe('You do not have permission to perform this action')
  })
})

describe('KG-MANAGE-017 - local chat send helper', () => {
  it('appends trimmed user messages to session history', () => {
    const history = appendLocalChatMessage(
      { message_history: [{ role: 'assistant', content: 'Hello' }] },
      '  Define schema  ',
    )

    expect(history).toHaveLength(2)
    expect(history[1]).toEqual({ role: 'user', content: 'Define schema' })
  })

  it('ignores blank chat submissions', () => {
    const history = appendLocalChatMessage(
      { message_history: [{ role: 'assistant', content: 'Hello' }] },
      '   ',
    )

    expect(history).toHaveLength(1)
  })
})
