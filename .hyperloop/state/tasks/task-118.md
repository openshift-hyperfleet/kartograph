---
id: task-118
title: UI Foundation — Design System, Layout, and Dark Mode
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): scaffold design system, base layout, and dark mode toggle"
pr_description: |
  ## What and Why

  Establishes the Kartograph front-end project from scratch. There is currently no
  `src/ui` directory — this task creates it and wires up the complete design system
  so every subsequent UI task has a consistent visual and structural foundation to
  build on.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Design Language**, **Requirement: Responsive Design**,
  and **Requirement: Dark Mode** from `specs/ui/experience.spec.md`.

  Specifically:
  - shadcn/vue (Reka UI) primitives + Tailwind CSS as the component library
  - Class Variance Authority (CVA) for variant definitions
  - Lucide Vue Next for icons
  - OKLCH CSS custom properties: brand amber/orange, neutral grays, destructive coral/red,
    5-color chart palette — light and dark variants
  - Border radius tokens: `0.625rem` base, `rounded-xl` cards, `rounded-md`
    buttons/inputs, `rounded-full` badges
  - Typography: system font stack, `text-sm` body, `text-[11px] tracking-wider`
    section headers, weights 400/500/600 only
  - Elevation: `shadow-sm` cards, `shadow-xs` buttons, predominantly flat UI
  - Dark mode toggle in header with `localStorage` persistence across sessions
  - Sidebar collapsible on desktop; sheet overlay on tablet/narrow screens
  - Single-column layout on narrow screens, multi-column where appropriate
  - 3 px primary-color-at-50%-opacity focus ring; native outlines suppressed
  - Copy-to-clipboard utility + toast confirmation (cross-cutting interaction principle)
  - Toast notification system for mutation feedback (success/failure)

  ## Design Decisions

  - **Framework**: Vue 3 + TypeScript + Vite (or Nuxt for SSR if preferred)
  - **Design tokens** live in `src/ui/assets/theme.css` as CSS custom properties;
    Tailwind `tailwind.config.ts` references them.
  - **Dark mode**: implemented via `class` strategy on `<html>`, toggled by a header
    button, persisted to `localStorage`. System preference is the initial default when
    no saved preference exists.
  - **Component library**: `src/ui/components/ui/` holds base primitives (Button,
    Input, Badge, Card, Sheet, Toast, Dialog). Variants defined with CVA.

  ## Files / Areas Affected

  - `src/ui/` — entire new directory
  - `src/ui/package.json`, `vite.config.ts`, `tsconfig.json`
  - `src/ui/assets/theme.css` — OKLCH design tokens
  - `src/ui/tailwind.config.ts`
  - `src/ui/components/ui/` — base primitive components
  - `src/ui/composables/useTheme.ts` — dark mode toggle + persistence
  - `src/ui/composables/useClipboard.ts` — copy-to-clipboard utility
  - `src/ui/layouts/AppLayout.vue` — shell with sidebar + main content area
  - `src/ui/components/AppSidebar.vue` — collapsible sidebar skeleton
  - `src/ui/components/AppHeader.vue` — header with dark mode toggle

  ## How to Verify

  1. `cd src/ui && npm run dev` — app loads without errors
  2. Toggle dark mode: colors switch according to OKLCH palette; preference survives refresh
  3. Resize to narrow viewport: sidebar collapses to sheet overlay
  4. All brand colors, border radii, and font weights match the spec values

  ## Caveats

  This task does not populate the sidebar with navigation items (see task-119) or
  implement any page-level routes. It only establishes the visual shell.
---
