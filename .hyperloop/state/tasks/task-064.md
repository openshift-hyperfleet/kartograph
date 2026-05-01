---
id: task-064
title: Data sources — animated progress indicator for active sync phases
spec_ref: specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3
status: in_progress
phase: verify
deps:
- task-041
- task-042
round: 0
branch: hyperloop/task-064
pr: https://github.com/openshift-hyperfleet/kartograph/pull/526
pr_title: 'feat(ui): add animated phase progress indicator for active data source
  sync runs'
pr_description: "## What & Why\n\nThe Sync Monitoring spec requires \"a progress indicator\
  \ **appropriate to the current\nphase**\" when a data source sync is in progress.\
  \ The existing implementation shows a\nstatic status Badge (e.g., `Ingesting`, `Extracting`)\
  \ but provides no animated or\nvisual progress cue to communicate that work is actively\
  \ happening.\n\nWithout an animated indicator, a user watching a long sync run cannot\
  \ distinguish\n\"the sync is paused / stuck\" from \"the sync is actively running\"\
  \ — both show the same\nstatic badge. An animated spinner or pulsing indicator gives\
  \ immediate visual\nconfirmation that the system is working.\n\n## Spec Requirements\
  \ Satisfied\n\n**Requirement: Sync Monitoring — Scenario: Active sync progress**\n\
  > GIVEN a data source with a sync in progress\n> WHEN the user views the data source\n\
  > THEN they see the current sync status (ingesting, extracting, applying)\n> AND\
  \ **a progress indicator appropriate to the current phase**\n\nThe \"a progress\
  \ indicator appropriate to the current phase\" requirement is not satisfied\nby\
  \ a static badge alone. Each active phase should have a distinct visual treatment.\n\
  \n## Key Design Decisions\n\n- **Phase-appropriate indicators:**\n  - `pending`\
  \ — subtle pulsing dot (waiting for a worker)\n  - `ingesting` — spinner with a\
  \ network/download icon (reading from external source)\n  - `ai_extracting` — spinner\
  \ with a sparkles/brain icon (AI processing)\n  - `applying` — progress pulse with\
  \ a database icon (writing to graph)\n- Indicators appear **inline** on the sync\
  \ run row in the history list, replacing (or\n  augmenting) the status badge for\
  \ active phases. Completed and failed runs keep the\n  existing badge-only display.\n\
  - The Kartograph design language is used throughout: Lucide icons, Tailwind `animate-spin`\n\
  \  / `animate-pulse`, OKLCH primary color tokens.\n- A `SyncPhaseIndicator.vue`\
  \ component encapsulates the logic so it can be reused if\n  sync status appears\
  \ elsewhere (e.g., the data source card header badge in the nav layout).\n\n## Files\
  \ Affected\n\n- `src/dev-ui/app/components/graph/SyncPhaseIndicator.vue` — new component\
  \ (TDD-first).\n  Props: `status: SyncRun['status']`. Renders the appropriate animated\
  \ indicator.\n- `src/dev-ui/app/pages/data-sources/index.vue` — replace the inline\
  \ Badge in the sync\n  history rows with `<SyncPhaseIndicator :status=\"run.status\"\
  \ />` for active phases;\n  keep the static Badge for completed/failed.\n- `src/dev-ui/app/tests/sync-phase-indicator.test.ts`\
  \ — new test file (TDD-first).\n\n## How to Verify\n\n1. Navigate to Data Sources\
  \ with at least one data source that has an active sync run\n   (status `ingesting`,\
  \ `ai_extracting`, or `applying`).\n2. The sync run row shows an animated spinner\
  \ (or phase-appropriate animation) next to\n   the phase label.\n3. A completed\
  \ run shows only the static Badge, no spinner.\n4. A failed run shows only the destructive\
  \ Badge, no spinner.\n5. Run `cd src/dev-ui && pnpm test` — all tests in `sync-phase-indicator.test.ts`\
  \ pass.\n6. Run tests from `sync-monitoring-extended.test.ts` — no regressions.\n\
  \n## Caveats\n\n- Depends on task-041 (fixes data source API response format) so\
  \ sync runs are populated\n  correctly, and task-042 (fixes status type values)\
  \ so the status strings match.\n- The indicator is purely visual — no polling is\
  \ added by this task. Polling (for\n  real-time status updates) is a separate concern\
  \ and a potential future task.\n- The `SyncPhaseIndicator` component must handle\
  \ the `undefined`/`null` run case\n  gracefully (data source with no sync runs yet\
  \ shows nothing)."
---
