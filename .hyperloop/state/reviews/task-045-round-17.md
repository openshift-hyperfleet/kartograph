---
task_id: task-045
round: 17
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — experience.spec.md

### Test Suite Status

All 913 unit tests pass across 26 test files (`src/dev-ui/app/tests/`). The
`check-frontend-scenario-labels.sh` check reports 60/60 scenario labels covered.

However, one scenario label passes the string-match check while the underlying
test asserts on an inadequate proxy — see the FAIL below.

---

### Requirements Status:

#### Requirement: Backend API Alignment
- Status: COVERED
- Implementation: `src/dev-ui/app/composables/api/useIamApi.ts`, `useGraphApi.ts`, `useQueryApi.ts`; reactive list refresh after all mutations.
- Tests: `src/dev-ui/app/tests/backend-api-alignment.test.ts` (57 tests); guards correct endpoint URLs, HTTP methods, and list-refresh pattern.

#### Requirement: Navigation Structure
- Status: COVERED
- Implementation: `src/dev-ui/app/layouts/default.vue` lines 241–284 — four nav sections (Explore: Query Console, Schema Browser, Graph Explorer, Mutations Console; Data: Knowledge Graphs, Data Sources; Connect: API Keys, MCP Integration; Settings: Workspaces, Groups, Tenants).
- Tests: `src/dev-ui/app/tests/default.layout.test.ts`

#### Requirement: Tenant and Workspace Context
- Status: COVERED
- Implementation: Tenant selector in `default.vue` (multi-tenant dropdown, single-tenant static display, zero-tenant warning); workspace guidance toast in `default.vue` lines 172–196.
- Tests: `src/dev-ui/app/tests/workspace-guidance.test.ts`

#### Requirement: Knowledge Graph Creation
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/knowledge-graphs/index.vue`; workspace-scoped creation with name/description.
- Tests: `src/dev-ui/app/tests/knowledge-graphs.test.ts`

#### Requirement: Data Source Connection
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/data-sources/index.vue`; adapter type selection, connection config, credentials sent server-side (never persisted in browser).
- Tests: `src/dev-ui/app/tests/data-sources.test.ts`

#### Requirement: Ontology Design
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/data-sources/index.vue` (intent description, agent-proposed ontology via `POST /management/data-sources/{id}/propose-ontology`, review/approval flow, individual type editing including add/remove). Backend endpoint: `src/api/management/presentation/data_sources/routes.py`. Ontology add-types: `src/dev-ui/app/tests/ontology-add-types.test.ts`.
- Tests: `src/dev-ui/app/tests/ontology-add-types.test.ts`, `data-sources.test.ts`

#### Requirement: Sync Monitoring
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/data-sources/index.vue`; active sync progress with phase indicator, sync history, sync logs viewer, manual sync trigger. `src/dev-ui/app/components/graph/SyncPhaseIndicator.vue`.
- Tests: `src/dev-ui/app/tests/sync-monitoring-extended.test.ts`, `sync-logs.test.ts`, `sync-phase-indicator.test.ts`

#### Requirement: Get Started Querying (MCP Connection)
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/integrate/mcp.vue`; inline API key creation prompt, copy-paste config snippet, secret shown once via `useTransientSecret`.
- Tests: `src/dev-ui/app/tests/mcp-integration.test.ts`

#### Requirement: Query Console
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/query/index.vue`; Cypher editor with syntax highlighting/autocomplete/linting, Ctrl/Cmd+Enter execution, results table with row count and execution time, history panel, KG scope selector (`selectedKgId` at line 73; when unscoped queries span all accessible KGs).
- Tests: `src/dev-ui/app/tests/query-history.test.ts`

#### Requirement: Schema Browser
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/graph/schema.vue`; type listing with search/filter, type detail (description, required/optional properties), cross-navigation links.
- Tests: `src/dev-ui/app/tests/schema-browser.test.ts`

#### Requirement: Graph Explorer
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/graph/explorer.vue`; node search by type/name/slug, neighbor exploration with labels and direction.
- Tests: `src/dev-ui/app/tests/graph-explorer.test.ts`

