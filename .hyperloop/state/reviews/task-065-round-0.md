---
task_id: task-065
round: 0
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — experience.spec.md

### Summary

The implementation is extensive and covers the vast majority of the spec. However, one requirement has a structural deviation that constitutes a FAIL: the Navigation Structure scenario specifies groupings that differ from what is implemented, and there is no test that validates the spec's exact grouping (though there are tests that validate the implemented grouping).

---

### Requirement-by-Requirement Assessment

#### Requirement: Backend API Alignment — COVERED
- Scenario "Resource operations succeed end-to-end": Covered by data-sources.test.ts (createDataSourceWithFetch tests), knowledge-graphs.test.ts (API call tests), mutations-kg-selector.test.ts (applyMutations URL and body tests).
- Scenario "Parent context is preserved": Covered by data-sources.test.ts `Backend API Alignment — data source creation uses KG-scoped endpoint` block which asserts POST URL includes parent KG ID and is not workspace-scoped.

#### Requirement: Navigation Structure — PARTIAL (FAIL)
- Scenario "Primary navigation":
  - Spec: sidebar grouped as Explore (Query Console, Schema Browser, Graph Explorer, Mutations Console), Connect (API Keys, MCP Integration), Settings (Workspaces, Groups, Tenants).
  - Implementation: has an additional "Data" section (Knowledge Graphs, Data Sources) inserted between Explore and Connect, which is NOT in the spec's navigation grouping.
  - The interaction-principles.test.ts "Navigation - sidebar section structure" describes 4 sections: Explore, Data, Connect, Settings — and the test explicitly lists "Data" as a spec-defined section. However the spec at experience.spec.md does NOT list a "Data" section. The spec only lists three groups: Explore, Connect, Settings.
  - PARTIAL: The implementation adds a "Data" section with Knowledge Graphs and Data Sources items that is not in the spec's navigation structure. However, the test suite has been written to match the implementation (not the spec), so the tests pass against the implementation but the implementation deviates from the spec.
  - NOTE: This is a spec deviation — the implementation is more complete than the spec in this regard (the Data section is a reasonable extension). This is a FAIL per the review rules ("Implemented feature deviates from spec" / extra behaviour not in spec).

- Scenario "Default landing" (returning user redirects to /query): COVERED by index.test.ts `Index Page — Default landing redirect`.
- Scenario "New user landing" (prompted to create KG): COVERED by index.test.ts `Index Page — Checklist includes "Create a knowledge graph" step`.

#### Requirement: Tenant and Workspace Context — COVERED
- Scenario "Tenant selector": Covered by default.layout.test.ts `Default layout — tenant selector in sidebar` tests.
- Scenario "Workspace guidance": Covered by workspace-guidance.test.ts and index.test.ts `Index Page — Workspace guidance toast`.

#### Requirement: Knowledge Graph Creation — COVERED
- Scenario "Create knowledge graph": Covered by knowledge-graphs.test.ts (name/description, workspace-scoped POST, data source prompt post-creation).

#### Requirement: Data Source Connection — COVERED
- Scenario "Adapter type selection": Covered by data-sources.test.ts step navigation tests.
- Scenario "Connection configuration": Covered by data-sources.test.ts form validation and name inference tests.
- Scenario "Credential handling": Covered structurally (credentials field in API body tests); credentials are sent server-side, not persisted in browser (tests in data-sources.test.ts approval flow).

#### Requirement: Ontology Design — COVERED
- Scenario "Intent description": Covered by data-sources.test.ts intent step tests.
- Scenario "Agent-proposed ontology": Covered by data-sources.test.ts `Ontology Design - Agent-Proposed Ontology` suite.
- Scenario "Ontology review and approval": Covered by data-sources.test.ts approval tests.
- Scenario "Individual type editing": Covered by data-sources.test.ts startEditNode/saveEditNode/cancelEditNode/removeNode/startEditEdge/saveEditEdge suites.
- Scenario "Ontology change after initial extraction": Covered by data-sources.test.ts `Ontology Edit - Post-Extraction Confirmation Gate`.

#### Requirement: Sync Monitoring — COVERED
- Scenario "Active sync progress": Covered by sync-monitoring-extended.test.ts and sync-phase-indicator.test.ts.
- Scenario "Sync history": Covered by sync-monitoring-extended.test.ts.
- Scenario "Sync logs": Covered by data-sources.test.ts `Sync Logs - Fetching log lines`.
- Scenario "Manual sync trigger": Covered by sync-monitoring-extended.test.ts (triggerSync tests).

#### Requirement: Get Started Querying (MCP Connection) — COVERED
- Scenario "API key creation inline": Covered by mcp-integration.test.ts inline API key creation tests.
- Scenario "Copy-paste connection command": Covered by mcp-integration.test.ts config snippet generation tests.
- Scenario "Secret shown once": Covered by mcp-integration.test.ts `MCP Integration - secret shown once` and `MCP Integration - dismissSecret`.

