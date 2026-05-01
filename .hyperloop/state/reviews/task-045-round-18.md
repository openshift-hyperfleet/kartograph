---
task_id: task-045
round: 18
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — specs/ui/experience.spec.md

**Branch:** hyperloop/task-045
**Rebase status:** Resolved. The previously reported conflict in `src/dev-ui/app/tests/data-sources.test.ts` was resolved in commit `f1dcc8873` ("add missing spec scenario labels for all 60 experience.spec.md scenarios"). Working tree is clean.

---

## Requirement Status

### Requirement: Backend API Alignment — COVERED
- **Scenario: Resource operations succeed end-to-end** — `backend-api-alignment.test.ts` tests the full validate → POST → reactive-refresh → success-toast pattern for groups and API keys. `data-sources.test.ts` tests exact API response format (direct arrays, not wrapped).
- **Scenario: Parent context is preserved** — `backend-api-alignment.test.ts` ("workspace parent context preserved") verifies `parent_workspace_id` is always included in createWorkspace calls and that creating without a parent is blocked.

### Requirement: Navigation Structure — COVERED
- **Scenario: Primary navigation** — `default.layout.test.ts` builds the navSections fixture with all 4 Explore items (Query Console, Schema Browser, Graph Explorer, Mutations Console) and verifies Mutations Console placement. `interaction-principles.test.ts` checks the 4-section sidebar structure. Minor inconsistency: the static navSections in `interaction-principles.test.ts` only lists 3 Explore items (omits Mutations Console), but `default.layout.test.ts` explicitly covers all 4 with dedicated tests.
- **Scenario: Default landing** — `interaction-principles.test.ts` ("returning user redirect") verifies localStorage query history detection and session-scoped redirect deduplication.
- **Scenario: New user landing** — `interaction-principles.test.ts` ("new user landing: setup guidance") verifies showChecklist logic, dismissal persistence, and new-user detection.

### Requirement: Tenant and Workspace Context — COVERED
- **Scenario: Tenant selector** — `interaction-principles.test.ts` ("switching tenants refreshes all data") verifies tenantVersion watcher pattern and stale-state clearing.
- **Scenario: Workspace guidance** — `workspace-guidance.test.ts` fully covers the 8 guidance scenarios (show on first entry, suppress after shown, create/join actions, guidance clears after creation).

### Requirement: Knowledge Graph Creation — PARTIAL → FAIL
- **Scenario: Create knowledge graph** — `knowledge-graphs.test.ts` ("Knowledge Graph Creation - Validation" and "Knowledge Graph Creation - API call") covers name/description validation, workspace scoping (`POST /management/workspaces/{id}/knowledge-graphs`), and success toast message.
- **MISSING test for:** "AND the user is prompted to add their first data source."
  **Implementation exists** in `knowledge-graphs/index.vue` lines 139–146:
  ```
  toast.success(`Knowledge graph "${name}" created`, {
    description: 'Next: connect a data source to start populating your graph.',
    action: { label: 'Add Data Source', onClick: () => navigateTo('/data-sources') },
    duration: 8000,
  })
  ```
  However the test only captures the primary toast message string and does not assert on the toast `description` or `action` (the "Add Data Source" navigation prompt). No test verifies that after successful KG creation the user is directed toward adding a data source.
  **Fix needed:** Add a test that asserts the toast description contains a data-source prompt and/or that an action callback navigates to `/data-sources`.

### Requirement: Data Source Connection — COVERED
- **Scenario: Adapter type selection** — `data-sources.test.ts` ("Data Source Connection - Adapter type selection"): step-1 guard, form field adaptation per adapter, field reset on adapter change.
- **Scenario: Connection configuration** — `data-sources.test.ts` ("Data Source Connection - Connection configuration"): name inference from repo URL, required-field validation, validation pass.
- **Scenario: Credential handling** — `data-sources.test.ts` ("Credential Handling - Token Not Persisted to Browser Storage"): localStorage spy, sessionStorage spy, URL serialization checks.

### Requirement: Ontology Design — COVERED
- **Scenario: Intent description** — `data-sources.test.ts` ("Data Sources Wizard - Intent Step"): intent required guard, advance on text provided.
- **Scenario: Agent-proposed ontology** — `data-sources.test.ts` ("Ontology Design - Propose Ontology API Call"): POST to `/management/ontology-proposals`, intent text in body, no setTimeout simulation, non-hardcoded response.
- **Scenario: Ontology review and approval** — `data-sources.test.ts` ("Ontology Design - Approve Ontology Payload"): node_types/edge_types included in createDataSource payload, edited types (not originals) sent, extraction not triggered before approve click.
- **Scenario: Individual type editing** — `data-sources.test.ts` (startEditNode, saveEditNode, cancelEditNode, removeNode, startEditEdge, saveEditEdge, cancelEditEdge, removeEdge suites): exhaustive property modification, relationship type editing, `source_url` exact requirement example.
- **Scenario: Ontology change after initial extraction** — `data-sources.test.ts` ("Ontology Design - Ontology change after initial extraction"): confirmation required when `hasCompletedExtraction`, immediate apply when not, apply on confirm, skip on cancel.

