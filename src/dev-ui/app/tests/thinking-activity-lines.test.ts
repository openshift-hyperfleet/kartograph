import { describe, expect, it } from 'vitest'
import {
  applyThinkingRecentUpdate,
  normalizeThinkingActivityLines,
  THINKING_DISPLAY_LINE_COUNT,
} from '../utils/thinkingActivityLines'

describe('thinkingActivityLines', () => {
  it('pads to three display slots with newest thoughts at the bottom', () => {
    expect(normalizeThinkingActivityLines(['Alpha', 'Beta'])).toEqual(['', 'Alpha', 'Beta'])
  })

  it('keeps only the last three lines', () => {
    expect(
      normalizeThinkingActivityLines(['one', 'two', 'three', 'four']),
    ).toEqual(['two', 'three', 'four'])
  })

  it('replaces activity from authoritative recent payloads', () => {
    expect(
      applyThinkingRecentUpdate(['stale'], ['Reading schema', 'Running Grep…']),
    ).toEqual(['', 'Reading schema', 'Running Grep…'])
  })

  it('uses the shared three-line contract', () => {
    expect(THINKING_DISPLAY_LINE_COUNT).toBe(3)
  })
})
