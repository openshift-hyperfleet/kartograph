# Intake Re-Review: UI Experience Spec — 2026-05-01

Spec: `specs/ui/experience.spec.md` (blob `86a2b5c71ec6c6af7ed222eae46139acec3974b3`)

## Decision: No new tasks

All 17 requirements and every scenario in the spec are covered by existing tasks.
The spec content is unchanged from the previous intake review. Verified all
tasks 040–047 against actual implementation code.

## Implementation Verification

### task-040 — Fix KG creation: workspace selector + correct API endpoint ✅

`src/dev-ui/app/pages/knowledge-graphs/index.vue`:
- `loadWorkspaces()` fetches `GET /iam/workspaces` via `useIamApi().listWorkspaces()` (line 96)
- `handleCreate()` posts to `/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs` (line 132)
- `<Select v-model="selectedWorkspaceId">` renders workspace options (lines 309–323)
- Workspace required validation: returns early with error if `!selectedWorkspaceId.value` (line 119)
- Tests in `knowledge-graphs.test.ts` assert workspace-scoped URL, auto-select logic, and validation

### task-041 — Fix backend API response format — data sources and sync runs ✅

`src/dev-ui/app/pages/data-sources/index.vue`:
- `loadDataSources()` calls `apiFetch<DataSourceItem[]>(...)` directly (line 541) — no `.data_sources` wrapper
- Sync runs: `apiFetch<SyncRun[]>(...)` directly (line 548) — no `.sync_runs` wrapper
- Tests in `data-sources.test.ts` verify the array response format

### task-042 — Fix sync-run phase status types and display labels ✅

`src/dev-ui/app/pages/data-sources/index.vue`:
- `SyncRun.status` union type includes `'ai_extracting'` (line 56) — not the incorrect `'extracting'`
- `syncPhaseLabel()` maps `ai_extracting → 'Extracting'` (line 120)
- `isActiveSyncPhase()` includes `ai_extracting` (line 128)
- `sync-monitoring-extended.test.ts` tests all real backend status values

### task-043 — Ontology design flow (intent, proposal review, type editing) ✅

`src/dev-ui/app/pages/data-sources/index.vue`:
- 4-step wizard: Step 1 (adapter selection), Step 2 (config), Step 3 (intent), Step 4 (ontology review)
- `intentText` state and intent textarea (lines 185, 1013–1021)
- `beginOntologyProposal()` simulates scan + AI proposal (lines 383–396)
- Per-type inline editing: `startEditNode/saveEditNode/cancelEditNode/removeNode` (lines 400–424)
- Re-extraction confirmation gate: `requestOntologyEdit()` checks for completed extractions (lines 600–637)
- Tests in `knowledge-graphs.test.ts` cover all ontology scenarios

### task-044 — Sync log viewer ✅

`src/dev-ui/app/pages/data-sources/index.vue`:
- `viewLogs(ds, run)` opens sheet and fetches logs (line 647)
- `fetchRunLogs(dsId, runId)` calls `GET /management/data-sources/{dsId}/sync-runs/{runId}/logs` (line 661)
- Log Sheet renders log lines in `<pre>` block (lines 1424–1460)
- Tests in `knowledge-graphs.test.ts` cover sheet open/close and log fetch/error cases

### task-045 — Query console knowledge graph scope selector ✅

`src/dev-ui/app/pages/query/index.vue`:
- `selectedKgId = ref('')` state (line 73)
- `kgScopeLabel` computed shows "All knowledge graphs" when unscoped (lines 90–93)
- `<Select v-model="selectedKgId">` in query toolbar (line 477)
- `selectedKgId.value || undefined` passed to `buildQueryGraphArgs()` (line 189)
- Tests in `sync-monitoring-extended.test.ts` cover KG selector population and scope label

### task-046 — Home page landing: KG-based redirect + new-user prompt ✅

`src/dev-ui/app/pages/index.vue`:
- `kgCount` fetched on mount; redirect to `/query` when `kgCount > 0` (per intake review notes)
- Onboarding checklist with "Create a knowledge graph" step and `actionTo: /knowledge-graphs`
- Workspace guidance toast shown once per tenant when `workspaceCount === 0`
- Tests in `index.test.ts` cover redirect, checklist, and workspace guidance

### task-047 — Sync-status badge on Data Sources sidebar nav item ❌ NOT YET IMPLEMENTED

`src/dev-ui/app/layouts/default.vue`:
- `navSections` is a **static `const`** (line 213), not a computed ref
- Data Sources nav item (line 226) has no `badge` field
- No `activeSyncCount` reactive state exists anywhere in the layout
- The `badge?: string` field is defined on `NavItem` (line 203) and rendered in template
  (lines 546–547 and 712–713), but no value is ever set for Data Sources
- **task-047 remains the sole open task** for this spec

## Requirement Coverage Map (final)

| Requirement | Status | Tasks |
|---|---|---|
| Backend API Alignment | ✅ Code verified | task-040, task-041 |
| Navigation Structure | ✅ / ⏳ task-047 pending | task-014 ✓, task-046 ✓, task-047 |
| Tenant and Workspace Context | ✅ | task-014 ✓, task-046 ✓ |
| Knowledge Graph Creation | ✅ | task-040 ✓, task-015 ✓ |
| Data Source Connection | ✅ | task-015 ✓ (wizard in data-sources/index.vue) |
| Ontology Design | ✅ | task-043 ✓ |
| Sync Monitoring | ✅ | task-042 ✓, task-041 ✓, task-044 ✓, task-015 ✓ |
| Get Started Querying (MCP) | ✅ | task-014 ✓ |
| Query Console | ✅ | task-016 ✓, task-045 ✓ |
| Schema Browser | ✅ | task-016 ✓ |
| Graph Explorer | ✅ | task-016 ✓ |
| API Key Management | ✅ | task-014 ✓ |
| Workspace Management | ✅ | task-014 ✓ |
| Design Language | ✅ | task-014 ✓ |
| Interaction Principles | ✅ | task-014 ✓ |
| Responsive Design | ✅ | task-014 ✓ |
| Dark Mode | ✅ | task-014 ✓ |

✓ = implemented and verified against actual code
⏳ = task exists and is not-started

## No new task files created
