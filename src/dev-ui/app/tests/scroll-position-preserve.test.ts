import { describe, expect, it } from 'vitest'
import { isScrollNearBottom } from '@/composables/useScrollPositionPreserve'

describe('isScrollNearBottom', () => {
  it('returns true when scrolled to the bottom within threshold', () => {
    const el = {
      scrollHeight: 1000,
      clientHeight: 200,
      scrollTop: 760,
    } as HTMLElement
    expect(isScrollNearBottom(el, 48)).toBe(true)
  })

  it('returns false when scrolled away from the bottom', () => {
    const el = {
      scrollHeight: 1000,
      clientHeight: 200,
      scrollTop: 100,
    } as HTMLElement
    expect(isScrollNearBottom(el, 48)).toBe(false)
  })
})
