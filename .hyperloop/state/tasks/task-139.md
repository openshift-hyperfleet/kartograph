---
id: task-139
title: "UI Foundation — Vue/Nuxt project init with design system"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): initialize Vue/Nuxt project with design system foundation"
pr_description: |
  ## What and Why

  This task bootstraps the Kartograph frontend from scratch. There is currently no
  `src/ui/` directory — the only frontend artifact is `demo-web/`, a static HTML
  prototype that does not use a component framework. The UI spec
  (`specs/ui/experience.spec.md`) requires a production-grade Vue application using
  shadcn/vue (Reka UI) primitives, Tailwind CSS, OKLCH color tokens, and dark mode
  support. Every subsequent UI task depends on this foundation being in place.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Design Language — Scenario: Component library**
    "uses shadcn/vue (Reka UI) primitives with Tailwind CSS; variants via CVA; icons via Lucide Vue Next"

  - **Requirement: Design Language — Scenario: Color theme**
    "colors are defined as OKLCH CSS custom properties; primary/brand is warm amber/orange
    (oklch(0.5768 0.2469 29.23) light, oklch(0.6857 0.1560 17.57) dark); neutral grays for
    background/card/border; destructive coral/red accent; 5-color chart palette"

  - **Requirement: Design Language — Scenario: Typography**
    "system font stack; body text-sm (0.875rem); section headers uppercase text-[11px]
    tracking-wider; font weights limited to 400, 500, 600"

  - **Requirement: Design Language — Scenario: Border radius**
    "base 0.625rem (10px); cards rounded-xl; buttons/inputs rounded-md; badges rounded-full"

  - **Requirement: Design Language — Scenario: Elevation**
    "cards shadow-sm; buttons shadow-xs; predominantly flat"

  - **Requirement: Dark Mode — Scenario: Toggle**
    "dark mode toggle in header; preference persists across sessions"

  - **Requirement: Interaction Principles — Scenario: Focus indicators**
    "3px ring in primary color at 50% opacity; native outlines suppressed"

  - **Requirement: Interaction Principles — Scenario: Copy-to-clipboard**
    "copy button present; toast confirms action" (base infrastructure for the composable)

  - **Requirement: Interaction Principles — Scenario: Mutation feedback**
    "toast notification confirms success or reports failure" (base toast component)

  ## Key Design Decisions

  - **Framework**: Nuxt 3 (Vue 3) for SSR capability and file-based routing, housed in `src/ui/`.
  - **UI primitives**: `shadcn-vue` (Reka UI) — install via the shadcn-vue CLI.
  - **Styling**: Tailwind CSS v4 with CSS custom property tokens (not Tailwind config
    color values) for OKLCH support.
  - **Icons**: `lucide-vue-next` — tree-shakable, consistent set.
  - **Variant utility**: `class-variance-authority` (CVA) for component variants.
  - **Dark mode**: Managed via `@nuxtjs/color-mode` with a system-font stack.
  - **API integration**: Nuxt's `useFetch` / `$fetch` wired to `NUXT_PUBLIC_API_BASE_URL`
    env var pointing at the Kartograph FastAPI backend.

  ## What Files Are Affected

  - **New**: `src/ui/` — entire Nuxt project scaffold (package.json, nuxt.config.ts,
    tailwind.config.ts, app.vue, components/ui/*, composables/useClipboard.ts,
    composables/useToast.ts, assets/css/globals.css with OKLCH tokens)
  - **No backend changes**.

  ## How to Verify

  ```bash
  cd src/ui && npm install && npm run dev
  # Navigate to http://localhost:3000
  # Confirm: amber/orange primary color, dark mode toggle in header,
  #          shadcn/vue Button renders with correct border-radius and shadow,
  #          copy-to-clipboard toast fires correctly.
  ```

  Unit test: `src/ui/tests/unit/design-system.test.ts` — verifies OKLCH variables
  are defined and the CVA component produces correct class combinations.

  ## Caveats

  - Tailwind CSS v4 uses CSS-first configuration. OKLCH tokens go into `globals.css`
    as CSS custom properties, NOT into `tailwind.config.ts`.
  - The Nuxt project lives at `src/ui/`, not the repo root, to stay consistent with
    the backend living at `src/api/`.
  - Dark mode class strategy: `class` (not `media`) so the toggle can override the
    system preference. Persist the preference in `localStorage`.
---
