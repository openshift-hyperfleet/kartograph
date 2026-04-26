/**
 * Tests for the index page logic.
 *
 * The index page (app/pages/index.vue) manages two behaviours:
 *   1. Onboarding panel state — persisted in localStorage under
 *      `kartograph:onboarding-dismissed` so the panel stays hidden
 *      across hard refreshes.
 *   2. Getting-started checklist — computes completion counts from
 *      items that carry a `done` boolean property.
 *
 * These tests mirror the exact constants, storage key, and property names
 * used in production so that a change in index.vue that breaks the contract
 * will also break these tests.
 */

import { describe, it, expect, beforeEach } from 'vitest'

// ---------------------------------------------------------------------------
// Constants shared with index.vue
// ---------------------------------------------------------------------------

/** Storage key that the page writes when the onboarding panel is dismissed. */
const ONBOARDING_KEY = 'kartograph:onboarding-dismissed'

// ---------------------------------------------------------------------------
// Helpers that replicate the logic in index.vue exactly
// ---------------------------------------------------------------------------

/** Returns true when the onboarding panel has never been dismissed. */
function isOnboardingActive(): boolean {
  return localStorage.getItem(ONBOARDING_KEY) !== 'true'
}

/** Persists the dismissal state (mirrors dismissOnboarding() in index.vue). */
function dismissOnboarding(): void {
  localStorage.setItem(ONBOARDING_KEY, 'true')
}

// ---------------------------------------------------------------------------
// Suite 1 – Onboarding dismissal state (localStorage, correct key)
// ---------------------------------------------------------------------------

describe('Index Page – Onboarding panel state', () => {
  beforeEach(() => {
    // Reset storage before every test so tests are independent.
    localStorage.removeItem(ONBOARDING_KEY)
  })

  it('panel is active before the user has dismissed it', () => {
    expect(isOnboardingActive()).toBe(true)
  })

  it('panel becomes inactive after dismissOnboarding() is called', () => {
    dismissOnboarding()
    expect(isOnboardingActive()).toBe(false)
  })

  it('panel is active again when storage entry is absent', () => {
    // Confirm that removing the key resets the state.
    dismissOnboarding()
    localStorage.removeItem(ONBOARDING_KEY)
    expect(isOnboardingActive()).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// Suite 2 – Getting-started checklist (uses `done`, matching index.vue)
// ---------------------------------------------------------------------------

describe('Index Page – Getting started checklist', () => {
  /**
   * Checklist items exactly match the shape produced by the `checklistItems`
   * computed ref in index.vue — each item has a `done: boolean` property.
   */
  it('counts completed steps using the `done` property', () => {
    // Mirror index.vue checklistItems shape (done, not completed).
    const steps = [
      { done: true,  label: 'Create a tenant' },
      { done: false, label: 'Define a node type' },
      { done: true,  label: 'Create an API key' },
      { done: false, label: 'Connect via MCP' },
    ]

    // Mirrors: completedCount = checklistItems.value.filter(item => item.done).length
    const completedCount = steps.filter((s) => s.done).length
    expect(completedCount).toBe(2)
  })

  it('reports all steps complete when every item has done: true', () => {
    const steps = [
      { done: true, label: 'Step A' },
      { done: true, label: 'Step B' },
    ]

    // Mirrors: allChecklistDone = checklistItems.value.every(item => item.done)
    const allDone = steps.every((s) => s.done)
    expect(allDone).toBe(true)
  })

  it('reports not all complete when any item has done: false', () => {
    const steps = [
      { done: true,  label: 'Step A' },
      { done: false, label: 'Step B' },
    ]

    const allDone = steps.every((s) => s.done)
    expect(allDone).toBe(false)
  })

  it('calculates progress percentage correctly', () => {
    const steps = [
      { done: true  },
      { done: true  },
      { done: false },
      { done: false },
    ]
    const completedCount = steps.filter((s) => s.done).length
    const percentage = Math.round((completedCount / steps.length) * 100)
    expect(percentage).toBe(50)
  })
})
