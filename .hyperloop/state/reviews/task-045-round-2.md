---
task_id: task-045
round: 2
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — specs/ui/experience.spec.md

Branch: hyperloop/task-045

### Summary

Most requirements are well-implemented and tested. Four scenarios under the
**Ontology Design** requirement are PARTIAL or MISSING — the ontology proposal
is entirely simulated with hardcoded data and no AI agent backend call, and the
edited ontology is never submitted to the backend on approval.

---

## Requirement-by-Requirement Findings

### Requirement: Backend API Alignment — COVERED

**Scenario: Resource operations succeed end-to-end** — COVERED
- Code: All pages use `useApiClient()` composables hitting REST endpoints.
  `data-sources/index.vue` makes calls to `/management/knowledge-graphs/{kg_id}/data-sources`,
  `/management/data-sources/{ds_id}/sync-runs`, etc.
- Test: `data-sources.test.ts` "Backend API Response Format" describe blocks (lines 580–682)
  verify the UI correctly handles the backend's direct-array response format (no wrapper key).

**Scenario: Parent context is preserved** — COVERED
- Code: KG creation POSTs to `/management/workspaces/{id}/knowledge-graphs`
  (`knowledge-graphs/index.vue`). Data source creation uses `kg_id` in the URL.
- Test: `knowledge-graphs.test.ts` "KG Creation API call" block verifies
  `apiFetch` is called with the workspace-scoped URL.

---

### Requirement: Navigation Structure — COVERED

**Scenario: Primary navigation** — COVERED
- Code: `layouts/default.vue` sidebar groups: Explore (Query Console, Schema Browser,
  Graph Explorer), Data (Knowledge Graphs, Data Sources), Connect (API Keys, MCP Integration),
  Settings (Workspaces, Groups, Tenants).
- Test: `interaction-principles.test.ts` "Sidebar nav structure" block verifies all
  four groups, labels, and routes.

**Scenario: Default landing** — COVERED
- Code: `pages/index.vue` fetches KGs on mount; if KGs exist and session key absent,
  redirects to `/query`.
- Test: `index.test.ts` "Default landing redirect" (5 tests) verifies redirect on
  existing KGs and suppression on empty list / error / already-redirected.

**Scenario: New user landing** — COVERED
- Code: `pages/index.vue` shows onboarding checklist with "Create a knowledge graph" step.
- Test: `index.test.ts` "Checklist shape" and `interaction-principles.test.ts`
  "New user landing" blocks verify the checklist and prompt.

---

### Requirement: Tenant and Workspace Context — COVERED

**Scenario: Tenant selector** — COVERED
- Code: `layouts/default.vue` renders tenant selector (static for single tenant,
  dropdown for multi-tenant).
- Test: `interaction-principles.test.ts` "Tenant switch" block verifies
  `tenantVersion` watcher triggers data reload and clears stale state.

**Scenario: Workspace guidance** — COVERED
- Code: Both `layouts/default.vue` and `pages/index.vue` show workspace guidance
  toast when `workspaceCount === 0`, guarded by a localStorage key per tenant.
- Test: `index.test.ts` "Workspace guidance toast" (5 tests) and
  `interaction-principles.test.ts` "Workspace guidance for new users" verify
  shown-once behaviour and guard key.

---

### Requirement: Knowledge Graph Creation — COVERED

**Scenario: Create knowledge graph** — COVERED
- Code: `pages/knowledge-graphs/index.vue` — create dialog loads workspaces,
  lets user pick workspace + name/description, POSTs, then shows a toast
  linking to `/data-sources`.
- Test: `knowledge-graphs.test.ts` "KG Creation Validation" (3 tests),
  "KG Creation API call" (3 tests), "Workspace Loading" (4 tests).

---

### Requirement: Data Source Connection — PARTIAL

**Scenario: Adapter type selection** — COVERED
- Code: `pages/data-sources/index.vue` step 1 — adapter card selection blocks
  advancing without a selection.
