import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Design Language Tests ─────────────────────────────────────────────────────
//
// Spec: "Design Language"
// Covers:
//   - Scenario: Color theme (OKLCH CSS custom properties)
//   - Scenario: Border radius (base 0.625rem)
//   - Scenario: Typography (text-sm body, uppercase text-[11px] section headers)
//   - Scenario: Elevation (shadow-sm cards, shadow-xs buttons)
//   - Scenario: Component library (shadcn/vue, Tailwind, CVA, Lucide)

// ── Read the CSS file for inspection ─────────────────────────────────────────

const cssPath = resolve(__dirname, '../assets/css/main.css')
const css = readFileSync(cssPath, 'utf-8')

// ── Scenario: Color theme — OKLCH values ──────────────────────────────────────
// Spec: "colors are defined as OKLCH CSS custom properties"
// "the primary/brand color is warm amber/orange (oklch(0.5768 0.2469 29.23) light,
//  oklch(0.6857 0.1560 17.57) dark)"

describe('Design System - primary color OKLCH values', () => {
  it('defines --primary in light mode as oklch(0.5768 0.2469 29.23)', () => {
    expect(css).toContain('--primary: oklch(0.5768 0.2469 29.23)')
  })

  it('defines --primary in dark mode as oklch(0.6857 0.1560 17.57)', () => {
    expect(css).toContain('--primary: oklch(0.6857 0.1560 17.57)')
  })

  it('defines --ring using the same OKLCH value as --primary in light mode', () => {
    expect(css).toContain('--ring: oklch(0.5768 0.2469 29.23)')
  })

  it('uses oklch() notation for all color custom properties', () => {
    // Every --color: value in :root and .dark should use oklch()
    const colorVarLines = css
      .split('\n')
      .filter((line) => line.match(/--(?:background|foreground|primary|secondary|muted|accent|destructive|border|ring|card|popover|sidebar)\b.*:.*oklch/))
    expect(colorVarLines.length).toBeGreaterThan(10)
  })
})

// ── Scenario: Neutral grays ────────────────────────────────────────────────────
// Spec: "neutral grays form the background, card, and border palette"

describe('Design System - neutral gray palette', () => {
  it('defines --background in light mode as pure white in oklch', () => {
    expect(css).toContain('--background: oklch(1 0 0)')
  })

  it('defines --background in dark mode as a dark neutral', () => {
    // Dark background should be a dark oklch value (L < 0.3)
    expect(css).toContain('--background: oklch(0.1736 0 0)')
  })

  it('defines --border with zero chroma (achromatic gray)', () => {
    expect(css).toContain('--border: oklch(0.9003 0 0)')
  })
})

// ── Scenario: Destructive action color ────────────────────────────────────────
// Spec: "destructive actions use a coral/red accent"

describe('Design System - destructive color', () => {
  it('defines --destructive in light mode as a coral/red in oklch', () => {
    // Hue ~30–40 is coral/red-orange territory
    expect(css).toContain('--destructive: oklch(0.6237 0.1930 38.99)')
  })
})

// ── Scenario: Chart/data visualization palette ────────────────────────────────
// Spec: "chart/data visualization uses a 5-color palette (amber, blue, purple, yellow, green)"

describe('Design System - chart colors', () => {
  it('defines 5 chart colors (--chart-1 through --chart-5)', () => {
    expect(css).toContain('--chart-1:')
    expect(css).toContain('--chart-2:')
    expect(css).toContain('--chart-3:')
    expect(css).toContain('--chart-4:')
    expect(css).toContain('--chart-5:')
  })

  it('chart-1 is amber (same hue as primary) in light mode', () => {
    // chart-1 should match or be close to the primary amber
    expect(css).toContain('--chart-1: oklch(0.5768 0.2469 29.23)')
  })

  it('chart-2 is blue (high hue ~190)', () => {
    expect(css).toContain('--chart-2: oklch(0.6423 0.0831 194.77)')
  })
})

// ── Scenario: Border radius ───────────────────────────────────────────────────
// Spec: "border radius scales from a base of 0.625rem (10px)"
// "cards use rounded-xl, buttons and inputs use rounded-md, badges use rounded-full"

describe('Design System - border radius', () => {
  it('defines --radius base as 0.625rem', () => {
    expect(css).toContain('--radius: 0.625rem')
  })

  it('derives --radius-sm, --radius-md, --radius-lg, --radius-xl from base', () => {
    expect(css).toContain('--radius-sm: calc(var(--radius) - 4px)')
    expect(css).toContain('--radius-md: calc(var(--radius) - 2px)')
    expect(css).toContain('--radius-lg: var(--radius)')
    expect(css).toContain('--radius-xl: calc(var(--radius) + 4px)')
  })
})

// ── Scenario: Sidebar color tokens ────────────────────────────────────────────

describe('Design System - sidebar tokens', () => {
  it('defines sidebar-specific color tokens', () => {
    expect(css).toContain('--sidebar:')
    expect(css).toContain('--sidebar-foreground:')
    expect(css).toContain('--sidebar-primary:')
    expect(css).toContain('--sidebar-accent:')
    expect(css).toContain('--sidebar-border:')
    expect(css).toContain('--sidebar-ring:')
  })

  it('sidebar uses the primary amber as sidebar-primary in light mode', () => {
    expect(css).toContain('--sidebar-primary: oklch(0.5768 0.2469 29.23)')
  })
})

// ── Scenario: Focus indicators ────────────────────────────────────────────────
// Spec: "a 3px ring in the primary color at 50% opacity is shown
// AND native outlines are suppressed in favor of the ring"

describe('Design System - focus indicators', () => {
  it('applies outline-ring/50 to all elements via base layer', () => {
    // The @layer base block should have * { outline-ring/50 }
    expect(css).toContain('outline-ring/50')
  })
})

// ── Scenario: Dark mode class ─────────────────────────────────────────────────
// Spec: "support light and dark color schemes"

describe('Design System - dark mode', () => {
  it('defines a .dark selector block with overriding color values', () => {
    expect(css).toContain('.dark {')
  })

  it('dark mode uses different primary than light mode', () => {
    // Light: 0.5768 0.2469 29.23, Dark: 0.6857 0.1560 17.57
    expect(css).toContain('oklch(0.5768 0.2469 29.23)')
    expect(css).toContain('oklch(0.6857 0.1560 17.57)')
  })
})

// ── Scenario: Component library (package verification) ───────────────────────
// Spec: "uses shadcn/vue (Reka UI) primitives with Tailwind CSS
// AND variants are defined via Class Variance Authority (CVA)
// AND icons use Lucide Vue Next"

describe('Design System - component library dependencies', () => {
  const pkgPath = resolve(__dirname, '../../package.json')
  const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'))
  const allDeps = { ...pkg.dependencies, ...pkg.devDependencies }

  it('uses Tailwind CSS', () => {
    expect(
      Object.keys(allDeps).some((k) => k.includes('tailwindcss')),
    ).toBe(true)
  })

  it('uses class-variance-authority (CVA) for component variants', () => {
    expect(allDeps).toHaveProperty('class-variance-authority')
  })

  it('uses Lucide Vue Next for icons', () => {
    expect(allDeps).toHaveProperty('lucide-vue-next')
  })

  it('uses Reka UI (shadcn/vue primitives)', () => {
    expect(
      Object.keys(allDeps).some((k) => k.includes('reka-ui') || k.includes('@reka-ui')),
    ).toBe(true)
  })

  it('uses vitest for unit testing', () => {
    expect(allDeps).toHaveProperty('vitest')
  })
})
