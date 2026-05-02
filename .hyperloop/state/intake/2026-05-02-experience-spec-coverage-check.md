# Intake: specs/ui/experience.spec.md (modified) — 2026-05-02

**Spec blob SHA:** `e77913c2cc6d8b719291e2dbb6870519a94d50da`

## Summary

Re-processed `specs/ui/experience.spec.md` at current HEAD. Performed line-by-line
verification of all 59 scenarios across 18 requirements against existing tasks
(task-001 through task-075).

**Result: No new tasks required.** All scenarios are covered.

## Spec History

The current spec blob (`e77913c2cc6d8b719291e2dbb6870519a94d50da`) was introduced
in commit `e3d22bccf` ("docs(ui): add backend API alignment and mutations console
graph selection specs"). Since the prior intake (2026-05-01 22:31, covering through
task-072), three additional tasks were generated to close remaining gaps:

| Task | What It Adds |
|---|---|
| task-073 | Dedicated sync history table, log viewer, and manual-trigger tests (previously spread across task-041/task-044/task-015) |
| task-074 | Workspace-scoped KG selector in Mutations Console (task-065 used tenant-wide listing, not workspace-scoped) |
| task-075 | UI list auto-refresh after CRUD for api-keys and workspaces pages (task-072 only covered KG and data-sources) |

All prior scenarios and requirements remain covered by tasks from earlier passes.

## Code-Level Verification Findings

Key spot-checks performed against the actual implementation:

- **`triggerSync()`** in `data-sources/index.vue` exists and posts to
  `/management/data-sources/${dsId}/sync`; auth is enforced server-side (403 if
  no `manage` permission). The spec's GIVEN condition is a precondition, not a
  frontend enforcement requirement. ✓
- **`viewLogs()` / `fetchRunLogs()`** are implemented in `data-sources/index.vue`
  and tested in `knowledge-graphs.test.ts` (lines 388–497). Coverage is functional
  but co-located with KG tests; task-073 consolidates dedicated tests. ✓
- **Mutations Console workspace scoping**: `pages/graph/mutations.vue` has 0
  references to `workspaceId` — confirms task-074 is correctly identified as
  outstanding work. ✓
- **Tenant selector refresh**: `default.layout.test.ts` verifies aria-label and
  multi-tenant computed values, but does not assert full page data refresh on
  tenant switch. task-058 remains valid outstanding work. ✓
- **Task-072 implemented**: commit `823db6fa1` (Task-Ref: task-072) added list
  refresh tests for KG and data-source pages. Task status still shows `not-started`
  (orchestrator manages status); the implementation is present. task-075 extends
  this to api-keys and workspaces pages. ✓

## Full Requirement Coverage Map (current spec)

| Requirement | Scenario | Task(s) |
|---|---|---|
| Backend API Alignment | Resource operations succeed end-to-end | task-050, task-068, task-072 ✓impl, task-075 |
| Backend API Alignment | Parent context is preserved | task-040, task-068 |
| Navigation Structure | Primary navigation | task-014 ✓impl, task-059 |
| Navigation Structure | Default landing | task-046 |
| Navigation Structure | New user landing | task-046 |
| Tenant & Workspace Context | Tenant selector | task-058 |
| Tenant & Workspace Context | Workspace guidance | task-062 |
| Knowledge Graph Creation | Create knowledge graph | task-040, task-071 |
| Data Source Connection | Adapter type selection | task-015, task-041 |
| Data Source Connection | Connection configuration | task-015, task-041 |
| Data Source Connection | Credential handling | task-015, task-069 |
| Ontology Design | Intent description | task-043 |
| Ontology Design | Agent-proposed ontology | task-043 |
| Ontology Design | Ontology review and approval | task-043 |
| Ontology Design | Individual type editing | task-043, task-063 |
| Ontology Design | Ontology change after initial extraction | task-043 |
| Sync Monitoring | Active sync progress | task-042, task-064 |
| Sync Monitoring | Sync history | task-073 |
| Sync Monitoring | Sync logs | task-044, task-073 |
| Sync Monitoring | Manual sync trigger | task-073 |
| Get Started Querying | API key creation inline | task-051 |
| Get Started Querying | Copy-paste connection command | task-051 |
| Get Started Querying | Secret shown once | task-051 |
| Query Console | Query editing | task-016 ✓impl |
| Query Console | Query execution | task-016 ✓impl |
| Query Console | Query history | task-016 ✓impl |
| Query Console | Knowledge graph context | task-045 |
| Schema Browser | Type listing | task-016 ✓impl |
| Schema Browser | Type detail | task-016 ✓impl |
| Schema Browser | Cross-navigation | task-048 |
| Graph Explorer | Node search | task-016 ✓impl |
| Graph Explorer | Neighbor exploration | task-016 ✓impl |
| Mutations Console | Empty state | task-060 |
| Mutations Console | JSONL editing | task-060 |
| Mutations Console | Live preview | task-060 |
| Mutations Console | File upload | task-060 |
| Mutations Console | Knowledge graph selection | task-065, task-074 |
| Mutations Console | Submission | task-061, task-065 |
| Mutations Console | Submission failure | task-061 |
| Mutations Console | Template insertion | task-060 |
| Mutations Console | Deep-link to editor with pre-filled content | task-060 |
| API Key Management | Create key | task-014 ✓impl, task-050 |
| API Key Management | List keys | task-014 ✓impl, task-050 |
| API Key Management | Revoke key | task-050 |
| Workspace Management | Create workspace | task-014 ✓impl, task-050 |
| Workspace Management | Member management | task-014 ✓impl, task-050 |
| Design Language | Component library | task-052 |
| Design Language | Color theme | task-052 |
| Design Language | Typography | task-052, task-066, task-067 |
| Design Language | Border radius | task-052 |
| Design Language | Elevation | task-052 |
| Interaction Principles | Progressive disclosure | task-057 |
| Interaction Principles | Inline actions over navigation | task-057 |
| Interaction Principles | Copy-to-clipboard | task-053 |
| Interaction Principles | Mutation feedback | task-053 |
| Interaction Principles | Keyboard shortcuts | task-054, task-070 |
| Interaction Principles | Focus indicators | task-049 |
| Responsive Design | Desktop layout | task-055 |
| Responsive Design | Tablet/mobile layout | task-055 |
| Dark Mode | Toggle | task-056 |