- Test: `data-sources.test.ts` "Step Navigation" (2 tests).

**Scenario: Connection configuration** — COVERED
- Code: Step 2 shows GitHub-specific fields; `connName` is auto-inferred from
  repo URL.
- Test: `data-sources.test.ts` "Form Validation" (3 tests) including name inference.

**Scenario: Credential handling** — PARTIAL
- Code: `connToken` is held in component state only; sent to backend in
  `createDataSource`. `useTransientSecret` composable explicitly stores API key
  secrets in Nuxt `useState` (memory-only, never localStorage/sessionStorage).
  The data source wizard token is never written to any persistent storage.
- Test: `data-sources.test.ts` covers token visibility toggle but there is **no
  explicit test** asserting "plaintext is never written to localStorage or
  sessionStorage". The non-persistence property is an implementation invariant
  without a dedicated regression test.
- **Needed:** A test that verifies `connToken` (or `access_token`) is never
  written to `localStorage`, `sessionStorage`, or the URL during the wizard flow.

---

### Requirement: Ontology Design — PARTIAL / FAIL

**Scenario: Intent description** — COVERED
- Code: Step 3 collects `intentText` and blocks advance when empty.
- Test: `data-sources.test.ts` "Intent Step" (2 tests).

**Scenario: Agent-proposed ontology** — PARTIAL
- Code: `pages/data-sources/index.vue` `beginOntologyProposal()` (line 381):
  ```js
  // Simulate a lightweight scan of the data source (1.5s) followed by AI proposal
  await new Promise<void>((resolve) => setTimeout(resolve, 1500))
  proposedNodes.value = GITHUB_PROPOSAL_NODES.map(toProposedNode)
  proposedEdges.value = GITHUB_PROPOSAL_EDGES.map(toProposedEdge)
  ```
  The proposal is entirely **simulated** with hardcoded constants `GITHUB_PROPOSAL_NODES`
  and `GITHUB_PROPOSAL_EDGES` (lines 198–291). There is no backend API call to an AI
  agent, no actual scan of the connected data source, and the intent text collected in
  step 3 is not sent anywhere.
- Test: `data-sources.test.ts` only tests that `scanningOntology` becomes `true`
  when advancing from step 3 to step 4. There is no test verifying:
  (a) a backend scan/AI-agent endpoint is called,
  (b) the intent text is included in that call, or
  (c) the proposed ontology (node types, edge types) reflects data actually read
      from the source.
- **Needed:** Either (a) implement a real backend endpoint for ontology proposal
  (scan + AI inference) and wire the UI to call it, OR (b) if the simulation is
  intentional for this phase, the spec requirement for "an AI agent explores the
  scanned data" is not met and the scenario must be marked as not yet implemented.
  A test should at minimum verify the intent text is passed to whatever backend
  call is made.

**Scenario: Ontology review and approval** — PARTIAL
- Code: `approveOntology()` (line 492) calls only `createDataSource(...)` with
  connection config (`name`, `adapter_type`, `connection_config`, `credentials`).
  The `proposedNodes` and `proposedEdges` — including any edits the user made —
  are **never submitted to the backend**. The approved ontology is silently discarded.
- Test: `data-sources.test.ts` "Approval" test only verifies that an error toast
  fires when no KG is selected. No test verifies that the approved ontology
  (node types, edge types) is persisted.
- **Needed:** The `approveOntology` function must include the proposed/edited
  ontology in the API payload (or make a separate POST to an ontology endpoint).
  A test must verify this payload is sent and that "extraction begins only after
  the user explicitly approves" (i.e., no extraction-triggering call is made
  before `approveOntology` is invoked).

**Scenario: Individual type editing** — PARTIAL
- Code: `startEditNode`, `saveEditNode`, `cancelEditNode`, `removeNode`,
  `startEditEdge`, `saveEditEdge`, `cancelEditEdge`, `removeEdge` are all
  implemented and mutate `proposedNodes`/`proposedEdges` in component state.
