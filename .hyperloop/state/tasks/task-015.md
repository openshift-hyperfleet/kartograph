---
id: task-015
title: Implement UI — knowledge graph management, data sources, and sync monitoring
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
  - task-014
  - task-008
  - task-009
  - task-040
  - task-041
  - task-042
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Knowledge Graph Creation** — `specs/ui/experience.spec.md`:

1. **Create knowledge graph** — User provides name and description; the KG is created
   within the currently selected workspace (workspace selector required); after creation
   the user is prompted to add their first data source.

   Note: the workspace-selector bug and wrong endpoint are fixed by task-040. This task
   verifies the complete creation UX end-to-end works after task-040 lands.

**Requirement: Data Source Connection** — all 3 scenarios:

2. **Adapter type selection** — Wizard step 1: user selects an adapter (e.g., GitHub);
   form adapts to show adapter-specific fields. Additional adapter types (GitLab, Jira)
   are listed as "coming soon" placeholders.

3. **Connection configuration** — Wizard step 2: user provides repo URL and token;
   data source name is inferred from the repo URL when left blank.

4. **Credential handling** — Token is masked in the UI (show/hide toggle); transmitted
   only over HTTPS to the backend; never stored in `localStorage` or query strings.
   The backend stores credentials encrypted via Vault (backend concern, UI must not
   persist the token after the wizard closes).

**Requirement: Sync Monitoring** — all 4 scenarios:

5. **Active sync progress** — Per-data-source badge shows current phase label
   (Pending / Ingesting / Extracting / Applying). Progress indicator is shown for
   in-progress phases. Note: phase label and status type fixes are in task-042.

6. **Sync history** — Expandable list of sync runs with status, timestamps, and
   duration. Note: response format fix is in task-041.

7. **Sync logs** — "View Logs" action on a sync run opens a sheet/panel with detailed
   log lines for that run.

8. **Manual sync trigger** — "Sync Now" button on a data source (for users with manage
   permission) starts a new sync run and refreshes the data source's sync status.

## Acceptance Criteria

- Knowledge graph creation dialog includes a workspace selector; the Create button is
  disabled until both a name and a workspace are selected (task-040 delivers this;
  task-015 validates integration and UX polish).
- KG list refreshes after creation without a full page reload.
- Data source wizard completes steps 1–2 and calls the correct backend endpoint:
  `POST /management/knowledge-graphs/{kg_id}/data-sources` with valid body.
- Token field shows a show/hide toggle; token is never stored in component state after
  the wizard is dismissed.
- Data source list renders correctly from the backend's direct array response
  (task-041 delivers this; task-015 confirms end-to-end correctness).
- Sync run history renders per-run status badges using human-readable labels (task-042
  delivers this; task-015 confirms integration).
- Manual sync trigger calls `POST /management/data-sources/{ds_id}/sync` and displays
  a success/error toast.
- Log viewer opens in a side panel and displays log lines from
  `GET /management/data-sources/{ds_id}/sync-runs/{run_id}/logs`.
- All mutations (create KG, create data source, trigger sync) show toast feedback.
- All tests are written before implementation (TDD). Tests live in:
  - `src/dev-ui/app/tests/knowledge-graphs.test.ts`
  - `src/dev-ui/app/tests/data-sources.test.ts`
  - `src/dev-ui/app/tests/sync-monitoring.test.ts`

## UI Location

- Knowledge graphs: `src/dev-ui/app/pages/knowledge-graphs/index.vue`
- Data sources + sync monitoring: `src/dev-ui/app/pages/data-sources/index.vue`
- Ontology design flow (wizard step 3): covered by task-043.

## Dependencies

- **task-014** must be complete (design system and navigation scaffold exist).
- **task-008** must be complete (data source backend: create/list endpoints exist).
- **task-009** must be complete (sync run backend: list/trigger endpoints exist).
- **task-040** must be complete (KG creation workspace bug fixed).
- **task-041** must be complete (data source list and sync run response format fixed).
- **task-042** must be complete (sync phase status types and labels corrected).

## TDD Cycle

1. Write tests in the test files above (they will fail initially).
2. Implement or extend components to pass tests.
3. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
4. Commit atomically per conventional commit conventions.