### Requirement: Sync Monitoring — COVERED
- **Scenario: Active sync progress** — `sync-monitoring-extended.test.ts` ("active sync progress phases"): ingesting/ai_extracting/applying phases, badge variants, animation indicators.
- **Scenario: Sync history** — `sync-monitoring-extended.test.ts` ("sync history list rendering"): completed/failed runs with status, timestamps, duration.
- **Scenario: Sync logs** — `sync-logs.test.ts`: full state machine (viewLogs, fetchRunLogs, closeLogs), API endpoint, loading lifecycle, empty state, error state, log display format.
- **Scenario: Manual sync trigger** — `sync-monitoring-extended.test.ts` ("manual sync trigger").

### Requirement: Get Started Querying (MCP Connection) — COVERED
- **Scenario: API key creation inline** — `mcp-integration.test.ts` ("inline API key creation"): no-keys prompt, key-exists state, name validation, expiry range, successful creation flow.
- **Scenario: Copy-paste connection command** — `mcp-integration.test.ts` ("config snippet generation"): Claude Code CLI snippet with endpoint + X-API-Key header, Cursor JSON snippet, placeholder when no key.
- **Scenario: Secret shown once** — `mcp-integration.test.ts` ("secret shown once", "dismissSecret"): null before creation, shown after creation, dismiss sets to null, configSecret falls back to placeholder.

### Requirement: Query Console — COVERED
- **Scenario: Query editing** — `query-history.test.ts` ("Cypher language extension", "Cypher autocomplete extension", "AGE Cypher linter extension", "staticExtensions array composition"): CodeMirror extensions wired for syntax highlighting, autocomplete, linting.
- **Scenario: Query execution** — `query-history.test.ts` ("execution result handling", "keyboard shortcut Ctrl/Cmd+Enter"): result captures execution time and row count; Ctrl/Cmd+Enter fires executeQuery.
- **Scenario: Query history** — `query-history.test.ts` ("addToHistory", "loadHistory", "clearHistory"): 20-item cap, deduplication, localStorage persistence.
- **Scenario: Knowledge graph context** — `knowledge-graphs.test.ts` ("Query Console - KG Selector Population"): scoped/unscoped label, tenant-switch reset, `buildQueryGraphArgs` omits `knowledge_graph_id` when unscoped.

### Requirement: Schema Browser — COVERED
- **Scenario: Type listing** — `schema-browser.test.ts`: listing without search, label-match search, property-match search.
- **Scenario: Type detail** — `schema-browser.test.ts`: description, required properties, optional properties.
- **Scenario: Cross-navigation** — `schema-browser.test.ts`: navigate to query console (pre-filled), graph explorer (filtered), ontology editor.

### Requirement: Graph Explorer — COVERED
- **Scenario: Node search** — `graph-explorer.test.ts` ("node type filter", "canSearch", "search mode descriptions"): search by type, name, slug.
- **Scenario: Neighbor exploration** — `graph-explorer.test.ts` ("neighbor exploration: getEdgeLabelForNeighbor", "exploration path (trail)", "drillIntoNeighbor"): edge labels, trail building, drill-in navigation.

### Requirement: Mutations Console — COVERED
- **Scenario: Empty state** — `mutations-console.test.ts`: "Upload File" and "Open Editor" actions present; 4 quick-start templates (Create a Node, Create an Edge, Update Properties, Delete an Entity); @drop.prevent/@dragover/@dragleave handlers.
- **Scenario: JSONL editing** — `mutations-console.test.ts`: CodeMirror imports (mutationAutocomplete, mutationLinter, lineNumbers, lintGutter, json()); extensions wired; Ctrl/Cmd+Enter submits.
- **Scenario: Live preview** — `mutations-console.test.ts`: `parseContent`/`getBreakdown` by type (DEFINE/CREATE/UPDATE/DELETE); validation warnings; inline parse error gutter.
- **Scenario: File upload** — `mutations-console.test.ts`: accepted extensions (.jsonl/.json/.ndjson); LARGE_FILE_THRESHOLD (5 MB) activates summary mode; drag-and-drop handling.
- **Scenario: Knowledge graph selection** — `mutations-console.test.ts`: KG selector present, submission guarded until KG selected.
- **Scenario: Submission** — `mutations-console.test.ts`: `useMutationSubmission` state machine (submitting/success/failed); `MutationProgress.vue` fixed bottom-right, shows status/operationCount/elapsed; minimizable to compact pill; dismissible after completion.
- **Scenario: Submission failure** — `mutations-console.test.ts`: `state.error` shown; truncatedError at 120 chars; `operations_applied` count shown.
- **Scenario: Template insertion** — `mutations-console.test.ts`: append with newline to existing content; replace empty; `activateEditor()` called before insert.
- **Scenario: Deep-link to editor** — `mutations-console.test.ts`: `?view=editor` opens editor; `?template=<content>` inserts content; browser back/forward navigation.

