import { describe, expect, it } from 'vitest'
import {
  isPrimaryRelationshipTypeForDisplay,
  primaryRelationshipTypeCount,
  primaryRelationshipTypeLabels,
} from '../utils/kgDesignArtifacts'

describe('kgDesignArtifacts relationship type counting', () => {
  const edgeTypes = [
    { label: 'contains', bidirectional: true },
    { label: 'contained_in', auto_generated: true, inverse_of: 'contains' },
    { label: 'calls', bidirectional: false },
    { label: 'calls_inverse', auto_generated: true, inverse_of: 'calls' },
  ]

  it('excludes auto-generated inverse edge types from primary counts', () => {
    expect(primaryRelationshipTypeLabels(edgeTypes)).toEqual(['contains', 'calls'])
    expect(primaryRelationshipTypeCount(edgeTypes)).toBe(2)
  })

  it('treats unidirectional edges as primary display types', () => {
    expect(isPrimaryRelationshipTypeForDisplay({ label: 'depends_on' })).toBe(true)
  })

  it('treats inverse edge types as non-primary', () => {
    expect(
      isPrimaryRelationshipTypeForDisplay({
        label: 'contained_in',
        auto_generated: true,
        inverse_of: 'contains',
      }),
    ).toBe(false)
  })
})
