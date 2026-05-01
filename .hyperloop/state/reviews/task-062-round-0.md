---
task_id: task-062
round: 0
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review — Kartograph UI (task-062)

Branch: hyperloop/task-062
Review date: 2026-05-01
Reviewer: spec-reviewer agent

## Summary

The majority of requirements are well-covered with code and tests using the
established pattern of extracting pure functions from Vue components and testing
them with Vitest. The implementation fails on the **Mutations Console** requirement,
where the page and components are implemented but no dedicated unit tests exist for
the spec-required scenarios (empty state, JSONL editing, live preview, file upload,
submission/failure indicators, template insertion, and deep-link). The Navigation
Structure requirement is also PARTIAL because the "Mutations Console" was recently
added to the nav (task-059/task-062) and tests covering it in the navigation now
exist, but this was the outstanding gap the task was meant to close.

---

## Requirement: Backend API Alignment

**Status: COVERED**

- Code: `src/dev-ui/app/composables/api/useIamApi.ts`, `useQueryApi.ts`, `useGraphApi.ts`
  — all API operations use the documented REST endpoints with correct HTTP methods.
- Test (resource operations): `src/dev-ui/app/tests/api-keys.test.ts` lines 317-397
  — explicit endpoint URL assertions for CRUD on `/iam/api-keys`.
- Test (resource operations): `src/dev-ui/app/tests/groups.test.ts` lines 251-330
  — CRUD assertions for `/iam/groups`.
- Test (resource operations): `src/dev-ui/app/tests/workspace-management.test.ts`
  lines 659+ — create workspace endpoint and parent context.
- Test (resource operations): `src/dev-ui/app/tests/data-sources.test.ts` lines 568-660
  — response format assertions for `/management/knowledge-graphs/{id}/data-sources`
  and `/management/data-sources/{id}/sync-runs`.
- Test (parent context): `src/dev-ui/app/tests/workspace-management.test.ts` lines
  659-750 (backend alignment section) — `parent_workspace_id` passed in workspace
  creation; KG creation scoped to `POST /management/workspaces/{ws_id}/knowledge-graphs`.
- Notes: All major resource operations have endpoint-level tests with both positive
  and error paths verified.

---

## Requirement: Navigation Structure

**Status: COVERED**

- Code: `src/dev-ui/app/layouts/default.vue` lines 241-285 — `navSections` computed
  defines all four groups: Explore (Query Console, Schema Browser, Graph Explorer,
  Mutations Console), Data (Knowledge Graphs, Data Sources), Connect (API Keys, MCP
  Integration), Settings (Workspaces, Groups, Tenants).
- Test (primary navigation): `src/dev-ui/app/tests/default.layout.test.ts` lines
  86-130 — `buildNavSections()` mirrors the implementation; tests verify all four
  sections with correct items including Mutations Console.
- Test (Mutations Console in Explore): `src/dev-ui/app/tests/default.layout.test.ts`
  lines 341-371 — four dedicated tests verify Mutations Console placement, route,
  absence from other sections, and ordering within Explore.
- Test (default landing — returning users): `src/dev-ui/app/tests/index.test.ts`
  lines 53-115 — redirect logic to `/query` when KGs exist.
- Test (new user landing): `src/dev-ui/app/tests/index.test.ts` lines 176-240 —
  checklist contains KG creation step.
- Code (default landing): `src/dev-ui/app/pages/index.vue` lines 270-299 —
  sessionStorage-gated redirect to `/query` when `kgCount > 0`.

---

## Requirement: Tenant and Workspace Context

**Status: COVERED**

- Code (tenant selector): `src/dev-ui/app/layouts/default.vue` lines 354-495 —
  tenant selector in sidebar with loading, zero-tenant, single-tenant, and
  multi-tenant states; `handleTenantChange()` calls `switchTenant()`.
- Code (workspace guidance): `src/dev-ui/app/components/workspaces/WorkspaceGuidance.vue`
  — component with create/join actions.
- Code (workspace guidance on home page): `src/dev-ui/app/pages/index.vue` lines
  338-343 — `v-if="!statsLoading && !hasWorkspace"` shows guidance.
- Test (tenant selector / switching): `src/dev-ui/app/tests/default.layout.test.ts`
  — badge/tenant logic; no dedicated tenant-switch test but the fetch and reconcile
  logic is tested via `index.test.ts` workspace guidance tests.
- Test (workspace guidance): `src/dev-ui/app/tests/workspace-guidance.test.ts` —
  seven scenario groups covering: guidance shown when no workspaces, create action,
  join action, guidance hidden when workspaces exist, KG prompt suppression, dialog
  open, guidance hides after creation, and backend API alignment.
- Notes: The toast-based workspace guidance in `layouts/default.vue` (lines 170-196)
  is also tested in `index.test.ts` lines 277-353.