#### Requirement: Query Console — COVERED
- Scenario "Query editing": Covered structurally (CodeMirror imports with syntax highlighting, autocomplete referenced in page structure).
- Scenario "Query execution": Covered by data-sources.test.ts `Query Console - KG Selector Population` and query-history.test.ts.
- Scenario "Query history": Covered by query-history.test.ts.
- Scenario "Knowledge graph context": Covered by data-sources.test.ts `Query Console - KG Selector Population` and knowledge-graphs.test.ts `buildQueryGraphArgs` tests.

#### Requirement: Schema Browser — COVERED
- Scenario "Type listing": Covered by schema-browser.test.ts filteredLabels tests.
- Scenario "Type detail": Covered by schema-browser.test.ts (expand/detail tests).
- Scenario "Cross-navigation": Covered by schema-browser.test.ts buildQueryNavigation and related tests.

#### Requirement: Graph Explorer — COVERED
- Scenario "Node search": Covered by graph-explorer.test.ts.
- Scenario "Neighbor exploration": Covered by graph-explorer.test.ts.

#### Requirement: Mutations Console — COVERED
- All 9 scenarios (Empty state, JSONL editing, Live preview, File upload, KG selection, Submission, Submission failure, Template insertion, Deep-link) are covered by mutations-console.test.ts, mutations-kg-selector.test.ts, and mutations-submission.test.ts.

#### Requirement: API Key Management — COVERED
- Scenario "Create key": Covered by api-keys.test.ts create key validation and success tests.
- Scenario "List keys": Covered by api-keys.test.ts list filtering by status, keyStatus, daysUntilExpiry tests.
- Scenario "Revoke key": Covered by api-keys.test.ts revoke key tests.

#### Requirement: Workspace Management — COVERED
- Scenario "Create workspace": Covered by workspace-management.test.ts.
- Scenario "Member management": Covered by workspace-management.test.ts.

#### Requirement: Design Language — COVERED
- Scenario "Component library" (shadcn/vue, Reka UI, CVA, Lucide): Covered by design-system.test.ts.
- Scenario "Color theme" (OKLCH, warm amber/orange): Covered by design-language.test.ts and design-system.test.ts.
- Scenario "Typography" (system font, text-sm, text-[11px] uppercase tracking-wider): Covered by design-language.test.ts and design-language-extended.test.ts.
- Scenario "Border radius" (0.625rem base): Covered by design-language.test.ts.
- Scenario "Elevation" (shadow-sm cards, shadow-xs buttons): Covered by design-language.test.ts.

#### Requirement: Interaction Principles — COVERED
- Scenario "Progressive disclosure": Covered by interaction-principles.test.ts.
- Scenario "Inline actions over navigation": Covered by interaction-principles.test.ts.
- Scenario "Copy-to-clipboard": Covered by interaction-principles.test.ts.
- Scenario "Mutation feedback": Covered by interaction-principles.test.ts.
- Scenario "Keyboard shortcuts": Partially covered (Ctrl/Cmd+Enter in mutations-console.test.ts; "/" search shortcut referenced in schema-browser.test.ts).
- Scenario "Focus indicators" (3px ring): Covered by focus-ring.test.ts.

#### Requirement: Responsive Design — COVERED
- Scenario "Desktop layout": Covered by responsive-design.test.ts.
- Scenario "Tablet/mobile layout" (sidebar collapses to sheet): Covered by responsive-design.test.ts.

#### Requirement: Dark Mode — COVERED
- Scenario "Toggle": Covered by color-mode.test.ts and the layout tests in color-mode.test.ts.

---

### FAIL Detail

**Navigation Structure — Primary navigation scenario FAILS:**

The spec states:
```
Explore — Query Console, Schema Browser, Graph Explorer, Mutations Console
Connect — API Keys, MCP Integration
Settings — Workspaces, Groups, Tenants
```

The implementation at `/home/jsell/code/kartograph/worktrees/workers/task-065/src/dev-ui/app/layouts/default.vue` (lines 247-284) implements:
```
Explore — Query Console, Schema Browser, Graph Explorer, Mutations Console
Data — Knowledge Graphs, Data Sources
Connect — API Keys, MCP Integration
Settings — Workspaces, Groups, Tenants
```

A "Data" section is added that is not in the spec. The test at `/home/jsell/code/kartograph/worktrees/workers/task-065/src/dev-ui/app/tests/interaction-principles.test.ts` line 252-286 tests the implemented 4-section structure, explicitly adding "Data" as a section — but the spec only specifies 3 sections. The test in `default.layout.test.ts` (line 87-129 buildNavSections) also models the 4-section structure.

No test validates the spec's 3-section navigation grouping (Explore, Connect, Settings). This is a case where the tests were written to match the implementation rather than the spec.

**What is needed to PASS:**
Either:
1. Update the spec (experience.spec.md) to include the "Data" section under Primary navigation, or
2. Reorganize the navigation to remove the separate "Data" section and move Knowledge Graphs and Data Sources into a spec-compliant grouping, and update tests accordingly.