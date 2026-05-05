---
task_id: task-141
round: 7
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review — specs/ui/experience.spec.md (task-141)

## Summary

**Backend suite:** ALL PASS (confirmed — 0 commits behind alpha)
**Frontend tests:** FAIL — `node_modules` absent in `src/dev-ui/`; `vitest` not found; `check-frontend-tests-pass.sh` exits non-zero

Per verifier guidelines: *"When node_modules is absent in the dev-ui directory, record it as a blocking FAIL and require the implementer to install dependencies with `cd src/dev-ui && pnpm install` before resubmission: absent node_modules prevents empirical test verification and type-checking; a test suite that cannot run cannot satisfy the PASS gate."*

**Note:** CI (`kartograph-dev-ui-on-pull-request`) passed (36m44s), providing external evidence the frontend tests and build succeed. The blocking issue is purely environmental in this worktree.

---

## Blocking Issue

```
FAIL: Frontend test suite exited with code 1.
  sh: line 1: vitest: command not found
  WARN: Local package.json exists, but node_modules missing, did you mean to install?
```

**Resolution required:** Run `cd src/dev-ui && pnpm install` then re-run `bash .hyperloop/checks/check-frontend-tests-pass.sh` and confirm exit 0 before resubmitting.

---

## Spec Coverage Findings (Static Analysis)

All findings below are based on static code analysis (file reads + grep). Empirical test execution was not possible due to missing `node_modules`.

### Requirement: Backend API Alignment — COVERED
- **Resource operations succeed end-to-end**: `api-alignment.test.ts` tests that every create/edit/delete/revoke operation calls `load*()` on success and NOT on failure; `api-alignment.test.ts` and `task-129-spec-alignment.test.ts` verify API URL patterns.
- **Parent context is preserved**: `api-alignment.test.ts` verifies workspace-scoped KG creation (`/management/workspaces/{ws_id}/knowledge-graphs`), KG-scoped data source creation, DS-scoped sync trigger, mutations KG-scoped URL (`/graph/knowledge-graphs/{kg_id}/mutations`).

### Requirement: Navigation Structure — COVERED
- **Primary navigation**: `task-129-spec-alignment.test.ts` validates all 4 sidebar groups (Explore/Data/Connect/Settings) with correct items. `default.layout.test.ts` verifies Mutations Console in Explore group.
- **Default landing**: `interaction-principles.test.ts` (`Navigation - returning user redirect`) verifies returning users (via localStorage query history) are redirected to `/query`.
- **New user landing**: `interaction-principles.test.ts` (`Navigation - new user landing: setup guidance`) verifies `showChecklist` logic, checklist items, `completedCount`, and `dismissOnboarding` persistence.

### Requirement: Tenant and Workspace Context — COVERED
- **Tenant selector**: `default.layout.test.ts` covers tenant selector in sidebar with aria-labels for loading/multi/single/no-tenant states.
- **Workspace guidance**: `interaction-principles.test.ts` (`Navigation - workspace guidance for new users`) verifies guidance shown when workspace count is 0, dismissed after shown, not shown when workspaces exist.

### Requirement: Knowledge Graph Creation — COVERED
- **Create knowledge graph**: `knowledge-graphs.test.ts` covers name+description form, workspace-scoped API call (`/management/workspaces/{ws_id}/knowledge-graphs`), and post-creation prompt to add first data source with navigation to `/data-sources?kg_id=...`.

### Requirement: Data Source Connection — COVERED
- **Adapter type selection**: `data-source-connection-wizard.test.ts` Group 1 verifies GitHub is the only selectable adapter, `canAdvanceStep1()` requires both adapter and KG.
- **Connection configuration**: Group 2 covers `inferNameFromRepoUrl()`, `validateStep2()` required fields, defaults.
- **Credential handling**: Group 3 verifies token is cleared after success, preserved on failure, not stored in `DataSourceItem`. `task-129-spec-alignment.test.ts` verifies `type="password"` masking and credential guard logic.