#### Requirement: Mutations Console — Scenario: Knowledge graph selection
- Status: MISSING (FAIL)
- Spec: "a knowledge graph selector is displayed before the user can submit"; "the selector lists all knowledge graphs the user has `edit` permission on within the current workspace"; "no submission is possible until a knowledge graph is selected"; "the selected knowledge graph is used as the target for the mutation submission"
- Implementation: `src/dev-ui/app/pages/graph/mutations.vue` contains NO knowledge graph selector. The `handleSubmit()` function (line 253) does not check for a selected KG before calling `submission.submit()`. `src/dev-ui/app/composables/useMutationSubmission.ts` calls `applyMutations(jsonlContent, ...)` with no `knowledge_graph_id` parameter. `src/dev-ui/app/composables/api/useGraphApi.ts` `applyMutations()` (line 28) sends `POST /graph/mutations` with no KG scoping.
- Tests: `src/dev-ui/app/tests/mutations-console.test.ts` lines 496–504 contain a test group labelled "Knowledge graph selection" but the assertions only verify the `hasTenant` guard ("No tenant selected" text) — they do NOT test KG selection, the selector component, the disabled submit state, or the KG ID being passed to the API.

#### Requirement: Mutations Console — all other scenarios
- Status: COVERED
- Implementation: Empty state (Upload File, Open Editor, quick-start templates, drag-and-drop), JSONL editing (CodeMirror with autocomplete/linter/lineNumbers), live preview (MutationPreview component, breakdown by DEFINE/CREATE/UPDATE/DELETE), file upload (large-file mode at 5 MB), submission (floating MutationProgress at bottom-right in app.vue), submission failure (error display, ops_applied before failure), template insertion, deep-link (?view=editor, ?template=).
- Tests: `src/dev-ui/app/tests/mutations-console.test.ts`

#### Requirement: API Key Management
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/api-keys/index.vue`; create (name + expiration), list (status/created/last-used/expiration), revoke (DELETE /iam/api-keys/{id}), secret shown once.
- Tests: `src/dev-ui/app/tests/api-keys.test.ts`

#### Requirement: Workspace Management
- Status: COVERED
- Implementation: `src/dev-ui/app/pages/workspaces/index.vue`, `src/dev-ui/app/components/settings/WorkspaceDetailPanel.vue`; create workspace with parent, add/remove/update-role for members.
- Tests: `src/dev-ui/app/tests/workspace-management.test.ts`

#### Requirement: Design Language
- Status: COVERED
- Implementation: `src/dev-ui/app/assets/` CSS; OKLCH custom properties for primary amber (`oklch(0.5768 0.2469 29.23)` light / `oklch(0.6857 0.1560 17.57)` dark), 5-color chart palette, shadcn/vue (Reka UI) + Tailwind + CVA + Lucide Vue Next; `0.625rem` base radius; `shadow-sm` cards.
- Tests: `src/dev-ui/app/tests/design-system.test.ts`, `design-language.test.ts`, `design-language-extended.test.ts`

#### Requirement: Interaction Principles
- Status: COVERED
- Implementation: Progressive disclosure (sheets/expanders), inline editing, copy-to-clipboard with toast, mutation feedback toasts, Ctrl/Cmd+Enter keyboard shortcuts, 3px focus ring at 50% opacity.
- Tests: `src/dev-ui/app/tests/interaction-principles.test.ts`, `focus-ring.test.ts`

#### Requirement: Responsive Design
- Status: COVERED
- Implementation: Desktop sidebar collapsible (`default.vue` `isCollapsed`); mobile sidebar collapses to Sheet overlay; `useMediaQuery('(min-width: 1024px)')` for layout switches.
- Tests: `src/dev-ui/app/tests/responsive-design.test.ts`

#### Requirement: Dark Mode
- Status: COVERED
- Implementation: Dark mode toggle in header (`default.vue` line 836); `useColorMode` composable; preference persisted via `localStorage`.
- Tests: `src/dev-ui/app/tests/color-mode.test.ts`

---

### Summary of Misalignments (Completed Work Only)

- **FAIL — Mutations Console: Knowledge graph selection scenario not implemented.**
  - The spec requires a KG selector before submission, with no submission possible until a KG is selected, and the selected KG used as the target for the API call.
  - `src/dev-ui/app/pages/graph/mutations.vue` has no KG selector UI.
  - `src/dev-ui/app/composables/api/useGraphApi.ts` `applyMutations()` sends no `knowledge_graph_id`.
  - `src/dev-ui/app/tests/mutations-console.test.ts` lines 496–504 test `hasTenant` guard only — not the KG selection requirement.