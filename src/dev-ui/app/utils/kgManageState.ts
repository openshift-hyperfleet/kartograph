export type ManageSectionId =
  | 'workspace-overview'
  | 'graph-management'
  | 'mutation-logs'
  | 'data-sources'
  | 'maintain'

export type SectionPhase = 'loading' | 'empty' | 'error' | 'ready' | 'forbidden'

export interface SectionStateContract {
  phase: SectionPhase
  title: string
  message: string
  actionLabel?: string
}

export const SECTION_STATE_MESSAGES: Record<
  ManageSectionId,
  { loading: string; empty: string; error: string; forbidden: string }
> = {
  'workspace-overview': {
    loading: 'Loading workspace overview and step readiness…',
    empty: 'Workspace overview is unavailable until status loads.',
    error: 'Could not load workspace overview for this knowledge graph.',
    forbidden: 'You do not have permission to view this workspace overview.',
  },
  'graph-management': {
    loading: 'Loading graph management session and workspace panels…',
    empty: 'Graph management is ready, but no session activity is loaded yet.',
    error: 'Could not load graph management session data.',
    forbidden: 'You do not have permission to manage this knowledge graph.',
  },
  'mutation-logs': {
    loading: 'Loading mutation log runs for this knowledge graph…',
    empty: 'No mutation log runs recorded for this knowledge graph yet.',
    error: 'Could not load mutation log runs for this knowledge graph.',
    forbidden: 'You do not have permission to view mutation logs for this graph.',
  },
  'data-sources': {
    loading: 'Loading data source readiness for this knowledge graph…',
    empty: 'Connect a data source to continue workspace setup.',
    error: 'Could not load data sources for this knowledge graph.',
    forbidden: 'You do not have permission to view data sources for this graph.',
  },
  maintain: {
    loading: 'Loading maintenance readiness for tracked sources…',
    empty: 'No tracked source changes are ready for maintenance.',
    error: 'Could not load maintenance readiness for this knowledge graph.',
    forbidden: 'You do not have permission to run maintenance for this graph.',
  },
}

export function isForbiddenHttpError(err: unknown): boolean {
  if (err && typeof err === 'object') {
    const fetchErr = err as { statusCode?: number; status?: number }
    const status = fetchErr.statusCode ?? fetchErr.status
    if (status === 403) return true
  }
  if (err instanceof Error) {
    const message = err.message.toLowerCase()
    return message.includes('forbidden') || message.includes('403')
  }
  return false
}

export function resolveForbiddenReason(
  err: unknown,
  fallback: string,
): string {
  if (err instanceof Error && err.message.trim()) {
    return err.message
  }
  if (err && typeof err === 'object') {
    const fetchErr = err as { data?: { detail?: unknown } }
    if (typeof fetchErr.data?.detail === 'string' && fetchErr.data.detail.trim()) {
      return fetchErr.data.detail
    }
  }
  return fallback
}

export function resolveSectionState(input: {
  section: ManageSectionId
  loading?: boolean
  error?: string | null
  forbidden?: boolean
  forbiddenReason?: string | null
  empty?: boolean
  emptyActionLabel?: string
}): SectionStateContract {
  const defaults = SECTION_STATE_MESSAGES[input.section]

  if (input.forbidden) {
    return {
      phase: 'forbidden',
      title: 'Access restricted',
      message: input.forbiddenReason?.trim() || defaults.forbidden,
    }
  }

  if (input.loading) {
    return {
      phase: 'loading',
      title: 'Loading',
      message: defaults.loading,
    }
  }

  if (input.error) {
    return {
      phase: 'error',
      title: 'Unable to load section',
      message: input.error,
    }
  }

  if (input.empty) {
    return {
      phase: 'empty',
      title: 'Nothing to show yet',
      message: defaults.empty,
      actionLabel: input.emptyActionLabel,
    }
  }

  return {
    phase: 'ready',
    title: 'Ready',
    message: '',
  }
}

export function handleChatInputKeydown(
  event: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'preventDefault'>,
  onSend: () => void,
): 'send' | 'newline' | 'ignored' {
  if (event.key !== 'Enter') return 'ignored'
  if (event.shiftKey) return 'newline'
  event.preventDefault()
  onSend()
  return 'send'
}

export function handleActivatableKeydown(
  event: Pick<KeyboardEvent, 'key' | 'preventDefault'>,
  onActivate: () => void,
): boolean {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    onActivate()
    return true
  }
  return false
}

export function buildTransitionRestrictionReason(
  canTransition: boolean,
  blockingReasons: string[],
): string | null {
  if (canTransition) return null
  if (blockingReasons.length > 0) {
    return `Transition blocked: ${blockingReasons.join('; ')}`
  }
  return 'Transition blocked until schema bootstrap readiness requirements are met.'
}

export function shouldApplyMutationResult(forbidden: boolean): boolean {
  return !forbidden
}

export function appendLocalChatMessage(
  session: { message_history: Array<{ role?: string; content?: string; message?: string }> } | null,
  content: string,
): Array<{ role?: string; content?: string; message?: string }> {
  const trimmed = content.trim()
  if (!trimmed) return session?.message_history ?? []
  const history = [...(session?.message_history ?? [])]
  history.push({ role: 'user', content: trimmed })
  return history
}
