---
id: task-118
title: 'UI Foundation: Design System, Project Setup & Shared Utilities'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps: []
round: 0
branch: hyperloop/task-118
pr: https://github.com/openshift-hyperfleet/kartograph/pull/587
pr_title: 'feat(ui): initialize Vue.js project with design system and shared utilities'
pr_description: "## What & Why\n\nThis PR scaffolds the entire Kartograph frontend\
  \ project (`src/ui/`) from scratch,\nestablishing the design system, tooling, and\
  \ shared utility primitives that every\nsubsequent UI task will build on.\n\n##\
  \ Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n- **Requirement:\
  \ Design Language** — all five scenarios (component library, color\n  theme, typography,\
  \ border radius, elevation)\n- **Requirement: Dark Mode** — toggle in header, preference\
  \ persisted across sessions\n- **Requirement: Interaction Principles** (shared utility\
  \ layer) — toast notification\n  system, copy-to-clipboard hook, focus ring CSS\n\
  \n## Key Design Decisions\n\n- **Framework:** Vue 3 with Vite (fast HMR, TypeScript-first)\n\
  - **Component primitives:** shadcn/vue built on Reka UI; components composed\n \
  \ with Class Variance Authority (CVA) variants\n- **Icons:** Lucide Vue Next\n-\
  \ **Styling:** Tailwind CSS v4; OKLCH color tokens as CSS custom properties\n  (light\
  \ + dark modes); no custom fonts — system stack only\n- **Dark mode:** `class` strategy\
  \ via `useDark()` / VueUse; preference stored in\n  `localStorage`\n\n## Color Palette\
  \ (OKLCH CSS custom properties)\n\n| Token | Light | Dark |\n|---|---|---|\n| `--color-primary`\
  \ | `oklch(0.5768 0.2469 29.23)` | `oklch(0.6857 0.1560 17.57)` |\n| Neutral grays\
  \ | background, card, border palette | |\n| Destructive | coral/red accent | |\n\
  | Chart | 5-color (amber, blue, purple, yellow, green) | |\n\n## Typography & Shape\n\
  \n- System font stack (no custom web fonts)\n- Body: `text-sm` (0.875rem); section\
  \ headers: `text-[11px] uppercase tracking-wider`\n- Font weights: 400, 500, 600\
  \ only\n- Border radius base: `0.625rem` (10px); cards `rounded-xl`, buttons/inputs\
  \ `rounded-md`,\n  badges `rounded-full`\n- Elevation: cards `shadow-sm`, buttons\
  \ `shadow-xs`; predominantly flat UI\n\n## Shared Utilities Built in This PR\n\n\
  - **Toast system** (`useToast` composable + `<Toaster>` component) — used by all\n\
  \  write operations and copy actions across the app\n- **`useClipboard` composable**\
  \ — copy-to-clipboard with automatic toast confirmation\n- **Focus ring CSS** —\
  \ global `focus-visible:ring-3 focus-visible:ring-primary/50`;\n  native `outline-none`\
  \ suppressed\n\n## Files / Areas Affected\n\n- `src/ui/` — new directory (entire\
  \ frontend lives here)\n- `src/ui/package.json`, `vite.config.ts`, `tsconfig.json`\n\
  - `src/ui/src/assets/` — Tailwind CSS entry with OKLCH tokens\n- `src/ui/src/components/ui/`\
  \ — shadcn/vue primitives (Button, Input, Badge, Card,\n  Sheet, Toast, Toaster,\
  \ Sonner)\n- `src/ui/src/composables/useClipboard.ts`, `useToast.ts`, `useDarkMode.ts`\n\
  - `src/ui/src/lib/utils.ts` — `cn()` helper (clsx + tailwind-merge)\n\n## How to\
  \ Verify\n\n```bash\ncd src/ui && npm install && npm run dev\n# App loads; dark\
  \ mode toggle switches themes and persists across reload;\n# Storybook (if included)\
  \ shows all component variants\n```\n\n## Caveats / Follow-up\n\n- No routing or\
  \ pages in this PR — those land in task-119 (UI Shell)\n- Component library is bootstrapped\
  \ with the minimum set needed by subsequent tasks;\n  additional components added\
  \ incrementally in feature tasks"
---
