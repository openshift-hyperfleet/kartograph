---
id: task-119
title: 'UI Shell: Navigation, Routing & Tenant Context'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-118
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add app shell with sidebar navigation, routing, and tenant selector'
pr_description: "## What & Why\n\nImplements the persistent application shell: the\
  \ sidebar navigation (grouped by\nuser goal), Vue Router configuration, tenant selector,\
  \ and the smart landing-page\nlogic that sends returning users to the Query Console\
  \ and new users to a setup prompt.\n\nThis PR depends on task-118 (design system\
  \ / project scaffold) and is the\nfoundation for every feature page that follows.\n\
  \n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n- **Requirement:\
  \ Navigation Structure** — all three scenarios (primary navigation\n  groups, returning-user\
  \ default landing, new-user setup prompt)\n- **Requirement: Tenant and Workspace\
  \ Context** — tenant selector (switches tenant,\n  refreshes all data), workspace\
  \ guidance when no personal workspace exists\n- **Requirement: Responsive Design**\
  \ — collapsible sidebar on desktop,\n  sheet overlay on narrow screens; layouts\
  \ adapt to single-column on mobile/tablet\n\n## Navigation Structure\n\nSidebar\
  \ groups (per spec):\n| Group | Items |\n|---|---|\n| **Explore** | Query Console,\
  \ Schema Browser, Graph Explorer, Mutations Console |\n| **Data** | Knowledge Graphs,\
  \ Data Sources (with sync status badge) |\n| **Connect** | API Keys, MCP Integration\
  \ |\n| **Settings** | Workspaces, Groups, Tenants |\n\nSection headers: `text-[11px]\
  \ uppercase tracking-wider` (design language spec).\n\n## Tenant Selector\n\n- Placed\
  \ in the sidebar (below the logo / above navigation groups)\n- Fetches the user's\
  \ tenants from `GET /iam/tenants` (or derived from JWT claims)\n- Selecting a different\
  \ tenant triggers a full data refresh (invalidate all queries,\n  re-navigate to\
  \ landing page)\n- Users belonging to a single tenant see a static label (no dropdown)\n\
  \n## Landing Page Logic\n\nOn authenticated app load:\n1. Fetch the user's knowledge\
  \ graphs (`GET /management/knowledge-graphs`)\n2. If ≥ 1 result → redirect to `/explore/query`\
  \ (Query Console)\n3. If 0 results → render a \"Get Started\" hero prompt to create\
  \ the first knowledge\n   graph (links to `/data/knowledge-graphs/new`)\n\n## Workspace\
  \ Guidance\n\nWhen a user enters a tenant for the first time and has no personal\
  \ workspace,\ndisplay an inline callout in the sidebar or landing page suggesting\
  \ they create\none or join an existing team workspace.\n\n## Responsive Layout\n\
  \n- `lg:` breakpoint: sidebar is rendered as a persistent column (collapsible to\n\
  \  icon-only rail via toggle button)\n- Below `lg:`: sidebar is hidden; hamburger\
  \ opens it as a `<Sheet>` overlay\n\n## Files / Areas Affected\n\n- `src/ui/src/router/index.ts`\
  \ — Vue Router configuration with all route definitions\n  (lazy-loaded per section)\n\
  - `src/ui/src/layouts/AppShell.vue` — root layout with sidebar + main content slot\n\
  - `src/ui/src/components/navigation/Sidebar.vue` — grouped nav items, active state\n\
  - `src/ui/src/components/navigation/TenantSelector.vue`\n- `src/ui/src/components/navigation/WorkspaceGuidance.vue`\n\
  - `src/ui/src/pages/LandingPage.vue` — smart redirect / new-user hero\n\n## How\
  \ to Verify\n\n1. Log in; if KGs exist → lands on `/explore/query`\n2. Log in with\
  \ no KGs → lands on setup prompt with CTA\n3. Resize browser to < 1024px → sidebar\
  \ collapses to sheet; hamburger visible\n4. Switch tenant in sidebar selector →\
  \ page refreshes with new tenant's data\n\n## Caveats / Follow-up\n\n- Feature pages\
  \ (Query Console, KG management, etc.) are stubs in this PR —\n  implemented in\
  \ tasks 120–129\n- Workspace guidance appears as a static callout; workspace creation\
  \ is wired in\n  task-127"
---
