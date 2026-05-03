import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync, readdirSync } from 'fs'
import { resolve } from 'path'

// ── Task-118 Spec Alignment: UI Foundation ─────────────────────────────────────
//
// Spec: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
// Task: task-118 — UI Foundation: Design System, Project Setup & Shared Utilities
//
// This file consolidates spec-alignment verification for task-118 requirements:
//
//   1. Requirement: Design Language (5 scenarios)
//      - Component library (shadcn/vue / Reka UI, Tailwind, CVA, Lucide)
//      - Color theme (OKLCH CSS custom properties)
//      - Typography (system font, text-sm body, text-[11px] headers)
//      - Border radius (base 0.625rem)
//      - Elevation (shadow-sm cards, shadow-xs buttons, flat)
//
//   2. Requirement: Dark Mode (1 scenario)
//      - Toggle in header, preference persisted in localStorage
//
//   3. Requirement: Interaction Principles — shared utility layer (partial)
//      - Toast system (vue-sonner Toaster mounted in app root)
//      - Copy-to-clipboard composable (useCopyToClipboard)
//      - Focus ring CSS (outline-ring/50 global, focus-visible:ring-[3px])
//
// Testing approach: source-level inspection via readFileSync.
// Mounting the full Nuxt application in unit tests is impractical; source
// inspection is the accepted pattern for design-system and layout verification
// throughout this project (see design-system.test.ts, focus-ring.test.ts).

// ── Source paths ──────────────────────────────────────────────────────────────

const root = resolve(__dirname, '../..')
const appDir = resolve(__dirname, '..')

const cssPath = resolve(appDir, 'assets/css/main.css')
const css = readFileSync(cssPath, 'utf-8')

const pkgPath = resolve(root, 'package.json')
const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'))
const allDeps = { ...pkg.dependencies, ...pkg.devDependencies }

const layoutPath = resolve(appDir, 'layouts/default.vue')
const layoutContent = readFileSync(layoutPath, 'utf-8')

const appVuePath = resolve(appDir, 'app.vue')
const appVueContent = readFileSync(appVuePath, 'utf-8')

const useColorModePath = resolve(appDir, 'composables/useColorMode.ts')
const useColorModeContent = readFileSync(useColorModePath, 'utf-8')

const useCopyPath = resolve(appDir, 'composables/useCopyToClipboard.ts')
const useCopyContent = readFileSync(useCopyPath, 'utf-8')

const buttonPath = resolve(appDir, 'components/ui/button/index.ts')
const buttonContent = readFileSync(buttonPath, 'utf-8')

const cardPath = resolve(appDir, 'components/ui/card/Card.vue')
const cardContent = readFileSync(cardPath, 'utf-8')

const badgePath = resolve(appDir, 'components/ui/badge/index.ts')
const badgeContent = readFileSync(badgePath, 'utf-8')

const inputPath = resolve(appDir, 'components/ui/input/Input.vue')
const inputContent = readFileSync(inputPath, 'utf-8')

const libUtilsPath = resolve(appDir, 'lib/utils.ts')

// ── Requirement: Design Language — Scenario: Component library ────────────────
//
// "GIVEN any UI component
//  THEN it uses shadcn/vue (Reka UI) primitives with Tailwind CSS
//  AND variants are defined via Class Variance Authority (CVA)
//  AND icons use Lucide Vue Next"

describe('Design Language — Scenario: Component library', () => {
  it('reka-ui is in project dependencies (shadcn/vue primitive layer)', () => {
    expect(
      Object.keys(allDeps).some((k) => k.includes('reka-ui') || k.includes('@reka-ui')),
    ).toBe(true)
  })

  it('@tailwindcss/vite or tailwindcss is in project dependencies', () => {
    expect(
      Object.keys(allDeps).some((k) => k.includes('tailwindcss')),
    ).toBe(true)
  })

  it('class-variance-authority (CVA) is in project dependencies', () => {
    expect(allDeps).toHaveProperty('class-variance-authority')
  })

  it('lucide-vue-next is in project dependencies', () => {
    expect(allDeps).toHaveProperty('lucide-vue-next')
  })

  it('vue-sonner is in project dependencies (toast system)', () => {
    expect(allDeps).toHaveProperty('vue-sonner')
  })

  it('lib/utils.ts exists with cn() helper (clsx + tailwind-merge)', () => {
    expect(existsSync(libUtilsPath)).toBe(true)
    const content = readFileSync(libUtilsPath, 'utf-8')
    expect(content).toContain('clsx')
    expect(content).toContain('twMerge')
    // cn() function exported
    expect(content).toContain('export function cn')
  })

  it('button component uses cva() for variant definitions', () => {
    expect(buttonContent).toContain('cva(')
  })

  it('badge component uses cva() for variant definitions', () => {
    expect(badgeContent).toContain('cva(')
  })

  it('Card.vue uses reka-ui or is a standard shadcn-style component', () => {
    // Card is a plain Reka-style component without Reka primitives (it is a
    // styled div), but it uses the CVA-composed base pattern imported via cn()
    expect(cardContent).toContain('cn(')
  })
})

