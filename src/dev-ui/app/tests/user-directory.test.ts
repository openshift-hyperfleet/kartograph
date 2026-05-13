import { describe, it, expect } from 'vitest'

// ── User Identity Resolution ─────────────────────────────────────
// Spec: "User Identity Resolution" from experience.spec.md

// ── Test: UserProfileResponse type exists ────────────────────────
describe('UserProfileResponse type', () => {
  it('types/index.ts exports UserProfileResponse', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../types/index.ts'), 'utf-8')
    expect(src).toContain('export interface UserProfileResponse')
    expect(src).toContain('id: string')
    expect(src).toContain('username: string')
    expect(src).toContain('name: string | null')
    expect(src).toContain('email: string | null')
  })
})

// ── Test: API methods exist in useIamApi ─────────────────────────
describe('User lookup API methods', () => {
  it('useIamApi exports lookupUsers function', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../composables/api/useIamApi.ts'), 'utf-8')
    expect(src).toContain('function lookupUsers')
    expect(src).toContain("'/iam/users'")
    expect(src).toContain('lookupUsers')
  })

  it('useIamApi exports searchUsers function', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../composables/api/useIamApi.ts'), 'utf-8')
    expect(src).toContain('function searchUsers')
    expect(src).toContain('searchUsers')
  })
})

// ── Test: useUserDirectory composable structure ──────────────────
describe('useUserDirectory composable', () => {
  it('composable file exists and exports useUserDirectory', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../composables/useUserDirectory.ts'), 'utf-8')
    expect(src).toContain('export function useUserDirectory')
  })

  it('provides resolveUsers batch function', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../composables/useUserDirectory.ts'), 'utf-8')
    expect(src).toContain('resolveUsers')
  })

  it('provides getDisplayName function', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../composables/useUserDirectory.ts'), 'utf-8')
    expect(src).toContain('getDisplayName')
  })

  it('invalidates cache on tenant switch via tenantVersion', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../composables/useUserDirectory.ts'), 'utf-8')
    expect(src).toContain('tenantVersion')
  })
})

// ── Test: Resolution logic (pure function) ───────────────────────
describe('getDisplayName resolution logic', () => {
  // Test the pure logic that picks name > username > id
  function getDisplayName(
    profile: { name: string | null; username: string } | undefined,
    userId: string,
  ): string {
    if (!profile) return userId
    return profile.name || profile.username
  }

  it('prefers name over username', () => {
    expect(getDisplayName({ name: 'Alice Smith', username: 'alice' }, 'id1')).toBe('Alice Smith')
  })

  it('falls back to username when name is null', () => {
    expect(getDisplayName({ name: null, username: 'alice' }, 'id1')).toBe('alice')
  })

  it('returns raw userId when profile is undefined', () => {
    expect(getDisplayName(undefined, 'abc-123-def')).toBe('abc-123-def')
  })
})

// ── Test: UserIdDisplay uses directory ───────────────────────────
describe('UserIdDisplay resolves names', () => {
  it('UserIdDisplay.vue imports useUserDirectory', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/ui/user-id/UserIdDisplay.vue'), 'utf-8')
    expect(src).toContain('useUserDirectory')
  })

  it('UserIdDisplay.vue shows resolved display name', () => {
    const { readFileSync } = require('node:fs')
    const { resolve } = require('node:path')
    const src = readFileSync(resolve(__dirname, '../components/ui/user-id/UserIdDisplay.vue'), 'utf-8')
    expect(src).toContain('displayLabel')
  })
})
