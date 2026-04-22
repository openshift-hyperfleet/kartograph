---
task_id: task-014
round: 0
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — task-014: UI/UX Experience Spec

This review checks every requirement in `specs/ui/experience.spec.md` against the
code in `src/dev-ui/` on branch `hyperloop/task-014`.

**Verdict rationale:** Many high-level features are fully implemented; however, multiple
spec requirements are MISSING (no code at all) and several others are only PARTIAL
(scaffolded or stubbed with explicit "coming soon" markers). Because the spec is evaluated
as a whole, the verdict is `fail`. The navigation restructure and stubs added in this
branch's commits are correct and properly scoped, but the majority of the spec is not yet
implemented.

---

### Requirement: Navigation Structure

#### Scenario: Primary navigation
- Status: COVERED
- Code: `src/dev-ui/app/layouts/default.vue` lines 181–212 define `navSections` with all
  four groups: Explore (Query Console, Schema Browser, Graph Explorer), Data (Knowledge
  Graphs, Data Sources), Connect (API Keys, MCP Integration), Settings (Workspaces,
  Groups, Tenants). Desktop sidebar at lines 262–551, mobile Sheet at lines 553–703.
- Tests: NONE — no frontend unit/component tests exist in this repo.

#### Scenario: Default landing (returning user)
- Status: PARTIAL
- Code: `src/dev-ui/app/pages/index.vue` — the Home dashboard shows stats cards and quick
  actions for returning users. However, there is no route guard or redirect logic that
  sends a "returning user with existing knowledge graphs" specifically to the Explore /
  Query Console view. The home route (`/`) always lands on the dashboard, not the Explore
  section.
- Tests: NONE

#### Scenario: New user landing
- Status: PARTIAL
- Code: `src/dev-ui/app/pages/knowledge-graphs/index.vue` lines 100–155 implement a
  "No knowledge graphs yet" empty state with a 3-step visual (Create → Connect → Query).
  `src/dev-ui/app/pages/index.vue` shows an onboarding checklist (lines 59–97). However,
  there is no automatic redirect: new users land on the generic home page, not a dedicated
  setup flow. The spec says "they are guided toward the setup flow", which is partially
  satisfied by the checklist but not by navigation.
- Tests: NONE

---

### Requirement: Tenant and Workspace Context

#### Scenario: Tenant selector
- Status: COVERED
- Code: `src/dev-ui/app/layouts/default.vue` lines 277–418 (desktop sidebar) and
  562–644 (mobile). Handles loading state, zero tenants, single tenant, and multi-tenant
  dropdown. Switching triggers `handleTenantChange` (line 121) → `switchTenant`, and all
  pages react to `tenantVersion` watcher to refresh data.
- Tests: NONE

#### Scenario: Workspace guidance (new user, no workspace)
- Status: MISSING
- Code: The workspaces page (`src/dev-ui/app/pages/workspaces/index.vue`) provides full
  CRUD for workspaces. However, there is NO detection of "entering a tenant for the first
  time with no personal workspace" and NO prompt to create/join. The spec says the UI
  SHALL suggest creating or joining a workspace in this case.
- Tests: NONE

---

### Requirement: Knowledge Graph Creation

#### Scenario: Create knowledge graph
- Status: PARTIAL
- Code: `src/dev-ui/app/pages/knowledge-graphs/index.vue` implements a create dialog
  (lines 159–206) with name + description fields and inline validation. The dialog
  description (line 163–169) mentions the user "will be prompted to add a data source
  after creation." However, the actual API call is stubbed (lines 58–63: emits an info
  toast and closes immediately). The "prompt to add data source" after creation is
  mentioned in copy but not wired as a post-creation navigation step or flow.
- Tests: NONE

---

### Requirement: Data Source Connection

#### Scenario: Adapter type selection
- Status: MISSING
- Code: `src/dev-ui/app/pages/data-sources/index.vue` is a "Coming Soon" placeholder
  (lines 47–87). No adapter type selection UI exists.
- Tests: NONE

#### Scenario: Connection configuration
- Status: MISSING
- Code: Same as above — entirely stubbed.
- Tests: NONE