// ── Requirement: Design Language — Scenario: Color theme ─────────────────────
//
// "THEN colors are defined as OKLCH CSS custom properties
//  AND the primary/brand color is warm amber/orange (oklch(0.5768 0.2469 29.23) light,
//    oklch(0.6857 0.1560 17.57) dark)
//  AND neutral grays form the background, card, and border palette
//  AND destructive actions use a coral/red accent
//  AND chart/data visualization uses a 5-color palette (amber, blue, purple, yellow, green)"

describe('Design Language — Scenario: Color theme', () => {
  it('light-mode --primary is warm amber oklch(0.5768 0.2469 29.23)', () => {
    expect(css).toContain('--primary: oklch(0.5768 0.2469 29.23)')
  })

  it('dark-mode --primary is warm amber oklch(0.6857 0.1560 17.57)', () => {
    expect(css).toContain('--primary: oklch(0.6857 0.1560 17.57)')
  })

  it('all color custom properties use oklch() notation (not hex or hsl)', () => {
    const colorVarLines = css
      .split('\n')
      .filter((line) => line.match(/--(?:background|foreground|primary|secondary|muted|accent|destructive|border|ring|card|popover)\b.*:.*oklch/))
    expect(colorVarLines.length).toBeGreaterThan(10)
  })

  it('neutral gray: --background light is pure white oklch(1 0 0)', () => {
    expect(css).toContain('--background: oklch(1 0 0)')
  })

  it('neutral gray: --border is achromatic (zero chroma)', () => {
    expect(css).toContain('--border: oklch(0.9003 0 0)')
  })

  it('neutral gray: --background dark is dark neutral oklch(0.1736 0 0)', () => {
    expect(css).toContain('--background: oklch(0.1736 0 0)')
  })

  it('destructive light: coral/red oklch(0.6237 0.1930 38.99)', () => {
    expect(css).toContain('--destructive: oklch(0.6237 0.1930 38.99)')
  })

  it('destructive dark: coral/red oklch(0.6891 0.1580 39.72)', () => {
    expect(css).toContain('--destructive: oklch(0.6891 0.1580 39.72)')
  })

  it('5-color chart palette: --chart-1 through --chart-5 defined in CSS', () => {
    for (let i = 1; i <= 5; i++) {
      expect(css).toContain(`--chart-${i}:`)
    }
  })

  it('chart-1 (amber) matches primary brand color in light mode', () => {
    // Amber is chart-1 — same hue as the primary brand
    expect(css).toContain('--chart-1: oklch(0.5768 0.2469 29.23)')
  })

  it('chart-2 is blue (hue ~194)', () => {
    expect(css).toContain('--chart-2: oklch(0.6423 0.0831 194.77)')
  })

  it('.dark selector block exists overriding color tokens for dark mode', () => {
    expect(css).toContain('.dark {')
  })
})

// ── Requirement: Design Language — Scenario: Typography ──────────────────────
//
// "THEN the system font stack is used (no custom fonts)
//  AND body text uses text-sm (0.875rem)
//  AND section headers use uppercase text-[11px] with tracking-wider
//  AND font weights are limited to regular (400), medium (500), and semibold (600)"

describe('Design Language — Scenario: Typography', () => {
  it('no @font-face or custom web font import in main.css', () => {
    expect(css).not.toContain('@font-face')
    expect(css).not.toContain('font-family:')
  })

  it('layout uses text-sm for body-sized navigation items', () => {
    expect(layoutContent).toContain('text-sm')
  })

  it('button component uses text-sm (0.875rem / 14px)', () => {
    expect(buttonContent).toContain('text-sm')
  })

  it('section headers use text-[11px] in the sidebar layout', () => {
    expect(layoutContent).toContain('text-[11px]')
  })

  it('section headers use uppercase class for ALL-CAPS labels', () => {
    expect(layoutContent).toContain('uppercase')
  })

  it('section headers use tracking-wider for letter spacing', () => {
    expect(layoutContent).toContain('tracking-wider')
  })

  it('button component uses font-medium (500 weight)', () => {
    expect(buttonContent).toContain('font-medium')
  })

  it('layout uses font-semibold (600 weight) for section header labels', () => {
    expect(layoutContent).toContain('font-semibold')
  })

  it('button component does NOT use font-bold (700) — weights capped at semibold (600)', () => {
    expect(buttonContent).not.toContain('font-bold')
  })

  it('badge component does NOT use font-bold (700) — weights capped at semibold (600)', () => {
    expect(badgeContent).not.toContain('font-bold')
  })
})

