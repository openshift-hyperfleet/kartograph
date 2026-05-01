---
task_id: task-041
round: 0
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — experience.spec.md

All 451 frontend tests pass. However, one SHALL requirement has a broken
implementation with a test that verifies the incorrect behavior.

---

### Requirement: Backend API Alignment — PARTIAL (→ FAIL)

#### Scenario: Resource operations succeed end-to-end — PARTIAL
- **Data source loading (FIXED):** `loadDataSources()` in
  `pages/data-sources/index.vue` correctly treats both the
  `GET /management/knowledge-graphs/{kg_id}/data-sources` and
  `GET /management/data-sources/{ds_id}/sync-runs` responses as plain JSON
  arrays (not wrapped objects). Tests in
  `data-sources.test.ts` → "Data Source Loading - API Array Response Format"
  cover all four cases (happy path, sync-runs array, graceful error on DS
  fetch, graceful error on sync-run fetch). **COVERED.**
- **Knowledge graph creation (BROKEN):** `handleCreate()` in
  `pages/knowledge-graphs/index.vue` calls
  `POST /management/knowledge-graphs`. That route does **not exist** in the
  backend. The only creation route is
  `POST /management/workspaces/{workspace_id}/knowledge-graphs`
  (see `src/api/management/presentation/knowledge_graphs/routes.py` line 113).
  Every knowledge graph creation attempt from the UI will receive a 404 and
  never succeed. **MISSING end-to-end success.**

#### Scenario: Parent context is preserved — PARTIAL
- **Data sources (COVERED):** `createDataSource()` correctly uses
  `/management/knowledge-graphs/${params.kg_id}/data-sources`, passing the
  parent KG id in the URL path. Tests cover this.
- **Knowledge graphs (MISSING):** The knowledge graph creation call omits the
  workspace context entirely. The spec example for this scenario is
  *"a knowledge graph within a workspace"* — which is precisely the broken
  case. The UI has no workspace selector on the knowledge-graphs page, and the
  API body contains only `name` and `description`. **MISSING workspace_id.**

**Root cause:** `pages/knowledge-graphs/index.vue` has no workspace state and
its `handleCreate()` posts to a non-existent flat endpoint.

**Test also wrong:** `knowledge-graphs.test.ts` line 50 —
  `"calls POST /management/knowledge-graphs with name and description"` —
  documents and asserts the broken URL. The test should instead assert that the
  call goes to `POST /management/workspaces/{workspace_id}/knowledge-graphs`
  with the appropriate `workspace_id`.

---

### Requirement: Knowledge Graph Creation — PARTIAL (→ FAIL)

#### Scenario: Create knowledge graph — PARTIAL
- User provides name and description: **COVERED** (dialog exists, validation
  tested in `knowledge-graphs.test.ts`).
- "the knowledge graph is created within the current workspace": **MISSING**.
  The workspace context is neither collected from the user nor passed to the
  backend. The page has no workspace selector and no workspace state.
- User is prompted to add their first data source after creation: **COVERED**
  (toast with "Add Data Source" action button at `index.vue` line 95).

---

### All Other Requirements — COVERED

The remaining 15 SHALL requirements are all implemented and tested:

- **Navigation Structure**: Sidebar has Explore/Data/Connect/Settings groups
  (`default.vue`). Tests in `interaction-principles.test.ts` →
  "Navigation - sidebar section structure" verify all 4 groups and their items.
  Default landing (returning user → `/query`) and new user setup checklist are
  tested in `interaction-principles.test.ts` and `index.test.ts`. **COVERED.**

- **Tenant and Workspace Context**: Tenant selector dropdown in `default.vue`
  (single-tenant static display, multi-tenant dropdown). Workspace guidance
  toast on first tenant entry tested in `interaction-principles.test.ts` →
  "Navigation - workspace guidance for new users". Tenant switch refreshing
  data tested in "Tenant Context - switching tenants refreshes all data".
  **COVERED.**

- **Data Source Connection**: Three-step wizard (adapter → config → intent →
  ontology) in `pages/data-sources/index.vue`. Adapter selection, form
  validation, name inference, token visibility, intent step all tested in
  `data-sources.test.ts`. **COVERED.**

