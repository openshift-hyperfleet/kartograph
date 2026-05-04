---
id: task-140
title: UI Application Shell — sidebar navigation, tenant context, responsive layout
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps:
- task-139
round: 0
branch: hyperloop/task-140
pr: https://github.com/openshift-hyperfleet/kartograph/pull/611
pr_title: 'feat(ui): add application shell with sidebar navigation and tenant context'
pr_description: "## What and Why\n\nWith the design system foundation in place (task-139),\
  \ this task builds the\npersistent application shell that every page lives inside.\
  \ The shell provides:\nthe sidebar with goal-oriented navigation groups, the tenant\
  \ selector for\nmulti-tenant users, responsive collapse behaviour (sheet overlay\
  \ on narrow\nscreens), default-vs-new-user landing logic, and the interaction infrastructure\n\
  that every feature page reuses (keyboard shortcuts, focus rings, mutation toasts).\n\
  \nWithout the shell, no feature page can be rendered in context.\n\n## Spec Requirements\
  \ Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Navigation Structure — Scenario: Primary navigation**\n  Sidebar\
  \ groups: Explore (Query Console, Schema Browser, Graph Explorer, Mutations Console),\n\
  \  Data (Knowledge Graphs, Data Sources with sync status), Connect (API Keys, MCP\
  \ Integration),\n  Settings (Workspaces, Groups, Tenants).\n\n- **Requirement: Navigation\
  \ Structure — Scenario: Default landing**\n  Returning users with existing KGs land\
  \ on Explore (Query Console).\n\n- **Requirement: Navigation Structure — Scenario:\
  \ New user landing**\n  Users with no KGs are directed toward the KG creation setup\
  \ flow.\n\n- **Requirement: Tenant and Workspace Context — Scenario: Tenant selector**\n\
  \  Multi-tenant users see a tenant selector in the sidebar; switching refreshes\
  \ all data.\n\n- **Requirement: Tenant and Workspace Context — Scenario: Workspace\
  \ guidance**\n  New-to-tenant users without a personal workspace see a prompt to\
  \ create or join one.\n\n- **Requirement: Responsive Design — Scenario: Desktop\
  \ layout**\n  Sidebar visible and collapsible; multi-column content layout.\n\n\
  - **Requirement: Responsive Design — Scenario: Tablet/mobile layout**\n  Sidebar\
  \ collapses to a sheet overlay; single-column layouts.\n\n- **Requirement: Interaction\
  \ Principles — Scenario: Keyboard shortcuts**\n  `/` key focuses global search;\
  \ discoverable via tooltip.\n\n- **Requirement: Interaction Principles — Scenario:\
  \ Mutation feedback**\n  Toast notification composable available to all child pages.\n\
  \n- **Requirement: Interaction Principles — Scenario: Progressive disclosure**\n\
  \  Summary-first pattern: sidebar shows section labels, detail on drill-in.\n\n\
  - **Requirement: Interaction Principles — Scenario: Inline actions over navigation**\n\
  \  Resource editing happens in side panels (Sheet), not separate pages.\n\n- **Requirement:\
  \ Backend API Alignment — Scenario: Parent context is preserved**\n  Every page\
  \ that renders workspace-scoped resources reads the active workspace\n  from the\
  \ tenant context store and passes it as a query param or path segment.\n\n## Key\
  \ Design Decisions\n\n- **Composable: `useTenantContext`** — reactive store (Pinia)\
  \ holding `tenantId`,\n  `workspaceId`, and the authenticated user. Populated at\
  \ app init from the JWT\n  claims; updated on tenant switch. All pages read from\
  \ this store.\n- **Shell layout**: `layouts/default.vue` with `<AppSidebar>` + `<slot>`\
  \ (content).\n- **Sidebar component**: `components/AppSidebar.vue` — uses `NavigationMenu`\
  \ from\n  shadcn/vue, section headers (`text-[11px] uppercase tracking-wider`),\
  \ icon links\n  via Lucide Vue Next.\n- **Tenant selector**: dropdown in the sidebar\
  \ footer reading from `useTenantContext`.\n  Switching tenant calls `GET /tenants`\
  \ and reloads the page state.\n- **Responsive**: Tailwind `lg:` breakpoint; below\
  \ `lg`, sidebar is a Sheet (shadcn).\n  A hamburger button in the top bar toggles\
  \ it.\n- **Landing logic**: `middleware/landing.ts` reads whether the user has any\
  \ KGs\n  (`GET /workspaces/{id}/knowledge-graphs`) and redirects accordingly.\n\n\
  ## What Files Are Affected\n\n- **New**: `src/ui/layouts/default.vue`\n- **New**:\
  \ `src/ui/components/AppSidebar.vue`\n- **New**: `src/ui/components/AppHeader.vue`\n\
  - **New**: `src/ui/components/TenantSelector.vue`\n- **New**: `src/ui/stores/tenantContext.ts`\
  \ (Pinia store)\n- **New**: `src/ui/middleware/landing.ts`\n- **New**: `src/ui/pages/index.vue`\
  \ (redirect to /explore/query or /setup)\n- **New**: `src/ui/tests/unit/AppSidebar.test.ts`\n\
  - **New**: `src/ui/tests/unit/useTenantContext.test.ts`\n\n## How to Verify\n\n\
  ```bash\ncd src/ui && npm run dev\n# Check: sidebar renders four sections (Explore,\
  \ Data, Connect, Settings)\n# Resize to tablet width: sidebar becomes sheet overlay\n\
  # Switch tenant: page data refreshes\n# New user (no KGs): redirected to /setup\n\
  # Returning user (has KGs): lands on /explore/query\n```\n\nUnit tests:\n```bash\n\
  cd src/ui && npm run test:unit\n# AppSidebar renders correct section labels and\
  \ navigation links\n# useTenantContext: tenant switch emits reload signal\n# landing\
  \ middleware: new-user vs returning-user redirect\n```\n\n## Caveats\n\n- The tenant\
  \ list comes from `GET /tenants` (IAM context). Users who belong to a\n  single\
  \ tenant will not see the selector (only show when `tenants.length > 1`).\n- Workspace\
  \ selection within a tenant is a secondary concern handled in the workspace\n  guidance\
  \ prompt; the primary ambient context is tenant only.\n- The Groups and Tenants\
  \ links in Settings are placeholders until task-151 is done."
---
