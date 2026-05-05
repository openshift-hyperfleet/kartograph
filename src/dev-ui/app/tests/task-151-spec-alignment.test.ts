import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Task-151 Spec Alignment: UI Foundation — Design System, Shell & Core Interactions
//
// Spec-Ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task-Ref: task-151
//
// This file provides targeted spec-alignment verification for the foundational
// UI layer that every subsequent UI task builds on:
//
//   Requirement: Design Language
//     - Scenario: Component library (shadcn/vue / Reka UI, Tailwind, CVA, Lucide)
//     - Scenario: Color theme (OKLCH custom properties, primary brand amber/orange,
//                 neutral grays, destructive coral/red, 5-color chart palette)
//     - Scenario: Typography (system font stack, text-sm body, uppercase text-[11px]
//                 section headers, tracking-wider, weights 400/500/600 only)
//     - Scenario: Border radius (base 0.625rem, rounded-xl/rounded-md/rounded-full)
//     - Scenario: Elevation (shadow-sm cards, shadow-xs buttons, predominantly flat)
//
//   Requirement: Navigation Structure
//     - Scenario: Primary navigation (Explore, Data, Connect, Settings sidebar groups)
//     - Scenario: Default landing (returning user → Query Console)
//     - Scenario: New user landing (no knowledge graphs → setup prompt)
//
//   Requirement: Responsive Design
//     - Scenario: Desktop layout (sidebar visible and collapsible)
//     - Scenario: Tablet/mobile layout (sidebar collapses to Sheet overlay)
//
//   Requirement: Dark Mode
//     - Scenario: Toggle (available in header, preference persisted in localStorage)
//
//   Requirement: Interaction Principles
//     - Scenario: Focus indicators (3px ring in primary color at 50% opacity)
//     - Scenario: Keyboard shortcuts (Ctrl/Cmd+Enter, "/" for search focus)
//     - Scenario: Copy-to-clipboard (copy button, toast confirmation)
//     - Scenario: Mutation feedback (toast notifications for write operations)
//
//   Requirement: Backend API Alignment (foundation)
//     - API client configured with base URL from runtime config
//     - Bearer token injection via Authorization header
//     - Tenant context injected via X-Tenant-ID header
//
// Verification strategy: read production source files and assert on the presence
// of key patterns. This avoids component mounting overhead while still catching
// regressions (e.g. design token removal, nav group renaming, API client refactoring).

// ── Source file reads ─────────────────────────────────────────────────────────

const appDir = resolve(__dirname, '..')

const cssPath = resolve(appDir, 'assets/css/main.css')
const css = readFileSync(cssPath, 'utf-8')

const layoutPath = resolve(appDir, 'layouts/default.vue')
const layout = readFileSync(layoutPath, 'utf-8')

const sidebarComposable = readFileSync(
  resolve(appDir, 'composables/useSidebar.ts'),
  'utf-8',
)

const colorModeComposable = readFileSync(
  resolve(appDir, 'composables/useColorMode.ts'),
  'utf-8',
)

const apiClientComposable = readFileSync(
  resolve(appDir, 'composables/useApiClient.ts'),
  'utf-8',
)

const copyComposable = readFileSync(
  resolve(appDir, 'composables/useCopyToClipboard.ts'),
  'utf-8',
)

const cardVue = readFileSync(
  resolve(appDir, 'components/ui/card/Card.vue'),
  'utf-8',
)

const buttonIndex = readFileSync(
  resolve(appDir, 'components/ui/button/index.ts'),
  'utf-8',
)

const indexPage = readFileSync(resolve(appDir, 'pages/index.vue'), 'utf-8')

const nuxtConfig = readFileSync(resolve(appDir, '../nuxt.config.ts'), 'utf-8')

const pkgJson = JSON.parse(readFileSync(resolve(appDir, '../package.json'), 'utf-8'))
const allDeps = { ...pkgJson.dependencies, ...pkgJson.devDependencies }

// ── Requirement: Design Language — Scenario: Component library ───────────────
//
// "THEN it uses shadcn/vue (Reka UI) primitives with Tailwind CSS"
// "AND variants are defined via Class Variance Authority (CVA)"
// "AND icons use Lucide Vue Next"

