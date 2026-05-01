---
task_id: task-044
round: 4
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — specs/ui/experience.spec.md (task-044)

**Branch:** hyperloop/task-044 (clean, no merge conflicts — the "Merge failed" annotation in the spec's Findings section appears to be a stale artifact from a prior review attempt; the worktree is fully clean)

**Task scope:** Sync Monitoring > Sync logs (primary), full experience.spec.md (all requirements reviewed per protocol)

---

## Requirement-by-Requirement Findings

### Requirement: Backend API Alignment — COVERED
- **Implementation:** `src/dev-ui/app/pages/data-sources/index.vue` calls correct endpoints with parent context (`/management/knowledge-graphs/{kgId}/data-sources`, `/management/data-sources/{dsId}/sync-runs`).
- **Scenario: Resource operations succeed end-to-end** — `tests/data-sources.test.ts` (lines ~630–681): "Handles direct array response", "Returns empty array when no data sources exist", "Calls correct API endpoint". COVERED.
- **Scenario: Parent context is preserved** — `tests/knowledge-graphs.test.ts`: "Calls POST /management/workspaces/{workspace_id}/knowledge-graphs". COVERED.

---

### Requirement: Navigation Structure — PARTIAL
- **Implementation:** `layouts/default.vue` `navSections` computed (lines 240–283) defines all four groups exactly as specified: Explore (Query Console, Schema Browser, Graph Explorer), Data (Knowledge Graphs, Data Sources), Connect (API Keys, MCP Integration), Settings (Workspaces, Groups, Tenants). Implementation is CORRECT.
- **Scenario: Primary navigation** — `tests/default.layout.test.ts` tests only badge behavior ("Data Sources nav item has badge when activeSyncCount > 0", "Other nav items are unaffected"). NO test explicitly asserts all four section titles and their required items. **Test gap: a test asserting navSections contains all 4 groups with the required items is missing.**
- **Scenario: Default landing** — `tests/index.test.ts`: "Redirects to /query when knowledge graphs exist". COVERED.
- **Scenario: New user landing** — `tests/index.test.ts`: "Does NOT redirect when no knowledge graphs exist" and the checklist contains a "Create a knowledge graph" item. COVERED.

---

### Requirement: Tenant and Workspace Context — PARTIAL
- **Scenario: Tenant selector** — `tests/default.layout.test.ts`: "Reflects the new tenant state after a second call with updated data" and "Does not call apiFetch when hasTenant is false". PARTIAL — the spec requires "switching tenants refreshes all data in the UI"; only badge count refresh is explicitly tested, not a full data refresh across all pages.
- **Scenario: Workspace guidance** — `tests/index.test.ts`: "Shows workspace guidance toast when workspaceCount is 0 and key not set", "Does NOT show toast if guidance was already shown". COVERED.

---

### Requirement: Knowledge Graph Creation — COVERED
- **Implementation:** `pages/knowledge-graphs/index.vue`.
- **Scenario: Create knowledge graph** — `tests/knowledge-graphs.test.ts`: "Rejects empty name", "Calls POST /management/workspaces/{workspace_id}/knowledge-graphs with name and description", "Blocks creation when no workspace is selected". COVERED.
- NOTE: The spec's "AND the user is prompted to add their first data source" sub-step is not explicitly tested but is present in the UI; this is a SHOULD-level detail within a SHALL scenario that is otherwise fully covered.

---

### Requirement: Data Source Connection — COVERED
- **Implementation:** `pages/data-sources/index.vue` (4-step wizard).
- **Scenario: Adapter type selection** — `tests/data-sources.test.ts`: wizard step navigation tests. COVERED.
- **Scenario: Connection configuration** — `tests/data-sources.test.ts`: "Infers data source name from GitHub repo URL". COVERED.
- **Scenario: Credential handling** — `tests/data-sources.test.ts`: "Token Visibility" (plaintext never persisted in browser). COVERED.

---

### Requirement: Ontology Design — PARTIAL
- **Scenario: Intent description** — `tests/data-sources.test.ts`: "Data Sources Wizard - Intent Step". COVERED.
- **Scenario: Agent-proposed ontology** — No test exists for the UI rendering of an AI-proposed ontology or the lightweight scan trigger. **Missing test.**
- **Scenario: Ontology review and approval** — `tests/data-sources.test.ts`: "Data Sources Wizard - Approval". COVERED.
- **Scenario: Individual type editing** — `tests/data-sources.test.ts`: startEditNode, saveEditNode, cancelEditNode, removeNode, startEditEdge, saveEditEdge, cancelEditEdge, removeEdge. COVERED.
- **Scenario: Ontology change after initial extraction** — `tests/data-sources.test.ts` references re-extraction dialog. COVERED.

---

### Requirement: Sync Monitoring — COVERED ✅ (primary task-044 scenario)
- **Implementation:** `pages/data-sources/index.vue` — `viewLogs()`, `fetchRunLogs()`, `closeLogs()`, log viewer Sheet component, state variables (`logSheetOpen`, `selectedLogRunId`, `selectedLogDsId`, `runLogs`, `logsLoading`, `logsError`).
- **Scenario: Active sync progress** — `tests/sync-monitoring-extended.test.ts`: real backend phase labels (ingesting, ai_extracting, applying), badge variants. COVERED.
- **Scenario: Sync history** — `tests/sync-monitoring-extended.test.ts`: "Computes duration in seconds", timestamps, history ordering. COVERED.
- **Scenario: Sync logs** (the task-044 focus) — `tests/sync-logs.test.ts` (357 lines, 7 test suites):
  - "viewLogs captures both dsId and runId, opens sheet immediately" COVERED.
  - "loading state lifecycle (logsLoading true/false)" COVERED.
  - "API endpoint construction: /management/data-sources/{dsId}/sync-runs/{runId}/logs" COVERED.
  - "empty state handling (empty array, omitted key)" COVERED.
  - "error state (captures message, clears on new fetch)" COVERED.
  - "log line display format (joined by newlines, monospace)" COVERED.
  - "closeLogs resets full state" COVERED.
  All acceptance criteria from task-044.md are satisfied.
- **Scenario: Manual sync trigger** — `tests/data-sources.test.ts` (lines ~196–213): sync trigger and progress shown. COVERED.

---

### Requirement: Get Started Querying (MCP Connection) — COVERED
- **Implementation:** `pages/integrate/mcp.vue`.
- **Scenario: API key creation inline** — `tests/mcp-integration.test.ts`: "Shows 'no keys' prompt state when activeKeys is empty". COVERED.
- **Scenario: Copy-paste connection command** — `tests/mcp-integration.test.ts`: "Claude Code snippet includes endpoint URL and secret", "Cursor snippet is valid JSON". COVERED.
- **Scenario: Secret shown once** — `tests/api-keys.test.ts`: "Creates key and shows secret once on success". COVERED.

---

### Requirement: Query Console — PARTIAL
- **Implementation:** `pages/query/index.vue`.
- **Scenario: Query editing** (Cypher syntax highlighting, autocomplete, linting) — No unit tests exist for editor capabilities. These are library-provided (Monaco/CodeMirror) features and the spec makes them a SHALL. **Missing tests.**
- **Scenario: Query execution** — `tests/query-history.test.ts`: "Records execution time and row count on success". COVERED.
- **Scenario: Query history** — `tests/query-history.test.ts`: add to front, deduplicate, cap at 20, persist to localStorage, recover from malformed JSON. COVERED.
- **Scenario: Knowledge graph context** (scope queries to specific KG or span all) — No test exists for this scenario. **Missing test.**

---

### Requirement: Schema Browser — PARTIAL
- **Implementation:** `pages/graph/schema.vue`.
- **Scenario: Type listing** — `tests/schema-browser.test.ts`: search by label, partial match, property match. COVERED.
- **Scenario: Type detail** — `tests/schema-browser.test.ts`: "Exposes description", "Exposes required and optional properties separately". COVERED.
- **Scenario: Cross-navigation** (navigate to query console pre-filled, graph explorer filtered, or ontology editor from schema browser type) — No test exists. NOTE: `tests/graph-explorer.test.ts` has "cross-page navigation (query builder)" but that is FROM the graph explorer TO the query console, not FROM the schema browser. **Missing tests for schema browser cross-navigation.**

---

### Requirement: Graph Explorer — COVERED
- **Implementation:** `pages/graph/explorer.vue`.
- **Scenario: Node search** — `tests/graph-explorer.test.ts`: "canSearch returns false when empty/whitespace", "returns true when type filter or query set", search mode descriptions. COVERED.
- **Scenario: Neighbor exploration** — `tests/graph-explorer.test.ts`: `getEdgeLabelForNeighbor` (outgoing/incoming direction), exploration path (addNode, navigateBackTo), drillIntoNeighbor (sets results, description, clears neighbors, sets hasSearched). COVERED.

---

### Requirement: API Key Management — COVERED
- **Implementation:** `pages/api-keys/index.vue`.
- **Scenario: Create key** — `tests/api-keys.test.ts`: "Creates key and shows secret once on success", expiry validation. COVERED.
- **Scenario: List keys** — `tests/api-keys.test.ts`: isExpired, keyStatus (active/expired/revoked), daysUntilExpiry, maskedSecret. COVERED.
- **Scenario: Revoke key** — `tests/interaction-principles.test.ts`: "Shows success toast on delete (revoke) operation". COVERED.

---

### Requirement: Workspace Management — COVERED
- **Implementation:** `pages/workspaces/index.vue`.
- **Scenario: Create workspace** — `tests/workspace-management.test.ts`: creation validation, API call, error toast. COVERED.
- **Scenario: Member management** — `tests/workspace-management.test.ts`: "add member" (6 tests), "remove member" (3 tests with confirmation guard), "role change" (4 tests), plus "backend endpoint alignment" verifying addWorkspaceMember/removeWorkspaceMember/updateWorkspaceMemberRole API calls. COVERED.

---

### Requirement: Design Language — COVERED
- **Scenario: Component library** — `tests/design-system.test.ts`: Tailwind CSS, CVA, Lucide Vue Next, Reka UI. COVERED.
- **Scenario: Color theme** — `tests/design-system.test.ts`: OKLCH values for primary (0.5768 0.2469 29.23 light, 0.6857 0.1560 17.57 dark), neutral grays, destructive coral, 5 chart colors. COVERED.
- **Scenario: Typography** — `tests/design-language-extended.test.ts`: text-sm body, text-[11px] uppercase tracking-wider section headers, font weights 400/500/600. COVERED.
- **Scenario: Border radius** — `tests/design-language-extended.test.ts`: 0.625rem base, rounded-xl cards, rounded-md buttons/inputs. COVERED.
- **Scenario: Elevation** — `tests/design-language-extended.test.ts`: shadow-sm cards, shadow-xs buttons, no shadow-lg/xl. COVERED.

---

### Requirement: Interaction Principles — PARTIAL
- **Scenario: Progressive disclosure** — `tests/interaction-principles.test.ts`: "Collapsible section starts collapsed", "Toggles section expanded when clicked". COVERED.
- **Scenario: Inline actions over navigation** — `tests/workspace-management.test.ts` rename tests cover in-place editing. Partially covered for workspace rename; no explicit test asserting that editing never navigates to a separate page. PARTIAL.
- **Scenario: Copy-to-clipboard** — `tests/interaction-principles.test.ts`: clipboard.writeText, error toast, copiedFlag. COVERED.
- **Scenario: Mutation feedback** — `tests/interaction-principles.test.ts`: success/error toasts, inline validation errors, error cleared on correction. COVERED.
- **Scenario: Keyboard shortcuts** — No tests exist for Ctrl/Cmd+Enter (execute query) or / (focus search). **Missing tests.**
- **Scenario: Focus indicators** — `tests/focus-ring.test.ts`: 3px ring, ring/50 opacity, outline-none. No regression to ring-2. COVERED.

---

### Requirement: Responsive Design — COVERED
- **Scenario: Desktop layout** — `tests/responsive-design.test.ts`: "Sidebar uses 'hidden md:flex'", expanded w-64 / collapsed w-16, multi-column grid. COVERED.
- **Scenario: Tablet/mobile layout** — `tests/responsive-design.test.ts`: mobile Sheet overlay, sheet triggers on menu button, workspace sheet mobile/desktop behavior. COVERED.

---

### Requirement: Dark Mode — COVERED
- **Scenario: Toggle** — `tests/color-mode.test.ts`: toggle, localStorage persistence, system preference fallback, CSS class application. COVERED.

---

## Summary Table

| Requirement                        | Status  |
|------------------------------------|---------|
| Backend API Alignment              | COVERED |
| Navigation Structure               | PARTIAL |
| Tenant and Workspace Context       | PARTIAL |
| Knowledge Graph Creation           | COVERED |
| Data Source Connection             | COVERED |
| Ontology Design                    | PARTIAL |
| Sync Monitoring (incl. Sync Logs)  | COVERED |
| Get Started Querying (MCP)         | COVERED |
| Query Console                      | PARTIAL |
| Schema Browser                     | PARTIAL |
| Graph Explorer                     | COVERED |
| API Key Management                 | COVERED |
| Workspace Management               | COVERED |
| Design Language                    | COVERED |
| Interaction Principles             | PARTIAL |
| Responsive Design                  | COVERED |
| Dark Mode                          | COVERED |

---

## Verdict: FAIL

**Reason:** Six SHALL scenarios across five requirements lack test coverage.

### Required Fixes (ordered by priority)

1. **Navigation Structure — Primary navigation scenario** (`tests/default.layout.test.ts` or new file):
   Add a test that asserts `navSections` contains exactly 4 sections titled "Explore", "Data", "Connect", "Settings" with the correct items in each (e.g., Explore contains Query Console/Schema Browser/Graph Explorer items).

2. **Query Console — Knowledge graph context scenario** (`tests/query-console.test.ts` or existing file):
   Add a test that verifies: (a) a KG selector exists and when a KG is selected the query scope is set; (b) when no KG is selected, queries span all accessible KGs.

3. **Schema Browser — Cross-navigation scenario** (`tests/schema-browser.test.ts`):
   Add tests that verify: from a selected type, (a) a "Query in Console" action builds a pre-filled Cypher query and routes to /query, (b) a "View in Explorer" action routes to /graph/explorer filtered by that type, (c) an "Edit Ontology" action routes to the ontology editor for that type.

4. **Interaction Principles — Keyboard shortcuts scenario** (`tests/interaction-principles.test.ts` or `tests/query-console.test.ts`):
   Add tests that verify: (a) Ctrl/Cmd+Enter triggers query execution, (b) / keypress focuses the search input.

5. **Ontology Design — Agent-proposed ontology scenario** (`tests/data-sources.test.ts`):
   Add tests that verify: after submitting free-text intent, the UI transitions to a "scanning" state, and upon receiving an API response, renders the proposed node types and edge types for review (even if the AI backend is stubbed/mocked in the test).

6. **Tenant and Workspace Context — Tenant selector refresh** (`tests/default.layout.test.ts`):
   Add a test that verifies switching the active tenant triggers a data refresh (not just badge count but page data re-fetch, even if scoped to one page).

---

**Note on task-044 primary scope:** The Sync Monitoring > Sync logs scenario (the explicit task-044 deliverable) is FULLY COVERED by `tests/sync-logs.test.ts` with comprehensive coverage of all acceptance criteria. The verdict is FAIL due to pre-existing test gaps in other requirements that are part of the same spec file.