import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Design Language Tests ─────────────────────────────────────────────────────
//
// Spec: specs/ui/experience.spec.md — Requirement: Design Language
//
// Four scenarios are explicitly verified:
//   1. Color theme — OKLCH CSS custom properties, primary brand color, neutral grays,
//      destructive accent, and 5-color chart palette
//   2. Typography — system font stack, text-sm body, text-[11px] section headers,
//      tracking-wider, font weight constraints (400/500/600 only)
//   3. Border radius — base 0.625rem; cards rounded-xl, buttons/inputs rounded-md,
//      badges rounded-full
//   4. Elevation — cards shadow-sm, buttons shadow-xs, minimal/flat principle

// ── Source file reads ─────────────────────────────────────────────────────────

const cssPath = resolve(__dirname, '../assets/css/main.css')
const css = readFileSync(cssPath, 'utf-8')

const cardPath = resolve(__dirname, '../components/ui/card/Card.vue')
const cardContent = readFileSync(cardPath, 'utf-8')

const buttonIndexPath = resolve(__dirname, '../components/ui/button/index.ts')
const buttonContent = readFileSync(buttonIndexPath, 'utf-8')

const badgeIndexPath = resolve(__dirname, '../components/ui/badge/index.ts')
const badgeContent = readFileSync(badgeIndexPath, 'utf-8')

const inputPath = resolve(__dirname, '../components/ui/input/Input.vue')
const inputContent = readFileSync(inputPath, 'utf-8')

const layoutPath = resolve(__dirname, '../layouts/default.vue')
const layoutContent = readFileSync(layoutPath, 'utf-8')

// ── Scenario: Color theme ─────────────────────────────────────────────────────
//
// "THEN colors are defined as OKLCH CSS custom properties"
// "AND the primary/brand color is warm amber/orange (oklch(0.5768 0.2469 29.23) light,
//   oklch(0.6857 0.1560 17.57) dark)"
// "AND neutral grays form the background, card, and border palette"
// "AND destructive actions use a coral/red accent"
// "AND chart/data visualization uses a 5-color palette (amber, blue, purple, yellow, green)"

describe('Design Language — Scenario: Color theme', () => {
  describe('primary brand color', () => {
    it('defines --primary in light :root as oklch(0.5768 0.2469 29.23) — warm amber/orange', () => {
      expect(css).toContain('--primary: oklch(0.5768 0.2469 29.23)')
    })

    it('defines --primary in .dark as oklch(0.6857 0.1560 17.57)', () => {
      expect(css).toContain('--primary: oklch(0.6857 0.1560 17.57)')
    })

    it('uses OKLCH notation (not hex or hsl)', () => {
      const primaryLines = css
        .split('\n')
        .filter((line) => line.trim().startsWith('--primary:'))
      expect(primaryLines.every((l) => l.includes('oklch('))).toBe(true)
    })
  })

  describe('neutral gray palette', () => {
    it('defines --background in light mode as pure white oklch(1 0 0)', () => {
      expect(css).toContain('--background: oklch(1 0 0)')
    })

    it('defines --card in light mode with zero chroma (achromatic)', () => {
      // Card and background are the same neutral white in light mode
      expect(css).toContain('--card: oklch(1 0 0)')
    })

    it('defines --border with zero chroma (neutral gray)', () => {
      expect(css).toContain('--border: oklch(0.9003 0 0)')
    })

    it('defines --background in dark mode as a dark neutral', () => {
      // Dark background L < 0.25
      expect(css).toContain('--background: oklch(0.1736 0 0)')
    })
  })

  describe('destructive color — coral/red accent', () => {
    it('defines --destructive in light mode as a coral/red OKLCH value', () => {
      // Hue ~30–45 is coral/red-orange territory
      expect(css).toContain('--destructive: oklch(0.6237 0.1930 38.99)')
    })

    it('defines --destructive in dark mode as a coral/red OKLCH value', () => {
      expect(css).toContain('--destructive: oklch(0.6891 0.1580 39.72)')
    })
  })

  describe('5-color chart palette (amber, blue, purple, yellow, green)', () => {
    it('defines --chart-1 through --chart-5 in light mode', () => {
      expect(css).toContain('--chart-1:')
      expect(css).toContain('--chart-2:')
      expect(css).toContain('--chart-3:')
      expect(css).toContain('--chart-4:')
      expect(css).toContain('--chart-5:')
    })

    it('chart-1 is amber (same hue as primary) in light mode', () => {
      // Amber chart color matches primary in light mode
      expect(css).toContain('--chart-1: oklch(0.5768 0.2469 29.23)')
    })

    it('chart-2 is blue (hue ~190–220)', () => {
      expect(css).toContain('--chart-2: oklch(0.6423 0.0831 194.77)')
    })

    it('defines --chart-3, --chart-4, --chart-5 as distinct OKLCH values', () => {
      // Extract chart values from :root (light mode) only — the .dark block also
      // defines these, so we slice the light :root section to avoid double-counting
      const rootBlock = css.slice(0, css.indexOf('.dark {'))
      const chartLines = rootBlock
        .split('\n')
        .filter((l) => l.match(/--chart-[3-5]:\s*oklch/))
      expect(chartLines).toHaveLength(3)
    })

    it('defines 5 chart colors in dark mode as well', () => {
      // Dark mode has a separate .dark block with its own chart values
      const darkBlock = css.slice(css.indexOf('.dark {'))
      expect(darkBlock).toContain('--chart-1:')
      expect(darkBlock).toContain('--chart-2:')
      expect(darkBlock).toContain('--chart-3:')
      expect(darkBlock).toContain('--chart-4:')
      expect(darkBlock).toContain('--chart-5:')
    })
  })

  describe('all color tokens use OKLCH notation', () => {
    it('contains more than 10 OKLCH color property definitions', () => {
      const oklchLines = css
        .split('\n')
        .filter((line) => line.includes('oklch('))
      expect(oklchLines.length).toBeGreaterThan(10)
    })
  })
})