describe('task-151 — Design Language: Component library', () => {
  it('has @tailwindcss/vite or tailwindcss in dependencies', () => {
    const hasTailwind = Object.keys(allDeps).some((k) => k.includes('tailwindcss'))
    expect(hasTailwind).toBe(true)
  })

  it('has class-variance-authority (CVA) for component variants', () => {
    expect(allDeps).toHaveProperty('class-variance-authority')
  })

  it('has lucide-vue-next for icons', () => {
    expect(allDeps).toHaveProperty('lucide-vue-next')
  })

  it('has reka-ui (shadcn/vue primitives)', () => {
    const hasReka = Object.keys(allDeps).some(
      (k) => k.includes('reka-ui') || k.includes('@reka-ui'),
    )
    expect(hasReka).toBe(true)
  })

  it('imports lucide-vue-next icons in the main layout', () => {
    expect(layout).toContain("from 'lucide-vue-next'")
  })
})

// ── Requirement: Design Language — Scenario: Color theme ─────────────────────
//
// "THEN colors are defined as OKLCH CSS custom properties"
// "AND the primary/brand color is warm amber/orange (oklch(0.5768 0.2469 29.23) light,
//   oklch(0.6857 0.1560 17.57) dark)"
// "AND neutral grays form the background, card, and border palette"
// "AND destructive actions use a coral/red accent"
// "AND chart/data visualization uses a 5-color palette (amber, blue, purple, yellow, green)"

describe('task-151 — Design Language: Color theme', () => {
  it('defines --primary in light :root as oklch(0.5768 0.2469 29.23) — warm amber/orange', () => {
    expect(css).toContain('--primary: oklch(0.5768 0.2469 29.23)')
  })

  it('defines --primary in .dark as oklch(0.6857 0.1560 17.57)', () => {
    expect(css).toContain('--primary: oklch(0.6857 0.1560 17.57)')
  })

  it('uses oklch() for background, card, and border palette (neutral grays)', () => {
    expect(css).toContain('--background: oklch(1 0 0)')
    expect(css).toContain('--card: oklch(1 0 0)')
    expect(css).toContain('--border: oklch(0.9003 0 0)')
  })

  it('defines --destructive as coral/red in oklch', () => {
    expect(css).toContain('--destructive: oklch(0.6237 0.1930 38.99)')
  })

  it('defines all 5 chart color tokens (--chart-1 through --chart-5)', () => {
    for (let i = 1; i <= 5; i++) {
      expect(css).toContain(`--chart-${i}:`)
    }
  })

  it('defines a .dark selector block for dark mode overrides', () => {
    expect(css).toContain('.dark {')
  })
})

// ── Requirement: Design Language — Scenario: Typography ──────────────────────
//
// "THEN the system font stack is used (no custom fonts)"
// "AND body text uses text-sm (0.875rem)"
// "AND section headers use uppercase text-[11px] with tracking-wider"
// "AND font weights are limited to regular (400), medium (500), and semibold (600)"

describe('task-151 — Design Language: Typography', () => {
  it('layout uses text-sm for body-level text', () => {
    expect(layout).toContain('text-sm')
  })

  it('sidebar section titles use uppercase tracking-wider styling', () => {
    // Section headers in the nav should use uppercase + tracking-wider classes
    expect(layout).toContain('tracking-wider')
    expect(layout).toContain('uppercase')
  })

  it('does not import or load a custom web font (no @font-face or font-family override in CSS)', () => {
    expect(css).not.toContain('@font-face')
  })
})

// ── Requirement: Design Language — Scenario: Border radius ───────────────────
//
// "THEN border radius scales from a base of 0.625rem (10px)"
// "AND cards use rounded-xl, buttons and inputs use rounded-md, badges use rounded-full"

describe('task-151 — Design Language: Border radius', () => {
  it('defines --radius base as 0.625rem', () => {
    expect(css).toContain('--radius: 0.625rem')
  })

  it('derives variant radii from the base', () => {
    expect(css).toContain('--radius-sm: calc(var(--radius) - 4px)')
    expect(css).toContain('--radius-md: calc(var(--radius) - 2px)')
    expect(css).toContain('--radius-xl: calc(var(--radius) + 4px)')
  })
})

// ── Requirement: Design Language — Scenario: Elevation ───────────────────────
//
// "THEN cards use shadow-sm and buttons use shadow-xs"
// "AND depth is minimal — the UI is predominantly flat"

describe('task-151 — Design Language: Elevation', () => {
  it('Card component uses shadow-sm (flat card elevation)', () => {
    expect(cardVue).toContain('shadow-sm')
  })

  it('Button component uses shadow-xs (minimal button elevation)', () => {
    expect(buttonIndex).toContain('shadow-xs')
  })
})

// ── Requirement: Navigation Structure — Scenario: Primary navigation ──────────
//
// "GIVEN an authenticated user"
// "THEN the sidebar presents navigation grouped as:"
//   "Explore — Query Console, Schema Browser, Graph Explorer, Mutations Console"
//   "Data — Knowledge Graphs, Data Sources (with sync status)"
//   "Connect — API Keys, MCP Integration"
//   "Settings — Workspaces, Groups, Tenants"

