---
task_id: task-045
round: 22
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review — User Experience (experience.spec.md)

## Branch
`hyperloop/task-045` — clean working tree, no merge conflict markers found.
The task notes say "Merge failed" but the branch as checked out is clean.

## Summary

The UI implementation is extensive and covers most spec requirements well.
However, one **blocking defect** was found in `mutations.vue`: a **duplicate
import block** for `@/components/ui/select` that will cause a TypeScript/build
error and likely cause test failures. Node modules are not installed
(`node_modules` missing), so `pnpm test` cannot run and test results cannot be
verified empirically. All other requirements are covered by both implementation
code and tests.

---

## Requirement Status

### Backend API Alignment — COVERED

- Implementation: `useIamApi.ts`, `useGraphApi.ts`, `useQueryApi.ts`,
  `useApiClient.ts` all use correct REST endpoints.
- Tests: `backend-api-alignment.test.ts` — 20+ tests covering group CRUD,
  API key CRUD (including the DELETE-not-POST guard for revoke), workspace
  parent context, tenant endpoint URLs, and reactive list refresh after
  mutations. Test also covers `api-keys.test.ts`.

### Navigation Structure — COVERED

- Implementation: `layouts/default.vue` defines four nav sections — Explore
  (Query Console, Schema Browser, Graph Explorer, Mutations Console), Data
  (Knowledge Graphs, Data Sources), Connect (API Keys, MCP Integration),
  Settings (Workspaces, Groups, Tenants). Home item and a mobile Sheet
  overlay are implemented.
- Tests: `default.layout.test.ts`, `mutations-console.test.ts`
  (navigation placement verify Mutations Console is in Explore section).
- The "new user landing" and "default landing" scenarios are partially
  addressed by `index.vue` which implements a checklist/guided flow
  including KG count, workspace check, and API key check.

### Tenant and Workspace Context — COVERED

- Implementation: `layouts/default.vue` implements a tenant selector with
  loading state, zero-tenant warning, single-tenant static display, and
  multi-tenant DropdownMenu switcher. `useTenant.ts` manages state.
  Workspace guidance toast is shown when no workspaces exist (implemented
  in `default.vue` `watch(currentTenantId, ...)` and
  `WorkspaceGuidance.vue`).
- Tests: `workspace-guidance.test.ts`, `default.layout.test.ts`.

### Knowledge Graph Creation — COVERED

- Implementation: `knowledge-graphs/index.vue` — create dialog with name,
  description, workspace selector. Creates KG under the selected workspace
  via `POST /management/workspaces/{id}/knowledge-graphs`.
- Tests: `knowledge-graphs.test.ts` covers validation, workspace selection,
  API call pattern, and "add data source" prompt after creation.

### Data Source Connection — COVERED

- Implementation: `data-sources/index.vue` — multi-step wizard: adapter
  selection (step 1), connection configuration (step 2, GitHub adapter with
  repo URL, token, auto-inferred name), credential handling (credentials
  submitted server-side via API, not stored in browser).
- Tests: `data-sources.test.ts` covers step navigation, form validation,
  credential submission flow.

### Ontology Design — COVERED

- Implementation: `data-sources/index.vue` — intent text step (step 3),
  `beginOntologyProposal()` calls `POST /management/ontology-proposals`,
  proposed node/edge types displayed for review, per-type inline editing
  (`editing`, `editLabel`, `editDescription`, `editRequired`, `editOptional`
  fields), `approveOntology()` submits approval. Re-extraction warning dialog
  implemented (`showReExtractionConfirm` state).
- Tests: `data-sources.test.ts`, `ontology-add-types.test.ts` — covers
  intent description, agent-proposed ontology, review/approval, individual
  type editing, and re-extraction confirmation.

### Sync Monitoring — COVERED

- Implementation: `data-sources/index.vue` — `SyncPhaseIndicator.vue`
  shows active sync phases, sync run history listed with status badges and
  timestamps, log viewer via `viewLogs()` / `fetchRunLogs()` calls
  `GET /management/data-sources/{id}/sync-runs/{id}/logs`, manual sync
  trigger via `triggerSync()`.
- Tests: `sync-monitoring-extended.test.ts`, `sync-logs.test.ts`,
  `sync-phase-indicator.test.ts` — cover phase labels, active vs. completed
  states, log loading, error handling.

### Get Started Querying (MCP Connection) — COVERED

- Implementation: `integrate/mcp.vue` — inline API key creation dialog,
  ready-to-paste config snippet with MCP endpoint URL and key placeholder,
  copy button via `useTransientSecret` (secret shown once and cleared on
  dismiss).
- Tests: `mcp-integration.test.ts` — covers configSecret logic,
  copy-paste snippet generation, secret-shown-once semantics.

### Query Console — COVERED

- Implementation: `query/index.vue` — CodeMirror editor with Cypher
  language (`lang-cypher`), syntax highlighting, autocomplete
  (`cypherAutocomplete`), linting (`ageCypherLinter`), query execution
  via `queryGraph()`, results table, history panel (`HistoryPanel.vue`,
  `useLocalStorage` backed), KG scope selector (resets when tenant changes
  per commit `068d78320`).
- Tests: `query-history.test.ts`, `schema-browser.test.ts` (cross-nav).