#### Scenario: Credential handling
- Status: MISSING
- Code: No credential handling UI. The spec requires credentials are encrypted
  server-side and plaintext is never persisted in the browser; this is a server concern,
  but the UI flow does not exist.
- Tests: NONE

---

### Requirement: Ontology Design

#### Scenario: Intent description
- Status: MISSING
- Code: No free-text intent description prompt exists anywhere in the codebase.
- Tests: NONE

#### Scenario: Agent-proposed ontology
- Status: MISSING
- Code: No AI-driven ontology proposal UI.
- Tests: NONE

#### Scenario: Ontology review and approval
- Status: MISSING
- Code: No review/approval flow.
- Tests: NONE

#### Scenario: Individual type editing
- Status: MISSING
- Code: `src/dev-ui/app/pages/graph/mutations.vue` exists and allows manual JSONL
  mutation authoring, which can define/edit types. However, the spec's individual-type
  editor (label, description, required/optional properties, relationship types) is not
  implemented as a guided UI step.
- Tests: NONE

#### Scenario: Ontology change warning after extraction
- Status: MISSING
- Code: No warning/confirmation flow for re-extraction.
- Tests: NONE

---

### Requirement: Sync Monitoring

#### Scenario: Active sync progress
- Status: MISSING
- Code: No sync progress UI exists. Data Sources page is a "Coming Soon" stub.
- Tests: NONE

#### Scenario: Sync history
- Status: MISSING
- Code: No sync history UI.
- Tests: NONE

#### Scenario: Sync logs
- Status: MISSING
- Code: No sync log viewer.
- Tests: NONE

#### Scenario: Manual sync trigger
- Status: MISSING
- Code: No manual sync trigger UI.
- Tests: NONE

---

### Requirement: Get Started Querying (MCP Connection)

#### Scenario: API key creation inline
- Status: COVERED
- Code: `src/dev-ui/app/pages/integrate/mcp.vue` lines 436–482 — when no active API
  keys exist, a "Create API Key" dialog is shown inline on the MCP page. Lines 387–434
  handle the "has existing keys" state with a "Create New Key" option.
- Tests: NONE

#### Scenario: Copy-paste connection command
- Status: COVERED
- Code: `src/dev-ui/app/pages/integrate/mcp.vue` lines 488–594 — tabbed config blocks
  for Claude Code, Cursor, Claude Desktop, and cURL, each with a copy button. The snippet
  includes MCP endpoint URL and API key placeholder (or real secret when just created).
- Tests: NONE

#### Scenario: Secret shown once
- Status: COVERED
- Code: `src/dev-ui/app/pages/api-keys/index.vue` lines 368–452 — newly created key is
  shown in an amber warning banner with "This is the only time the full secret will be
  shown." The secret display is removed when dismissed. `useTransientSecret` composable
  (`src/dev-ui/app/composables/useTransientSecret.ts`) handles cross-page secret transfer
  without persisting to localStorage.
- Tests: NONE

---

### Requirement: Query Console

#### Scenario: Query editing (syntax highlighting, autocomplete, linting)
- Status: COVERED
- Code: `src/dev-ui/app/pages/query/index.vue` lines 107–138 — CodeMirror with
  `cypher()` language, `ageCypherLinter()`, `cypherTooltips()`, and
  `cypherAutocomplete()` (schema-aware). Theme in
  `src/dev-ui/app/lib/codemirror/theme.ts`.
- Tests: NONE

#### Scenario: Query execution (button + Ctrl/Cmd+Enter, results table)
- Status: COVERED
- Code: `src/dev-ui/app/pages/query/index.vue` lines 112–123 (keymap), 142–186
  (executeQuery), 457–479 (Execute button with Ctrl+Enter tooltip). Results displayed via
  `QueryResultsPanel` component.
- Tests: NONE

#### Scenario: Query history
- Status: COVERED
- Code: `src/dev-ui/app/pages/query/index.vue` lines 232–261 — history stored in
  localStorage, browsable via `QuerySidebar` / `HistoryPanel` component.
- Tests: NONE