- Test: `data-sources.test.ts` has 27 tests covering all edit operations (node
  and edge editing sections).
- Gap: The edits are reflected in the UI but are discarded at approval (see
  "Ontology review and approval" above). Tests for the edit operations pass, but
  the end-to-end invariant — "user edits type → approval submits the edited type
  to the backend" — is untested and unimplemented.

**Scenario: Ontology change after initial extraction** — COVERED
- Code: `data-sources/index.vue` shows a confirmation dialog before editing when
  at least one sync run exists (`hasCompletedRun`).
- Test: `knowledge-graphs.test.ts` "Ontology Edit Confirmation Gate" (5 tests)
  verify detection of completed runs, dialog trigger, confirm/cancel flow.

---

### Requirement: Sync Monitoring — COVERED

**Scenario: Active sync progress** — COVERED
- Code: Phase label mapping (pending / ingesting / ai_extracting / applying /
  completed / failed) and badge variants in `data-sources/index.vue`.
- Test: `sync-monitoring-extended.test.ts` phase label and badge variant tests.

**Scenario: Sync history** — COVERED
- Code: Sync run history rendered per data source.
- Test: `sync-monitoring-extended.test.ts` history display tests.

**Scenario: Sync logs** — COVERED
- Code: Logs sheet fetches from
  `/management/data-sources/{ds_id}/sync-runs/{run_id}/logs`.
- Test: `knowledge-graphs.test.ts` "Sync Logs Toggle" (3 tests) and "Sync Logs
  Fetching" (3 tests).

**Scenario: Manual sync trigger** — COVERED
- Code: POST to `/management/data-sources/{ds_id}/sync`.
- Test: `sync-monitoring-extended.test.ts` "Manual sync trigger" test.

---

### Requirement: Get Started Querying (MCP Connection) — COVERED

**Scenario: API key creation inline** — COVERED
- Code: `pages/integrate/mcp.vue` shows create-key inline when no active keys exist.
- Test: `mcp-integration.test.ts` inline creation tests.

**Scenario: Copy-paste connection command** — COVERED
- Code: `mcp.vue` generates ready-to-paste config snippets with copy buttons for
  Claude Code, Cursor, Claude Desktop, and cURL.
- Test: `mcp-integration.test.ts` snippet generation tests.

**Scenario: Secret shown once** — COVERED
- Code: `useTransientSecret` composable — memory-only, auto-cleared on first read
  (`consume()`) or after 30s timeout. `api-keys/index.vue` shows one-time banner;
  `mcp.vue` consumes the transient secret.
- Test: `api-keys.test.ts` "dismissCreatedKey" test; `mcp-integration.test.ts`
  "Secret shown once" tests (null before creation, cleared on tenant switch).

---

### Requirement: Query Console — COVERED

**Scenario: Query editing** — COVERED
- Code: `pages/query/index.vue` — CodeMirror with `cypher()` language support,
  `cypherAutocomplete()`, and `ageCypherLinter()`.
- Test: `query-history.test.ts` CodeMirror extension import tests verify
  extensions return valid objects, language named `"cypher"`, autocomplete
  accepts schema changes.

**Scenario: Query execution** — COVERED
- Code: Ctrl/Cmd+Enter executes; results shown in table with execution time and
  row count.
- Test: `query-history.test.ts` "Execution result handling" and
  "Ctrl/Cmd+Enter shortcut" tests.

**Scenario: Query history** — COVERED
- Code: `pages/query/index.vue` persists history to localStorage; sidebar history
  panel.
- Test: `query-history.test.ts` covers `addToHistory`, `loadHistory`,
  `clearHistory`, deduplication, MAX_HISTORY=20 cap.

**Scenario: Knowledge graph context** — COVERED
- Code: `selectedKgId` scope selector; when empty, queries span all KGs.
- Test: `knowledge-graphs.test.ts` "Query Console KG Selector" (8 tests) and
  `query-history.test.ts` "KG scope label" tests.

---