- **Ontology Design**: Intent step, proposed ontology display, individual
  node/edge type editing (startEditNode/saveEditNode/cancelEditNode/removeNode,
  same for edges), approval gate. Ontology change after extraction confirmation
  dialog tested in `knowledge-graphs.test.ts`. **COVERED.**

- **Sync Monitoring**: Status badges, sync history rows, log sheet with
  `fetchRunLogs()` API call, manual sync trigger. Tested across
  `sync-monitoring-extended.test.ts`, `data-sources.test.ts`, and
  `knowledge-graphs.test.ts`. **COVERED.**

- **MCP Connection**: Inline key creation, config snippet generation (Claude
  Code + Cursor), secret shown once/cleared on tenant switch. Tested in
  `mcp-integration.test.ts`. **COVERED.**

- **Query Console**: CodeMirror with Cypher syntax, autocomplete, linting, and
  Ctrl/Cmd+Enter in `pages/query/index.vue`. KG scope selector. Query history
  with dedup and localStorage persistence. Tested in `query-history.test.ts`
  and `knowledge-graphs.test.ts`. **COVERED.**

- **Schema Browser**: filteredNodeLabels/filteredEdgeLabels with search,
  cross-navigation to query console, graph explorer, and ontology editor.
  Tested in `schema-browser.test.ts`. **COVERED.**

- **Graph Explorer**: escapeCypherString, transformCypherRow,
  drillIntoNeighbor, neighbor expansion. Tested in `graph-explorer.test.ts`.
  **COVERED.**

- **API Key Management**: Create (with secret shown once), list (active/
  expired/revoked status logic), revoke with confirmation dialog. Tested in
  `api-keys.test.ts`. **COVERED.**

- **Workspace Management**: Creation validation, tree building, flatten with
  expandedIds, member add/remove/role-change, rename. Responsive layout
  (desktop panel vs mobile sheet). Tested in `workspace-management.test.ts`.
  **COVERED.**

- **Design Language**: OKLCH color vars, OKLCH primary values, border-radius
  base, shadcn/vue + CVA + Lucide confirmed in package.json. Typography
  (text-sm body, text-[11px] section headers, tracking-wider), elevation
  (shadow-sm cards, shadow-xs buttons). Tested in `design-system.test.ts` and
  `design-language-extended.test.ts`. **COVERED.**

- **Interaction Principles**: Copy-to-clipboard toast, mutation feedback toasts,
  inline editing (in-place or side panel, no separate edit page), progressive
  disclosure, Ctrl+Enter and "/" keyboard shortcuts, focus ring via
  `outline-ring/50`. Tested in `interaction-principles.test.ts`,
  `query-history.test.ts`, and `design-system.test.ts`. **COVERED.**

- **Responsive Design**: Collapsible sidebar (w-16/w-64), Sheet overlay for
  mobile, multi-column to single-column layout adaptation. Tested in
  `responsive-design.test.ts`. **COVERED.**

- **Dark Mode**: Toggle in header, localStorage persistence for preference.
  Tested in `color-mode.test.ts`. **COVERED.**

---

## What the Implementer Must Fix

**File:** `src/dev-ui/app/pages/knowledge-graphs/index.vue`

1. Add a workspace selector (using `listWorkspaces` from `useIamApi`) so the
   user can pick a workspace before creating a knowledge graph. The selected
   `workspace_id` must be stored in a `selectedWorkspaceId` ref.

2. Change the `handleCreate()` API call from:
   ```
   POST /management/knowledge-graphs
   ```
   to:
   ```
   POST /management/workspaces/{selectedWorkspaceId}/knowledge-graphs
   ```

3. Validate that a workspace is selected before allowing creation (similar to
   how the data-sources wizard validates `selectedKnowledgeGraphId`).

**File:** `src/dev-ui/app/tests/knowledge-graphs.test.ts`

4. Update the test at line 50 (`"calls POST /management/knowledge-graphs"`) to
   assert the correct URL pattern:
   `POST /management/workspaces/{workspace_id}/knowledge-graphs`. Add a test
   that verifies creation is blocked when no workspace is selected.