#### Scenario: Knowledge graph context selector
- Status: MISSING
- Code: The query console has no "select a specific knowledge graph" dropdown to scope
  queries. Queries span all graphs accessible in the tenant with no per-graph scoping.
  The spec requires a KG context selector with graceful fall-through to all-graphs.
- Tests: NONE

---

### Requirement: Schema Browser

#### Scenario: Type listing with search and filter
- Status: COVERED
- Code: `src/dev-ui/app/pages/graph/schema.vue` lines 291–305 — unified search input
  with keyboard shortcut (`/` or `Ctrl+K`). Node types and edge types listed in tabs with
  counts.
- Tests: NONE

#### Scenario: Type detail (description, required, optional properties)
- Status: COVERED
- Code: `src/dev-ui/app/pages/graph/schema.vue` lines 454–511 — inline expand shows
  description, required properties (Required badge), and optional properties (Optional
  badge).
- Tests: NONE

#### Scenario: Cross-navigation (query console, graph explorer, ontology editor)
- Status: PARTIAL
- Code: Node types have three action buttons: navigate to query console (line 414),
  navigate to explorer (line 429), navigate to mutations/edit (line 444). However, edge
  types only have query console and mutations — the explorer cross-link is absent for
  edges (lines 607–629). The spec says "from a type in the schema browser, navigate to
  graph explorer" but this is only wired for node types.
- Tests: NONE

---

### Requirement: Graph Explorer

#### Scenario: Node search (by type, name, slug)
- Status: COVERED
- Code: `src/dev-ui/app/pages/graph/explorer.vue` implements search with a type filter
  combobox and text search. Uses `findNodesBySlug` and `listNodeLabels` from the graph
  API.
- Tests: NONE

#### Scenario: Neighbor exploration
- Status: COVERED
- Code: `src/dev-ui/app/pages/graph/explorer.vue` — `getNodeNeighbors` is imported and
  used; `neighborNodes`, `neighborEdges`, `explorationPath`, and `centralNode` state
  exist. Neighbor nodes and edges are displayed with labels and direction; exploration
  trail is tracked.
- Tests: NONE

---

### Requirement: API Key Management

#### Scenario: Create key
- Status: COVERED
- Code: `src/dev-ui/app/pages/api-keys/index.vue` lines 302–345 — dialog with name and
  expiration. Secret shown once in amber banner (lines 368–452).
- Tests: NONE

#### Scenario: List keys (status, creation date, last used, expiration)
- Status: COVERED
- Code: `src/dev-ui/app/pages/api-keys/index.vue` lines 495–685 — tables for active,
  expired, and revoked keys with all required columns (status via section headers/badges,
  created, expires, last used). Summary bar (lines 476–493).
- Tests: NONE

#### Scenario: Revoke key
- Status: COVERED
- Code: `src/dev-ui/app/pages/api-keys/index.vue` lines 186–209 — `handleRevoke` calls
  `revokeApiKey` and refreshes. Confirmation dialog lines 733–757.
- Tests: NONE

---

### Requirement: Workspace Management

#### Scenario: Create workspace
- Status: COVERED
- Code: `src/dev-ui/app/pages/workspaces/index.vue` — `createWorkspace` API call wired,
  name + optional parent dialog.
- Tests: NONE

#### Scenario: Member management (add, remove, change roles)
- Status: COVERED
- Code: `src/dev-ui/app/pages/workspaces/index.vue` — `addWorkspaceMember`,
  `removeWorkspaceMember`, `updateWorkspaceMemberRole` all imported and wired. Role
  editing, member removal confirmation dialog exist.
- Tests: NONE

---

### Requirement: Design Language

#### Scenario: Component library (shadcn/vue + Reka UI + Tailwind + CVA + Lucide)
- Status: COVERED
- Code: `src/dev-ui/components.json` confirms shadcn-vue. `package.json` lists
  `reka-ui`, `tailwindcss`, `class-variance-authority`, `lucide-vue-next`. Button CVA
  definition at `src/dev-ui/app/components/ui/button/index.ts` lines 6–37.
- Tests: NONE