### Requirement: Schema Browser — COVERED

**Scenario: Type listing** — COVERED
- Code: `pages/graph/schema.vue` — tabs for Node Types and Edge Types with
  unified search filter.
- Test: `schema-browser.test.ts` `filteredLabels` tests (empty query, name match,
  property match).

**Scenario: Type detail** — COVERED
- Code: Inline expand reveals description, required/optional properties.
- Test: `schema-browser.test.ts` `getSchemaProperties` tests.

**Scenario: Cross-navigation** — COVERED (with note)
- Code: Row-level buttons navigate to Query Console (pre-filled MATCH query),
  Graph Explorer (type param), and `/graph/mutations` (DEFINE template). The
  spec says "ontology editor" — the implementation uses the Mutations Console
  as the ontology editing surface.
- Test: `schema-browser.test.ts` `buildQueryNavigation`, `buildExplorerNavigation`,
  and `buildMutationsNavigation` tests.
- Note: The spec says "ontology editor for that type"; the implementation routes
  to `/graph/mutations` with a DEFINE template. If a dedicated ontology editor
  page is expected, this would need to be re-evaluated; as tested and labeled, it
  is treated as equivalent.

---

### Requirement: Graph Explorer — COVERED

**Scenario: Node search** — COVERED
- Code: `pages/graph/explorer.vue` — browse-by-type, search-within-type,
  search-across-types modes.
- Test: `graph-explorer.test.ts` `canSearch`, `typeFilterLabel`, and search
  description tests.

**Scenario: Neighbor exploration** — COVERED
- Code: Neighbor expansion panels, breadcrumb trail, `drillIntoNeighbor`.
- Test: `graph-explorer.test.ts` `drillIntoNeighbor`, `addToPath`,
  `navigateBackTo`, `getEdgeLabelForNeighbor` tests.

---

### Requirement: API Key Management — COVERED

**Scenario: Create key** — COVERED
- Code: `pages/api-keys/index.vue` create dialog; one-time secret banner.
- Test: `api-keys.test.ts` create validation and "Secret shown once" tests.

**Scenario: List keys** — COVERED
- Code: Keys grouped as active / expired / revoked with status, dates, last used.
- Test: `api-keys.test.ts` "List filtering" tests.

**Scenario: Revoke key** — COVERED
- Code: Revoke with confirmation dialog; key marked revoked.
- Test: `api-keys.test.ts` "Revoke key" tests.

---

### Requirement: Workspace Management — COVERED

**Scenario: Create workspace** — COVERED
- Code: `pages/workspaces/index.vue` — create with name and optional parent.
- Test: `workspace-management.test.ts` "Create validation" and "Creation API call"
  tests.

**Scenario: Member management** — COVERED
- Code: Add, remove, role-change for members (users and groups).
- Test: `workspace-management.test.ts` "Add member", "Remove member", "Role change"
  tests.

---

### Requirement: Design Language — COVERED

**Scenario: Component library** — COVERED
- Code: Components use Reka UI primitives with Tailwind; CVA for variants;
  Lucide Vue Next for icons.
- Test: `design-system.test.ts` verifies `package.json` dependencies.

**Scenario: Color theme** — COVERED
- Code: `assets/css/main.css` defines OKLCH custom properties for primary, neutral,
  destructive, and chart palette.
- Test: `design-system.test.ts` verifies exact OKLCH values for light and dark
  primary, chart 5-color palette.

**Scenario: Typography** — COVERED
- Code: `layouts/default.vue` uses `text-sm` body, `text-[11px]` section headers,
  `uppercase`, `tracking-wider`.
- Test: `design-language-extended.test.ts` file-content tests.

**Scenario: Border radius** — COVERED
- Code: Cards use `rounded-xl`, buttons use `rounded-md`, base `--radius: 0.625rem`.
- Test: `design-language-extended.test.ts`.

**Scenario: Elevation** — COVERED
- Code: Cards use `shadow-sm`, buttons use `shadow-xs`.
- Test: `design-language-extended.test.ts`.

