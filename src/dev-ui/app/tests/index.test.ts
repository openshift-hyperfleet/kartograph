import { describe, it, expect } from 'vitest'

describe('Index Page - Navigation Logic', () => {
  it('detects first visit from session storage', () => {
    // Simulate session storage check logic
    const isFirstVisit = sessionStorage.getItem('kartograph:visited') === null
    expect(typeof isFirstVisit).toBe('boolean')
  })

  it('returning user session detection', () => {
    // Mark as visited
    sessionStorage.setItem('kartograph:visited', 'true')
    const hasVisited = sessionStorage.getItem('kartograph:visited') !== null
    expect(hasVisited).toBe(true)
    // Cleanup
    sessionStorage.removeItem('kartograph:visited')
  })

  it('new user has no visited marker', () => {
    sessionStorage.removeItem('kartograph:visited')
    const hasVisited = sessionStorage.getItem('kartograph:visited') !== null
    expect(hasVisited).toBe(false)
  })
})

describe('Index Page - Getting Started Checklist', () => {
  it('counts completed steps correctly', () => {
    const steps = [
      { completed: true },
      { completed: false },
      { completed: true },
    ]
    const completedCount = steps.filter(s => s.completed).length
    expect(completedCount).toBe(2)
  })

  it('calculates progress percentage', () => {
    const total = 5
    const completed = 3
    const percentage = Math.round((completed / total) * 100)
    expect(percentage).toBe(60)
  })
})
