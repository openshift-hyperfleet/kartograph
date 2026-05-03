---
id: task-102
title: "Reorganize sidebar navigation into Explore/Data/Connect/Settings sections with tenant selector"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): reorganize sidebar into Explore/Data/Connect/Settings navigation sections"
pr_description: |
  ## What & Why

  The **Navigation Structure** requirement in `specs/ui/experience.spec.md` mandates
  that the sidebar groups links by user goals, not internal architecture:

  > "the sidebar presents navigation grouped as:
  > - **Explore** — Query Console, Schema Browser, Graph Explorer, Mutations Console
  > - **Data** — Knowledge Graphs, Data Sources (with sync status)
  > - **Connect** — API Keys, MCP Integration
  > - **Settings** — Workspaces, Groups, Tenants"

  The current sidebar (`src/dev-ui/app/layouts/`) presents a flat or differently
  organized list. This task restructures the navigation to match the spec's
  goal-oriented groupings and implements the tenant selector behavior.

  The **Tenant and Workspace Context** requirement also specifies:

  > "a tenant selector is available in the sidebar AND switching tenants refreshes
  > all data in the UI"

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Navigation Structure** — Scenario: *Primary navigation*
  - **Requirement: Tenant and Workspace Context** — Scenario: *Tenant selector*

  ## What This Change Does

  ### Sidebar Layout Refactor

  Update the layout component (likely `src/dev-ui/app/layouts/default.vue` or
  equivalent) to group navigation items under labeled sections:

  ```
  [Explore]
    Query Console   → /query
    Schema Browser  → /graph/schema
    Graph Explorer  → /graph/explorer
    Mutations       → /graph/mutations

  [Data]
    Knowledge Graphs → /knowledge-graphs
    Data Sources     → /data-sources   (show active sync indicator badge if any in progress)

  [Connect]
    API Keys        → /api-keys
    MCP Integration → /integrate/mcp

  [Settings]
    Workspaces      → /workspaces
    Groups          → /groups
    Tenants         → /tenants
  ```

  Section headers use the established design pattern: `text-[11px] uppercase tracking-wider`
  (muted/secondary color). Active link state uses the primary amber accent.

  ### Tenant Selector

  Add (or wire up) a tenant selector component at the top or bottom of the sidebar.
  Requirements:
  - Only visible when the authenticated user belongs to more than one tenant.
  - Selecting a tenant sets the active tenant in global state (composable or Pinia store).
  - After switching, all data-fetching composables must re-trigger (invalidate cached
    queries / reactive state bound to the tenant ID).
  - The selected tenant ID must be included in subsequent API requests via the
    `X-Tenant-ID` header.

  ### Data Source Sync Indicator

  The "Data Sources" nav item should show a subtle badge or pulsing dot when any
  data source has a sync in progress (active status). This is the "with sync status"
  requirement from the spec.

  ## Files / Areas Affected

  - `src/dev-ui/app/layouts/default.vue` (or equivalent layout) — primary sidebar restructure
  - `src/dev-ui/app/components/` — new `NavSection.vue` component for labeled groups
  - `src/dev-ui/app/composables/useTenantContext.ts` (or similar) — tenant switching logic
  - `src/dev-ui/app/components/TenantSelector.vue` — tenant selector dropdown (new or update)
  - Existing page navigation links updated to new paths if any changed

  ## Tests

  Vitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:
  - `test_sidebar_groups_match_spec`: mount the layout, assert all four section
    headers exist (Explore, Data, Connect, Settings) with the correct child links
  - `test_tenant_selector_hidden_single_tenant`: mock user with one tenant,
    assert selector not rendered
  - `test_tenant_selector_visible_multiple_tenants`: mock user with two tenants,
    assert selector is rendered
  - `test_tenant_switch_invalidates_data`: select a different tenant, assert
    reactive data composables emit new fetch calls with the updated tenant ID

  ## How to Verify

  1. Start the dev environment: `make dev` or `make instance-up`
  2. Open the UI and confirm the sidebar shows four labeled sections in order
  3. Verify each link navigates to the correct page
  4. If the test user has multiple tenants, confirm the tenant selector appears
     and switching updates the active tenant header

  ## Caveats

  - The Data Source sync indicator requires polling or a reactive status source;
    if the Ingestion context is not yet implemented, show a static placeholder and
    skip the live sync badge until Ingestion is ready.
  - This task intentionally excludes new-user landing logic (handled in task-103)
    and ontology-related navigation (blocked on Extraction context).
  - Keep the sidebar collapsible on desktop and ensure it collapses to a sheet
    overlay on narrow screens (existing responsive behavior must be preserved).
---
