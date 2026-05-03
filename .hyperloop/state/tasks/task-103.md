---
id: task-103
title: 'New-user onboarding: empty-state landing and workspace guidance for first-time
  users'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps:
- task-102
round: 0
branch: hyperloop/task-103
pr: https://github.com/openshift-hyperfleet/kartograph/pull/575
pr_title: 'feat(ui): add new-user empty-state landing and workspace guidance flow'
pr_description: "## What & Why\n\nTwo spec requirements address how the UI handles\
  \ first-time and returning users:\n\n**Navigation Structure — New user landing:**\n\
  > \"GIVEN a user with no knowledge graphs WHEN they open Kartograph THEN they are\n\
  > guided toward the setup flow with a prompt to create their first knowledge graph\"\
  \n\n**Tenant and Workspace Context — Workspace guidance:**\n> \"GIVEN a user entering\
  \ a tenant for the first time WHEN no personal workspace\n> exists THEN the UI suggests\
  \ creating one or joining an existing team workspace\"\n\nCurrently the app shows\
  \ the same layout to all users regardless of setup state.\nFirst-time users land\
  \ in an empty explorer with no guidance on what to do next.\n\nThis task adds onboarding-aware\
  \ behavior to the default landing experience.\n\n## Spec Requirements Satisfied\n\
  \n`specs/ui/experience.spec.md`:\n- **Requirement: Navigation Structure** — Scenario:\
  \ *New user landing*\n- **Requirement: Navigation Structure** — Scenario: *Default\
  \ landing* (returning user)\n- **Requirement: Tenant and Workspace Context** — Scenario:\
  \ *Workspace guidance*\n\n## What This Change Does\n\n### Returning User (existing\
  \ KGs)\n\nWhen the user navigates to `/` or `/query` and has at least one accessible\n\
  knowledge graph, the existing behavior is preserved: land on the Query Console.\n\
  \nThis case requires no code changes beyond confirming the existing default route\n\
  is `/query`.\n\n### New User (no KGs)\n\nWhen the user navigates to `/` and has\
  \ zero accessible knowledge graphs:\n\n1. Redirect or render an **onboarding landing\
  \ page** (could be the home dashboard\n   `/` or an explicit `/welcome` route).\n\
  2. The landing page shows a hero prompt:\n   - **Heading:** \"Welcome to Kartograph\"\
  \n   - **Subtext:** \"Create your first knowledge graph to start connecting your\
  \ data.\"\n   - **Primary CTA:** \"Create Knowledge Graph →\" → navigates to `/knowledge-graphs`\n\
  \     with the creation dialog open\n3. The sidebar is still visible (per task-102),\
  \ allowing manual navigation.\n\nDetection: check `GET /management/knowledge-graphs`\
  \ (or a cached reactive state)\nat startup. If the response is an empty list, trigger\
  \ the onboarding redirect.\n\n### No Workspace Guidance\n\nAfter a successful tenant\
  \ switch or on first visit to a tenant, check whether the\nuser has a personal workspace:\n\
  - Call `GET /iam/workspaces` and filter workspaces where the user is a direct member.\n\
  - If none exist, show an inline **guidance banner** (dismissable, not a blocking\
  \ modal)\n  below the tenant selector in the sidebar:\n  - \"You don't have a personal\
  \ workspace yet.\"\n  - Two actions: **\"Create Workspace\"** → opens workspace\
  \ creation dialog,\n    **\"Browse Workspaces\"** → navigates to `/workspaces`\n\
  - Once dismissed (stored in `localStorage` keyed by tenant ID), do not show again.\n\
  \n## Files / Areas Affected\n\n- `src/dev-ui/app/pages/index.vue` — onboarding redirect\
  \ logic or welcome page\n- `src/dev-ui/app/layouts/default.vue` — workspace guidance\
  \ banner (near tenant selector)\n- `src/dev-ui/app/composables/useOnboardingState.ts`\
  \ (new) — reactive state tracking\n  whether user has KGs and workspaces; drives\
  \ guidance UI\n- `src/dev-ui/app/components/WorkspaceGuidanceBanner.vue` (new) —\
  \ sidebar guidance banner\n- `src/dev-ui/app/components/OnboardingLanding.vue` (new)\
  \ — welcome hero content\n\n## Tests\n\nVitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:\n\
  - `test_returning_user_lands_on_query_console`: mock non-empty KG list,\n  assert\
  \ the root route renders the query console (or redirects to `/query`)\n- `test_new_user_lands_on_onboarding`:\
  \ mock empty KG list, assert welcome\n  content and \"Create Knowledge Graph\" CTA\
  \ are rendered on `/`\n- `test_new_user_cta_navigates_to_kg_creation`: click \"\
  Create Knowledge Graph →\",\n  assert router push to `/knowledge-graphs` with creation\
  \ dialog state\n- `test_workspace_guidance_shown_when_no_workspaces`: mock empty\
  \ workspace list,\n  assert guidance banner visible in layout\n- `test_workspace_guidance_dismissed_and_hidden`:\
  \ click dismiss, assert banner\n  hidden; simulate page reload (check localStorage\
  \ key) and assert banner stays hidden\n\n## How to Verify\n\n1. Start the dev environment:\
  \ `make dev`\n2. Log in with a user who has no knowledge graphs — confirm onboarding\
  \ landing appears\n3. Click \"Create Knowledge Graph →\" — confirm the creation\
  \ flow opens\n4. Create a KG — confirm the user is no longer sent to onboarding\
  \ on next visit\n5. Log in with a user who has no workspace — confirm the workspace\
  \ guidance banner\n   appears in the sidebar\n6. Dismiss the banner — confirm it\
  \ disappears and stays dismissed on reload\n\n## Caveats\n\n- The KG list check\
  \ calls `GET /management/knowledge-graphs` which is scoped to\n  the active tenant.\
  \ If the user has KGs in another tenant, the new-user flow\n  still applies for\
  \ the current tenant.\n- Workspace guidance uses `localStorage` for dismissal state;\
  \ clearing storage\n  resets the banner. This is acceptable UX.\n- This task depends\
  \ on task-102 (sidebar restructure) because the workspace\n  guidance banner lives\
  \ within the sidebar component.\n- Do NOT implement the full knowledge graph creation\
  \ wizard here — that is handled\n  in `src/dev-ui/app/pages/knowledge-graphs/index.vue`.\
  \ This task only adds the\n  navigation trigger and landing page."
---
