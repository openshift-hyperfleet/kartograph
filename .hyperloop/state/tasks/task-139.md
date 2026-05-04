---
id: task-139
title: UI Foundation — Vue/Nuxt project init with design system
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps: []
round: 1
branch: hyperloop/task-139
pr: https://github.com/openshift-hyperfleet/kartograph/pull/609
pr_title: 'feat(ui): initialize Vue/Nuxt project with design system foundation'
pr_description: "## What and Why\n\nThis task bootstraps the Kartograph frontend from\
  \ scratch. There is currently no\n`src/ui/` directory — the only frontend artifact\
  \ is `demo-web/`, a static HTML\nprototype that does not use a component framework.\
  \ The UI spec\n(`specs/ui/experience.spec.md`) requires a production-grade Vue application\
  \ using\nshadcn/vue (Reka UI) primitives, Tailwind CSS, OKLCH color tokens, and\
  \ dark mode\nsupport. Every subsequent UI task depends on this foundation being\
  \ in place.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Design Language — Scenario: Component library**\n  \"uses shadcn/vue\
  \ (Reka UI) primitives with Tailwind CSS; variants via CVA; icons via Lucide Vue\
  \ Next\"\n\n- **Requirement: Design Language — Scenario: Color theme**\n  \"colors\
  \ are defined as OKLCH CSS custom properties; primary/brand is warm amber/orange\n\
  \  (oklch(0.5768 0.2469 29.23) light, oklch(0.6857 0.1560 17.57) dark); neutral\
  \ grays for\n  background/card/border; destructive coral/red accent; 5-color chart\
  \ palette\"\n\n- **Requirement: Design Language — Scenario: Typography**\n  \"system\
  \ font stack; body text-sm (0.875rem); section headers uppercase text-[11px]\n \
  \ tracking-wider; font weights limited to 400, 500, 600\"\n\n- **Requirement: Design\
  \ Language — Scenario: Border radius**\n  \"base 0.625rem (10px); cards rounded-xl;\
  \ buttons/inputs rounded-md; badges rounded-full\"\n\n- **Requirement: Design Language\
  \ — Scenario: Elevation**\n  \"cards shadow-sm; buttons shadow-xs; predominantly\
  \ flat\"\n\n- **Requirement: Dark Mode — Scenario: Toggle**\n  \"dark mode toggle\
  \ in header; preference persists across sessions\"\n\n- **Requirement: Interaction\
  \ Principles — Scenario: Focus indicators**\n  \"3px ring in primary color at 50%\
  \ opacity; native outlines suppressed\"\n\n- **Requirement: Interaction Principles\
  \ — Scenario: Copy-to-clipboard**\n  \"copy button present; toast confirms action\"\
  \ (base infrastructure for the composable)\n\n- **Requirement: Interaction Principles\
  \ — Scenario: Mutation feedback**\n  \"toast notification confirms success or reports\
  \ failure\" (base toast component)\n\n## Key Design Decisions\n\n- **Framework**:\
  \ Nuxt 3 (Vue 3) for SSR capability and file-based routing, housed in `src/ui/`.\n\
  - **UI primitives**: `shadcn-vue` (Reka UI) — install via the shadcn-vue CLI.\n\
  - **Styling**: Tailwind CSS v4 with CSS custom property tokens (not Tailwind config\n\
  \  color values) for OKLCH support.\n- **Icons**: `lucide-vue-next` — tree-shakable,\
  \ consistent set.\n- **Variant utility**: `class-variance-authority` (CVA) for component\
  \ variants.\n- **Dark mode**: Managed via `@nuxtjs/color-mode` with a system-font\
  \ stack.\n- **API integration**: Nuxt's `useFetch` / `$fetch` wired to `NUXT_PUBLIC_API_BASE_URL`\n\
  \  env var pointing at the Kartograph FastAPI backend.\n\n## What Files Are Affected\n\
  \n- **New**: `src/ui/` — entire Nuxt project scaffold (package.json, nuxt.config.ts,\n\
  \  tailwind.config.ts, app.vue, components/ui/*, composables/useClipboard.ts,\n\
  \  composables/useToast.ts, assets/css/globals.css with OKLCH tokens)\n- **No backend\
  \ changes**.\n\n## How to Verify\n\n```bash\ncd src/ui && npm install && npm run\
  \ dev\n# Navigate to http://localhost:3000\n# Confirm: amber/orange primary color,\
  \ dark mode toggle in header,\n#          shadcn/vue Button renders with correct\
  \ border-radius and shadow,\n#          copy-to-clipboard toast fires correctly.\n\
  ```\n\nUnit test: `src/ui/tests/unit/design-system.test.ts` — verifies OKLCH variables\n\
  are defined and the CVA component produces correct class combinations.\n\n## Caveats\n\
  \n- Tailwind CSS v4 uses CSS-first configuration. OKLCH tokens go into `globals.css`\n\
  \  as CSS custom properties, NOT into `tailwind.config.ts`.\n- The Nuxt project\
  \ lives at `src/ui/`, not the repo root, to stay consistent with\n  the backend\
  \ living at `src/api/`.\n- Dark mode class strategy: `class` (not `media`) so the\
  \ toggle can override the\n  system preference. Persist the preference in `localStorage`."
---