## Open (not-started) Tasks for This Spec

| Task | Title | Status |
|---|---|---|
| task-015 | Implement UI — knowledge graph management, data sources, and sync monitoring | not-started |
| task-040 | Fix KG creation — workspace selector and correct API endpoint | not-started |
| task-041 | Fix backend API response format — data sources and sync runs | not-started |
| task-042 | Fix sync-run phase status types and display labels in UI | not-started |
| task-043 | Implement UI — ontology design flow (intent, proposal review, type editing) | not-started |
| task-044 | Implement UI — sync log viewer (Sync Monitoring > Sync logs) | not-started |
| task-045 | Implement UI — query console knowledge graph scope selector | not-started |
| task-046 | Fix home page landing — KG-based redirect and new-user KG creation prompt | not-started |
| task-047 | Add sync-status badge to Data Sources sidebar nav item | not-started |
| task-048 | Update schema browser cross-navigation — add ontology editor link per type | not-started |
| task-049 | Fix focus ring inconsistencies — ring-2 → ring-[3px] on custom interactive elements | not-started |
| task-050 | Backend API alignment audit — IAM and explore page CRUD operations | not-started |
| task-051 | Audit MCP integration page — Get Started Querying scenarios and API alignment | not-started |
| task-052 | Audit and implement Design Language — OKLCH tokens, typography, border radius, elevation | not-started |
| task-053 | Cross-page copy-to-clipboard and mutation feedback consistency audit | not-started |
| task-054 | Implement keyboard shortcuts — slash-to-focus-search and discoverable Ctrl/Cmd+Enter | not-started |
| task-055 | Audit and verify Responsive Design — desktop sidebar collapsible, mobile sheet overlay | not-started |
| task-056 | Audit and verify Dark Mode — header toggle and session-persistent preference | not-started |
| task-057 | Audit interaction principles — progressive disclosure and inline actions | not-started |
| task-058 | Audit tenant selector — verify all tenant-scoped pages refresh on tenant switch | not-started |
| task-059 | Navigation update — add Mutations Console to Explore sidebar group | not-started |
| task-060 | Mutations Console — core editor (empty state, JSONL editing, live preview, file upload, templates, deep-link) | not-started |
| task-061 | Mutations Console — submission flow (floating progress indicator, failure handling) | not-started |
| task-062 | Audit workspace guidance — first-time tenant entry with no personal workspace | not-started |
| task-063 | Ontology wizard and editor — add new node and edge types from scratch | not-started |
| task-064 | Data sources — animated progress indicator for active sync phases | not-started |
| task-065 | Mutations Console — knowledge graph selector and scoped API submission | not-started |
| task-066 | Design language — fix font weight violations in page headers and add regression tests | not-started |
| task-067 | Design language — fix font-bold violations in QueryResultsPanel keyboard shortcut badges | not-started |
| task-068 | Backend API Alignment — test data source creation uses KG-scoped endpoint | not-started |
| task-069 | Data source credential handling — test plaintext not persisted in browser | not-started |
| task-070 | Keyboard shortcut discoverability — test tooltip and kbd hints | not-started |
| task-071 | Knowledge Graph Creation — test post-creation data source prompt | not-started |
| task-072 | Backend API Alignment — test UI list auto-refresh after KG and data source creation | not-started (implemented in commit 823db6fa1) |
| task-073 | Sync Monitoring — sync history, log viewer, and manual trigger | not-started |
| task-074 | Mutations Console — workspace-scoped KG selector (workspace picker before KG picker) | not-started |
| task-075 | Backend API Alignment — test UI state refresh after CRUD operations | not-started |

## Conclusion

**No new task files created.** The spec is fully covered at blob SHA
`e77913c2cc6d8b719291e2dbb6870519a94d50da` by existing tasks 014–075.