### Schema Browser — COVERED

- Implementation: `graph/schema.vue` — node/edge type listing with search
  (virtualised), type expand to show description + required/optional
  properties, cross-navigation to query console (pre-filled Cypher), graph
  explorer (type filter), and ontology editor (opens data-sources with
  `?openOntologyType=<label>`).
- Tests: `schema-browser.test.ts` — covers filtering logic, property
  display, cross-navigation URL construction, keyboard shortcut (`/`).

### Graph Explorer — COVERED

- Implementation: `graph/explorer.vue` — node search by type/slug,
  neighbor expansion via `getNodeNeighbors()`, exploration trail with
  drill-in, `CopyableText` for node IDs.
- Tests: `graph-explorer.test.ts`.

### Mutations Console — PARTIAL (blocking defect)

- Implementation: `graph/mutations.vue` — empty state with two primary
  actions (Upload File, Open Editor), drag-and-drop, four quick-start
  templates, CodeMirror editor with JSON syntax highlighting,
  `mutationAutocomplete`, `mutationLinter`, `lineNumbers`, `lintGutter`,
  Ctrl/Cmd+Enter submission, live preview via `MutationPreview.vue`,
  large-file mode (5 MB threshold), KG selector (filtered to `edit`
  permission), `MutationProgress.vue` (fixed bottom-right, persists via
  `useState` in `useMutationSubmission`), template insertion, deep-link
  (`?view=editor`, `?template=<content>`).

  **BLOCKING DEFECT**: `mutations.vue` contains a duplicate import block for
  `@/components/ui/select` (lines 21–27 and 34–40). This is a valid
  JavaScript/TypeScript syntax error that will cause the Nuxt build to fail
  and TypeScript to report an error. The duplicate was introduced when the KG
  selector feature (task-074) was added without removing the pre-existing
  Select import.

- Tests: `mutations-console.test.ts`, `mutations-kg-selector.test.ts`,
  `mutations-submission.test.ts` — comprehensive coverage. However, because
  `node_modules` is not installed, tests cannot be run to confirm they pass.

### API Key Management — COVERED

- Implementation: `api-keys/index.vue` — create key (name + expiry),
  list with status badges (active/expired/revoked), creation date, last
  used, revoke via `DELETE /iam/api-keys/{id}`.
- Tests: `api-keys.test.ts`, `backend-api-alignment.test.ts`.

### Workspace Management — COVERED

- Implementation: `workspaces/index.vue` — create workspace dialog with
  name and parent selector, member management (add/remove/change role) via
  `WorkspaceDetailPanel.vue`, responsive layout (desktop detail panel vs.
  mobile sheet).
- Tests: `workspace-management.test.ts`.

### Design Language — COVERED

- Implementation: `assets/css/main.css` — OKLCH CSS custom properties,
  primary amber `oklch(0.5768 0.2469 29.23)` light / `oklch(0.6857 0.1560
  17.57)` dark, neutral gray palette, destructive coral/red, 5-color chart
  palette. `shadcn/vue` (Reka UI) component primitives used throughout.
  Lucide Vue Next icons throughout. CVA variants in button/badge `index.ts`.
  `rounded-xl` cards, `rounded-md` buttons/inputs, `rounded-full` badges.
- Tests: `design-language.test.ts`, `design-language-extended.test.ts`,
  `design-system.test.ts`, `mutations-console.test.ts` (font-bold check).

### Interaction Principles — COVERED

- Implementation: progressive disclosure via sheets and expand patterns
  throughout. Inline editing (workspace name in `WorkspaceDetailPanel`,
  group name in `GroupDetailPanel`). `CopyableText.vue` for identifiers.
  Toast notifications via `vue-sonner` on all mutations. Ctrl/Cmd+Enter
  keyboard shortcut in query and mutations consoles. Focus ring via
  `focus-visible:ring-[3px]` throughout.
- Tests: `interaction-principles.test.ts`, `focus-ring.test.ts`.

### Responsive Design — COVERED

- Implementation: `layouts/default.vue` — `hidden md:flex` for desktop
  sidebar, Sheet overlay for mobile. `useMediaQuery('(min-width: 1024px)')`
  used in workspaces and mutations pages to switch between master-detail and
  sheet layouts.
- Tests: `responsive-design.test.ts`.

### Dark Mode — COVERED

- Implementation: `layouts/default.vue` — dark mode toggle button in header
  using `useColorMode` composable (`localStorage` persistence, `.dark` class
  on `<html>`).
- Tests: `color-mode.test.ts`.

---

## Blocking Issue

**`src/dev-ui/app/pages/graph/mutations.vue` — duplicate `Select` import**

The `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue`
components from `@/components/ui/select` are imported twice (lines 21–27 and
again at lines 34–40). This is a syntax/build error. The second block was
added when the KG selector was wired up (task-074) without removing the
first import that already existed. The fix is to remove the duplicate block
(lines 34–40).

This defect does not prevent the spec-level logic tests from passing (most
tests exercise pure utility functions, not the mounted component), but it
prevents the production build from succeeding and constitutes a broken
implementation.

**Verdict: FAIL** — due to the duplicate import causing a broken build.
All spec requirements are logically implemented and tested, but the broken
`mutations.vue` must be fixed before the branch can merge.