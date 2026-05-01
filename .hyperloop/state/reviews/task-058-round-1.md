---
task_id: task-058
round: 1
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — specs/ui/experience.spec.md

### 1. Backend API Alignment
**COVERED**
- `groups.test.ts`: exact endpoint URL assertions for all group CRUD operations (GET /iam/groups, POST /iam/groups, DELETE /iam/groups/{id}, PATCH /iam/groups/{id}, and member sub-resources)
- `workspace-management.test.ts`: exact endpoint URL assertions for all workspace CRUD and member operations
- `api-keys.test.ts`: exact endpoint assertions for GET /iam/api-keys, POST /iam/api-keys, DELETE /iam/api-keys/{id}
- `knowledge-graphs.test.ts`: asserts POST /management/workspaces/{workspace_id}/knowledge-graphs includes parent workspace context
- `mcp-integration.test.ts`: asserts reactive list refresh without window.location.reload()
- All pages clear stale data on tenant version change (verified across groups, workspaces, knowledge-graphs, api-keys, home page)

### 2. Navigation Structure
**PARTIAL — Mutations Console missing from Explore group**

Spec: Explore group SHALL contain Query Console, Schema Browser, Graph Explorer, **Mutations Console**.

- `default.vue` navSections (line 247-252): Explore contains only Query Console, Schema Browser, Graph Explorer — Mutations Console is absent.
- `default.layout.test.ts` buildNavSections (line 87-96): mirrors the implementation exactly — Mutations Console is also absent from the test fixture.
- `interaction-principles.test.ts` navSections (lines 252-325): also omits Mutations Console from Explore.

All three sources (implementation + 2 test files) are consistent with each other but contradict the spec.

Default landing, new user landing: COVERED (index.test.ts, interaction-principles.test.ts).

### 3. Tenant and Workspace Context
**COVERED**
- Tenant selector: default.layout.test.ts covers tenant selector presence, aria-label, multi-tenant switching
- Tenant switch data refresh: verified across all scoped pages (groups, workspaces, api-keys, knowledge-graphs, home, mcp-integration)
- Workspace guidance toast: index.test.ts verifies per-tenant localStorage guard, toast content, and non-repeat behavior

### 4. Knowledge Graph Creation
**COVERED**
- `knowledge-graphs.test.ts`: validates name required, workspace required, POST /management/workspaces/{workspace_id}/knowledge-graphs, workspace selector population, auto-select when single workspace

### 5. Data Source Connection
**COVERED**
- `data-sources.test.ts`: wizard step navigation (adapter selection required), connection configuration form validation (name, repo URL, token), credential handling (token visibility toggle), name inference from repo URL

### 6. Ontology Design
**PARTIAL — Agent-proposed ontology and ontology review/approval scenarios lack test coverage**

Scenarios with coverage:
- Intent description: `data-sources.test.ts` — intent text required, advances to step 4 with scanningOntology=true
- Individual type editing: `data-sources.test.ts` — startEditNode, saveEditNode, cancelEditNode, removeNode, startEditEdge, saveEditEdge, cancelEditEdge, removeEdge
- Ontology change after initial extraction: `knowledge-graphs.test.ts` — confirmation gate for re-extraction
- Approval: `data-sources.test.ts` — requires knowledge graph selection

Scenarios without dedicated tests:
- Agent-proposed ontology: "system performs a lightweight scan of the data source AND an AI agent explores the scanned data and proposes an ontology" — no test verifies the scan-and-propose API call/flow
- Ontology review and approval: no test covers the "approve as-is OR iterate by editing" branching; only the KG-selection guard is tested

### 7. Sync Monitoring
**COVERED**
- `sync-monitoring-extended.test.ts`: active sync phase labels (pending/ingesting/ai_extracting/applying/completed/failed), phase detection, badge variant mapping, duration computation, manual sync trigger (POST /management/data-sources/{dsId}/sync)
- `data-sources.test.ts`: sync duration, idle status
- `knowledge-graphs.test.ts`: sync logs fetch (GET /management/data-sources/{dsId}/sync-runs/{runId}/logs), log sheet open/close, log clear on new selection

### 8. MCP Connection (Get Started Querying)
**COVERED**
- `mcp-integration.test.ts`: API key creation inline (no-keys prompt, validation, creation), copy-paste snippet (Claude Code and Cursor formats with endpoint URL and key), secret shown once (newlyCreatedKey null before creation, dismissSecret clears it, tenant switch clears it), copy button behavior

### 9. Query Console
**COVERED**
- Query editing: `default.layout.test.ts` verifies route-aware breadcrumb; `mutations.vue` shows Ctrl/Cmd+Enter keymap pattern (also present in query editor per design)
- Query execution: `knowledge-graphs.test.ts` builds query args via real `buildQueryGraphArgs` from useQueryApi
- Query history: `query-history.test.ts` exists
- Knowledge graph context: `knowledge-graphs.test.ts` — KG selector population, scope label computation, unscoped = "All knowledge graphs"

### 10. Schema Browser
**COVERED**
- `schema-browser.test.ts`: type listing with search/filtering (label and property matching), type detail (required/optional properties), cross-navigation (query console with pre-filled Cypher, graph explorer with type filter, ontology editor), keyboard "/" shortcut