---

## Requirement: Knowledge Graph Creation

**Status: COVERED**

- Code: `src/dev-ui/app/pages/knowledge-graphs/index.vue` — create dialog with name,
  description, workspace selector; calls `POST /management/workspaces/{ws_id}/knowledge-graphs`.
- Test: `src/dev-ui/app/tests/knowledge-graphs.test.ts` lines 1-170 — validation
  (empty name, no workspace), API call with correct endpoint, toast on success,
  "prompted to add first data source" redirect.

---

## Requirement: Data Source Connection

**Status: COVERED**

- Code: `src/dev-ui/app/pages/data-sources/index.vue` — multi-step wizard with
  adapter selection (step 1), connection configuration (step 2), intent (step 3),
  ontology proposal (step 4). Token visibility toggle. UI states credential note:
  "Credentials are encrypted server-side using Vault and are never stored in plain text."
- Test (adapter type selection): `src/dev-ui/app/tests/data-sources.test.ts` lines
  6-38 — step 1 requires adapter selection before advancing.
- Test (connection configuration): `src/dev-ui/app/tests/data-sources.test.ts` lines
  41-113 — form validation for required fields, inferred defaults from URL.
- Test (credential handling): `src/dev-ui/app/tests/data-sources.test.ts` lines
  163-177 — token visibility toggle; the server-side encryption is enforced by the
  backend; the UI never stores tokens in localStorage or state beyond the form field.
- Notes: No explicit test asserts "plaintext never persisted" — this is implicit from
  the token never being written to localStorage/sessionStorage. The test for "Token
  Visibility" covers the toggle but not the no-persistence guarantee explicitly.
  Status is COVERED because the spec says "credentials encrypted server-side" which is
  a backend guarantee, and the UI's responsibility (not persisting) is satisfied by
  the implementation pattern.

---

## Requirement: Ontology Design

**Status: COVERED**

- Code: `src/dev-ui/app/pages/data-sources/index.vue` — intent step (step 3),
  ontology proposal with `beginOntologyProposal()` / `scanningOntology`, review
  (`approveOntology()`), individual type editing via `startEditNode/saveEditNode/
  cancelEditNode/removeNode` and corresponding edge functions.
- Code (ontology change after extraction): `src/dev-ui/app/pages/knowledge-graphs/index.vue`
  — confirmation gate before re-extraction.
- Test (intent description): `src/dev-ui/app/tests/data-sources.test.ts` lines
  115-160 — intent required to advance to ontology step.
- Test (AI proposed ontology): `src/dev-ui/app/tests/data-sources.test.ts` lines
  137-160 — `scanningOntology` set to true on advance.
- Test (review and approval): `src/dev-ui/app/tests/data-sources.test.ts` lines
  179-193 — KG selection required before approval.
- Test (individual type editing): `src/dev-ui/app/tests/data-sources.test.ts` lines
  215-565 — eight describe blocks covering startEditNode, saveEditNode, cancelEditNode,
  removeNode, startEditEdge, saveEditEdge, cancelEditEdge, removeEdge.
- Test (ontology change after extraction): `src/dev-ui/app/tests/knowledge-graphs.test.ts`
  lines 289-380 — confirmation gate describes.

---

## Requirement: Sync Monitoring

**Status: COVERED**

- Code: `src/dev-ui/app/pages/data-sources/index.vue` — sync run list, status badges,
  duration, manual trigger button, logs view with `fetchLogs()`.
- Test (active sync progress): `src/dev-ui/app/tests/sync-monitoring-extended.test.ts`
  lines 86-133 — phase labels and badge variants for all four active statuses.
- Test (sync history): `src/dev-ui/app/tests/sync-monitoring-extended.test.ts` lines
  136-230 — completed/failed runs, duration computation.
- Test (sync logs): `src/dev-ui/app/tests/knowledge-graphs.test.ts` lines 383-480 —
  log fetch from `/management/data-sources/{ds_id}/sync-runs/{run_id}/logs`, log
  panel open, clear on new run selection.
- Test (manual sync trigger): `src/dev-ui/app/tests/sync-monitoring-extended.test.ts`
  lines 72-84 — `triggerSync()` calls `POST /management/data-sources/{id}/sync`.

---

## Requirement: Get Started Querying (MCP Connection)

**Status: COVERED**

- Code: `src/dev-ui/app/pages/integrate/mcp.vue` — inline API key creation, config
  snippet generator, secret-shown-once pattern, copy-to-clipboard.
- Test (API key creation inline): `src/dev-ui/app/tests/mcp-integration.test.ts`
  lines 122-196 — no-keys prompt, validation, creation.
- Test (copy-paste connection command): `src/dev-ui/app/tests/mcp-integration.test.ts`
  lines 69-119 — snippet contains endpoint URL and API key.