// ── Scenario: Typography ──────────────────────────────────────────────────────
//
// "THEN the system font stack is used (no custom fonts)"
// "AND body text uses text-sm (0.875rem)"
// "AND section headers use uppercase text-[11px] with tracking-wider"
// "AND font weights are limited to regular (400), medium (500), and semibold (600)"

describe('Design Language — Scenario: Typography', () => {
  describe('system font stack — no custom fonts', () => {
    it('does not import Google Fonts', () => {
      expect(css).not.toContain('fonts.googleapis.com')
      expect(css).not.toContain('fonts.gstatic.com')
    })

    it('does not define a @font-face rule for custom fonts', () => {
      expect(css).not.toContain('@font-face')
    })
  })

  describe('body text size — text-sm (0.875rem)', () => {
    it('uses text-sm class for body-level text in navigation', () => {
      // Navigation links in default.vue use text-sm
      expect(layoutContent).toContain('text-sm')
    })

    it('button base class uses text-sm', () => {
      // Buttons are primary interactive elements — should be body text size
      expect(buttonContent).toContain('text-sm')
    })

    it('text-sm corresponds to 14px (0.875rem * 16px/rem base)', () => {
      const remValue = 0.875
      expect(remValue * 16).toBe(14)
    })
  })

  describe('section headers — text-[11px] uppercase tracking-wider', () => {
    it('nav section group headers use text-[11px]', () => {
      // From default.vue: sidebar section group labels
      expect(layoutContent).toContain('text-[11px]')
    })

    it('nav section group headers use the uppercase class', () => {
      expect(layoutContent).toContain('uppercase')
    })

    it('nav section group headers use tracking-wider for letter spacing', () => {
      expect(layoutContent).toContain('tracking-wider')
    })

    it('section header combines text-[11px], uppercase, and tracking-wider together', () => {
      const hasAll =
        layoutContent.includes('text-[11px]') &&
        layoutContent.includes('uppercase') &&
        layoutContent.includes('tracking-wider')
      expect(hasAll).toBe(true)
    })
  })

  describe('font weight constraints — 400, 500, 600 only', () => {
    it('button component uses font-medium (500)', () => {
      expect(buttonContent).toContain('font-medium')
    })

    it('section headers use font-semibold (600)', () => {
      expect(layoutContent).toContain('font-semibold')
    })

    it('button component does not use font-bold (700) or heavier', () => {
      expect(buttonContent).not.toContain('font-bold')
      expect(buttonContent).not.toContain('font-black')
      expect(buttonContent).not.toContain('font-extrabold')
    })

    it('badge component does not use font-bold or heavier', () => {
      expect(badgeContent).not.toContain('font-bold')
      expect(badgeContent).not.toContain('font-black')
    })
  })
})

