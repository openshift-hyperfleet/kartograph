---
task_id: task-044
round: 14
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review: specs/ui/experience.spec.md

Branch: hyperloop/task-044

### Test Results
- Frontend tests: **1252 passed, 0 failed** (`pnpm test` in `src/dev-ui`)
- Backend unit tests: 2696 passed, 0 failed
- CI check `check-frontend-scenario-labels.sh`: **FAIL** — 4 of 60 spec scenarios
  lack the required scenario name label in any test file.

---

## Requirement-by-Requirement Findings

### Requirement: Backend API Alignment — COVERED
- Scenario: Resource operations succeed end-to-end — COVERED
  - Code: CRUD operations in `src/dev-ui/app/pages/**/*.vue` + `src/dev-ui/app/composables/use*Api.ts`
  - Tests: `workspace-management.test.ts` (API endpoint alignment suite),
    `api-keys.test.ts` (backend endpoint alignment), `data-sources.test.ts`, etc.
- Scenario: Parent context is preserved — COVERED
  - Code: `workspaces/index.vue` requires `parent_workspace_id`; KG creation uses workspace-scoped URL
  - Test: `workspace-management.test.ts` — "createWorkspace parent_workspace_id is REQUIRED in request body"

### Requirement: Navigation Structure — COVERED
- Scenario: Primary navigation — COVERED
  - Code: `layouts/default.vue` — 4 sections: Explore, Data, Connect, Settings
  - Tests: `interaction-principles.test.ts` — "has exactly 4 nav sections", lists all items per section
- Scenario: Default landing — COVERED
  - Tests: `interaction-principles.test.ts` — "detects returning user via query history in localStorage"
- Scenario: New user landing — COVERED
  - Tests: `interaction-principles.test.ts` — "new user without dismissed state and no completed items sees full setup guidance"

### Requirement: Tenant and Workspace Context — COVERED
- Scenario: Tenant selector — COVERED
  - Tests: `default.layout.test.ts` — "sidebar has tenant selector region with aria-label",
    "fetchActiveSyncCount — badge updates on tenant change"
- Scenario: Workspace guidance — COVERED
  - Tests: `workspace-guidance.test.ts`, `index.test.ts` — workspace guidance toast,
    per-tenant localStorage guard

### Requirement: Knowledge Graph Creation — COVERED
- Scenario: Create knowledge graph — COVERED
  - Code: `pages/knowledge-graphs/index.vue`
  - Tests: `knowledge-graphs.test.ts` — validation, POST endpoint, auto-select workspace,
    prompt to add data source

### Requirement: Data Source Connection — PARTIAL
- Scenario: Adapter type selection — MISSING LABEL
  - Code: `pages/data-sources/index.vue` — wizard step 1 is adapter selection, form adapts
  - Tests: `data-sources.test.ts` has wizard step navigation tests and tests for adapter
    selection logic (e.g. "requires adapter selection to proceed to step 2") BUT the exact
    string "Adapter type selection" does not appear anywhere in any test file.
  - **Action needed**: Add `describe('Scenario: Adapter type selection', ...)` in
    `data-sources.test.ts` with the existing adapter-selection tests inside it.

- Scenario: Connection configuration — MISSING LABEL
  - Code: `pages/data-sources/index.vue` — step 2 form with required fields and default inference
  - Tests: `data-sources.test.ts` — "validates required fields in step 2",
    "infers data source name from GitHub repo URL" — BUT the exact string
    "Connection configuration" does not appear in any test file.
  - **Action needed**: Add `describe('Scenario: Connection configuration', ...)` in
    `data-sources.test.ts`.

- Scenario: Credential handling — COVERED
  - Tests: `data-sources.test.ts` — "UI shows warning that credentials are encrypted server-side",
    "UI warns that the token will not be retrievable after saving"

### Requirement: Ontology Design — PARTIAL
- Scenario: Intent description — COVERED
  - Tests: `data-sources.test.ts` — "Data Sources Wizard - Intent Step"
- Scenario: Agent-proposed ontology — COVERED
  - Tests: `data-sources.test.ts` — "Scenario: Agent-proposed ontology — proposal lifecycle",
    `scanningOntology` state machine tests (lines 718+)
- Scenario: Ontology review and approval — COVERED
  - Tests: `data-sources.test.ts` — "Ontology Design - Ontology Review and Approval"
- Scenario: Individual type editing — COVERED
  - Tests: `data-sources.test.ts` — startEditNode/saveEditNode/cancelEditNode/removeNode suites;
    `ontology-add-types.test.ts` — newBlankNode/newBlankEdge/saveNode/saveEdge
- Scenario: Ontology change after initial extraction — MISSING LABEL
  - Code: `pages/knowledge-graphs/index.vue` — re-extraction confirmation dialog
  - Tests: `knowledge-graphs.test.ts` has "FAIL 2: Ontology Change After Extraction
    (Confirmation Gate)" with full coverage of the confirmation gate, warn, and confirm
    logic — BUT the spec scenario string "Ontology change after initial extraction"
    does not appear anywhere in any test file.
  - **Action needed**: Rename the describe group in `knowledge-graphs.test.ts` to include
    "Ontology change after initial extraction" (e.g. add it as an alias comment or rename the block).

### Requirement: Sync Monitoring — COVERED
- Scenario: Active sync progress — COVERED
  - Tests: `sync-monitoring-extended.test.ts` — phase labels (Pending/Ingesting/Extracting/Applying),
    `sync-phase-indicator.test.ts` — animated status
