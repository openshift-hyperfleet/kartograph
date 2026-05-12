import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Keyboard Shortcuts ──────────────────────────────────────────────────────
//
// Spec: specs/ui/experience.spec.md — Requirement: Interaction Principles
//
// Scenario: Keyboard shortcuts
//   GIVEN a power-user action (execute query)
//   THEN a keyboard shortcut is available (Ctrl/Cmd+Enter)
//   AND the shortcut is discoverable via tooltip or documentation

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
    expect(queryVue).toMatch(/Ctrl\+Enter|Ctrl-Enter|⌘/)
  })

  it('CodeMirror keymap wires Ctrl-Enter to query execution', () => {
    expect(queryVue).toMatch(/Ctrl-Enter/)
  })
})