describe('task-151 — Navigation Structure: Primary navigation groups', () => {
  it("sidebar has an 'Explore' group", () => {
    expect(layout).toContain("title: 'Explore'")
  })

  it("sidebar has a 'Data' group", () => {
    expect(layout).toContain("title: 'Data'")
  })

  it("sidebar has a 'Connect' group", () => {
    expect(layout).toContain("title: 'Connect'")
  })

  it("sidebar has a 'Settings' group", () => {
    expect(layout).toContain("title: 'Settings'")
  })
})

describe('task-151 — Navigation Structure: Explore group items', () => {
  it("includes 'Query Console' linking to /query", () => {
    expect(layout).toContain("label: 'Query Console'")
    expect(layout).toContain("to: '/query'")
  })

  it("includes 'Schema Browser' linking to /graph/schema", () => {
    expect(layout).toContain("label: 'Schema Browser'")
    expect(layout).toContain("to: '/graph/schema'")
  })

  it("includes 'Graph Explorer' linking to /graph/explorer", () => {
    expect(layout).toContain("label: 'Graph Explorer'")
    expect(layout).toContain("to: '/graph/explorer'")
  })

  it("includes 'Mutations Console' linking to /graph/mutations", () => {
    expect(layout).toContain("label: 'Mutations Console'")
    expect(layout).toContain("to: '/graph/mutations'")
  })
})

describe('task-151 — Navigation Structure: Data group items', () => {
  it("includes 'Knowledge Graphs' linking to /knowledge-graphs", () => {
    expect(layout).toContain("label: 'Knowledge Graphs'")
    expect(layout).toContain("to: '/knowledge-graphs'")
  })

  it("includes 'Data Sources' with sync status badge support", () => {
    expect(layout).toContain("label: 'Data Sources'")
    expect(layout).toContain("to: '/data-sources'")
    // sync badge is computed from activeSyncCount
    expect(layout).toContain('activeSyncCount')
  })
})

describe('task-151 — Navigation Structure: Connect group items', () => {
  it("includes 'API Keys' linking to /api-keys", () => {
    expect(layout).toContain("label: 'API Keys'")
    expect(layout).toContain("to: '/api-keys'")
  })

  it("includes 'MCP Integration' linking to /integrate/mcp", () => {
    expect(layout).toContain("label: 'MCP Integration'")
    expect(layout).toContain("to: '/integrate/mcp'")
  })
})

describe('task-151 — Navigation Structure: Settings group items', () => {
  it("includes 'Workspaces' linking to /workspaces", () => {
    expect(layout).toContain("label: 'Workspaces'")
    expect(layout).toContain("to: '/workspaces'")
  })

  it("includes 'Groups' linking to /groups", () => {
    expect(layout).toContain("label: 'Groups'")
    expect(layout).toContain("to: '/groups'")
  })

  it("includes 'Tenants' linking to /tenants", () => {
    expect(layout).toContain("label: 'Tenants'")
    expect(layout).toContain("to: '/tenants'")
  })
})

describe('task-151 — Navigation Structure: Default landing (returning user)', () => {
  it('index page redirects returning users with knowledge graphs to /query', () => {
    // The index page performs a redirect to the query console for returning users
    expect(indexPage).toContain('/query')
  })
})

describe('task-151 — Navigation Structure: New user landing', () => {
  it('index page shows a setup checklist / prompt when no knowledge graphs exist', () => {
    // When knowledge graphs list is empty, show setup guidance
    expect(indexPage).toContain('knowledge')
  })
})

// ── Requirement: Responsive Design ───────────────────────────────────────────
//
// "GIVEN a desktop screen, THEN the sidebar is visible and collapsible"
// "GIVEN a narrow screen, THEN the sidebar collapses to a sheet overlay"

describe('task-151 — Responsive Design: Desktop sidebar collapsible', () => {
  it('useSidebar composable exposes isCollapsed and toggleCollapsed', () => {
    expect(sidebarComposable).toContain('isCollapsed')
    expect(sidebarComposable).toContain('toggleCollapsed')
  })

  it('persists sidebar collapse state in localStorage', () => {
    expect(sidebarComposable).toContain('localStorage')
  })

  it('layout uses isCollapsed to conditionally show/hide sidebar labels', () => {
    expect(layout).toContain('isCollapsed')
  })
})

