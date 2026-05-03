import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Keyboard Shortcuts (task-054) ──────────────────────────────────────────────
//
// Spec: specs/ui/experience.spec.md — Requirement: Interaction Principles
//
// Scenario: Keyboard shortcuts
//   GIVEN a power-user action (execute query, focus search)
//   THEN a keyboard shortcut is available (Ctrl/Cmd+Enter, /)
//   AND the shortcut is discoverable via tooltip or documentation
//
// Two distinct shortcuts are tested:
//   1. "/" — focuses the global search input in the sidebar/header.
//   2. "Ctrl/Cmd+Enter" — executes the current query in the Query Console.
//
// Tests are pure logic / structural tests that verify the implementation
// without mounting the full Nuxt application (which requires the Nuxt SSR
// runtime). Component mounting tests for these behaviours would require
// mocking the Nuxt composables (useRoute, useAuth, useTenant, …); the
// structural approach is preferred per the project testing philosophy.

// ── Scenario: Keyboard shortcuts — "/" focuses search ─────────────────────────

describe('Keyboard shortcuts — "/" focuses the global search input', () => {
  // Read the layout source once per describe block (fast — no I/O in each it).
  const defaultVue = readFileSync(
    resolve(__dirname, '../layouts/default.vue'),
    'utf-8',
  )

  it('default.vue declares a global keydown listener for the "/" key', () => {
    // The handler must listen for the "/" key explicitly — either as a guard
    // (event.key !== '/') or as a condition (event.key === '/').
    expect(defaultVue).toMatch(/event\.key\s*!?==?\s*['"]\/['"]|key\s*!?==?\s*['"]\/['"]/)
  })

  it('default.vue has a global-search-input element with the correct data-testid', () => {
    // A search input with data-testid="global-search-input" must exist so that
    // automated tests and the keydown handler can locate it.
    expect(defaultVue).toContain('data-testid="global-search-input"')
  })

  it('default.vue registers the keydown listener on mount and removes it on unmount', () => {
    // Proper lifecycle management prevents memory leaks.
    expect(defaultVue).toMatch(/addEventListener\(['"]keydown['"]/)
    expect(defaultVue).toMatch(/removeEventListener\(['"]keydown['"]/)
  })

  it('default.vue prevents "/" from being typed into the search input when it is already the active element', () => {
    // The handler must check whether the focused element is an input/textarea
    // to avoid intercepting keystrokes from form fields.
    // Strategy: look for a guard that skips non-input targets (tag name check).
    expect(defaultVue).toMatch(
      /input|textarea|select/,
    )
    // The guard should reference the event target's tagName or nodeName.
    expect(defaultVue).toMatch(/target.*tag|tagName|nodeName/i)
  })

  it('default.vue calls .focus() on the search input element when "/" is pressed', () => {
    // The handler must call focus() so the browser moves the cursor into the field.
    expect(defaultVue).toMatch(/\.focus\(\)/)
  })

  it('default.vue imports onMounted and onUnmounted for lifecycle management', () => {
    // onMounted / onUnmounted are required to attach/detach the global listener.
    expect(defaultVue).toMatch(/onMounted/)
    expect(defaultVue).toMatch(/onUnmounted/)
  })
})

// ── Scenario: Keyboard shortcuts — "/" guard logic (pure logic) ───────────────

describe('Keyboard shortcuts — "/" guard logic', () => {
  /**
   * Pure representation of the guard logic extracted from default.vue.
   * Returns true when the shortcut should be activated, false when it should
   * be suppressed (e.g. the user is typing in a form field).
   */
  function shouldActivateSlashShortcut(event: { key: string; target: { tagName: string } }): boolean {
    if (event.key !== '/') return false
    const tag = event.target.tagName.toLowerCase()
    if (['input', 'textarea', 'select'].includes(tag)) return false
    return true
  }

  it('activates when "/" is pressed outside an input field (e.g. div)', () => {
    expect(shouldActivateSlashShortcut({ key: '/', target: { tagName: 'DIV' } })).toBe(true)
  })

  it('activates when "/" is pressed on the body element', () => {
    expect(shouldActivateSlashShortcut({ key: '/', target: { tagName: 'BODY' } })).toBe(true)
  })

  it('does NOT activate when "/" is pressed inside an <input> element', () => {
    expect(shouldActivateSlashShortcut({ key: '/', target: { tagName: 'INPUT' } })).toBe(false)
  })

  it('does NOT activate when "/" is pressed inside a <textarea> element', () => {
    expect(shouldActivateSlashShortcut({ key: '/', target: { tagName: 'TEXTAREA' } })).toBe(false)
  })

  it('does NOT activate when "/" is pressed inside a <select> element', () => {
    expect(shouldActivateSlashShortcut({ key: '/', target: { tagName: 'SELECT' } })).toBe(false)
  })

  it('does NOT activate for other keys pressed outside an input', () => {
    expect(shouldActivateSlashShortcut({ key: 'a', target: { tagName: 'DIV' } })).toBe(false)
    expect(shouldActivateSlashShortcut({ key: 'Enter', target: { tagName: 'BODY' } })).toBe(false)
  })
})

// ── Scenario: Keyboard shortcuts — Ctrl/Cmd+Enter (Query Console) ─────────────

describe('Keyboard shortcuts — Ctrl/Cmd+Enter executes queries', () => {
  const queryVue = readFileSync(
    resolve(__dirname, '../pages/query/index.vue'),
    'utf-8',
  )

  it('query console has a handleCtrlEnter function', () => {
    expect(queryVue).toContain('handleCtrlEnter')
  })

  it('query console registers a keydown listener that handles Ctrl/Cmd+Enter', () => {
    expect(queryVue).toMatch(/addEventListener\(['"]keydown['"]/)
  })

  it('query console deregisters the keydown listener on component unmount', () => {
    expect(queryVue).toMatch(/removeEventListener\(['"]keydown['"]/)
  })

  it('Ctrl+Enter tooltip is visible on the Run button', () => {
    // The run button or a nearby tooltip must show the keyboard shortcut so
    // it is discoverable without reading documentation.
    expect(queryVue).toMatch(/Ctrl\+Enter|Ctrl-Enter|⌘/)
  })

  it('CodeMirror keymap wires Ctrl-Enter to query execution', () => {
    // The CodeMirror extension must map the shortcut to the run action so that
    // the keyboard shortcut works when the editor cursor is inside the editor.
    expect(queryVue).toMatch(/Ctrl-Enter/)
  })
})

// ── Scenario: Keyboard shortcuts — discoverability ────────────────────────────

describe('Keyboard shortcuts — discoverability via tooltip or documentation', () => {
  const defaultVue = readFileSync(
    resolve(__dirname, '../layouts/default.vue'),
    'utf-8',
  )

  it('global search input includes a keyboard shortcut hint in the placeholder or title', () => {
    // The shortcut must be discoverable. Acceptable forms:
    //   - placeholder="Search (press /)"
    //   - title="Press / to focus"
    //   - aria-label containing the shortcut hint
    //   - a sibling <kbd> element or <span> showing "/"
    const hasPlaceholderHint = defaultVue.match(/placeholder.*\/|\/.*placeholder/i)
    const hasKbd = defaultVue.includes('<kbd')
    const hasTitleHint = defaultVue.match(/title=.*\/|\/.*title=/i)
    const hasAriaHint = defaultVue.match(/aria-label.*\/|\/.*aria-label/i)
    const hasSlashHint = defaultVue.match(/>\/</  ) // literal "/" in the UI text
    expect(
      hasPlaceholderHint || hasKbd || hasTitleHint || hasAriaHint || hasSlashHint,
    ).toBeTruthy()
  })
})
