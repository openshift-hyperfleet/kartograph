---
task_id: task-141
round: 14
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review — task-141
**Spec:** specs/ui/experience.spec.md (User Experience)
**Branch:** hyperloop/task-141

## Summary

17 of 18 requirements are fully COVERED with implementation and test coverage. One requirement — **Ontology Design** — is PARTIAL because the "Individual type editing" scenario's "add or remove relationship types" condition is not verifiably implemented.

---

## Requirement-by-Requirement Findings

### Requirement: Backend API Alignment — COVERED
- `useApiClient` composable injects `X-Tenant-ID` header on every request
- Workspace-scoped KG operations include parent context automatically
- Tests: `src/dev-ui/app/tests/api-alignment.test.ts`

### Requirement: Navigation Structure — COVERED
- `layouts/default.vue` renders exactly four groups: **Explore** (Query Console, Schema Browser, Graph Explorer, Mutations Console), **Data** (Knowledge Graphs, Data Sources), **Connect** (API Keys, MCP Integration), **Settings** (Workspaces, Groups, Tenants)
- `pages/index.vue` redirects returning users (with KGs) to `/query`; shows Getting Started checklist with `data-testid="new-user-kg-prompt"` when no KGs exist
- Tests: `navigation-structure.test.ts`, `new-user-landing.test.ts`

### Requirement: Tenant and Workspace Context — COVERED
- Tenant selector: `DropdownMenu` in sidebar; `switchTenant()` refreshes all data via `tenantVersion` reactivity
- Workspace guidance: toast + `WorkspaceGuidance` component with "Create" and "Join" actions when no workspace exists
- Tests: `tenant-switch.test.ts`, `workspace-guidance.test.ts`

### Requirement: Knowledge Graph Creation — COVERED
- `pages/knowledge-graphs/index.vue` with name, description, workspace selector
- After creation, user is prompted to add first data source
- Tests: `knowledge-graphs.test.ts`

### Requirement: Data Source Connection — COVERED
- 4-step wizard in `pages/data-sources/index.vue`
- Adapter type selection with GitHub/GitLab/Jira options; form adapts per adapter
- `inferNameFromRepoUrl()` in `utils/dataSourceWizard.ts` provides name inference
- Credentials sent to API (encrypted via Vault server-side); plaintext cleared from browser state after submission
- Tests: `data-source-connection-wizard.test.ts`, `data-sources.test.ts`

### Requirement: Ontology Design — PARTIAL ⚠️

**Covered scenarios:**
- **Intent description:** Free-text field in wizard step 3 ✅
- **Agent-proposed ontology:** Lightweight scan phase + AI-proposed node/edge types presented ✅
- **Ontology review and approval:** Inline type editor, "Approve & Begin Extraction" button required ✅
- **Ontology change after initial extraction:** Warning dialog with re-extraction confirmation ✅

**Partially covered scenario:**
- **Individual type editing:** Editing of `label`, `description`, `required_properties`, `optional_properties` is implemented. However, the spec's THEN block also requires:
  - **"AND they can add or remove relationship types"** — the implementation does not appear to expose controls to add new edge types or remove existing proposed edge types within the type editor; the edge type set is fixed at proposal time.
  - **"AND they can specify exact property requirements (e.g., 'documentation_page must have source_url')"** — per-property requirement specification may be limited to adding/removing property names rather than constraint-level requirements.

  Tests: `ontology-design.test.ts`, `ontology-add-types.test.ts`

**What is needed:** The individual type editor must allow the user to add relationship types (edge types) to a node type and remove existing relationship types from the proposed ontology. This corresponds to the `AND they can add or remove relationship types` THEN condition.

### Requirement: Sync Monitoring — COVERED
- `SyncPhaseIndicator` component shows pending/ingesting/ai_extracting/applying phases
- Sync history with completed/failed runs, timestamps, duration
- Logs sheet panel per sync run
- Manual sync trigger with permission guard; polling when active syncs present
- Tests: `sync-monitoring-extended.test.ts`, `sync-phase-indicator.test.ts`, `sync-logs.test.ts`

### Requirement: Get Started Querying (MCP Connection) — COVERED
- `pages/integrate/mcp.vue` — inline API key creation prompt when `activeKeys.length === 0`
- Multi-tool config snippets (Claude Code, Cursor, Claude Desktop, cURL) with copy buttons
- Newly created key secret shown once via `newlyCreatedKey` state; cleared (`dismissSecret()`) on dismiss, making it unrecoverable from UI
- Tests: `mcp-integration.test.ts`, `transient-secret.test.ts`

### Requirement: Query Console — COVERED
- `pages/query/index.vue` with CodeMirror: `cypher()`, `ageCypherLinter()`, `cypherAutocomplete()` (schema-aware), `cypherTooltips()`
- Execute button + Ctrl/Cmd+Enter; `QueryResultsPanel` with row count and execution time
- `HistoryPanel` persisted to localStorage; re-execute and insert-at-cursor
- KG scope selector defaulting to "All knowledge graphs"
- Tests: `query.test.ts`, `query-history.test.ts`, `query-kg-selector.test.ts`

### Requirement: Schema Browser — COVERED
- `pages/graph/schema.vue` with node/edge type tabs, search filtering, virtual scrolling
- Inline expansion shows description, required properties (badged), optional properties (badged)
- Cross-navigation: Terminal→`/query` (pre-filled), Share2→`/graph/explorer?type=`, PenLine→`/data-sources?openOntologyType=`
- Tests: `schema-browser.test.ts`, `schema-crossnav-deeplink.test.ts`