### Requirement: API Key Management — COVERED
- **Scenario: Create key** — `api-keys.test.ts` ("create key validation"): name required, expiry validation, secret shown once.
- **Scenario: List keys** — `api-keys.test.ts` ("list filtering by status"): active/expired/revoked status; keyStatus computed.
- **Scenario: Revoke key** — `api-keys.test.ts` ("revoke key") + `backend-api-alignment.test.ts`: DELETE /iam/api-keys/{id} (not POST /revoke), reactive reload after revoke.

### Requirement: Workspace Management — COVERED
- **Scenario: Create workspace** — `workspace-management.test.ts` ("creation validation", "creation API call"): name required, parent required, POST /iam/workspaces with parent_workspace_id.
- **Scenario: Member management** — `workspace-management.test.ts` ("add member", "remove member", "role change"): add/remove/role-update with reactive refresh.

### Requirement: Design Language — COVERED
- **Scenario: Component library** — `design-system.test.ts`: shadcn/vue, Tailwind, CVA, Lucide Vue Next dependencies.
- **Scenario: Color theme** — `design-language.test.ts` + `design-system.test.ts`: exact OKLCH values for primary (0.5768 0.2469 29.23 light; 0.6857 0.1560 17.57 dark), neutral grays, destructive (0.6237 0.1930 38.99), 5 chart colors.
- **Scenario: Typography** — `design-language.test.ts` + `design-language-extended.test.ts`: system font stack, text-sm body, text-[11px] uppercase tracking-wider section headers, font-weight 400/500/600 constraint (no font-bold/700).
- **Scenario: Border radius** — `design-language.test.ts` + `design-system.test.ts`: base 0.625rem, cards rounded-xl, buttons/inputs rounded-md, badges rounded-full.
- **Scenario: Elevation** — `design-language.test.ts` + `design-language-extended.test.ts`: cards shadow-sm, buttons shadow-xs, minimal/flat principle.

### Requirement: Interaction Principles — COVERED
- **Scenario: Progressive disclosure** — `interaction-principles.test.ts`: collapsible starts collapsed, toggles, sheet opens on action.
- **Scenario: Inline actions over navigation** — `interaction-principles.test.ts`: dialog opens for edit, no route navigation, close resets state.
- **Scenario: Copy-to-clipboard** — `interaction-principles.test.ts`: clipboard.writeText called with correct content, success/error toast.
- **Scenario: Mutation feedback** — `interaction-principles.test.ts`: success toast on create, error toast on failure, inline validation errors, clear on correction.
- **Scenario: Keyboard shortcuts** — `interaction-principles.test.ts`: Ctrl/Cmd+Enter executes query, / focuses search, / ignored when in input.
- **Scenario: Focus indicators** — `focus-ring.test.ts`: 3px ring in primary color, no ring-2 regressions, focus-ring consistency across components.

### Requirement: Responsive Design — COVERED
- **Scenario: Desktop layout** — `responsive-design.test.ts`: sidebar visible, collapsible, localStorage persistence, multi-column conventions.
- **Scenario: Tablet/mobile layout** — `responsive-design.test.ts`: sheet overlay on mobile, auto-close on route change, single-column layout.

### Requirement: Dark Mode — COVERED
- **Scenario: Toggle** — `color-mode.test.ts` ("Dark Mode - toggle in header"): toggle persists to localStorage, system preference fallback, CSS class applied.

---

## Summary

| Requirement                  | Status   |
|------------------------------|----------|
| Backend API Alignment        | COVERED  |
| Navigation Structure         | COVERED  |
| Tenant and Workspace Context | COVERED  |
| Knowledge Graph Creation     | PARTIAL  |
| Data Source Connection       | COVERED  |
| Ontology Design              | COVERED  |
| Sync Monitoring              | COVERED  |
| Get Started Querying (MCP)   | COVERED  |
| Query Console                | COVERED  |
| Schema Browser               | COVERED  |
| Graph Explorer               | COVERED  |
| Mutations Console            | COVERED  |
| API Key Management           | COVERED  |
| Workspace Management         | COVERED  |
| Design Language              | COVERED  |
| Interaction Principles       | COVERED  |
| Responsive Design            | COVERED  |
| Dark Mode                    | COVERED  |

## What Is Needed to Fix

**Knowledge Graph Creation — "AND the user is prompted to add their first data source"**

In `src/dev-ui/app/tests/knowledge-graphs.test.ts`, the test for `handleCreate()` captures the toast title but not the toast `description` or `action`. Add a test that verifies the post-creation data source prompt, for example:

```typescript
it('shows a data source prompt in the success toast after KG creation', async () => {
  let capturedToastDescription = ''
  let capturedActionLabel = ''

  function mockToastSuccess(message: string, opts: { description?: string; action?: { label: string } }) {
    capturedToastDescription = opts.description ?? ''
    capturedActionLabel = opts.action?.label ?? ''
  }

  // ... invoke handleCreate() using mockToastSuccess ...

  expect(capturedToastDescription).toContain('data source')
  expect(capturedActionLabel).toBe('Add Data Source')
})
```

This is the only failing condition. All other 17 requirements and their scenarios are fully implemented and tested.