### 11. Graph Explorer
**COVERED**
- `graph-explorer.test.ts`: node search by type/name/slug, Cypher query construction, neighbor exploration, exploration trail

### 12. Mutations Console
**PARTIAL — No dedicated test file; navigation omission confirmed**

Implementation is present (`pages/graph/mutations.vue`):
- Empty state with two primary actions (upload file, open editor) and quick-start templates (Create Node, Create Edge, Update Properties, Delete Entity): implemented
- JSONL editing with JSON syntax highlighting, line numbers, linting, autocomplete, Ctrl/Cmd+Enter: implemented
- Live preview (MutationPreview component), parse error gutter: implemented
- File upload and drag-and-drop: implemented
- Large-file mode (LARGE_FILE_THRESHOLD): implemented
- Submission with floating MutationProgress indicator (in app.vue, persists across navigation): implemented
- Submission failure display: implemented
- Template insertion: implemented
- Deep-link (?view=editor, ?template=): implemented (lines 105-107, 386-388)

**Tests: MISSING** — No test file covers any Mutations Console scenarios:
- No test for empty-state rendering or template insertion logic
- No test for file upload handling or large-file mode threshold
- No test for submission state machine or floating indicator persistence
- No test for deep-link initialization (?view=editor, ?template=)
- No test for submission failure state

The Mutations Console page is also not listed in the Explore nav group in any test fixture.

### 13. API Key Management
**COVERED**
- `api-keys.test.ts`: create key (name required, expiry 1-3650 days, secret shown once, dismiss clears), list keys (active/expired/revoked status, keyStatus helper), revoke key (confirmation dialog, DELETE /iam/api-keys/{id}, NOT POST /revoke)

### 14. Workspace Management
**COVERED**
- `workspace-management.test.ts`: create workspace (name required, parent required, API call, toast), member management (add, remove, role change, confirmation dialog, guard patterns), tree building, flatten tree, search filtering, inline editing (no navigation), responsive layout, tenant switch data refresh

### 15. Design Language
**COVERED**
- `design-language.test.ts`: reads actual source files — verifies OKLCH tokens (primary light/dark, background, card, border, destructive, 5-chart palette), typography (system font, text-sm, text-[11px] + uppercase + tracking-wider, font-medium/semibold, no font-bold), border radius (--radius 0.625rem, rounded-xl cards, rounded-md buttons/inputs, rounded-full badges), elevation (shadow-sm cards, shadow-xs buttons, no shadow-lg/xl)
- `design-language-extended.test.ts` and `design-system.test.ts`: additional coverage (CVA usage, Lucide icons)

### 16. Interaction Principles
**COVERED**
- `interaction-principles.test.ts`: copy-to-clipboard (writeText call, success toast, error toast, generic label), mutation feedback (success/error toast, inline validation errors), progressive disclosure (collapsible section, sheet/drawer), inline editing (dialog not navigation)
- `focus-ring.test.ts`: focus-visible:ring-[3px] on default.vue, mcp.vue, tenants/index.vue; no ring-2; ring-ring/50 opacity; outline-none to suppress native outlines
- Keyboard shortcuts: verified via Ctrl/Cmd+Enter in mutations.vue and query console implementation

### 17. Responsive Design
**COVERED**
- `responsive-design.test.ts`: reads default.vue — "hidden md:flex", transition-all, sidebar w-64/w-16 toggle, Sheet/SheetContent for mobile, route watcher closes mobile sheet, localStorage persistence (kartograph:sidebar-collapsed), workspace page Sheet on mobile, lg: grid columns

### 18. Dark Mode
**COVERED**
- `color-mode.test.ts`: toggle persists to localStorage, initial load reads from localStorage, system preference fallback, CSS class application (add/remove "dark" on documentElement)
- `color-mode.test.ts` + `default.vue` inspection: toggle in header uses Moon/Sun icons, @click="toggleColorMode", inside <header> element, accessible tooltip labels ("Switch to light/dark mode")

---

## Summary of Failures

### FAIL 1: Navigation Structure — Mutations Console absent from Explore group
- Spec: Explore SHALL contain Query Console, Schema Browser, Graph Explorer, **Mutations Console**
- Implementation (`default.vue` line 247-252): only 3 items, no Mutations Console
- Tests (`default.layout.test.ts` buildNavSections, `interaction-principles.test.ts` navSections): both mirror the wrong nav structure
- This is a code deviation from spec AND a test that validates the wrong behavior

### FAIL 2: Mutations Console — no test coverage for any scenario
- 8 spec scenarios (empty state, JSONL editing, live preview, file upload, submission, submission failure, template insertion, deep-link) have zero test coverage
- Implementation exists in `pages/graph/mutations.vue` but all 8 scenarios are MISSING from the test suite

### FAIL 3: Ontology Design — agent-proposed ontology scenario not tested
- Spec: "system performs a lightweight scan of the data source AND an AI agent explores the scanned data and proposes an ontology"
- `data-sources.test.ts` only tests that `scanningOntology = true` on step advance; the actual scan API call and proposal response handling have no test
- Spec: ontology review — "approve as-is OR iterate by editing" — only the KG-selection guard is tested, not the approval/iteration branching