#### Scenario: Color theme (OKLCH custom properties, exact primary values)
- Status: COVERED
- Code: `src/dev-ui/app/assets/css/main.css` — `--radius: 0.625rem` (line 45),
  `--primary: oklch(0.5768 0.2469 29.23)` (line 52, light), `--primary: oklch(0.6857
  0.1560 17.57)` (line 86, dark). Five chart colors defined (lines 64–68 / 97–101). All
  values match the spec exactly.
- Tests: NONE

#### Scenario: Typography (system font, text-sm body, text-[11px] uppercase headers)
- Status: COVERED
- Code: `src/dev-ui/app/layouts/default.vue` line 466 — section headers use
  `text-[11px] font-semibold uppercase tracking-wider`. Body text uses `text-sm` via
  Tailwind defaults. No custom fonts imported.
- Tests: NONE

#### Scenario: Border radius (base 0.625rem, cards rounded-xl, buttons rounded-md)
- Status: COVERED
- Code: `src/dev-ui/app/assets/css/main.css` line 45 `--radius: 0.625rem`. CVA button
  uses `rounded-md` (index.ts line 7). Cards use `rounded-xl` via shadcn card component.
- Tests: NONE

#### Scenario: Elevation (shadow-sm cards, shadow-xs buttons, flat UI)
- Status: PARTIAL
- Code: Button CVA (button/index.ts line 17) uses `shadow-xs` for the outline variant.
  Card components use `shadow-sm` via shadcn defaults. However, there is no explicit
  validation that ALL cards use shadow-sm and ALL buttons use shadow-xs — some button
  variants (e.g., ghost, link) have no shadow at all, which is consistent with the "flat"
  principle but not explicitly verified.
- Tests: NONE

---

### Requirement: Interaction Principles

#### Scenario: Progressive disclosure
- Status: COVERED
- Code: Schema browser expands type detail on demand (schema.vue). MCP page uses
  collapsible sections (mcp.vue lines 602–680). Query sidebar is collapsible.
- Tests: NONE

#### Scenario: Inline actions over navigation
- Status: COVERED
- Code: Workspaces page uses inline rename (editingName state) and a Sheet panel for
  detail/member management. No separate edit pages exist.
- Tests: NONE

#### Scenario: Copy-to-clipboard with toast
- Status: COVERED
- Code: `copyToClipboard` helper in api-keys and mcp pages; `CopyableText` component;
  toast on success/failure throughout.
- Tests: NONE

#### Scenario: Mutation feedback (toast on success/failure, inline validation)
- Status: COVERED
- Code: All create/update/delete operations use `toast.success` / `toast.error`.
  Inline field errors (e.g., `createNameError`, `createExpiryError`) displayed on form
  fields.
- Tests: NONE

#### Scenario: Keyboard shortcuts (Ctrl/Cmd+Enter, /)
- Status: PARTIAL
- Code: `Ctrl+Enter` for query execution (query/index.vue lines 112–123). `/` and
  `Ctrl+K` for search focus in schema browser (schema.vue lines 221–238). No keyboard
  shortcut documented for the explorer or other power-user actions.
  The spec says shortcuts should be "discoverable via tooltip" — the query Execute button
  shows `Ctrl+Enter` in the tooltip (line 476); schema browser shows `/ Ctrl+K` in the
  input placeholder and a `kbd` hint (line 301). Partially satisfied.
- Tests: NONE

#### Scenario: Focus indicators (3px ring at primary color 50% opacity)
- Status: COVERED
- Code: `src/dev-ui/app/components/ui/button/index.ts` line 7 —
  `focus-visible:ring-ring/50 focus-visible:ring-[3px]`. `main.css` line 115 —
  `@apply border-border outline-ring/50` globally suppresses native outlines in favor of
  the ring system.
- Tests: NONE

---

### Requirement: Responsive Design

#### Scenario: Desktop layout (collapsible sidebar, multi-column)
- Status: COVERED
- Code: `src/dev-ui/app/layouts/default.vue` — desktop sidebar (`hidden md:flex`,
  lines 260–551) with collapse toggle. Content area uses multi-column grids (e.g.,
  index.vue `grid grid-cols-2 md:grid-cols-4`).
- Tests: NONE

