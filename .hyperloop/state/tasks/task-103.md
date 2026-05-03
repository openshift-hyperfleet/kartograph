---
id: task-103
title: "New-user onboarding: empty-state landing and workspace guidance for first-time users"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-102]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add new-user empty-state landing and workspace guidance flow"
pr_description: |
  ## What & Why

  Two spec requirements address how the UI handles first-time and returning users:

  **Navigation Structure — New user landing:**
  > "GIVEN a user with no knowledge graphs WHEN they open Kartograph THEN they are
  > guided toward the setup flow with a prompt to create their first knowledge graph"

  **Tenant and Workspace Context — Workspace guidance:**
  > "GIVEN a user entering a tenant for the first time WHEN no personal workspace
  > exists THEN the UI suggests creating one or joining an existing team workspace"

  Currently the app shows the same layout to all users regardless of setup state.
  First-time users land in an empty explorer with no guidance on what to do next.

  This task adds onboarding-aware behavior to the default landing experience.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Navigation Structure** — Scenario: *New user landing*
  - **Requirement: Navigation Structure** — Scenario: *Default landing* (returning user)
  - **Requirement: Tenant and Workspace Context** — Scenario: *Workspace guidance*

  ## What This Change Does

  ### Returning User (existing KGs)

  When the user navigates to `/` or `/query` and has at least one accessible
  knowledge graph, the existing behavior is preserved: land on the Query Console.

  This case requires no code changes beyond confirming the existing default route
  is `/query`.

  ### New User (no KGs)

  When the user navigates to `/` and has zero accessible knowledge graphs:

  1. Redirect or render an **onboarding landing page** (could be the home dashboard
     `/` or an explicit `/welcome` route).
  2. The landing page shows a hero prompt:
     - **Heading:** "Welcome to Kartograph"
     - **Subtext:** "Create your first knowledge graph to start connecting your data."
     - **Primary CTA:** "Create Knowledge Graph →" → navigates to `/knowledge-graphs`
       with the creation dialog open
  3. The sidebar is still visible (per task-102), allowing manual navigation.

  Detection: check `GET /management/knowledge-graphs` (or a cached reactive state)
  at startup. If the response is an empty list, trigger the onboarding redirect.

  ### No Workspace Guidance

  After a successful tenant switch or on first visit to a tenant, check whether the
  user has a personal workspace:
  - Call `GET /iam/workspaces` and filter workspaces where the user is a direct member.
  - If none exist, show an inline **guidance banner** (dismissable, not a blocking modal)
    below the tenant selector in the sidebar:
    - "You don't have a personal workspace yet."
    - Two actions: **"Create Workspace"** → opens workspace creation dialog,
      **"Browse Workspaces"** → navigates to `/workspaces`
  - Once dismissed (stored in `localStorage` keyed by tenant ID), do not show again.

  ## Files / Areas Affected

  - `src/dev-ui/app/pages/index.vue` — onboarding redirect logic or welcome page
  - `src/dev-ui/app/layouts/default.vue` — workspace guidance banner (near tenant selector)
  - `src/dev-ui/app/composables/useOnboardingState.ts` (new) — reactive state tracking
    whether user has KGs and workspaces; drives guidance UI
  - `src/dev-ui/app/components/WorkspaceGuidanceBanner.vue` (new) — sidebar guidance banner
  - `src/dev-ui/app/components/OnboardingLanding.vue` (new) — welcome hero content

  ## Tests

  Vitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:
  - `test_returning_user_lands_on_query_console`: mock non-empty KG list,
    assert the root route renders the query console (or redirects to `/query`)
  - `test_new_user_lands_on_onboarding`: mock empty KG list, assert welcome
    content and "Create Knowledge Graph" CTA are rendered on `/`
  - `test_new_user_cta_navigates_to_kg_creation`: click "Create Knowledge Graph →",
    assert router push to `/knowledge-graphs` with creation dialog state
  - `test_workspace_guidance_shown_when_no_workspaces`: mock empty workspace list,
    assert guidance banner visible in layout
  - `test_workspace_guidance_dismissed_and_hidden`: click dismiss, assert banner
    hidden; simulate page reload (check localStorage key) and assert banner stays hidden

  ## How to Verify

  1. Start the dev environment: `make dev`
  2. Log in with a user who has no knowledge graphs — confirm onboarding landing appears
  3. Click "Create Knowledge Graph →" — confirm the creation flow opens
  4. Create a KG — confirm the user is no longer sent to onboarding on next visit
  5. Log in with a user who has no workspace — confirm the workspace guidance banner
     appears in the sidebar
  6. Dismiss the banner — confirm it disappears and stays dismissed on reload

  ## Caveats

  - The KG list check calls `GET /management/knowledge-graphs` which is scoped to
    the active tenant. If the user has KGs in another tenant, the new-user flow
    still applies for the current tenant.
  - Workspace guidance uses `localStorage` for dismissal state; clearing storage
    resets the banner. This is acceptable UX.
  - This task depends on task-102 (sidebar restructure) because the workspace
    guidance banner lives within the sidebar component.
  - Do NOT implement the full knowledge graph creation wizard here — that is handled
    in `src/dev-ui/app/pages/knowledge-graphs/index.vue`. This task only adds the
    navigation trigger and landing page.
---
