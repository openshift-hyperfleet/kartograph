---
id: task-140
title: "UI Application Shell — sidebar navigation, tenant context, responsive layout"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-139]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add application shell with sidebar navigation and tenant context"
pr_description: |
  ## What and Why

  With the design system foundation in place (task-139), this task builds the
  persistent application shell that every page lives inside. The shell provides:
  the sidebar with goal-oriented navigation groups, the tenant selector for
  multi-tenant users, responsive collapse behaviour (sheet overlay on narrow
  screens), default-vs-new-user landing logic, and the interaction infrastructure
  that every feature page reuses (keyboard shortcuts, focus rings, mutation toasts).

  Without the shell, no feature page can be rendered in context.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Navigation Structure — Scenario: Primary navigation**
    Sidebar groups: Explore (Query Console, Schema Browser, Graph Explorer, Mutations Console),
    Data (Knowledge Graphs, Data Sources with sync status), Connect (API Keys, MCP Integration),
    Settings (Workspaces, Groups, Tenants).

  - **Requirement: Navigation Structure — Scenario: Default landing**
    Returning users with existing KGs land on Explore (Query Console).

  - **Requirement: Navigation Structure — Scenario: New user landing**
    Users with no KGs are directed toward the KG creation setup flow.

  - **Requirement: Tenant and Workspace Context — Scenario: Tenant selector**
    Multi-tenant users see a tenant selector in the sidebar; switching refreshes all data.

  - **Requirement: Tenant and Workspace Context — Scenario: Workspace guidance**
    New-to-tenant users without a personal workspace see a prompt to create or join one.

  - **Requirement: Responsive Design — Scenario: Desktop layout**
    Sidebar visible and collapsible; multi-column content layout.

  - **Requirement: Responsive Design — Scenario: Tablet/mobile layout**
    Sidebar collapses to a sheet overlay; single-column layouts.

  - **Requirement: Interaction Principles — Scenario: Keyboard shortcuts**
    `/` key focuses global search; discoverable via tooltip.

  - **Requirement: Interaction Principles — Scenario: Mutation feedback**
    Toast notification composable available to all child pages.

  - **Requirement: Interaction Principles — Scenario: Progressive disclosure**
    Summary-first pattern: sidebar shows section labels, detail on drill-in.

  - **Requirement: Interaction Principles — Scenario: Inline actions over navigation**
    Resource editing happens in side panels (Sheet), not separate pages.

  - **Requirement: Backend API Alignment — Scenario: Parent context is preserved**
    Every page that renders workspace-scoped resources reads the active workspace
    from the tenant context store and passes it as a query param or path segment.

  ## Key Design Decisions

  - **Composable: `useTenantContext`** — reactive store (Pinia) holding `tenantId`,
    `workspaceId`, and the authenticated user. Populated at app init from the JWT
    claims; updated on tenant switch. All pages read from this store.
  - **Shell layout**: `layouts/default.vue` with `<AppSidebar>` + `<slot>` (content).
  - **Sidebar component**: `components/AppSidebar.vue` — uses `NavigationMenu` from
    shadcn/vue, section headers (`text-[11px] uppercase tracking-wider`), icon links
    via Lucide Vue Next.
  - **Tenant selector**: dropdown in the sidebar footer reading from `useTenantContext`.
    Switching tenant calls `GET /tenants` and reloads the page state.
  - **Responsive**: Tailwind `lg:` breakpoint; below `lg`, sidebar is a Sheet (shadcn).
    A hamburger button in the top bar toggles it.
  - **Landing logic**: `middleware/landing.ts` reads whether the user has any KGs
    (`GET /workspaces/{id}/knowledge-graphs`) and redirects accordingly.

  ## What Files Are Affected

  - **New**: `src/ui/layouts/default.vue`
  - **New**: `src/ui/components/AppSidebar.vue`
  - **New**: `src/ui/components/AppHeader.vue`
  - **New**: `src/ui/components/TenantSelector.vue`
  - **New**: `src/ui/stores/tenantContext.ts` (Pinia store)
  - **New**: `src/ui/middleware/landing.ts`
  - **New**: `src/ui/pages/index.vue` (redirect to /explore/query or /setup)
  - **New**: `src/ui/tests/unit/AppSidebar.test.ts`
  - **New**: `src/ui/tests/unit/useTenantContext.test.ts`

  ## How to Verify

  ```bash
  cd src/ui && npm run dev
  # Check: sidebar renders four sections (Explore, Data, Connect, Settings)
  # Resize to tablet width: sidebar becomes sheet overlay
  # Switch tenant: page data refreshes
  # New user (no KGs): redirected to /setup
  # Returning user (has KGs): lands on /explore/query
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit
  # AppSidebar renders correct section labels and navigation links
  # useTenantContext: tenant switch emits reload signal
  # landing middleware: new-user vs returning-user redirect
  ```

  ## Caveats

  - The tenant list comes from `GET /tenants` (IAM context). Users who belong to a
    single tenant will not see the selector (only show when `tenants.length > 1`).
  - Workspace selection within a tenant is a secondary concern handled in the workspace
    guidance prompt; the primary ambient context is tenant only.
  - The Groups and Tenants links in Settings are placeholders until task-151 is done.
---
