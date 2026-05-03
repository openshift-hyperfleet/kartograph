---
id: task-119
title: UI Navigation Structure & Routing
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add sidebar navigation structure and route scaffolding"
pr_description: |
  ## What and Why

  Populates the collapsible sidebar (built in task-118) with the four goal-oriented
  navigation groups and wires up Vue Router. This is the prerequisite for every
  feature page — nothing can be routed to without it.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Navigation Structure** from
  `specs/ui/experience.spec.md`.

  Specifically:
  - Sidebar groups: **Explore** (Query Console, Schema Browser, Graph Explorer,
    Mutations Console), **Data** (Knowledge Graphs, Data Sources with sync status
    badge), **Connect** (API Keys, MCP Integration), **Settings** (Workspaces,
    Groups, Tenants)
  - **Default landing for returning users**: user with existing knowledge graphs
    lands on the Explore section (Query Console or dashboard)
  - **New user landing**: user with no knowledge graphs is guided toward creating
    their first KG (setup prompt / empty state message with CTA button)

  The "returning vs. new user" detection calls `GET /api/management/knowledge-graphs`
  on app load and branches based on whether the response is empty.

  ## Design Decisions

  - Navigation items are defined in a typed constant (`NAV_ITEMS`) so the sidebar
    renders from data, not hard-coded markup — easier to extend.
  - Route guards check auth on every navigation; unauthenticated users are
    redirected to the login page.
  - The new-user landing state is a route-level decision: if the KG list is empty
    the router redirects to `/setup` which renders a welcome/onboarding prompt.
  - Keyboard shortcut `/` focuses the sidebar search (where applicable) — baked
    into the sidebar component per interaction principles.

  ## Files / Areas Affected

  - `src/ui/router/index.ts` — Vue Router with all top-level route definitions
  - `src/ui/router/guards.ts` — auth guard, new-user redirect guard
  - `src/ui/components/AppSidebar.vue` — populated with nav groups and items
  - `src/ui/pages/` — stub page components for each nav destination
  - `src/ui/composables/useAuthUser.ts` — current authenticated user + KG count check

  ## How to Verify

  1. Navigate to each sidebar item — correct route renders
  2. With an empty KG list (new user): landing redirects to `/setup` with onboarding CTA
  3. With existing KGs (returning user): landing goes to `/explore/query`
  4. Sidebar active state highlights current route
  5. Keyboard `/` shortcut opens sidebar search focus (if search is present)

  ## Caveats

  Page components are stubs only (showing placeholder text). Actual page content
  is implemented in subsequent tasks. The sidebar's Data Sources items show a sync
  status badge placeholder that will be wired up in task-122.
---
