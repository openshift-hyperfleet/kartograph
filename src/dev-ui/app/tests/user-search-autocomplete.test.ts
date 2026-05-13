import { describe, it, expect } from 'vitest'

// ── User Search and Autocomplete ─────────────────────────────────
// Spec: "User Search and Autocomplete" from experience.spec.md

describe('UserSearchInput component', () => {
  it('component file exists', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/UserSearchInput.vue'), 'utf-8')
    expect(src).toContain('UserSearchInput')
  })

  it('uses searchUsers from useIamApi', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/UserSearchInput.vue'), 'utf-8')
    expect(src).toContain('searchUsers')
  })

  it('uses Command and Popover components for combobox pattern', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/UserSearchInput.vue'), 'utf-8')
    expect(src).toContain('Popover')
    expect(src).toContain('Command')
  })

  it('implements debounced search', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/UserSearchInput.vue'), 'utf-8')
    // Must have debounce logic (either useDebounceFn from @vueuse/core or setTimeout)
    expect(src).toMatch(/debounce|setTimeout/)
  })

  it('enforces minimum query length', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/UserSearchInput.vue'), 'utf-8')
    // Must check for minimum 2 characters
    expect(src).toMatch(/length\s*[<>=]+\s*2|\.length\s*<\s*2/)
  })

  it('shows no results message', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/UserSearchInput.vue'), 'utf-8')
    expect(src).toContain('No users found')
  })

  it('emits modelValue update when user is selected', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/UserSearchInput.vue'), 'utf-8')
    expect(src).toContain("update:modelValue")
  })
})

describe('Detail panels use UserSearchInput', () => {
  it('GroupDetailPanel uses UserSearchInput', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/GroupDetailPanel.vue'), 'utf-8')
    expect(src).toContain('UserSearchInput')
  })

  it('TenantDetailPanel uses UserSearchInput', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/TenantDetailPanel.vue'), 'utf-8')
    expect(src).toContain('UserSearchInput')
  })

  it('WorkspaceDetailPanel uses UserSearchInput for user member type', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/settings/WorkspaceDetailPanel.vue'), 'utf-8')
    expect(src).toContain('UserSearchInput')
  })
})