### Requirement: Ontology Design — COVERED
- **Intent description**: `task-129-spec-alignment.test.ts` verifies `intentText`, `intentError`, `validateIntentText()`, `beginOntologyProposal()`.
- **Agent-proposed ontology**: `proposedNodes`/`proposedEdges`/`ontologyReady` lifecycle tested; reset before re-fetch, set true after complete.
- **Ontology review and approval**: `approveOntology()`, `:disabled="!ontologyReady"`, `approvingOntology` flag, approval → triggerSync.
- **Individual type editing**: `editing`/`editLabel`, `startEditingNode()`/`saveNodeEdit()`/`cancelNodeEdit()`, `editRequired`/`editOptional`.
- **Ontology change after initial extraction**: `knowledge-graphs.test.ts` (`Ontology Edit - Post-Extraction Confirmation Gate`) verifies completed-extraction detection, confirmation dialog, `confirmReExtraction`/`cancelReExtraction`.

### Requirement: Sync Monitoring — COVERED
- **Active sync progress**: `sync-monitoring-extended.test.ts` covers phase labels (ingesting/ai_extracting/applying/pending), badge variants, `isActiveSyncPhase` for each status.
- **Sync history**: `sync-monitoring-extended.test.ts` (`Sync Monitoring - sync history list rendering`) verifies duration computation, required display fields, error message, human-readable timestamps, multiple runs listed most-recent-first.
- **Sync logs**: `knowledge-graphs.test.ts` (`Sync Logs - View Logs Toggle`, `Sync Logs - Fetching log lines`) covers log sheet toggle and API fetch.
- **Manual sync trigger**: `sync-monitoring-extended.test.ts` covers `POST /management/data-sources/{ds_id}/sync`, success/failure toasts, polling starts after trigger.

### Requirement: Get Started Querying (MCP Connection) — COVERED
- **API key creation inline**: `mcp-integration.test.ts` verifies empty `activeKeys` → show create prompt; name/expiry validation; successful creation sets `newlyCreatedKey`.
- **Copy-paste connection command**: Claude Code CLI snippet, Cursor JSON snippet, placeholder when no key, copy button all verified in `mcp-integration.test.ts`.
- **Secret shown once**: `newlyCreatedKey` null before creation; tenant switch clears it; `dismissSecret` sets null; `configSecret` falls back to placeholder after dismiss.

### Requirement: Query Console — COVERED
- **Query editing**: `task-125-spec-alignment.test.ts` verifies Cypher syntax highlighting (`cypher()` language extension), schema-aware autocomplete (`cypherAutocomplete()`), and AGE Cypher linter (`ageCypherLinter()`).
- **Query execution**: Execute button wired to `executeQuery()`, Ctrl/Cmd+Enter keymap, results table (`useVueTable`+`FlexRender`), `executionTime` in ms, `row_count`.
- **Query history**: `query-history.test.ts` covers `addToHistory` (deduplication, cap at 20, localStorage), `loadHistory`, `clearHistory`, KG scope labels, Ctrl/Cmd+Enter trigger.
- **Knowledge graph context**: `query.test.ts` and `query-kg-selector.test.ts` verify `selectedKgId` ref (`''` default), `|| undefined` gate in `buildQueryGraphArgs`, Scoped/Unscoped badges, KG selector populated from `/management/knowledge-graphs`.

### Requirement: Schema Browser — COVERED
- **Type listing**: `schema-browser.test.ts` covers filtering by label/property name, search.
- **Type detail**: Description, required/optional properties, `hasProperties` computed.
- **Cross-navigation**: To query console (pre-filled Cypher), to graph explorer (type param), to ontology editor (`/data-sources?openOntologyType=...`).

### Requirement: Graph Explorer — COVERED
- **Node search**: `graph-explorer.test.ts` covers `canSearch`, node type filter, search mode descriptions.
- **Neighbor exploration**: `getEdgeLabelForNeighbor`, `addToPath`, `drillIntoNeighbor()`, `navigationTrail` tested.

### Requirement: Mutations Console — COVERED
All 9 scenarios covered in `mutations-console.test.ts`, `mutations-kg-selector.test.ts`, `mutations-submission.test.ts`, `mutations-indicator-persistence.test.ts`:
- **Empty state**: Upload/Open Editor actions, drag-and-drop, 4 quick-start templates.
- **JSONL editing**: CodeMirror extensions, linting, autocomplete, Ctrl/Cmd+Enter keymap.
- **Live preview**: `parseContent` op-type breakdown (DEFINE/CREATE/UPDATE/DELETE), validation warnings, parse errors.
- **File upload**: `.jsonl`/`.json`/`.ndjson` accepted, `LARGE_FILE_THRESHOLD`, large-file mode disables editing.
- **Knowledge graph selection**: `selectedKnowledgeGraphId`, `canSubmitMutations`, no submission without KG, KG-scoped URL.
- **Submission**: `useMutationSubmission` state machine, floating indicator (`fixed bottom-4 right-4`) in `app.vue` via `useState`, persists across navigation.
- **Submission failure**: `state.error`, truncated to 120 chars, `operations_applied` displayed.
- **Template insertion**: `getMergedEditorContent`, `insertTemplate`, `toJsonl` utility.
- **Deep-link**: `route.query.view === 'editor'`, `route.query.template` → `insertTemplate`.

