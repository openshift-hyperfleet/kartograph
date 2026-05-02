# Intake: specs/ui/experience.spec.md (modified) — 2026-05-01

**Spec blob SHA:** `e77913c2cc6d8b719291e2dbb6870519a94d50da`

## Summary

Re-processed `specs/ui/experience.spec.md` at current HEAD. Performed line-by-line
verification of all 59 scenarios across 17 requirements against existing tasks
(task-001 through task-072).

**Result: No new tasks required.** All scenarios are covered.

## Spec History

The current spec blob (`e77913c2cc6d8b719291e2dbb6870519a94d50da`) was introduced
in commit `e3d22bccf` ("docs(ui): add backend API alignment and mutations console
graph selection specs"). Relative to the prior version
(`14b2efabc5d0910e59494fd9b111b00c8a4383b3`), two changes were made:

1. **New — Mutations Console: Scenario: Knowledge graph selection** — covered by task-065.
2. **Updated — Mutations Console: Scenario: Submission** ("and a knowledge graph
   selected", "scoped to the selected knowledge graph") — also covered by task-065.

All prior scenarios and requirements remain covered by tasks created in earlier passes.

## Line-by-Line Verification

### Requirement: Backend API Alignment

| Scenario | Task(s) |
|---|---|
| Resource operations succeed end-to-end | task-050, task-068, task-072 |
| Parent context is preserved | task-040, task-068 |

### Requirement: Navigation Structure

| Scenario | Task(s) |
|---|---|
| Primary navigation | task-014 ✓, task-059 |
| Default landing | task-046 |
| New user landing | task-046 |

### Requirement: Tenant and Workspace Context

| Scenario | Task(s) |
|---|---|
| Tenant selector | task-058 |
| Workspace guidance | task-062 |

### Requirement: Knowledge Graph Creation

| Scenario | Task(s) |
|---|---|
| Create knowledge graph | task-040, task-015, task-071 |

### Requirement: Data Source Connection

| Scenario | Task(s) |
|---|---|
| Adapter type selection | task-015, task-041 |
| Connection configuration | task-015, task-041 |
| Credential handling | task-015, task-069 |

### Requirement: Ontology Design

| Scenario | Task(s) |
|---|---|
| Intent description | task-043 |
| Agent-proposed ontology | task-043 |
| Ontology review and approval | task-043 |
| Individual type editing | task-043, task-063 |
| Ontology change after initial extraction | task-043 |

### Requirement: Sync Monitoring

| Scenario | Task(s) |
|---|---|
| Active sync progress | task-042, task-064 |
| Sync history | task-041, task-015 |
| Sync logs | task-044 |
| Manual sync trigger | task-015, task-041 |

### Requirement: Get Started Querying (MCP Connection)

| Scenario | Task(s) |
|---|---|
| API key creation inline | task-051 |
| Copy-paste connection command | task-051 |
| Secret shown once | task-051 |

### Requirement: Query Console

| Scenario | Task(s) |
|---|---|
| Query editing | task-016 ✓ |
| Query execution | task-016 ✓ |
| Query history | task-016 ✓ |
| Knowledge graph context | task-045 |

### Requirement: Schema Browser

| Scenario | Task(s) |
|---|---|
| Type listing | task-016 ✓ |
| Type detail | task-016 ✓ |
| Cross-navigation | task-048 |

### Requirement: Graph Explorer

| Scenario | Task(s) |
|---|---|
| Node search | task-016 ✓ |
| Neighbor exploration | task-016 ✓ |

### Requirement: Mutations Console

| Scenario | Task(s) |
|---|---|
| Empty state | task-060 |
| JSONL editing | task-060 |
| Live preview | task-060 |
| File upload | task-060 |
| Knowledge graph selection | task-065 |
| Submission | task-061, task-065 |
| Submission failure | task-061 |
| Template insertion | task-060 |
| Deep-link to editor with pre-filled content | task-060 |

### Requirement: API Key Management

| Scenario | Task(s) |
|---|---|
| Create key | task-014 ✓, task-050 |
| List keys | task-014 ✓, task-050 |
| Revoke key | task-050 |

### Requirement: Workspace Management

| Scenario | Task(s) |
|---|---|
| Create workspace | task-014 ✓, task-050 |
| Member management | task-014 ✓, task-050 |

### Requirement: Design Language

| Scenario | Task(s) |
|---|---|
| Component library | task-052 |
| Color theme | task-052 |
| Typography | task-052, task-066, task-067 |
| Border radius | task-052 |
| Elevation | task-052 |

### Requirement: Interaction Principles

| Scenario | Task(s) |
|---|---|
| Progressive disclosure | task-057 |
| Inline actions over navigation | task-057 |
| Copy-to-clipboard | task-053 |
| Mutation feedback | task-053 |
| Keyboard shortcuts | task-054, task-070 |
| Focus indicators | task-049 |

### Requirement: Responsive Design

| Scenario | Task(s) |
|---|---|
| Desktop layout | task-055 |
| Tablet/mobile layout | task-055 |

### Requirement: Dark Mode

| Scenario | Task(s) |
|---|---|
| Toggle | task-056 |

## Open (not-started) Tasks for This Spec

| Task | Title |
|---|---|
| task-015 | Implement UI — knowledge graph management, data sources, and sync monitoring |
| task-040 | Fix KG creation — workspace selector and correct API endpoint |
| task-041 | Fix backend API response format — data sources and sync runs |
| task-042 | Fix sync-run phase status types and display labels in UI |
| task-043 | Implement UI — ontology design flow (intent, proposal review, type editing) |
| task-044 | Implement UI — sync log viewer (Sync Monitoring > Sync logs) |
| task-045 | Implement UI — query console knowledge graph scope selector |
| task-046 | Fix home page landing — KG-based redirect and new-user KG creation prompt |
| task-047 | Add sync-status badge to Data Sources sidebar nav item |
| task-048 | Update schema browser cross-navigation — add ontology editor link per type |
| task-049 | Fix focus ring inconsistencies — ring-2 → ring-[3px] on custom interactive elements |
| task-050 | Backend API alignment audit — IAM and explore page CRUD operations |
| task-051 | Audit MCP integration page — Get Started Querying scenarios and API alignment |
| task-052 | Audit and implement Design Language — OKLCH tokens, typography, border radius, elevation |
| task-053 | Cross-page copy-to-clipboard and mutation feedback consistency audit |
| task-054 | Implement keyboard shortcuts — slash-to-focus-search and discoverable Ctrl/Cmd+Enter |
| task-055 | Audit and verify Responsive Design — desktop sidebar collapsible, mobile sheet overlay |
| task-056 | Audit and verify Dark Mode — header toggle and session-persistent preference |
| task-057 | Audit interaction principles — progressive disclosure and inline actions |
| task-058 | Audit tenant selector — verify all tenant-scoped pages refresh on tenant switch |
| task-059 | Navigation update — add Mutations Console to Explore sidebar group |
| task-060 | Mutations Console — core editor (empty state, JSONL editing, live preview, file upload, templates, deep-link) |
| task-061 | Mutations Console — submission flow (floating progress indicator, failure handling) |
| task-062 | Audit workspace guidance — first-time tenant entry with no personal workspace |
| task-063 | Ontology wizard and editor — add new node and edge types from scratch |
| task-064 | Data sources — animated progress indicator for active sync phases |
| task-065 | Mutations Console — knowledge graph selector and scoped API submission |
| task-066 | Design language — fix font weight violations in page headers and add regression tests |
| task-067 | Design language — fix font-bold violations in QueryResultsPanel keyboard shortcut badges |
| task-068 | Backend API Alignment — test data source creation uses KG-scoped endpoint |
| task-069 | Data source credential handling — test plaintext not persisted in browser |
| task-070 | Keyboard shortcut discoverability — test tooltip and kbd hints |
| task-071 | Knowledge Graph Creation — test post-creation data source prompt |
| task-072 | Backend API Alignment — test UI list auto-refresh after KG and data source creation |

## Conclusion

**No new task files created.** The spec is fully covered at blob SHA
`e77913c2cc6d8b719291e2dbb6870519a94d50da` by the 72 existing tasks.