- Test (secret shown once): `src/dev-ui/app/tests/mcp-integration.test.ts` lines
  199-342 — dismissSecret clears newlyCreatedKey; tenant switch clears secret.

---

## Requirement: Query Console

**Status: COVERED**

- Code: `src/dev-ui/app/pages/query/index.vue` — CodeMirror with Cypher language,
  autocomplete, linting, results table, history, KG scope selector, Ctrl/Cmd+Enter.
- Test (query editing): `src/dev-ui/app/tests/query-history.test.ts` lines 392-428
  — cypher language extension, autocomplete extension both tested for correct type.
- Test (query execution): `src/dev-ui/app/tests/query-history.test.ts` lines
  190-274 — execution result shape, row count, execution time.
- Test (query history): `src/dev-ui/app/tests/query-history.test.ts` lines 22-188
  — addToHistory, deduplication, MAX_HISTORY cap, localStorage persistence.
- Test (knowledge graph context): `src/dev-ui/app/tests/query-history.test.ts`
  lines 276-314 and `src/dev-ui/app/tests/knowledge-graphs.test.ts` lines 488-607 —
  scope selector label, unscoped spans all KGs.
- Test (Ctrl/Cmd+Enter): `src/dev-ui/app/tests/query-history.test.ts` lines 316-375
  — keyboard shortcut triggers execute.

---

## Requirement: Schema Browser

**Status: COVERED**

- Code: `src/dev-ui/app/pages/graph/schema.vue` — type listing with search/filter,
  type detail with expand, cross-navigation to query console and graph explorer.
- Test (type listing): `src/dev-ui/app/tests/schema-browser.test.ts` lines 27-100
  — filteredLabels() with search query matching label name or properties.
- Test (type detail): `src/dev-ui/app/tests/schema-browser.test.ts` lines 100-160
  — required/optional properties expansion.
- Test (cross-navigation): `src/dev-ui/app/tests/schema-browser.test.ts` lines
  48-100 — buildQueryNavigation(), buildExplorerNavigation().

---

## Requirement: Graph Explorer

**Status: COVERED**

- Code: `src/dev-ui/app/pages/graph/explorer.vue` — node search by type/name/slug,
  neighbor traversal via Cytoscape.
- Test (node search): `src/dev-ui/app/tests/graph-explorer.test.ts` — search by
  type, name, slug; Cypher escaping, node transformation.
- Test (neighbor exploration): `src/dev-ui/app/tests/graph-explorer.test.ts` —
  edge traversal and neighbor drill-in.

---

## Requirement: Mutations Console

**Status: PARTIAL**

- Code: `src/dev-ui/app/pages/graph/mutations.vue` (845 lines) — full implementation
  including:
  - Empty state with two primary actions (upload file, open editor), quick-start
    templates, drag-and-drop support.
  - JSONL editing with CodeMirror, JSON syntax highlighting, line numbers,
    JSONL-aware linting, autocomplete, Ctrl/Cmd+Enter submits.
  - Live preview via MutationPreview component with DEFINE/CREATE/UPDATE/DELETE
    breakdown, validation warnings.
  - File upload: `handleFileUpload()` with `LARGE_FILE_THRESHOLD` (5MB) activating
    large-file mode via `useMutationWorker`.
  - Submission via `useMutationSubmission` composable.
  - Floating progress indicator in `src/dev-ui/app/app.vue` (MutationProgress fixed
    bottom-right, persists across navigation, can be dismissed).
  - Template insertion: `insertTemplate()` appends to existing content; editor
    activated. Templates in quick-start list and MutationTemplates component.
  - Deep-link: `?view=editor` initializes `showEditor` to true (line 106);
    `?template=<content>` processed in `onMounted` (lines 386-389).

- Test (navigation): `src/dev-ui/app/tests/default.layout.test.ts` lines 341-371 —
  Mutations Console appears in Explore nav group. This is the ONLY test file that
  tests Mutations Console behavior.

- **Missing tests** — no test file covers the following spec scenarios:
  - Empty state: two primary actions (upload file, open editor), quick-start
    templates, drag-and-drop.
  - JSONL editing: CodeMirror extension configuration (linting, autocomplete,
    line numbers — unlike Query Console which tests its extensions in
    query-history.test.ts, there is no equivalent for the mutation editor).
  - Live preview: operation count by type (DEFINE/CREATE/UPDATE/DELETE),
    validation warnings, parse errors inline.
  - File upload: file loaded into editor, >5MB large-file mode activation.
  - Submission: mutations submitted to API; floating indicator status/count/elapsed;
    persists when navigating away; minimize/dismiss.
  - Submission failure: error in floating indicator; operations applied count.
  - Template insertion: appended to existing content, editor activated.
  - Deep-link: `?view=editor` initializes editor, `?template=<content>` inserts.