### Requirement: API Key Management — COVERED
- **Create key**: `api-keys.test.ts` verifies name/expiry validation, creation flow, secret shown once.
- **List keys**: Status filtering (active/expired/revoked), `isExpired`, `keyStatus`, `daysUntilExpiry`.
- **Revoke key**: `DELETE /iam/api-keys/{id}`, confirmation dialog, list refresh.

### Requirement: Workspace Management — COVERED
- **Create workspace**: `workspace-management.test.ts` validates name, optional parent, POST `/iam/workspaces`.
- **Member management**: Add (`POST /iam/workspaces/{id}/members`), remove (DELETE), role change (PATCH) all tested.

### Requirement: Design Language — COVERED
- **Component library**: `design-system.test.ts` verifies Reka UI (shadcn/vue) import in `alert-dialog.test.ts`, Tailwind CSS, CVA (`class-variance-authority`), Lucide Vue Next (Moon/Sun icons in color-mode.test.ts).
- **Color theme**: `design-language.test.ts` verifies primary OKLCH values (light: `oklch(0.5768 0.2469 29.23)`, dark: `oklch(0.6857 0.1560 17.57)`), 5-color chart palette, destructive coral/red, all tokens use OKLCH.
- **Typography**: System font stack (no custom fonts), `text-sm` body, `text-[11px] uppercase tracking-wider` section headers, font weights limited to 400/500/600 (no `font-bold` in any page file — parameterized test across all pages).
- **Border radius**: `--radius: 0.625rem` base, `rounded-xl` cards, `rounded-md` buttons/inputs, `rounded-full` badges.
- **Elevation**: `shadow-sm` cards, `shadow-xs` buttons (outline variant), no deep shadows.

### Requirement: Interaction Principles — COVERED
- **Progressive disclosure**: `interaction-principles.test.ts` (starts collapsed, toggle, sheet), `workspace-management.test.ts` (Progressive Disclosure describe group).
- **Inline actions over navigation**: `interaction-principles.test.ts`, `workspace-management.test.ts` (no `/edit` routes, in-place rename, SheetContent not a route).
- **Copy-to-clipboard**: `interaction-principles.test.ts` + `copy-composable.test.ts`.
- **Mutation feedback**: Toast notifications for success/error across all page tests.
- **Keyboard shortcuts**: Ctrl/Cmd+Enter for query/mutations; `/` for search focus; tested in `interaction-principles.test.ts` and `keyboard-shortcuts.test.ts`.
- **Focus indicators**: `focus-ring.test.ts` verifies `focus-visible:ring-[3px]`, `ring-ring/50`, `outline-none` suppression across all key interactive elements.

### Requirement: Responsive Design — COVERED
- **Desktop layout**: `responsive-design.test.ts` verifies collapsible sidebar (`isCollapsed`, `toggleCollapsed`, `sidebarWidth`), `"hidden md:flex"` class.
- **Tablet/mobile layout**: `computeSheetOpen()`, `SheetContent` overlay verified. `task-129-spec-alignment.test.ts` validates source-level `isCollapsed`/`PanelLeftClose`/`SheetContent`/`Menu` hamburger.

### Requirement: Dark Mode — COVERED
- **Toggle**: `color-mode.test.ts` covers toggle persistence to localStorage, initial-load reads preference, system preference fallback, CSS `dark` class application on `documentElement`, Moon/Sun icons in header.

---

## Required Fix

1. Install frontend dependencies in the worktree:
   ```bash
   cd src/dev-ui && pnpm install
   ```
2. Confirm frontend tests pass:
   ```bash
   bash .hyperloop/checks/check-frontend-tests-pass.sh
   ```
3. Confirm exit 0 before resubmitting.

**All 18 spec requirements are COVERED based on static analysis. The sole blocker is the missing `node_modules` preventing empirical test execution.**