import { describe, expect, it } from 'vitest'
import {
  graphManagementModeLockReason,
  isGraphManagementModeUnlocked,
  resolveEffectiveGraphManagementMode,
} from '../utils/kgGraphManagement'

describe('graph management mode gates', () => {
  const bootstrap = {
    workspaceMode: 'schema_bootstrap' as const,
    transitionEligible: false,
  }

  const validatedBootstrap = {
    workspaceMode: 'schema_bootstrap' as const,
    transitionEligible: true,
  }

  const operations = {
    workspaceMode: 'extraction_operations' as const,
    transitionEligible: true,
  }

  it('always unlocks initial schema design', () => {
    expect(isGraphManagementModeUnlocked('initial-schema-design', bootstrap)).toBe(true)
  })

  it('locks extraction modes until extraction operations', () => {
    expect(isGraphManagementModeUnlocked('extraction-jobs', bootstrap)).toBe(false)
    expect(isGraphManagementModeUnlocked('one-off-mutations', validatedBootstrap)).toBe(false)
    expect(isGraphManagementModeUnlocked('extraction-jobs', operations)).toBe(true)
    expect(isGraphManagementModeUnlocked('one-off-mutations', operations)).toBe(true)
  })

  it('returns contextual lock reasons', () => {
    expect(graphManagementModeLockReason('extraction-jobs', bootstrap)).toContain('validation')
    expect(graphManagementModeLockReason('one-off-mutations', validatedBootstrap)).toContain(
      'Extraction/Mutations',
    )
    expect(graphManagementModeLockReason('extraction-jobs', operations)).toBeNull()
  })

  it('coerces locked query modes back to initial schema design', () => {
    expect(resolveEffectiveGraphManagementMode('extraction-jobs', bootstrap)).toBe('initial-schema-design')
    expect(resolveEffectiveGraphManagementMode('extraction-jobs', operations)).toBe('extraction-jobs')
  })
})