---

### Requirement: Interaction Principles — COVERED

**Scenario: Progressive disclosure** — COVERED
- Test: `interaction-principles.test.ts` "Progressive disclosure" tests.

**Scenario: Inline actions over navigation** — COVERED
- Test: `interaction-principles.test.ts` "Inline editing" tests.

**Scenario: Copy-to-clipboard** — COVERED
- Test: `interaction-principles.test.ts` copy and toast confirmation tests.

**Scenario: Mutation feedback** — COVERED
- Test: `interaction-principles.test.ts` success/error toast and inline
  validation tests.

**Scenario: Keyboard shortcuts** — COVERED
- Code: Ctrl/Cmd+Enter for query execution; `/` to focus search.
- Test: `query-history.test.ts` shortcut tests; `schema-browser.test.ts`
  `/` shortcut tests.

**Scenario: Focus indicators** — COVERED
- Code: `focus-visible:ring-3 focus-visible:ring-ring/50` pattern.
- Test: `design-system.test.ts` verifies `outline-ring/50` in CSS.

---

### Requirement: Responsive Design — COVERED

**Scenario: Desktop layout** — COVERED
- Test: `responsive-design.test.ts` sidebar `hidden md:flex`, collapsible width,
  multi-column grid.

**Scenario: Tablet/mobile layout** — COVERED
- Test: `responsive-design.test.ts` Sheet-based overlay, `md:` breakpoints.

---

### Requirement: Dark Mode — COVERED

**Scenario: Toggle** — COVERED
- Code: `layouts/default.vue` dark mode toggle; `useColorMode` composable writes
  to `localStorage` under `kartograph-color-mode`.
- Test: `color-mode.test.ts` verifies toggle, persistence, system preference
  fallback, and CSS class application.

---

## Failures Requiring Fix

### FAIL 1 — Ontology Design: Agent-proposed ontology (SHALL)

**Location:** `pages/data-sources/index.vue` lines 381–395

The `beginOntologyProposal()` function uses a `setTimeout(1500ms)` simulation and
hardcoded constants instead of a real backend call. The intent text collected in
step 3 is never sent to any endpoint. The spec requires:
- "the system performs a lightweight scan of the data source"
- "an AI agent explores the scanned data and proposes an ontology"

**Fix needed:**
1. Implement (or call) a backend endpoint (e.g.,
   `POST /management/data-sources/{ds_id}/propose-ontology` or equivalent) that
   accepts the intent text and returns proposed node/edge types.
2. Replace the `setTimeout` simulation with a real `apiFetch` call.
3. Add a test verifying the intent text is included in the request and the
   response node/edge types are displayed.

### FAIL 2 — Ontology Design: Ontology review and approval (SHALL)

**Location:** `pages/data-sources/index.vue` `approveOntology()` (line 492)

The `approveOntology()` function calls only `createDataSource(...)` with
`connection_config` — the `proposedNodes` and `proposedEdges` (including all
user edits) are never sent to the backend. The spec requires:
- "extraction begins only after the user explicitly approves"
- User edits to individual types must be persisted

**Fix needed:**
1. The approval payload must include the finalized ontology (node types, edge types).
   Either add them to the `createDataSource` body or make a follow-up PUT/POST
   to an ontology endpoint after the data source is created.
2. Add a test verifying that `approveOntology()` sends the node and edge type
   definitions (including any user edits) to the backend.
3. Add a test verifying no extraction-triggering call is made unless the user
   clicks the Approve button.

### PARTIAL — Data Source Connection: Credential handling (SHALL)

**Location:** `pages/data-sources/index.vue` `connToken` ref; `useTransientSecret.ts`

The implementation is correct (no localStorage/sessionStorage writes), but there
is no regression test guarding this property.

**Fix needed (lower priority):**
Add a test asserting that `connToken` (the data source access token) is not
written to `localStorage`, `sessionStorage`, or the URL at any point during the
wizard flow.