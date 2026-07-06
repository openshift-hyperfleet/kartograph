import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Graph Management — extraction session load must wait for tenant ────────
//
// Bug: on a hard refresh of
// /knowledge-graphs/{kgId}/manage?step=graph-management, the page's
// `watch([activeStep, route.query.gm_mode], ..., { immediate: true })`
// fires `loadExtractionSession()` synchronously on mount — before the
// default layout's async `fetchTenants()` has resolved and populated
// `currentTenantId` (a hard refresh resets all Nuxt `useState`, unlike a
// client-side navigation where tenant state is already warm). Every other
// data loader on this page (`loadKgIdentity`, `loadWorkspaceStatus`,
// `loadOverviewMetrics`, `loadArchivedWriteCount`,
// `loadGraphManagementDataSources`, `refreshDesignArtifacts`) guards on
// `hasTenant.value`, but `loadExtractionSession` was missing that guard, so
// it fired an authenticated request with no X-Tenant-ID header, which the
// API correctly rejects with 400 "X-Tenant-ID header is required" — surfaced
// to the user as the generic toast "Failed to load extraction conversation".
//
// This is a source-reading (structural constraint) test — no DOM mounting
// or network calls — matching the convention used by
// knowledge-graph-manage-workspace.test.ts / mutations-kg-loading.test.ts
// for this page.

const manageVuePath = resolve(__dirname, '../pages/knowledge-graphs/[kgId]/manage.vue')
const manageVue = readFileSync(manageVuePath, 'utf-8')

function extractFunctionBody(source: string, signature: string): string {
  const start = source.indexOf(signature)
  expect(start).toBeGreaterThan(-1)
  // Grab a generous window after the signature — enough to cover the guard
  // line without needing a full brace-matching parser.
  return source.slice(start, start + 400)
}

describe('Graph Management — loadExtractionSession waits for tenant context', () => {
  it('guards on hasTenant.value, like every other loader on this page', () => {
    const body = extractFunctionBody(manageVue, 'async function loadExtractionSession()')
    expect(body).toContain('!hasTenant.value')
  })

  it('still guards on kgId and the active step (existing behavior preserved)', () => {
    const body = extractFunctionBody(manageVue, 'async function loadExtractionSession()')
    expect(body).toContain('!kgId.value')
    expect(body).toContain("activeStep.value !== 'graph-management'")
  })

  it('the hasTenant guard is a short-circuit return, not a separate branch', () => {
    // Must be part of the same early-return `if (...) return` as the other
    // guards — a separate `if (!hasTenant.value) { ... }` block later in the
    // function would still let the fetch race ahead in some code paths.
    const body = extractFunctionBody(manageVue, 'async function loadExtractionSession()')
    const guardLine = body.split('\n')[1]
    expect(guardLine).toContain('if (')
    expect(guardLine).toContain('return')
    expect(guardLine).toContain('!hasTenant.value')
    expect(guardLine).toContain('!kgId.value')
  })
})

describe('Graph Management — hasTenant guard convention (regression baseline)', () => {
  // Documents the existing convention this fix now matches, so a future
  // refactor that drops the guard from other loaders also gets caught.
  it.each([
    'async function refreshDesignArtifacts(',
    'async function loadKgIdentity()',
    'async function loadOverviewMetrics()',
    'async function loadGraphManagementDataSources()',
    'async function loadWorkspaceStatus()',
    'async function loadArchivedWriteCount()',
  ])('%s guards on hasTenant.value', (signature) => {
    const body = extractFunctionBody(manageVue, signature)
    expect(body).toContain('!hasTenant.value')
  })
})