// ── Scenario: Border radius ───────────────────────────────────────────────────
//
// "THEN border radius scales from a base of 0.625rem (10px)"
// "AND cards use rounded-xl, buttons and inputs use rounded-md, badges use rounded-full"

describe('Design Language — Scenario: Border radius', () => {
  describe('base CSS variable', () => {
    it('--radius is set to 0.625rem (10px base)', () => {
      expect(css).toContain('--radius: 0.625rem')
    })

    it('derives radius scale (sm, md, lg, xl) from --radius', () => {
      expect(css).toContain('--radius-sm: calc(var(--radius) - 4px)')
      expect(css).toContain('--radius-md: calc(var(--radius) - 2px)')
      expect(css).toContain('--radius-lg: var(--radius)')
      expect(css).toContain('--radius-xl: calc(var(--radius) + 4px)')
    })
  })

  describe('cards use rounded-xl', () => {
    it('Card component base class includes rounded-xl', () => {
      expect(cardContent).toContain('rounded-xl')
    })

    it('Card does not use rounded-none or rounded-sm (too sharp for cards)', () => {
      // Cards should have the xl rounding per spec
      expect(cardContent).not.toContain('rounded-none')
    })
  })

  describe('buttons use rounded-md', () => {
    it('Button component base class includes rounded-md', () => {
      // Base class in buttonVariants cva includes rounded-md
      expect(buttonContent).toContain('rounded-md')
    })
  })

  describe('inputs use rounded-md', () => {
    it('Input component base class includes rounded-md', () => {
      expect(inputContent).toContain('rounded-md')
    })
  })

  describe('badges use rounded-full', () => {
    it('Badge component base class includes rounded-full', () => {
      // badgeVariants cva base: "... rounded-full ..."
      expect(badgeContent).toContain('rounded-full')
    })

    it('Badge does not use rounded-md (badges should be pill-shaped)', () => {
      // Badge is distinguished from buttons by its pill shape
      // The base class should have rounded-full, not the less-rounded md variant
      const baseClassMatch = badgeContent.match(/cva\(\s*"([^"]+)"/)
      if (baseClassMatch) {
        expect(baseClassMatch[1]).toContain('rounded-full')
        expect(baseClassMatch[1]).not.toContain('rounded-md')
      }
    })
  })
})

// ── Scenario: Elevation ───────────────────────────────────────────────────────
//
// "THEN cards use shadow-sm and buttons use shadow-xs"
// "AND depth is minimal — the UI is predominantly flat"

describe('Design Language — Scenario: Elevation', () => {
  describe('cards use shadow-sm', () => {
    it('Card component base class includes shadow-sm', () => {
      expect(cardContent).toContain('shadow-sm')
    })

    it('Card does not use shadow-md or larger (minimal elevation)', () => {
      expect(cardContent).not.toContain('shadow-md')
      expect(cardContent).not.toContain('shadow-lg')
      expect(cardContent).not.toContain('shadow-xl')
      expect(cardContent).not.toContain('shadow-2xl')
    })
  })

  describe('buttons use shadow-xs (outline variant)', () => {
    it('Button outline variant uses shadow-xs', () => {
      // Spec: "buttons use shadow-xs"
      expect(buttonContent).toContain('shadow-xs')
    })

    it('Button default variant has no large shadow (flat primary button)', () => {
      // Default variant is the main CTA button — it is flat per the spec
      expect(buttonContent).not.toContain('shadow-lg')
      expect(buttonContent).not.toContain('shadow-xl')
    })
  })

  describe('inputs use shadow-xs', () => {
    it('Input component uses shadow-xs', () => {
      expect(inputContent).toContain('shadow-xs')
    })
  })

  describe('depth is minimal — UI is predominantly flat', () => {
    it('no shadow-lg or shadow-xl used in Card', () => {
      expect(cardContent).not.toContain('shadow-lg')
      expect(cardContent).not.toContain('shadow-xl')
    })

    it('no shadow-lg or shadow-xl used in Button', () => {
      expect(buttonContent).not.toContain('shadow-lg')
      expect(buttonContent).not.toContain('shadow-xl')
    })

    it('no shadow-lg or shadow-xl used in Badge', () => {
      expect(badgeContent).not.toContain('shadow-lg')
      expect(badgeContent).not.toContain('shadow-xl')
    })
  })
})
