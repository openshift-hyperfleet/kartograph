---
task_id: task-045
round: 7
role: spec-reviewer
verdict: fail
---
## Summary

Branch `hyperloop/task-045` is clean (no merge conflict markers, working tree is clean). The "Merge failed" note in the task description was historical — the branch is in a coherent state. All 533 UI unit tests pass on the current branch.

However, there are two **FAIL** items against completed work.

---

## Requirement Status

### Requirement: Backend API Alignment — PARTIAL / FAIL

**Status: task-050 is `not-started` and no tests assert exact endpoint URLs for IAM CRUD operations.**

The spec requires:
- Every create/read/update/delete via the UI must call the correct backend API endpoint (2xx response)
- Parent context must be included in scoped resources

**What exists:**
- `workspace-management.test.ts` line 169–184 tests `createWorkspace` with `parent_workspace_id` — COVERED
- `data-sources.test.ts` tests the data source wizard with adapter selection and credential handling — COVERED
- `knowledge-graphs.test.ts` tests `POST /management/workspaces/{id}/knowledge-graphs` — COVERED

**What is missing (task-050 scope, not yet implemented):**
- No test asserts the exact endpoint URL for group CRUD operations (list, create, member management)
- No test asserts the exact endpoint URL for API key lifecycle operations (list uses `/iam/api-keys`, revoke uses `DELETE /iam/api-keys/{id}`)
- No test asserts UI state refresh (reactive update without page reload) after workspace/group/API key mutations
- Scenario "Resource operations succeed end-to-end" has no test verifying that after a workspace creation the workspace list is reactively updated without a manual refresh
- Scenario "Parent context is preserved" has partial coverage (workspace parent_id is tested) but no verification that the actual API call succeeds (tests use mocked `createWorkspace`, not the real endpoint path string)

**Failing scenario coverage:**
- "Resource operations succeed end-to-end": no integration or end-to-end test verifies 2xx API response; unit tests mock all API calls
- "Parent context is preserved": workspace parent tested in unit tests with mock; no test verifies the exact URL path sent to the real backend

---

### Requirement: Navigation Structure — COVERED

- Primary navigation: `default.layout.test.ts` and `interaction-principles.test.ts` verify all 4 sections (Explore, Data, Connect, Settings) with all items
- Default landing (returning user redirect): `index.test.ts` covers redirect to `/query` when KGs exist
- New user landing (checklist): `index.test.ts` and `interaction-principles.test.ts` cover the onboarding checklist prompt

**No deviations from spec.**

---

### Requirement: Tenant and Workspace Context — COVERED

- Tenant selector: implemented in `layouts/default.vue` with DropdownMenu for multi-tenant, single display for single-tenant
- Switching tenants refreshes data: `interaction-principles.test.ts` covers tenantVersion watcher pattern
- Workspace guidance: `index.test.ts` and `default.vue` both implement the toast guidance when workspace count is 0

**No deviations from spec.**

---

### Requirement: Knowledge Graph Creation — COVERED

- `knowledge-graphs/index.vue` implements the create dialog with name, description, and workspace selector
- API call uses `POST /management/workspaces/{id}/knowledge-graphs` (workspace-scoped) — matches spec
- After creation, user is prompted to add a data source via toast notification
- Tests in `knowledge-graphs.test.ts` verify all validation paths and the API endpoint

**No deviations from spec.**

---

### Requirement: Data Source Connection — COVERED

- 4-step wizard: adapter selection → connection config → intent → ontology review
- GitHub adapter type selection implemented; form adapts to show adapter-specific fields
- Name inferred from GitHub repo URL (tested in `data-sources.test.ts` line 97–112)
- Token/credential is never persisted in browser state (uses transient secret pattern via `useTransientSecret`)
- Tests in `data-sources.test.ts` cover all wizard steps

**No deviations from spec.**

---

### Requirement: Ontology Design — COVERED

- Intent description step: implemented in data-sources wizard step 3 (intentText required)
- Agent-proposed ontology: `0d7d39463` implements the backend endpoint; frontend wires the approval payload
- Ontology review and approval: implemented in wizard step 4 with node/edge type review
- Individual type editing: `startEditNode`/`saveEditNode`/`cancelEditNode` implemented; tests in `data-sources.test.ts` cover all edit operations
- Post-extraction confirmation gate: tested in `knowledge-graphs.test.ts` lines 293–379 (re-extraction warning dialog)

**No deviations from spec.**

---

### Requirement: Sync Monitoring — COVERED (with note)

- Active sync progress: implemented with phase labels (pending/ingesting/ai_extracting/applying)
- Sync history: list of sync runs with status, timestamps, duration
- Sync logs: `viewLogs`/`fetchRunLogs`/`closeLogs` implemented in `data-sources/index.vue`; tests in `knowledge-graphs.test.ts` lines 382–490
- Manual sync trigger: implemented in data-sources page

**Note:** A dedicated `sync-logs.test.ts` file exists in commit `61cacb9fc` but that commit is NOT on the current branch `hyperloop/task-045` — it was made on a diverged parallel branch. The sync log scenarios ARE covered by tests in `knowledge-graphs.test.ts` (lines 382–490), so this is not a spec gap; it is a test organization issue only.

