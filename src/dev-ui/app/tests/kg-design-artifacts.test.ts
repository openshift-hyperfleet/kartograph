/** Tests for design artifact UI helpers. */

import { describe, expect, it } from 'vitest'
import {
  pageSlice,
  prepopulationBadgeClass,
  prepopulationLabel,
  prepopulationMode,
} from '../utils/kgDesignArtifacts'

describe('kgDesignArtifacts', () => {
  it('maps prepopulation flags to k-extract-style labels', () => {
    expect(prepopulationMode(true)).toBe('true')
    expect(prepopulationMode(false)).toBe('false')
    expect(prepopulationLabel(true)).toContain('prepopulated: true')
    expect(prepopulationBadgeClass(true)).toContain('cyan')
  })

  it('pages instance lists consistently', () => {
    const items = Array.from({ length: 25 }, (_, index) => index)
    const slice = pageSlice({}, 'service', items)
    expect(slice.items).toHaveLength(20)
    expect(slice.totalPages).toBe(2)
  })
})