- Scenario: Sync history — COVERED
  - Tests: `sync-monitoring-extended.test.ts` — duration computation, history run display fields
- Scenario: Sync logs — COVERED
  - Tests: `sync-logs.test.ts` — viewLogs, loading state, API endpoint, error state, closeLogs
- Scenario: Manual sync trigger — COVERED
  - Tests: `sync-monitoring-extended.test.ts` — "Manual sync trigger" suite,
    POST to `/management/data-sources/{dsId}/sync`

### Requirement: Get Started Querying (MCP Connection) — COVERED
- Scenario: API key creation inline — COVERED
  - Tests: `mcp-integration.test.ts` — "shows 'no keys' prompt state when activeKeys is empty"
- Scenario: Copy-paste connection command — COVERED
  - Tests: `mcp-integration.test.ts` — Claude Code and Cursor snippet generation tests
- Scenario: Secret shown once — COVERED
  - Tests: `mcp-integration.test.ts` — "dismissSecret sets newlyCreatedKey to null",
    `api-keys.test.ts` — "dismissCreatedKey clears newlyCreatedKey"

### Requirement: Query Console — COVERED
- Scenario: Query editing — COVERED (cypher(), cypherAutocomplete(), ageCypherLinter() extension tests)
- Scenario: Query execution — COVERED (`query-history.test.ts` — execution time and row count)
- Scenario: Query history — COVERED (`query-history.test.ts` — addToHistory, loadHistory, clearHistory)
- Scenario: Knowledge graph context — COVERED (`knowledge-graphs.test.ts` — KG selector, scope label)

### Requirement: Schema Browser — COVERED
- All 3 scenarios covered in `schema-browser.test.ts`

### Requirement: Graph Explorer — COVERED
- Scenarios covered in `graph-explorer.test.ts` — node search, type filter, neighbor exploration, trail

### Requirement: Mutations Console — COVERED
- All 9 scenarios covered across `mutations-console.test.ts`, `mutations-kg-selector.test.ts`,
  `mutations-submission.test.ts`

### Requirement: API Key Management — COVERED
- All 3 scenarios covered in `api-keys.test.ts`

### Requirement: Workspace Management — COVERED
- Scenario: Create workspace — COVERED (requires parent per architecture; tested in
  `workspace-management.test.ts`)
- Scenario: Member management — COVERED (add/remove/role-change member tests)

### Requirement: Design Language — COVERED
- All 5 scenarios covered in `design-language.test.ts`, `design-language-extended.test.ts`,
  `design-system.test.ts`

### Requirement: Interaction Principles — PARTIAL
- Scenario: Progressive disclosure — COVERED (`interaction-principles.test.ts`)
- Scenario: Inline actions over navigation — COVERED (`interaction-principles.test.ts`)
- Scenario: Copy-to-clipboard — COVERED (`interaction-principles.test.ts`)
- Scenario: Mutation feedback — COVERED (`interaction-principles.test.ts`)
- Scenario: Keyboard shortcuts — MISSING LABEL
  - Code: `pages/query/index.vue` has `<TooltipContent><p>Ctrl+Enter</p></TooltipContent>`;
    `pages/graph/mutations.vue` has same; `pages/graph/schema.vue` has "/" shortcut.
    Keyboard shortcut FUNCTIONALITY is tested in `query-history.test.ts` (Ctrl/Cmd+Enter),
    `schema-browser.test.ts` ("/"), and `mutations-console.test.ts` (Ctrl/Cmd+Enter keymap).
  - The exact string "Keyboard shortcuts" does not appear in any test file, so the
    CI check `check-frontend-scenario-labels.sh` flags this as MISSING.
  - **Action needed**: Add `describe('Keyboard shortcuts', ...)` or `// Keyboard shortcuts`
    comment in `interaction-principles.test.ts` (or another test file), add at least one
    assertion that the shortcut is discoverable via tooltip or documentation.
- Scenario: Focus indicators — COVERED (`focus-ring.test.ts` — ring-[3px], /50 opacity, outline-none)

### Requirement: Responsive Design — COVERED
- Both scenarios covered in `responsive-design.test.ts`

### Requirement: Dark Mode — COVERED
- Scenario: Toggle — COVERED (`color-mode.test.ts`)

---

## Summary of Failures

The `check-frontend-scenario-labels.sh` CI check fails with 4 MISSING scenario labels:

1. **"Adapter type selection"** (Data Source Connection)
   - Fix: Add `describe('Scenario: Adapter type selection', ...)` in `data-sources.test.ts`
     wrapping the existing adapter selection tests.

2. **"Connection configuration"** (Data Source Connection)
   - Fix: Add `describe('Scenario: Connection configuration', ...)` in `data-sources.test.ts`
     wrapping the existing required-fields and name-inference tests.

3. **"Ontology change after initial extraction"** (Ontology Design)
   - Fix: The test group in `knowledge-graphs.test.ts` is labeled "Post-Extraction
     Confirmation Gate". Add the spec scenario name (e.g. rename describe to include
     "Ontology change after initial extraction" or add an inline comment visible to grep).

4. **"Keyboard shortcuts"** (Interaction Principles)
   - Fix: Add a `describe('Keyboard shortcuts', ...)` block in `interaction-principles.test.ts`
     (or another file) with at least one assertion covering the discoverability requirement
     (tooltip or documentation shows the shortcut).

No code changes are needed — only test label additions/renames. All existing tests pass.