// ── Requirement: Design Language — Scenario: Border radius ───────────────────
//
// "THEN border radius scales from a base of 0.625rem (10px)
//  AND cards use rounded-xl, buttons and inputs use rounded-md, badges use rounded-full"

describe('Design Language — Scenario: Border radius', () => {
  it('--radius base is 0.625rem (10px) in CSS custom properties', () => {
    expect(css).toContain('--radius: 0.625rem')
  })

  it('radius scale derives --radius-sm, --radius-md, --radius-lg, --radius-xl from base', () => {
    expect(css).toContain('--radius-sm: calc(var(--radius) - 4px)')
    expect(css).toContain('--radius-md: calc(var(--radius) - 2px)')
    expect(css).toContain('--radius-lg: var(--radius)')
    expect(css).toContain('--radius-xl: calc(var(--radius) + 4px)')
  })

  it('Card uses rounded-xl', () => {
    expect(cardContent).toContain('rounded-xl')
  })

  it('Button uses rounded-md', () => {
    expect(buttonContent).toContain('rounded-md')
  })

  it('Input uses rounded-md', () => {
    expect(inputContent).toContain('rounded-md')
  })

  it('Badge uses rounded-full (pill shape)', () => {
    expect(badgeContent).toContain('rounded-full')
  })

  it('Badge does NOT use rounded-md (must be pill-shaped, not slightly rounded)', () => {
    // The CVA base class for Badge must be rounded-full, not rounded-md
    const cvaBaseMatch = badgeContent.match(/cva\(\s*['"`]([^'"`]+)['"`]/)
    if (cvaBaseMatch) {
      expect(cvaBaseMatch[1]).not.toContain('rounded-md')
    }
  })
})

// ── Requirement: Design Language — Scenario: Elevation ───────────────────────
//
// "THEN cards use shadow-sm and buttons use shadow-xs
//  AND depth is minimal — the UI is predominantly flat"

describe('Design Language — Scenario: Elevation', () => {
  it('Card uses shadow-sm (minimal card elevation)', () => {
    expect(cardContent).toContain('shadow-sm')
  })

  it('Card does NOT use shadow-md, shadow-lg, or shadow-xl', () => {
    expect(cardContent).not.toContain('shadow-md')
    expect(cardContent).not.toContain('shadow-lg')
    expect(cardContent).not.toContain('shadow-xl')
  })

  it('Button outline variant uses shadow-xs (minimal button elevation)', () => {
    expect(buttonContent).toContain('shadow-xs')
  })

  it('Button does NOT use shadow-lg or shadow-xl (flat principle)', () => {
    expect(buttonContent).not.toContain('shadow-lg')
    expect(buttonContent).not.toContain('shadow-xl')
  })
})

// ── Requirement: Dark Mode — Scenario: Toggle ────────────────────────────────
//
// "THEN a dark mode toggle is available in the header
//  AND the preference persists across sessions"

describe('Dark Mode — Scenario: Toggle in header', () => {
  it('default.vue imports useColorMode composable', () => {
    expect(layoutContent).toContain('useColorMode')
  })

  it('dark mode toggle calls toggleColorMode on click (header region)', () => {
    const headerStart = layoutContent.indexOf('<header ')
    const headerEnd = layoutContent.indexOf('</header>')
    expect(headerStart).toBeGreaterThan(-1)
    expect(headerEnd).toBeGreaterThan(headerStart)
    const headerSection = layoutContent.slice(headerStart, headerEnd + '</header>'.length)
    expect(headerSection).toContain('@click="toggleColorMode"')
  })

  it('Sun and Moon icons from lucide-vue-next are used in the toggle', () => {
    expect(layoutContent).toContain('Sun')
    expect(layoutContent).toContain('Moon')
  })

  it('toggle has accessible label via tooltip (Switch to light/dark mode)', () => {
    expect(layoutContent).toContain('Switch to light mode')
    expect(layoutContent).toContain('Switch to dark mode')
  })

  it('useColorMode composable writes preference to localStorage on toggle', () => {
    expect(useColorModeContent).toContain('localStorage.setItem')
    expect(useColorModeContent).toContain('kartograph-color-mode')
  })

  it('useColorMode composable reads preference from localStorage on load', () => {
    expect(useColorModeContent).toContain('localStorage.getItem')
  })

  it('useColorMode applies "dark" class to documentElement', () => {
    expect(useColorModeContent).toContain('classList.add')
    expect(useColorModeContent).toContain("'dark'")
  })

  it('useColorMode removes "dark" class from documentElement for light mode', () => {
    expect(useColorModeContent).toContain('classList.remove')
  })
})

// ── Requirement: Interaction Principles — shared utility layer ────────────────

// Scenario: Toast system (mutation feedback + copy confirmation)
describe('Interaction Principles — Scenario: Mutation feedback (toast system)', () => {
  it('app.vue mounts the Toaster component globally (available on all pages)', () => {
    expect(appVueContent).toContain('Toaster')
  })

  it('app.vue uses richColors Toaster for consistent success/error styling', () => {
    expect(appVueContent).toContain('richColors')
  })

  it('vue-sonner Toaster is imported from @/components/ui/sonner (project wrapper)', () => {
    // app.vue should import from the project wrapper, not raw vue-sonner
    const importLine = appVueContent.split('\n').find((l) => l.includes('Toaster'))
    expect(importLine).toBeDefined()
    expect(importLine).toContain('@/components/ui/sonner')
  })

  it('Sonner.vue component wrapper exists in ui/sonner/', () => {
    const sonnerPath = resolve(appDir, 'components/ui/sonner/Sonner.vue')
    expect(existsSync(sonnerPath)).toBe(true)
  })
})

// Scenario: Copy-to-clipboard composable
describe('Interaction Principles — Scenario: Copy-to-clipboard (useCopyToClipboard)', () => {
  it('useCopyToClipboard.ts exists in composables/', () => {
    expect(existsSync(useCopyPath)).toBe(true)
  })

  it('composable exports a copyToClipboard async function', () => {
    expect(useCopyContent).toContain('async function copyToClipboard')
    expect(useCopyContent).toContain('export function useCopyToClipboard')
  })

  it('composable calls navigator.clipboard.writeText', () => {
    expect(useCopyContent).toContain('navigator.clipboard.writeText')
  })

  it('composable shows success toast via vue-sonner on successful copy', () => {
    expect(useCopyContent).toContain('toast.success')
  })

  it('composable shows error toast on clipboard failure', () => {
    expect(useCopyContent).toContain('toast.error')
  })

  it('composable exposes a reactive copied ref that resets after 2s', () => {
    expect(useCopyContent).toContain('const copied = ref(false)')
    expect(useCopyContent).toContain('setTimeout')
    expect(useCopyContent).toContain('copied.value = false')
  })

  it('composable returns false on failure and true on success', () => {
    expect(useCopyContent).toContain('return true')
    expect(useCopyContent).toContain('return false')
  })
})

// Scenario: Focus indicators
describe('Interaction Principles — Scenario: Focus indicators', () => {
  it('main.css applies outline-ring/50 globally via @layer base', () => {
    // Spec: "native outlines are suppressed in favor of the ring"
    expect(css).toContain('outline-ring/50')
  })

  it('main.css has a @layer base block applying global focus styles', () => {
    expect(css).toContain('@layer base')
  })

  it('--ring is set to the primary brand color (oklch(0.5768 0.2469 29.23) light)', () => {
    // The focus ring must use the primary brand color at 50% opacity
    expect(css).toContain('--ring: oklch(0.5768 0.2469 29.23)')
  })

  it('--ring in dark mode is oklch(0.6857 0.1560 17.57)', () => {
    expect(css).toContain('--ring: oklch(0.6857 0.1560 17.57)')
  })

  it('layout default.vue does NOT use focus-visible:ring-2 (must use ring-[3px] per spec)', () => {
    // ring-2 = Tailwind preset 8px unit; spec requires explicit 3px literal
    expect(layoutContent).not.toContain('focus-visible:ring-2')
  })

  it('layout default.vue uses focus-visible:ring-[3px] for manual interactive elements', () => {
    expect(layoutContent).toContain('focus-visible:ring-[3px]')
  })
})