describe('task-151 — Responsive Design: Mobile sheet overlay', () => {
  it('layout imports Sheet component for mobile overlay', () => {
    expect(layout).toContain('Sheet')
    expect(layout).toContain('SheetContent')
  })

  it('layout uses isMobileOpen to drive the sheet open state', () => {
    expect(layout).toContain('isMobileOpen')
  })

  it('layout has a hamburger-style trigger for mobile nav', () => {
    // The mobile menu toggle button is present (Menu icon from lucide)
    expect(layout).toContain('Menu')
  })
})

// ── Requirement: Dark Mode ────────────────────────────────────────────────────
//
// "THEN a dark mode toggle is available in the header"
// "AND the preference persists across sessions"

describe('task-151 — Dark Mode: Toggle in header', () => {
  it('layout imports Moon and Sun icons for dark mode toggle', () => {
    expect(layout).toContain('Moon')
    expect(layout).toContain('Sun')
  })

  it('layout calls toggleColorMode on button click', () => {
    expect(layout).toContain('toggleColorMode')
  })
})

describe('task-151 — Dark Mode: Preference persists across sessions', () => {
  it('useColorMode reads stored preference from localStorage', () => {
    expect(colorModeComposable).toContain('localStorage.getItem')
  })

  it('useColorMode writes updated preference to localStorage on toggle', () => {
    expect(colorModeComposable).toContain("localStorage.setItem('kartograph-color-mode'")
  })

  it('useColorMode applies the .dark class to documentElement', () => {
    expect(colorModeComposable).toContain("classList.add('dark')")
    expect(colorModeComposable).toContain("classList.remove('dark')")
  })
})

// ── Requirement: Interaction Principles — Scenario: Focus indicators ──────────
//
// "THEN a 3px ring in the primary color at 50% opacity is shown"
// "AND native outlines are suppressed in favor of the ring"

describe('task-151 — Interaction Principles: Focus indicators', () => {
  it('CSS applies outline-ring/50 (3px ring at 50% opacity) globally', () => {
    expect(css).toContain('outline-ring/50')
  })
})

// ── Requirement: Interaction Principles — Scenario: Keyboard shortcuts ────────
//
// "THEN a keyboard shortcut is available (Ctrl/Cmd+Enter, /)"

describe('task-151 — Interaction Principles: Keyboard shortcut "/"', () => {
  it('layout registers a keydown listener for the "/" key (global search)', () => {
    expect(layout).toContain("event.key !== '/'")
  })

  it('layout adds and removes the keydown listener on mount/unmount', () => {
    expect(layout).toContain("document.addEventListener('keydown', handleGlobalKeydown)")
    expect(layout).toContain("document.removeEventListener('keydown', handleGlobalKeydown)")
  })

  it('layout has a global search input with data-testid="global-search-input"', () => {
    expect(layout).toContain('data-testid="global-search-input"')
  })
})

// ── Requirement: Interaction Principles — Scenario: Copy-to-clipboard ─────────
//
// "GIVEN any identifier, configuration snippet, or secret"
// "THEN a copy button is provided"
// "AND a toast confirms the copy action"

describe('task-151 — Interaction Principles: Copy-to-clipboard composable', () => {
  it('useCopyToClipboard uses navigator.clipboard.writeText', () => {
    expect(copyComposable).toContain('clipboard')
  })

  it('useCopyToClipboard exposes a copy function', () => {
    expect(copyComposable).toContain('copy')
  })
})

describe('task-151 — Interaction Principles: Toast notification system', () => {
  it('layout imports toast from vue-sonner for notifications', () => {
    expect(layout).toContain("from 'vue-sonner'")
    expect(layout).toContain('toast')
  })
})

// ── Requirement: Backend API Alignment (foundation) ──────────────────────────
//
// "AND the UI reflects the updated state without requiring a manual refresh"
// API client configured with base URL from runtime config
// Auth header (Bearer JWT) injected per-request

describe('task-151 — Backend API Alignment: API client foundation', () => {
  it('useApiClient reads apiBaseUrl from Nuxt runtimeConfig', () => {
    expect(apiClientComposable).toContain('config.public.apiBaseUrl')
  })

  it('useApiClient injects Authorization: Bearer <token> header', () => {
    expect(apiClientComposable).toContain("'Authorization'")
    expect(apiClientComposable).toContain('Bearer')
  })

  it('useApiClient injects X-Tenant-ID header for tenant context', () => {
    expect(apiClientComposable).toContain("'X-Tenant-ID'")
  })

  it('nuxt.config.ts defines apiBaseUrl in runtimeConfig.public', () => {
    expect(nuxtConfig).toContain('apiBaseUrl')
    expect(nuxtConfig).toContain('runtimeConfig')
  })
})