- Notes: The `useMutationSubmission`, `useMutationWorker`, `useMutationEditorState`
  composables, `MutationProgress`, `MutationPreview`, `MutationTemplates`, and
  `mutationParser.ts` / `mutationLinter.ts` / `mutationAutocomplete.ts` utilities
  all lack unit tests. The spec has eight named scenarios for Mutations Console and
  only the navigation placement scenario has a test.

---

## Requirement: API Key Management

**Status: COVERED**

- Code: `src/dev-ui/app/pages/api-keys/index.vue` — create, list, revoke UI.
- Test: `src/dev-ui/app/tests/api-keys.test.ts` — full coverage of create validation,
  secret shown once, status computation, revoke with confirmation, list filtering,
  backend endpoint alignment.

---

## Requirement: Workspace Management

**Status: COVERED**

- Code: `src/dev-ui/app/pages/workspaces/index.vue` — workspace tree, create dialog
  with optional parent, member management panel.
- Test: `src/dev-ui/app/tests/workspace-management.test.ts` (41KB) — tree building,
  flatten, create with name/parent validation, member add/remove/role-change,
  backend endpoint assertions.

---

## Requirement: Design Language

**Status: COVERED**

- Code: `src/dev-ui/app/assets/css/main.css` — OKLCH custom properties, amber primary,
  5-color chart palette, border radius base 0.625rem, cards rounded-xl,
  buttons/inputs rounded-md, badges rounded-full, shadow-sm/shadow-xs.
- Code: `src/dev-ui/app/components/ui/button/index.ts`, `badge/index.ts`,
  `card/Card.vue`, `input/Input.vue` — CVA-based variant definitions.
- Test: `src/dev-ui/app/tests/design-language.test.ts` — color theme, typography,
  border radius, elevation.
- Test: `src/dev-ui/app/tests/design-language-extended.test.ts` — chart palette,
  typography details.
- Test: `src/dev-ui/app/tests/design-system.test.ts` — shadcn/vue (reka-ui), CVA,
  lucide-vue-next dependency verification via package.json.

---

## Requirement: Interaction Principles

**Status: COVERED**

- Code: Multiple pages implement copy-to-clipboard with toast, inline editing (side
  panels, WorkspaceDetailPanel), mutation feedback via vue-sonner toast.
- Code: `useCodemirror.ts`, `useModifierKeys.ts` — Ctrl/Cmd+Enter keyboard shortcuts.
- Code: `src/dev-ui/app/components/ui/copyable-text/CopyableText.vue` — reusable
  copy button.
- Test: `src/dev-ui/app/tests/interaction-principles.test.ts` — copy-to-clipboard
  with toast, mutation feedback (toast success/failure), inline actions, progressive
  disclosure.
- Test: `src/dev-ui/app/tests/focus-ring.test.ts` — 3px focus ring in primary color
  at 50% opacity, no ring-2 usage.

---

## Requirement: Responsive Design

**Status: COVERED**

- Code: `src/dev-ui/app/layouts/default.vue` — `hidden md:flex` sidebar, Sheet
  overlay for mobile, `useSidebar` composable with `isCollapsed` / `isMobileOpen`.
- Test: `src/dev-ui/app/tests/responsive-design.test.ts` — sidebar visibility
  (hidden md:flex), collapsible width (w-16/w-64), mobile Sheet open/close,
  sheet closes on route change.

---

## Requirement: Dark Mode

**Status: COVERED**

- Code: `src/dev-ui/app/composables/useColorMode.ts` — localStorage persistence,
  classList.add('dark'), system preference fallback.
- Code: `src/dev-ui/app/layouts/default.vue` lines 833-844 — toggle button in header
  with Sun/Moon icons and accessible tooltip.
- Test: `src/dev-ui/app/tests/color-mode.test.ts` — toggle/persistence, initial load
  from localStorage, system preference fallback, CSS class application.
- Test: `src/dev-ui/app/tests/color-mode.test.ts` lines 201-272 — toggle present in
  header, located inside `<header>`, imports `useColorMode`, classList.add, localStorage.

---

## Verdict: FAIL

The single failing requirement is **Mutations Console**. The implementation is
complete and sophisticated, but none of the eight spec scenarios (empty state, JSONL
editing, live preview, file upload, submission, submission failure, template insertion,
deep-link) have corresponding unit tests. Every other requirement has both code and
test coverage meeting the spec's SHALL-level scenarios.

To pass, unit tests must be added covering the Mutations Console scenarios, following
the established pattern of extracting pure logic from composables/utilities and testing
them with Vitest (e.g. test `mutationParser.ts`, `mutationLinter.ts`,
`useMutationSubmission`, `useMutationEditorState`, `useMutationWorker` logic functions,
and the `?view=editor` / `?template=` deep-link initialization).