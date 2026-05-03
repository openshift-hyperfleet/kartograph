---
id: task-118
title: "UI Foundation: Design System, Project Setup & Shared Utilities"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): initialize Vue.js project with design system and shared utilities"
pr_description: |
  ## What & Why

  This PR scaffolds the entire Kartograph frontend project (`src/ui/`) from scratch,
  establishing the design system, tooling, and shared utility primitives that every
  subsequent UI task will build on.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Design Language** — all five scenarios (component library, color
    theme, typography, border radius, elevation)
  - **Requirement: Dark Mode** — toggle in header, preference persisted across sessions
  - **Requirement: Interaction Principles** (shared utility layer) — toast notification
    system, copy-to-clipboard hook, focus ring CSS

  ## Key Design Decisions

  - **Framework:** Vue 3 with Vite (fast HMR, TypeScript-first)
  - **Component primitives:** shadcn/vue built on Reka UI; components composed
    with Class Variance Authority (CVA) variants
  - **Icons:** Lucide Vue Next
  - **Styling:** Tailwind CSS v4; OKLCH color tokens as CSS custom properties
    (light + dark modes); no custom fonts — system stack only
  - **Dark mode:** `class` strategy via `useDark()` / VueUse; preference stored in
    `localStorage`

  ## Color Palette (OKLCH CSS custom properties)

  | Token | Light | Dark |
  |---|---|---|
  | `--color-primary` | `oklch(0.5768 0.2469 29.23)` | `oklch(0.6857 0.1560 17.57)` |
  | Neutral grays | background, card, border palette | |
  | Destructive | coral/red accent | |
  | Chart | 5-color (amber, blue, purple, yellow, green) | |

  ## Typography & Shape

  - System font stack (no custom web fonts)
  - Body: `text-sm` (0.875rem); section headers: `text-[11px] uppercase tracking-wider`
  - Font weights: 400, 500, 600 only
  - Border radius base: `0.625rem` (10px); cards `rounded-xl`, buttons/inputs `rounded-md`,
    badges `rounded-full`
  - Elevation: cards `shadow-sm`, buttons `shadow-xs`; predominantly flat UI

  ## Shared Utilities Built in This PR

  - **Toast system** (`useToast` composable + `<Toaster>` component) — used by all
    write operations and copy actions across the app
  - **`useClipboard` composable** — copy-to-clipboard with automatic toast confirmation
  - **Focus ring CSS** — global `focus-visible:ring-3 focus-visible:ring-primary/50`;
    native `outline-none` suppressed

  ## Files / Areas Affected

  - `src/ui/` — new directory (entire frontend lives here)
  - `src/ui/package.json`, `vite.config.ts`, `tsconfig.json`
  - `src/ui/src/assets/` — Tailwind CSS entry with OKLCH tokens
  - `src/ui/src/components/ui/` — shadcn/vue primitives (Button, Input, Badge, Card,
    Sheet, Toast, Toaster, Sonner)
  - `src/ui/src/composables/useClipboard.ts`, `useToast.ts`, `useDarkMode.ts`
  - `src/ui/src/lib/utils.ts` — `cn()` helper (clsx + tailwind-merge)

  ## How to Verify

  ```bash
  cd src/ui && npm install && npm run dev
  # App loads; dark mode toggle switches themes and persists across reload;
  # Storybook (if included) shows all component variants
  ```

  ## Caveats / Follow-up

  - No routing or pages in this PR — those land in task-119 (UI Shell)
  - Component library is bootstrapped with the minimum set needed by subsequent tasks;
    additional components added incrementally in feature tasks
---