**No spec deviations.**

---

### Requirement: Get Started Querying (MCP Connection) — COVERED

- API key creation inline: implemented in `integrate/mcp.vue` — prompts when no active keys
- Copy-paste connection command: snippet with endpoint URL and key placeholder; copy button
- Secret shown once: `useTransientSecret` composable pattern; `mcp-integration.test.ts` covers all scenarios

**No deviations from spec.**

---

### Requirement: Query Console — COVERED

- Cypher syntax highlighting, autocomplete, linting: CodeMirror with `lang-cypher` extension
- Query execution (button + Ctrl/Cmd+Enter): `query-history.test.ts` verifies keyboard shortcut
- Query history: addToHistory/loadHistory/clearHistory logic tested in `query-history.test.ts`
- KG context selector: implemented; `9f7632593` fixes tenant-change reset; tests in `knowledge-graphs.test.ts` and `query-history.test.ts`

**No deviations from spec.**

---

### Requirement: Schema Browser — COVERED

- Type listing with search/filtering: `filteredLabels` function tested in `schema-browser.test.ts`
- Type detail: required/optional properties on expand tested
- Cross-navigation: links to query console, graph explorer, and ontology editor — all three tested in `schema-browser.test.ts`

**No deviations from spec.**

---

### Requirement: Graph Explorer — COVERED

- Node search by type, name, slug: tested in `graph-explorer.test.ts`
- Neighbor exploration: connected nodes and edges with labels and direction
- Exploration trail (drill-in breadcrumb): tested

**No deviations from spec.**

---

### Requirement: API Key Management — COVERED

- Create key: name + expiration, secret shown once via `useTransientSecret`
- List keys: status (active/expired/revoked), creation date, last used, expiration — `keyStatus` function tested in `api-keys.test.ts`
- Revoke key: implemented; `revokeApiKey` uses `DELETE /iam/api-keys/{id}`

**No deviations from spec.**

---

### Requirement: Workspace Management — COVERED

- Create workspace with name and optional parent: `workspace-management.test.ts` line 169 verifies `parent_workspace_id` is sent
- Member management (add/remove/change roles): implemented in `workspaces/index.vue`

**No deviations from spec.**

---

### Requirement: Design Language — COVERED

- shadcn/vue (Reka UI) primitives with Tailwind CSS: verified in `design-system.test.ts`
- OKLCH color custom properties: verified in `design-system.test.ts`
- Typography: `text-sm`, `text-[11px]` uppercase section headers, `tracking-wider` — all tested in `design-language-extended.test.ts`
- Border radius: `rounded-xl`, `rounded-md`, `rounded-full` — verified in `design-system.test.ts`
- Elevation: `shadow-sm`, `shadow-xs` — verified in `design-language-extended.test.ts`

**No deviations from spec.**

---

### Requirement: Interaction Principles — COVERED

- Progressive disclosure: tested in `interaction-principles.test.ts`
- Inline actions over navigation: editing happens in-place (dialogs/sheets)
- Copy-to-clipboard with toast confirmation: tested
- Mutation feedback (toast on create/update/delete): tested
- Keyboard shortcuts (Ctrl/Cmd+Enter, /): tested in `query-history.test.ts`
- Focus indicators (3px ring): `focus-ring.test.ts` verifies `focus-visible:ring-[3px]` not `ring-2`

**No deviations from spec.**

---

### Requirement: Responsive Design — COVERED

- Desktop sidebar (hidden md:flex, collapsible): tested in `responsive-design.test.ts`
- Mobile sidebar (Sheet overlay, single-column): tested in `responsive-design.test.ts`

**No deviations from spec.**

---

### Requirement: Dark Mode — COVERED

- Toggle available in header (Sun/Moon icons): implemented in `layouts/default.vue`
- Preference persists across sessions (localStorage): tested in `color-mode.test.ts`
- System preference fallback: tested

**No deviations from spec.**

---

## FAIL Items

1. **Requirement: Backend API Alignment — task-050 not started**
   - Scenario "Resource operations succeed end-to-end": no test verifies that a 2xx response actually follows from the UI operation (all tests mock the API layer; no integration-level verification for group, tenant list, query console, schema browser, or graph explorer CRUD paths)
   - Scenario "Parent context is preserved": workspace parent_id is unit-tested with mocks; no test uses the real endpoint string from `useIamApi.createWorkspace` to assert the complete call — task-050 was created to close this gap but is `not-started`
   - The `useIamApi.ts` composable itself uses correct endpoint strings (`/iam/workspaces`, `/iam/groups`, `/iam/api-keys`) but the spec requires tests that assert these exact URLs per operation

2. **sync-logs.test.ts missing from current branch**
   - Commit `61cacb9fc` added a dedicated `sync-logs.test.ts` file but it is not on `hyperloop/task-045`. Sync log scenarios have fallback coverage in `knowledge-graphs.test.ts`, so this is a test completeness issue but not a functional gap. Noted for tracking.

## Action Required

- Complete task-050: add tests for IAM CRUD endpoint URLs and UI refresh behavior after mutations
- Optionally cherry-pick or merge `61cacb9fc` to add the dedicated sync-logs test file