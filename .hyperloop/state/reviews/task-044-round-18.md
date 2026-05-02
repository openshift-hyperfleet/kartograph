---
task_id: task-044
round: 18
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — ui/experience.spec.md (task-044)

All 1277 frontend tests pass (`pnpm run test` in `src/dev-ui`).

---

## Requirement-by-Requirement Findings

### Requirement: Backend API Alignment — COVERED
- Scenario: Resource operations succeed end-to-end — COVERED
  - `data-sources.test.ts`: `createDataSource POSTs to /management/knowledge-graphs/{id}/data-sources`, `UI reflects updated state after create`
  - `knowledge-graphs.test.ts`: `calls loadKnowledgeGraphs() after successful KG creation`
  - `mcp-integration.test.ts`: `key list refreshes reactively after creation`
- Scenario: Parent context is preserved — COVERED
  - `data-sources.test.ts`: `POST URL includes the parent knowledge graph ID`, `knowledge graph is included in the URL when creating a data source`

### Requirement: Navigation Structure — COVERED
- Scenario: Primary navigation — COVERED
  - `default.layout.test.ts`: exact nav section structure verified (Explore/Data/Connect/Settings)
  - `interaction-principles.test.ts`: `has exactly 4 nav sections`, item membership verified per section
  - Implementation: `layouts/default.vue` defines `navSections` with all four groups and correct items
- Scenario: Default landing — COVERED
  - `index.test.ts`: redirects to `/query` when KGs exist, stays when none exist
- Scenario: New user landing — COVERED
  - `index.test.ts`: checklist includes "Create a knowledge graph" step with `actionTo: '/knowledge-graphs'`

### Requirement: Tenant and Workspace Context — COVERED
- Scenario: Tenant selector — COVERED
  - `default.layout.test.ts`: tenant selector region tested, switching tenants clears stale data
  - `interaction-principles.test.ts`: `switching tenants refreshes all data`
- Scenario: Workspace guidance — COVERED
  - `workspace-guidance.test.ts`: guidance shown when no workspaces, create/join actions present
  - `index.test.ts`: `shows workspace guidance toast when workspaceCount is 0`

### Requirement: Knowledge Graph Creation — COVERED
- Scenario: Create knowledge graph — COVERED
  - `knowledge-graphs.test.ts`: creates in workspace-scoped endpoint, success toast prompts to add data source
  - `knowledge-graphs.test.ts`: `toast description prompts the user to connect a data source`

### Requirement: Data Source Connection — COVERED
- Scenario: Adapter type selection — COVERED
  - `data-sources.test.ts`: `adapter list includes GitHub`, step 1 requires adapter selection, form adapts
- Scenario: Connection configuration — COVERED
  - `data-sources.test.ts`: validates required fields, infers name from repo URL
- Scenario: Credential handling — COVERED
  - `data-sources.test.ts`: `connToken is in-memory only — no localStorage.setItem`, token sent as credentials object, `page shows security notice: credentials encrypted server-side`

### Requirement: Ontology Design — COVERED
- Scenario: Intent description — COVERED
  - `data-sources.test.ts`: `requires intent text to proceed to ontology step`
- Scenario: Agent-proposed ontology — COVERED
  - `data-sources.test.ts`: scan initiation, proposal population (node/edge types), `ontologyReady transitions from false to true`
- Scenario: Ontology review and approval — COVERED
  - `data-sources.test.ts`: `approveOntology() calls the data source API`, `extraction does not happen until the user explicitly approves`
- Scenario: Individual type editing — COVERED
  - `data-sources.test.ts`: `startEditNode`, `saveEditNode`, `cancelEditNode`, property modification, `allows specifying exact property requirements (source_url example)`
- Scenario: Ontology change after initial extraction — COVERED
  - `data-sources.test.ts`: `requestOntologyEdit() opens re-extraction confirmation when extraction has completed`, `re-extraction confirmation dialog warns about full re-extraction`

### Requirement: Sync Monitoring — COVERED
- Scenario: Active sync progress — COVERED
  - `sync-monitoring-extended.test.ts`: phase labels (ingesting/ai_extracting/applying), badge variants
  - `sync-phase-indicator.test.ts`: animated status, indicator style per phase
- Scenario: Sync history — COVERED
  - `sync-monitoring-extended.test.ts`: `computes duration`, `history run with error shows error message`, `renders timestamps as human-readable dates`
