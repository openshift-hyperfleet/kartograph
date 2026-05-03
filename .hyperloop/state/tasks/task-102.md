---
id: task-102
title: Reorganize sidebar navigation into Explore/Data/Connect/Settings sections with
  tenant selector
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps: []
round: 0
branch: hyperloop/task-102
pr: https://github.com/openshift-hyperfleet/kartograph/pull/568
pr_title: 'feat(ui): reorganize sidebar into Explore/Data/Connect/Settings navigation
  sections'
pr_description: "## What & Why\n\nThe **Navigation Structure** requirement in `specs/ui/experience.spec.md`\
  \ mandates\nthat the sidebar groups links by user goals, not internal architecture:\n\
  \n> \"the sidebar presents navigation grouped as:\n> - **Explore** — Query Console,\
  \ Schema Browser, Graph Explorer, Mutations Console\n> - **Data** — Knowledge Graphs,\
  \ Data Sources (with sync status)\n> - **Connect** — API Keys, MCP Integration\n\
  > - **Settings** — Workspaces, Groups, Tenants\"\n\nThe current sidebar (`src/dev-ui/app/layouts/`)\
  \ presents a flat or differently\norganized list. This task restructures the navigation\
  \ to match the spec's\ngoal-oriented groupings and implements the tenant selector\
  \ behavior.\n\nThe **Tenant and Workspace Context** requirement also specifies:\n\
  \n> \"a tenant selector is available in the sidebar AND switching tenants refreshes\n\
  > all data in the UI\"\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n\
  - **Requirement: Navigation Structure** — Scenario: *Primary navigation*\n- **Requirement:\
  \ Tenant and Workspace Context** — Scenario: *Tenant selector*\n\n## What This Change\
  \ Does\n\n### Sidebar Layout Refactor\n\nUpdate the layout component (likely `src/dev-ui/app/layouts/default.vue`\
  \ or\nequivalent) to group navigation items under labeled sections:\n\n```\n[Explore]\n\
  \  Query Console   → /query\n  Schema Browser  → /graph/schema\n  Graph Explorer\
  \  → /graph/explorer\n  Mutations       → /graph/mutations\n\n[Data]\n  Knowledge\
  \ Graphs → /knowledge-graphs\n  Data Sources     → /data-sources   (show active\
  \ sync indicator badge if any in progress)\n\n[Connect]\n  API Keys        → /api-keys\n\
  \  MCP Integration → /integrate/mcp\n\n[Settings]\n  Workspaces      → /workspaces\n\
  \  Groups          → /groups\n  Tenants         → /tenants\n```\n\nSection headers\
  \ use the established design pattern: `text-[11px] uppercase tracking-wider`\n(muted/secondary\
  \ color). Active link state uses the primary amber accent.\n\n### Tenant Selector\n\
  \nAdd (or wire up) a tenant selector component at the top or bottom of the sidebar.\n\
  Requirements:\n- Only visible when the authenticated user belongs to more than one\
  \ tenant.\n- Selecting a tenant sets the active tenant in global state (composable\
  \ or Pinia store).\n- After switching, all data-fetching composables must re-trigger\
  \ (invalidate cached\n  queries / reactive state bound to the tenant ID).\n- The\
  \ selected tenant ID must be included in subsequent API requests via the\n  `X-Tenant-ID`\
  \ header.\n\n### Data Source Sync Indicator\n\nThe \"Data Sources\" nav item should\
  \ show a subtle badge or pulsing dot when any\ndata source has a sync in progress\
  \ (active status). This is the \"with sync status\"\nrequirement from the spec.\n\
  \n## Files / Areas Affected\n\n- `src/dev-ui/app/layouts/default.vue` (or equivalent\
  \ layout) — primary sidebar restructure\n- `src/dev-ui/app/components/` — new `NavSection.vue`\
  \ component for labeled groups\n- `src/dev-ui/app/composables/useTenantContext.ts`\
  \ (or similar) — tenant switching logic\n- `src/dev-ui/app/components/TenantSelector.vue`\
  \ — tenant selector dropdown (new or update)\n- Existing page navigation links updated\
  \ to new paths if any changed\n\n## Tests\n\nVitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:\n\
  - `test_sidebar_groups_match_spec`: mount the layout, assert all four section\n\
  \  headers exist (Explore, Data, Connect, Settings) with the correct child links\n\
  - `test_tenant_selector_hidden_single_tenant`: mock user with one tenant,\n  assert\
  \ selector not rendered\n- `test_tenant_selector_visible_multiple_tenants`: mock\
  \ user with two tenants,\n  assert selector is rendered\n- `test_tenant_switch_invalidates_data`:\
  \ select a different tenant, assert\n  reactive data composables emit new fetch\
  \ calls with the updated tenant ID\n\n## How to Verify\n\n1. Start the dev environment:\
  \ `make dev` or `make instance-up`\n2. Open the UI and confirm the sidebar shows\
  \ four labeled sections in order\n3. Verify each link navigates to the correct page\n\
  4. If the test user has multiple tenants, confirm the tenant selector appears\n\
  \   and switching updates the active tenant header\n\n## Caveats\n\n- The Data Source\
  \ sync indicator requires polling or a reactive status source;\n  if the Ingestion\
  \ context is not yet implemented, show a static placeholder and\n  skip the live\
  \ sync badge until Ingestion is ready.\n- This task intentionally excludes new-user\
  \ landing logic (handled in task-103)\n  and ontology-related navigation (blocked\
  \ on Extraction context).\n- Keep the sidebar collapsible on desktop and ensure\
  \ it collapses to a sheet\n  overlay on narrow screens (existing responsive behavior\
  \ must be preserved)."
---