#### Scenario: Tablet/mobile (sheet overlay, single-column)
- Status: COVERED
- Code: `src/dev-ui/app/layouts/default.vue` lines 553–703 — mobile sidebar uses Sheet
  component (overlay). Mobile header shows hamburger (line 710). Layouts adapt to
  single-column on narrow screens (`sm:grid-cols-2`, etc.).
- Tests: NONE

---

### Requirement: Dark Mode

#### Scenario: Toggle in header, persists across sessions
- Status: COVERED
- Code: `src/dev-ui/app/layouts/default.vue` lines 749–760 — dark mode toggle button in
  header with Sun/Moon icons. `src/dev-ui/app/composables/useColorMode.ts` — persists
  via `localStorage.setItem('kartograph-color-mode', ...)` (line 17) and reads on
  `onMounted` (lines 20–28).
- Tests: NONE

---

## Summary Table

| Requirement | Scenarios | Status |
|---|---|---|
| Navigation Structure | Primary nav | COVERED |
| Navigation Structure | Default landing (returning) | PARTIAL |
| Navigation Structure | New user landing | PARTIAL |
| Tenant/Workspace Context | Tenant selector | COVERED |
| Tenant/Workspace Context | Workspace guidance | MISSING |
| Knowledge Graph Creation | Create KG | PARTIAL (API stubbed) |
| Data Source Connection | Adapter selection | MISSING |
| Data Source Connection | Connection config | MISSING |
| Data Source Connection | Credential handling | MISSING |
| Ontology Design | Intent description | MISSING |
| Ontology Design | Agent-proposed ontology | MISSING |
| Ontology Design | Review and approval | MISSING |
| Ontology Design | Individual type editing | MISSING |
| Ontology Design | Change warning | MISSING |
| Sync Monitoring | Active sync progress | MISSING |
| Sync Monitoring | Sync history | MISSING |
| Sync Monitoring | Sync logs | MISSING |
| Sync Monitoring | Manual trigger | MISSING |
| MCP Connection | API key creation inline | COVERED |
| MCP Connection | Copy-paste command | COVERED |
| MCP Connection | Secret shown once | COVERED |
| Query Console | Query editing | COVERED |
| Query Console | Query execution | COVERED |
| Query Console | Query history | COVERED |
| Query Console | KG context selector | MISSING |
| Schema Browser | Type listing with search | COVERED |
| Schema Browser | Type detail | COVERED |
| Schema Browser | Cross-navigation | PARTIAL (edges missing explorer link) |
| Graph Explorer | Node search | COVERED |
| Graph Explorer | Neighbor exploration | COVERED |
| API Key Management | Create key | COVERED |
| API Key Management | List keys | COVERED |
| API Key Management | Revoke key | COVERED |
| Workspace Management | Create workspace | COVERED |
| Workspace Management | Member management | COVERED |
| Design Language | Component library | COVERED |
| Design Language | Color theme | COVERED |
| Design Language | Typography | COVERED |
| Design Language | Border radius | COVERED |
| Design Language | Elevation | PARTIAL |
| Interaction Principles | Progressive disclosure | COVERED |
| Interaction Principles | Inline actions | COVERED |
| Interaction Principles | Copy-to-clipboard | COVERED |
| Interaction Principles | Mutation feedback | COVERED |
| Interaction Principles | Keyboard shortcuts | PARTIAL |
| Interaction Principles | Focus indicators | COVERED |
| Responsive Design | Desktop layout | COVERED |
| Responsive Design | Tablet/mobile | COVERED |
| Dark Mode | Toggle + persistence | COVERED |

## Key Gaps

1. **Data Source Connection** (all 3 scenarios) — entirely "Coming Soon"
2. **Ontology Design** (all 5 scenarios) — not implemented at all
3. **Sync Monitoring** (all 4 scenarios) — not implemented at all
4. **Workspace guidance** for new tenant entry — missing
5. **Query Console KG context selector** — not wired
6. **Schema Browser cross-navigation for edge types** — no explorer link

## Testing Gap

There are ZERO frontend component or unit tests. The spec does not explicitly mandate
frontend tests, but the project's TDD mandate in AGENTS.md requires tests to verify
behavior. All UI scenarios listed above have no corresponding test coverage.