- Scenario: Sync logs — COVERED
  - `sync-logs.test.ts` (task-044): `viewLogs captures dsId and runId`, loading lifecycle, API endpoint construction, empty/error state, log display format, `closeLogs resets full state`
- Scenario: Manual sync trigger — COVERED
  - `sync-monitoring-extended.test.ts`: `calls the correct API endpoint to trigger sync`, success/failure message, uses POST method

### Requirement: Get Started Querying (MCP Connection) — COVERED
- Scenario: API key creation inline — COVERED
  - `mcp-integration.test.ts`: `shows "no keys" prompt state when activeKeys is empty`
- Scenario: Copy-paste connection command — COVERED
  - `mcp-integration.test.ts`: snippet includes endpoint URL and API key placeholder
- Scenario: Secret shown once — COVERED
  - `mcp-integration.test.ts`: `dismissSecret sets newlyCreatedKey to null so secret is no longer accessible`, `hasRealSecret becomes false after dismissSecret`

### Requirement: Query Console — COVERED
- Scenario: Query editing — COVERED
  - `query-history.test.ts`: `cypher() LanguageSupport has language named "cypher"`, `cypherAutocomplete()`, `ageCypherLinter()`, `staticExtensions array composition`
- Scenario: Query execution — COVERED
  - `query-history.test.ts`: `records execution time and row count on success`, `does not execute when query string is empty`
- Scenario: Query history — COVERED
  - `query-history.test.ts`: `addToHistory`, `loadHistory`, `clearHistory`, deduplication, persistence to localStorage
- Scenario: Knowledge graph context — COVERED
  - `knowledge-graphs.test.ts`: `populates knowledgeGraphs from API on mount`, `includes knowledge_graph_id in MCP args when KG selected`, `omits when unscoped`

### Requirement: Schema Browser — COVERED
- Scenario: Type listing — COVERED
  - `schema-browser.test.ts`: search/filter by name and properties, returns all when empty query
- Scenario: Type detail — COVERED
  - `schema-browser.test.ts`: description, required/optional properties, `spec-required fields`
- Scenario: Cross-navigation — COVERED
  - `schema-browser.test.ts`: navigates to query console (pre-filled MATCH query), graph explorer (type param), ontology editor (`/data-sources?openOntologyType=`)

### Requirement: Graph Explorer — COVERED
- Scenario: Node search — COVERED
  - `graph-explorer.test.ts`: `canSearch`, `typeFilterLabel`, `transformCypherRow`, `getNodeDisplayName` priority
- Scenario: Neighbor exploration — COVERED
  - `graph-explorer.test.ts`: `getEdgeLabelForNeighbor`, direction detection (outgoing/incoming)

### Requirement: Mutations Console — PARTIAL
- Scenario: Empty state — COVERED
  - `mutations-console.test.ts`: two primary actions, quick-start templates (all 4), drag-and-drop handlers
- Scenario: JSONL editing — COVERED
  - `mutations-console.test.ts`: CodeMirror extension imports and wiring, `Ctrl/Cmd+Enter submits`
- Scenario: Live preview — COVERED
  - `mutations-console.test.ts`: `parseContent` (all op types), `getBreakdown`, validation warnings, parse errors
- Scenario: File upload — COVERED
  - `mutations-console.test.ts`: accepted extensions (.jsonl/.json/.ndjson), large-file mode (>5MB disables editing)
- Scenario: Knowledge graph selection — **PARTIAL**
  - COVERED: `mutations-kg-selector.test.ts` — disabled until KG selected, submit uses selected KG ID, resets on tenant change
  - COVERED: `mutations-workspace-selector.test.ts` — workspace gate for submission, workspace selector structural checks
  - **MISSING**: No test verifies that the API call for KG list loading includes `permission: 'edit'` query parameter. The code in `pages/graph/mutations.vue` (lines 145–150) does pass `{ permission: 'edit', workspace_id: ... }`, but this specific contract is not exercised by any test. The intake commit `8bdf985b3` explicitly logs `task-076` to add this test, confirming it is pending.
- Scenario: Submission — COVERED
  - `mutations-submission.test.ts`: floating progress indicator (fixed bottom-right), status display, operation count, elapsed time, cross-page persistence via `useState`
- Scenario: Submission failure — COVERED
  - `mutations-submission.test.ts`: error message display, truncation at 120 chars, `operations_applied` before failure
- Scenario: Template insertion — COVERED
  - `mutations-console.test.ts`: `getMergedEditorContent`, `activateEditor()` called before insert, `toJsonl`
