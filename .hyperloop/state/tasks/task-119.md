---
id: task-119
title: "UI Shell: Navigation, Routing & Tenant Context"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add app shell with sidebar navigation, routing, and tenant selector"
pr_description: |
  ## What & Why

  Implements the persistent application shell: the sidebar navigation (grouped by
  user goal), Vue Router configuration, tenant selector, and the smart landing-page
  logic that sends returning users to the Query Console and new users to a setup prompt.

  This PR depends on task-118 (design system / project scaffold) and is the
  foundation for every feature page that follows.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Navigation Structure** — all three scenarios (primary navigation
    groups, returning-user default landing, new-user setup prompt)
  - **Requirement: Tenant and Workspace Context** — tenant selector (switches tenant,
    refreshes all data), workspace guidance when no personal workspace exists
  - **Requirement: Responsive Design** — collapsible sidebar on desktop,
    sheet overlay on narrow screens; layouts adapt to single-column on mobile/tablet

  ## Navigation Structure

  Sidebar groups (per spec):
  | Group | Items |
  |---|---|
  | **Explore** | Query Console, Schema Browser, Graph Explorer, Mutations Console |
  | **Data** | Knowledge Graphs, Data Sources (with sync status badge) |
  | **Connect** | API Keys, MCP Integration |
  | **Settings** | Workspaces, Groups, Tenants |

  Section headers: `text-[11px] uppercase tracking-wider` (design language spec).

  ## Tenant Selector

  - Placed in the sidebar (below the logo / above navigation groups)
  - Fetches the user's tenants from `GET /iam/tenants` (or derived from JWT claims)
  - Selecting a different tenant triggers a full data refresh (invalidate all queries,
    re-navigate to landing page)
  - Users belonging to a single tenant see a static label (no dropdown)

  ## Landing Page Logic

  On authenticated app load:
  1. Fetch the user's knowledge graphs (`GET /management/knowledge-graphs`)
  2. If ≥ 1 result → redirect to `/explore/query` (Query Console)
  3. If 0 results → render a "Get Started" hero prompt to create the first knowledge
     graph (links to `/data/knowledge-graphs/new`)

  ## Workspace Guidance

  When a user enters a tenant for the first time and has no personal workspace,
  display an inline callout in the sidebar or landing page suggesting they create
  one or join an existing team workspace.

  ## Responsive Layout

  - `lg:` breakpoint: sidebar is rendered as a persistent column (collapsible to
    icon-only rail via toggle button)
  - Below `lg:`: sidebar is hidden; hamburger opens it as a `<Sheet>` overlay

  ## Files / Areas Affected

  - `src/ui/src/router/index.ts` — Vue Router configuration with all route definitions
    (lazy-loaded per section)
  - `src/ui/src/layouts/AppShell.vue` — root layout with sidebar + main content slot
  - `src/ui/src/components/navigation/Sidebar.vue` — grouped nav items, active state
  - `src/ui/src/components/navigation/TenantSelector.vue`
  - `src/ui/src/components/navigation/WorkspaceGuidance.vue`
  - `src/ui/src/pages/LandingPage.vue` — smart redirect / new-user hero

  ## How to Verify

  1. Log in; if KGs exist → lands on `/explore/query`
  2. Log in with no KGs → lands on setup prompt with CTA
  3. Resize browser to < 1024px → sidebar collapses to sheet; hamburger visible
  4. Switch tenant in sidebar selector → page refreshes with new tenant's data

  ## Caveats / Follow-up

  - Feature pages (Query Console, KG management, etc.) are stubs in this PR —
    implemented in tasks 120–129
  - Workspace guidance appears as a static callout; workspace creation is wired in
    task-127
---