### Requirement: Graph Explorer — COVERED
- `pages/graph/explorer.vue` — search by name/slug/title, type filter combobox
- "Explore Neighbors" calls `getNodeNeighbors(nodeId)`; connected nodes with edge labels and direction; drill-in with breadcrumb trail
- Tests: `graph-explorer.test.ts`

### Requirement: Mutations Console — COVERED
All 8 scenarios implemented:
- Empty state with two primary cards + 4 quick-start templates + drag-and-drop
- CodeMirror: JSON highlighting, line numbers, `lintGutter()`, mutation linter/autocomplete; Ctrl/Cmd+Enter submits
- Live preview: `MutationPreview` with DEFINE/CREATE/UPDATE/DELETE breakdown; parse errors in gutter
- File upload: picker + drag-and-drop; ≥5MB → large-file mode (`LargeFileSummary`)
- KG selection: workspace then KG two-step selector, filtered to `permission=edit`; submission blocked until selected
- Submission: `useMutationSubmission` (Nuxt `useState`) with floating `MutationProgress` indicator in `app.vue` persisting across navigation; shows status/op count/elapsed time; minimize-to-pill and dismiss
- Failure: error message + `operations_applied` count in indicator
- Template insertion: appends to existing content; activates editor if closed
- Deep-link: `?view=editor` opens editor; `?template=<content>` inserts content
- Tests: `mutations-console.test.ts`, `mutations-submission.test.ts`, `mutations-indicator-persistence.test.ts`, `mutations-kg-selector.test.ts`, `mutations-kg-loading.test.ts`, `mutations-workspace-selector.test.ts`

### Requirement: API Key Management — COVERED
- `pages/api-keys/index.vue` — create dialog (name + expiration), secret shown once in amber banner with copy
- Three sections: Active, Expired, Revoked; status, creation date, last used, expiration shown
- Revoke: `AlertDialog` confirmation, `revokeApiKey()` call
- Tests: `api-keys.test.ts`

### Requirement: Workspace Management — COVERED
- `pages/workspaces/index.vue` — create dialog with name and optional parent selector
- Member sheet per workspace: add/remove/role-change for users and groups via `addWorkspaceMember`, `removeWorkspaceMember`, `updateWorkspaceMemberRole`
- Tests: `workspace-management.test.ts`

### Requirement: Design Language — COVERED
- `components.json` configures shadcn/vue (Reka UI primitives)
- `Button.vue` uses `reka-ui` `Primitive`; variants via `class-variance-authority` (`cva`); icons from `lucide-vue-next`
- `main.css`: OKLCH custom properties match spec exactly (`--primary: oklch(0.5768 0.2469 29.23)` light, `oklch(0.6857 0.1560 17.57)` dark); 5-color chart palette; destructive coral
- System font stack (no custom font imports); `text-sm` body; `text-[11px] uppercase tracking-wider` section headers; font weights 500/600 only
- `--radius: 0.625rem` base; `rounded-xl` cards, `rounded-md` buttons/inputs, `rounded-full` badges
- `shadow-sm` cards, `shadow-xs` outline buttons
- Tests: `design-language.test.ts`, `design-language-extended.test.ts`, `design-system.test.ts`

### Requirement: Interaction Principles — COVERED
- Progressive disclosure via expand/sheet/drill-in patterns throughout
- Inline/sheet editing for workspaces, groups, tenants — no separate edit pages
- `useCopyToClipboard` composable + `CopyableText` component + Sonner toast confirmation
- All write operations use `toast.success`/`toast.error`; inline validation errors with `text-destructive`
- Ctrl/Cmd+Enter in Query Console and Mutations Console; "/" global search; Ctrl+K in Schema Browser
- `focus-visible:ring-[3px] focus-visible:ring-ring/50` in `Button.vue` CVA base
- Tests: `interaction-principles.test.ts`, `keyboard-shortcuts.test.ts`, `focus-ring.test.ts`

### Requirement: Responsive Design — COVERED
- Desktop: sidebar visible (`hidden md:flex`), collapsible via `useSidebar`; multi-column grids
- Mobile: `Sheet` overlay triggered by hamburger (`md:hidden`); query sidebar Sheet on mobile (`xl:hidden`); mutations templates → Sheet; single-column responsive grids
- Tests: `responsive-design.test.ts`

### Requirement: Dark Mode — COVERED
- `composables/useColorMode.ts`: `kartograph-color-mode` persisted to localStorage; `prefers-color-scheme` fallback; toggles `.dark` on `documentElement`
- Toggle button (Sun/Moon) in `default.vue` header with tooltip
- Dark theme variables in `main.css` under `.dark {}`
- Tests: `color-mode.test.ts`

---

## Verdict: FAIL

**Blocking finding:** The **Ontology Design** requirement — specifically the **"Individual type editing"** scenario — is PARTIAL. The spec's THEN block requires:

> "AND they can add or remove relationship types"

The current implementation provides per-type editing of label, description, required_properties, and optional_properties, but the edge type set appears fixed at proposal time with no UI controls to add new relationship types or remove existing ones within the type editor.

**Required fix:** Implement "add/remove relationship types" functionality in the individual type editor. This should allow users to:
1. Add a new edge type (specify label, direction, from/to node types)
2. Remove an existing proposed edge type from the ontology

After implementing this, re-run `bash .hyperloop/checks/check-frontend-tests-pass.sh` and verify the scenario is covered by a test that exercises the add/remove relationship types interaction.

No other spec requirement has a missing or partial implementation. All 17 other requirements are fully covered with tests.