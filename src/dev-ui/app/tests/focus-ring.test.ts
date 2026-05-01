import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Focus Ring Consistency Tests ──────────────────────────────────────────────
//
// Spec: "Interaction Principles — Scenario: Focus indicators"
// "GIVEN an interactive element receiving focus
//  THEN a 3px ring in the primary color at 50% opacity is shown
//  AND native outlines are suppressed in favor of the ring"
//
// The shadcn/vue component library uses `focus-visible:ring-[3px]` consistently.
// Several manually-written interactive elements were using `focus-visible:ring-2`
// (Tailwind's preset 8px unit) instead of the spec-required 3px literal.
//
// These tests enforce that all manually-written interactive elements in:
//   - app/layouts/default.vue (tenant selector buttons)
//   - app/pages/integrate/mcp.vue (collapsible section buttons)
//   - app/pages/tenants/index.vue (tenant list items)
// ... use `focus-visible:ring-[3px]` (3px) and NOT `focus-visible:ring-2` (8px).
//
// Testing approach: Source-level inspection via readFileSync, matching the
// pattern used by design-system.test.ts. Mounting the full Nuxt layout in a
// unit test is impractical; source inspection is equivalent and more targeted.

// ── Read source files ─────────────────────────────────────────────────────────

const layoutsDir = resolve(__dirname, '../layouts')
const pagesDir = resolve(__dirname, '../pages')

const defaultVue = readFileSync(resolve(layoutsDir, 'default.vue'), 'utf-8')
const mcpVue = readFileSync(resolve(pagesDir, 'integrate/mcp.vue'), 'utf-8')
const tenantsVue = readFileSync(resolve(pagesDir, 'tenants/index.vue'), 'utf-8')

// ── default.vue — Tenant selector buttons ─────────────────────────────────────

describe('Focus Rings - default.vue: tenant selector buttons', () => {
  it('does NOT use focus-visible:ring-2 anywhere in default.vue', () => {
    // ring-2 is a Tailwind preset unit (8px), not the spec-required 3px
    expect(defaultVue).not.toContain('focus-visible:ring-2')
  })

  it('uses focus-visible:ring-[3px] on the collapsed tenant icon button', () => {
    // Line ~394: collapsed sidebar tenant trigger (icon-only)
    // Must have ring-[3px] rather than ring-2
    expect(defaultVue).toContain('focus-visible:ring-[3px]')
  })

  it('has ring-sidebar-ring/50 opacity on all sidebar focus rings in default.vue', () => {
    // Every focus-visible:ring-sidebar-ring must include the /50 opacity modifier
    // so the ring renders at 50% opacity as required by the spec
    const withoutOpacity = [...defaultVue.matchAll(/focus-visible:ring-sidebar-ring(?!\/)/g)]
    expect(withoutOpacity).toHaveLength(0)
  })

  it('retains outline-none on tenant selector buttons to suppress native outlines', () => {
    // outline-none suppresses the browser default focus outline in favour of the ring
    expect(defaultVue).toContain('focus-visible:outline-none')
  })
})

// ── mcp.vue — Collapsible section buttons ─────────────────────────────────────

describe('Focus Rings - mcp.vue: collapsible section buttons', () => {
  it('does NOT use focus-visible:ring-2 anywhere in mcp.vue', () => {
    expect(mcpVue).not.toContain('focus-visible:ring-2')
  })

  it('uses focus-visible:ring-[3px] on the Endpoint Details collapsible button', () => {
    // Line ~605: "Endpoint Details" section toggle button
    expect(mcpVue).toContain('focus-visible:ring-[3px]')
  })

  it('has ring-ring/50 opacity on all focus ring colors in mcp.vue', () => {
    // focus-visible:ring-ring must always be focus-visible:ring-ring/50
    // A bare `focus-visible:ring-ring` without the opacity modifier violates the spec
    const bareRing = [...mcpVue.matchAll(/focus-visible:ring-ring(?!\/)/g)]
    expect(bareRing).toHaveLength(0)
  })

  it('retains outline-none on collapsible buttons to suppress native outlines', () => {
    expect(mcpVue).toContain('focus-visible:outline-none')
  })
})

// ── tenants/index.vue — Tenant list items ─────────────────────────────────────

describe('Focus Rings - tenants/index.vue: tenant list items', () => {
  it('does NOT use focus-visible:ring-2 anywhere in tenants/index.vue', () => {
    expect(tenantsVue).not.toContain('focus-visible:ring-2')
  })

  it('uses focus-visible:ring-[3px] on the tenant list item divs', () => {
    // Line ~333: keyboard-focusable tenant row divs (role="listitem", tabindex="0")
    expect(tenantsVue).toContain('focus-visible:ring-[3px]')
  })

  it('has ring-ring/50 opacity on all focus ring colors in tenants/index.vue', () => {
    // focus-visible:ring-ring must always be focus-visible:ring-ring/50
    const bareRing = [...tenantsVue.matchAll(/focus-visible:ring-ring(?!\/)/g)]
    expect(bareRing).toHaveLength(0)
  })

  it('retains outline-none on tenant list items to suppress native outlines', () => {
    expect(tenantsVue).toContain('focus-visible:outline-none')
  })
})

// ── Cross-file regression guard ───────────────────────────────────────────────

describe('Focus Rings - global: no new ring-2 regressions', () => {
  it('default.vue uses ring-[3px] for all manual interactive elements (no ring-2)', () => {
    const ring2Count = (defaultVue.match(/focus-visible:ring-2/g) ?? []).length
    expect(ring2Count).toBe(0)
  })

  it('mcp.vue uses ring-[3px] for all manual interactive elements (no ring-2)', () => {
    const ring2Count = (mcpVue.match(/focus-visible:ring-2/g) ?? []).length
    expect(ring2Count).toBe(0)
  })

  it('tenants/index.vue uses ring-[3px] for all manual interactive elements (no ring-2)', () => {
    const ring2Count = (tenantsVue.match(/focus-visible:ring-2/g) ?? []).length
    expect(ring2Count).toBe(0)
  })
})