- Scenario: Deep-link to editor — COVERED
  - `mutations-console.test.ts`: `?view=editor` opens editor, `?template=<content>` inserts content

### Requirement: API Key Management — COVERED
- Scenario: Create key — COVERED
  - `api-keys.test.ts`: validation (name required, expiry range), creates key and shows secret once
- Scenario: List keys — COVERED
  - `api-keys.test.ts`: `keyStatus` (active/expired/revoked), creation date, `maskedSecret`
- Scenario: Revoke key — COVERED
  - `api-keys.test.ts`: `calls revoke API and reloads key list on confirmation`, confirmation dialog

### Requirement: Workspace Management — COVERED
- Scenario: Create workspace — COVERED
  - `workspace-management.test.ts`: `calls createWorkspace with correct name and parent_workspace_id`, validation
- Scenario: Member management — COVERED
  - `workspace-management.test.ts`: add member, remove member, role change, rename

### Requirement: Design Language — COVERED
- Scenario: Component library — COVERED
  - `design-language.test.ts`: shadcn/vue primitives verified in components (Button, Card, Badge, Input)
- Scenario: Color theme — COVERED
  - `design-language.test.ts`: OKLCH primary colors exact values (light/dark), neutral grays, destructive, 5-color chart palette
- Scenario: Typography — COVERED
  - `design-language.test.ts` + `design-language-extended.test.ts`: text-sm body, text-[11px] uppercase headers, font-weight constraints (no font-bold)
- Scenario: Border radius — COVERED
  - `design-language.test.ts`: `--radius: 0.625rem`, cards=rounded-xl, buttons/inputs=rounded-md, badges=rounded-full
- Scenario: Elevation — COVERED
  - `design-language.test.ts` + `design-language-extended.test.ts`: cards=shadow-sm, buttons=shadow-xs, no shadow-lg/xl

### Requirement: Interaction Principles — COVERED
- Scenario: Progressive disclosure — COVERED
  - `interaction-principles.test.ts`: collapsible section starts collapsed, toggles on click, sheet starts closed
- Scenario: Inline actions over navigation — COVERED
  - `interaction-principles.test.ts`: `dialog/sheet opens for inline edit rather than route navigation`
- Scenario: Copy-to-clipboard — COVERED
  - `interaction-principles.test.ts`: `calls clipboard.writeText`, `shows error toast when clipboard write fails`
- Scenario: Mutation feedback — COVERED
  - `interaction-principles.test.ts`: success/error toasts on CRUD, inline validation errors
- Scenario: Keyboard shortcuts — COVERED
  - `interaction-principles.test.ts`: `Ctrl/Cmd+Enter triggers primary action`, tooltip discoverability
  - `query-history.test.ts`: query console keyboard shortcut
- Scenario: Focus indicators — COVERED
  - `focus-ring.test.ts`: `focus-visible:ring-[3px]` at 50% opacity, `outline-none` suppresses native outlines

### Requirement: Responsive Design — COVERED
- Scenario: Desktop layout — COVERED
  - `responsive-design.test.ts`: `hidden md:flex` sidebar, collapsible (w-64/w-16), multi-column grid
- Scenario: Tablet/mobile layout — COVERED
  - `responsive-design.test.ts`: Sheet component for mobile nav, route change closes mobile sheet

### Requirement: Dark Mode — COVERED
- Scenario: Toggle — COVERED
  - `color-mode.test.ts`: toggle persists to localStorage, reads on load, CSS class application
  - `default.layout.test.ts`: `renders a dark mode toggle button in the header`, located inside `<header>`

---

## Failure Summary

**ONE FAILING SCENARIO: Mutations Console — Knowledge graph selection**

The spec requires (SHALL):
> AND the selector lists all knowledge graphs the user has `edit` permission on within the current workspace

- **Code**: `pages/graph/mutations.vue` lines 145–150 correctly passes `permission: 'edit'` in the query — implementation is present.
- **Test**: No test in `mutations-kg-selector.test.ts` or `mutations-workspace-selector.test.ts` verifies that the API call includes `{ permission: 'edit', ... }` as a query parameter.
- **Evidence of gap**: Commit `8bdf985b3` adds `task-076` to the intake queue specifically to write this test.

**Action needed**: Add a test to `mutations-workspace-selector.test.ts` (or a new `mutations-edit-permission.test.ts`) that verifies the `loadKnowledgeGraphs` function passes `permission: 'edit'` in the query when calling the knowledge-graphs API endpoint.