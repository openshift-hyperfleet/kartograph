import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// ── useCopyToClipboard Composable Tests ───────────────────────────────────────
//
// Spec: specs/ui/experience.spec.md — Requirement: Interaction Principles
// Scenario: Copy-to-clipboard
//   "GIVEN any identifier, configuration snippet, or secret
//    THEN a copy button is provided
//    AND a toast confirms the copy action"
//
// These tests verify the useCopyToClipboard composable that centralises all
// clipboard + toast logic in the UI. The composable must:
//   1. Call navigator.clipboard.writeText with the provided text.
//   2. Show a success toast (with optional label) on success.
//   3. Show an error toast on clipboard failure.
//   4. Expose a reactive `copied` boolean that resets after 2 s.
//   5. Return `true` on success, `false` on failure.
//
// Testing approach: vi.mock for vue-sonner (external I/O), Object.defineProperty
// for navigator.clipboard (browser API not available in happy-dom).

// ── Mock vue-sonner (external I/O dependency) ─────────────────────────────────
vi.mock('vue-sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeClipboard(impl: { writeText: ReturnType<typeof vi.fn> }) {
  Object.defineProperty(navigator, 'clipboard', {
    value: impl,
    configurable: true,
    writable: true,
  })
}

// ── Import under test ─────────────────────────────────────────────────────────
// We import AFTER mocking so vue-sonner is already swapped out.

import { useCopyToClipboard } from '~/composables/useCopyToClipboard'
import { toast } from 'vue-sonner'

// ── Suite ─────────────────────────────────────────────────────────────────────

describe('useCopyToClipboard — success path', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    makeClipboard({ writeText: vi.fn().mockResolvedValue(undefined) })
  })

  it('calls navigator.clipboard.writeText with the provided text', async () => {
    const { copyToClipboard } = useCopyToClipboard()
    await copyToClipboard('hello-world')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('hello-world')
  })

  it('returns true on success', async () => {
    const { copyToClipboard } = useCopyToClipboard()
    const result = await copyToClipboard('value')
    expect(result).toBe(true)
  })

  it('shows a generic success toast when no label is provided', async () => {
    const { copyToClipboard } = useCopyToClipboard()
    await copyToClipboard('some-id')
    expect(toast.success).toHaveBeenCalledWith('Copied to clipboard')
  })

  it('shows a labelled success toast when a label is provided', async () => {
    const { copyToClipboard } = useCopyToClipboard()
    await copyToClipboard('krtgph_abc123', 'API key secret')
    expect(toast.success).toHaveBeenCalledWith('API key secret copied')
  })

  it('sets the copied reactive flag to true after a successful copy', async () => {
    const { copyToClipboard, copied } = useCopyToClipboard()
    expect(copied.value).toBe(false)
    await copyToClipboard('ping')
    expect(copied.value).toBe(true)
  })
})

describe('useCopyToClipboard — failure path', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    makeClipboard({
      writeText: vi.fn().mockRejectedValue(new Error('Permission denied')),
    })
  })

  it('returns false when clipboard write fails', async () => {
    const { copyToClipboard } = useCopyToClipboard()
    const result = await copyToClipboard('secret')
    expect(result).toBe(false)
  })

  it('shows an error toast when clipboard write fails', async () => {
    const { copyToClipboard } = useCopyToClipboard()
    await copyToClipboard('secret')
    expect(toast.error).toHaveBeenCalledWith('Failed to copy to clipboard')
  })

  it('does NOT show a success toast when the write fails', async () => {
    const { copyToClipboard } = useCopyToClipboard()
    await copyToClipboard('secret')
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('leaves copied flag false when write fails', async () => {
    const { copyToClipboard, copied } = useCopyToClipboard()
    await copyToClipboard('secret')
    expect(copied.value).toBe(false)
  })
})

describe('useCopyToClipboard — source file usage', () => {
  // Source-level inspection verifying the composable is actually imported and
  // used in key pages (not just inlined one-off implementations).

  const { readFileSync } = require('fs')
  const { resolve } = require('path')

  it('api-keys/index.vue imports useCopyToClipboard from the composable', () => {
    const src = readFileSync(
      resolve(__dirname, '../pages/api-keys/index.vue'),
      'utf-8',
    )
    expect(src).toContain('useCopyToClipboard')
  })

  it('integrate/mcp.vue imports useCopyToClipboard from the composable', () => {
    const src = readFileSync(
      resolve(__dirname, '../pages/integrate/mcp.vue'),
      'utf-8',
    )
    expect(src).toContain('useCopyToClipboard')
  })

  it('api-keys/index.vue does not contain a local copyToClipboard function (uses composable instead)', () => {
    const src = readFileSync(
      resolve(__dirname, '../pages/api-keys/index.vue'),
      'utf-8',
    )
    // Should NOT have an inline async function copyToClipboard definition
    expect(src).not.toMatch(/^async function copyToClipboard/m)
  })

  it('integrate/mcp.vue does not contain a local copyToClipboard function (uses composable instead)', () => {
    const src = readFileSync(
      resolve(__dirname, '../pages/integrate/mcp.vue'),
      'utf-8',
    )
    expect(src).not.toMatch(/^async function copyToClipboard/m)
  })
})
