import { describe, it, expect } from 'vitest'

type SyncStatus = 'pending' | 'ingesting' | 'ai_extracting' | 'applying' | 'completed' | 'failed'

/**
 * Core logic: determine whether a given status warrants an animated indicator
 * vs. a static badge.
 */
function isAnimatedStatus(status: SyncStatus): boolean {
  return status === 'pending' || status === 'ingesting' || status === 'ai_extracting' || status === 'applying'
}

/**
 * Determine the indicator style for a given active phase.
 */
type IndicatorStyle = 'pulse' | 'spin'

function getIndicatorStyle(status: SyncStatus): IndicatorStyle | null {
  switch (status) {
    case 'pending':    return 'pulse'
    case 'ingesting':  return 'spin'
    case 'ai_extracting': return 'spin'
    case 'applying':   return 'pulse'
    default:           return null
  }
}

/**
 * Map a status to its badge variant — active phases use 'secondary',
 * completed uses 'default', failed uses 'destructive'.
 */
type BadgeVariant = 'default' | 'secondary' | 'destructive'

function getBadgeVariant(status: SyncStatus): BadgeVariant {
  if (status === 'completed') return 'default'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

/**
 * Map a status to its user-readable phase label.
 */
const PHASE_LABELS: Record<SyncStatus, string> = {
  pending:       'Pending',
  ingesting:     'Ingesting',
  ai_extracting: 'Extracting',
  applying:      'Applying',
  completed:     'Completed',
  failed:        'Failed',
}

function getPhaseLabel(status: SyncStatus): string {
  return PHASE_LABELS[status] ?? status
}

// ── isAnimatedStatus() ──────────────────────────────────────────────────────

describe('SyncPhaseIndicator — isAnimatedStatus()', () => {
  it('returns true for pending', () => {
    expect(isAnimatedStatus('pending')).toBe(true)
  })
  it('returns true for ingesting', () => {
    expect(isAnimatedStatus('ingesting')).toBe(true)
  })
  it('returns true for ai_extracting', () => {
    expect(isAnimatedStatus('ai_extracting')).toBe(true)
  })
  it('returns true for applying', () => {
    expect(isAnimatedStatus('applying')).toBe(true)
  })
  it('returns false for completed', () => {
    expect(isAnimatedStatus('completed')).toBe(false)
  })
  it('returns false for failed', () => {
    expect(isAnimatedStatus('failed')).toBe(false)
  })
})

// ── getIndicatorStyle() ─────────────────────────────────────────────────────

describe('SyncPhaseIndicator — getIndicatorStyle()', () => {
  it('pending uses pulse (waiting)', () => {
    expect(getIndicatorStyle('pending')).toBe('pulse')
  })
  it('ingesting uses spin (actively reading)', () => {
    expect(getIndicatorStyle('ingesting')).toBe('spin')
  })
  it('ai_extracting uses spin (AI processing)', () => {
    expect(getIndicatorStyle('ai_extracting')).toBe('spin')
  })
  it('applying uses pulse (writing)', () => {
    expect(getIndicatorStyle('applying')).toBe('pulse')
  })
  it('completed returns null (no animation needed)', () => {
    expect(getIndicatorStyle('completed')).toBeNull()
  })
  it('failed returns null (no animation needed)', () => {
    expect(getIndicatorStyle('failed')).toBeNull()
  })
})

// ── getBadgeVariant() ───────────────────────────────────────────────────────

describe('SyncPhaseIndicator — getBadgeVariant()', () => {
  it('pending uses secondary variant', () => {
    expect(getBadgeVariant('pending')).toBe('secondary')
  })
  it('ingesting uses secondary variant', () => {
    expect(getBadgeVariant('ingesting')).toBe('secondary')
  })
  it('ai_extracting uses secondary variant', () => {
    expect(getBadgeVariant('ai_extracting')).toBe('secondary')
  })
  it('applying uses secondary variant', () => {
    expect(getBadgeVariant('applying')).toBe('secondary')
  })
  it('completed uses default variant', () => {
    expect(getBadgeVariant('completed')).toBe('default')
  })
  it('failed uses destructive variant', () => {
    expect(getBadgeVariant('failed')).toBe('destructive')
  })
})

// ── getPhaseLabel() ─────────────────────────────────────────────────────────

describe('SyncPhaseIndicator — getPhaseLabel()', () => {
  it('pending maps to Pending', () => {
    expect(getPhaseLabel('pending')).toBe('Pending')
  })
  it('ingesting maps to Ingesting', () => {
    expect(getPhaseLabel('ingesting')).toBe('Ingesting')
  })
  it('ai_extracting maps to Extracting', () => {
    expect(getPhaseLabel('ai_extracting')).toBe('Extracting')
  })
  it('applying maps to Applying', () => {
    expect(getPhaseLabel('applying')).toBe('Applying')
  })
  it('completed maps to Completed', () => {
    expect(getPhaseLabel('completed')).toBe('Completed')
  })
  it('failed maps to Failed', () => {
    expect(getPhaseLabel('failed')).toBe('Failed')
  })
})

// ── Compound behaviour: active phases have both animated + secondary badge ──

describe('SyncPhaseIndicator — active phase compound behaviour', () => {
  const activeStatuses: SyncStatus[] = ['pending', 'ingesting', 'ai_extracting', 'applying']

  activeStatuses.forEach((status) => {
    it(`${status} is animated with secondary badge`, () => {
      expect(isAnimatedStatus(status)).toBe(true)
      expect(getBadgeVariant(status)).toBe('secondary')
      expect(getIndicatorStyle(status)).not.toBeNull()
    })
  })
})

// ── Compound behaviour: terminal phases have static badge, no animation ─────

describe('SyncPhaseIndicator — terminal phase compound behaviour', () => {
  it('completed: no animation, default badge', () => {
    expect(isAnimatedStatus('completed')).toBe(false)
    expect(getBadgeVariant('completed')).toBe('default')
    expect(getIndicatorStyle('completed')).toBeNull()
  })

  it('failed: no animation, destructive badge', () => {
    expect(isAnimatedStatus('failed')).toBe(false)
    expect(getBadgeVariant('failed')).toBe('destructive')
    expect(getIndicatorStyle('failed')).toBeNull()
  })
})

// ── Icon choice consistency: spin phases use Loader2-style, pulse use pulse ──

describe('SyncPhaseIndicator — icon animation class mapping', () => {
  it('ingesting and ai_extracting both use spin animation', () => {
    expect(getIndicatorStyle('ingesting')).toBe('spin')
    expect(getIndicatorStyle('ai_extracting')).toBe('spin')
  })

  it('pending and applying both use pulse animation', () => {
    expect(getIndicatorStyle('pending')).toBe('pulse')
    expect(getIndicatorStyle('applying')).toBe('pulse')
  })
})
