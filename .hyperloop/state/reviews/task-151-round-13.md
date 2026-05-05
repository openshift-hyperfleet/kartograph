---
task_id: task-151
round: 13
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — task-151

### Summary

The branch `hyperloop/task-151` contains a substantial Nuxt/Vue dev-UI implementation
at `src/dev-ui/`. All 2615 unit tests pass. However, one spec requirement is
structurally missing from the implementation, causing a FAIL verdict.

---

### Requirement Status

**1. Backend API Alignment — COVERED**
- `src/dev-ui/app/composables/useApiClient.ts` injects `Authorization: Bearer` and
  `X-Tenant-ID` headers per request.
- `src/dev-ui/app/tests/api-alignment.test.ts` (47 tests, all pass).

**2. Navigation Structure — PARTIAL**
- Explore, Data, Connect, Settings groups are implemented in
  `src/dev-ui/app/layouts/default.vue` (lines 281-319).
- The spec (line 29) requires the Explore group to contain:
  "Query Console, Schema Browser, Graph Explorer, **Graph Visualizer**, Mutations Console"
- The implementation's Explore group contains only:
  Query Console, Schema Browser, Graph Explorer, Mutations Console.
- **"Graph Visualizer" nav entry is absent from the sidebar.**
- No `/graph/visualizer` (or equivalent) page file exists under
  `src/dev-ui/app/pages/graph/`.
- `src/dev-ui/app/tests/task-151-spec-alignment.test.ts` and
  `src/dev-ui/app/tests/navigation-structure.test.ts` both omit any assertion for
  Graph Visualizer — the gap is untested and undetected by the existing suite.

**3. Tenant and Workspace Context — COVERED**
- Multi-tenant selector with switching implemented in `default.vue`.
- Workspace guidance toast implemented in `default.vue` (lines 200-230).

**4. Knowledge Graph Creation — COVERED**
- `src/dev-ui/app/pages/knowledge-graphs/index.vue` implements create/list/delete.
- `src/dev-ui/app/tests/knowledge-graphs.test.ts` (76 tests, all pass).

**5. Data Source Connection — COVERED**
- Adapter type selection, connection configuration, credential handling all in
  `src/dev-ui/app/pages/data-sources/index.vue`.
- `src/dev-ui/app/tests/data-sources.test.ts` (183 tests) and
  `src/dev-ui/app/tests/data-source-connection-wizard.test.ts` (30 tests), all pass.

**6. Ontology Design — COVERED**
- Ontology intent, proposal, review/approval, and individual type editing implemented
  inside `src/dev-ui/app/pages/data-sources/index.vue` and
  `src/dev-ui/app/utils/ontologyWizard.ts`.
- `src/dev-ui/app/tests/ontology-design.test.ts` (58 tests) and
  `src/dev-ui/app/tests/ontology-add-types.test.ts` (14 tests), all pass.

**7. Sync Monitoring — COVERED**
- Phase indicator, sync history, logs, and manual trigger in
  `src/dev-ui/app/pages/data-sources/index.vue` and
  `src/dev-ui/app/components/graph/SyncPhaseIndicator.vue`.
- `src/dev-ui/app/tests/sync-monitoring-extended.test.ts` (44 tests) and
  `src/dev-ui/app/tests/sync-logs.test.ts` (20 tests), all pass.

**8. Get Started Querying (MCP Connection) — COVERED**
- Inline API key creation, copy-paste snippet, secret-shown-once flow in
  `src/dev-ui/app/pages/integrate/mcp.vue`.
- `src/dev-ui/app/tests/mcp-integration.test.ts` (27 tests, all pass).

**9. Query Console — COVERED**
- Cypher editor with syntax highlighting (CodeMirror + custom lang-cypher),
  autocomplete, linting, Ctrl/Cmd+Enter execution, history panel, KG selector in
  `src/dev-ui/app/pages/query/index.vue`.
- `src/dev-ui/app/tests/query.test.ts` (16 tests) and related query tests pass.

**10. Schema Browser — COVERED**
- Node/edge type listing with virtual scroll, search, inline expand, cross-navigation
  in `src/dev-ui/app/pages/graph/schema.vue`.
- `src/dev-ui/app/tests/schema-browser.test.ts` (47 tests) and
  `src/dev-ui/app/tests/schema-crossnav-deeplink.test.ts` (30 tests), all pass.

**11. Graph Explorer — COVERED**
- Node search by type/name/slug, neighbor expansion, drill trail in
  `src/dev-ui/app/pages/graph/explorer.vue`.
- `src/dev-ui/app/tests/graph-explorer.test.ts` (76 tests, all pass).

**12. Graph Visualizer — MISSING**
- Spec requirement (lines 221-290) mandates a full-screen force-directed graph
  visualization using the `@cosmograph/cosmograph` npm package with:
    - Dark background `#0a0a0a`, nodes colored by type (`pointColorBy: 'nodeType'`),
      sized by degree (`pointSizeBy: 'degree'`, range [1,100]).
    - Edges as thin gray lines (`linkWidth: 0.5`, `linkColor: '#555555'`).
    - Force simulation: `gravity: 0.1`, `repulsion: 1.0`, `linkSpring: 0.5`,
      `friction: 0.9`.
    - Floating control panel (top-left, `rgba(20,20,20,0.95)`) with KG selector,
      search-and-highlight, pause/play, fit-to-screen controls.
    - Node hover/click metadata panel (top-right), edge hover tooltip.
    - Streaming data load via `response.body.getReader()` with progress bar.
    - Empty-graph state message.
    - Dedicated backend bulk-data endpoint querying AGE label tables via SQL UNION ALL.
- The spec references `src/api/util/dev_routes.py` as the reference implementation
  being promoted from a dev utility — that file was NOT reviewed to be in scope for
  this task but the UI page is clearly absent.
- `@cosmograph/cosmograph` is NOT in `src/dev-ui/package.json`. The only graph
  library present is `cytoscape` (used by the Query Console results graph, not a
  dedicated Visualizer page).
- No `/graph/visualizer.vue` (or any equivalent page) exists.
- The sidebar nav entry "Graph Visualizer" linking to `/graph/visualizer` is absent.
- No tests exist for the Graph Visualizer requirement.
- The spec explicitly requires the Cosmograph npm package, NOT a CDN load.

**13. Mutations Console — COVERED**
- JSONL editor with CodeMirror, linting, autocomplete, drag-and-drop upload,
  large-file mode, KG selector, template insertion, deep-link support, floating
  progress indicator in `src/dev-ui/app/pages/graph/mutations.vue` and
  `src/dev-ui/app/components/graph/`.
- Extensive test suite (mutations-console, mutations-submission, mutations-kg-selector,
  etc.) — 174+ tests, all pass.

**14. API Key Management — COVERED**
- Create, list (with status/dates), revoke, secret-shown-once in
  `src/dev-ui/app/pages/api-keys/index.vue`.
- `src/dev-ui/app/tests/api-keys.test.ts` (43 tests, all pass).

**15. Workspace Management — COVERED**
- Create workspace, member add/remove/role-change in
  `src/dev-ui/app/pages/workspaces/` and related components.
- `src/dev-ui/app/tests/workspace-management.test.ts` (79 tests, all pass).

**16. Design Language — COVERED**
- shadcn/vue (reka-ui), Tailwind CSS, CVA, Lucide Vue Next all present in
  `src/dev-ui/package.json`.
- OKLCH CSS custom properties in `src/dev-ui/app/assets/css/main.css`:
  light primary `oklch(0.5768 0.2469 29.23)`, dark primary `oklch(0.6857 0.1560 17.57)`,
  5 chart tokens, destructive coral, base radius `0.625rem`.
- `src/dev-ui/app/tests/design-language.test.ts` (184 tests, all pass).

**17. Interaction Principles — COVERED**
- Progressive disclosure, inline editing, copy-to-clipboard, toast notifications,
  keyboard shortcuts (Ctrl/Cmd+Enter, "/"), focus rings implemented.
- `src/dev-ui/app/tests/interaction-principles.test.ts` (45 tests, all pass).

**18. Responsive Design — COVERED**
- Desktop sidebar collapsible via `useSidebar.ts`; mobile Sheet overlay in
  `default.vue`.
- `src/dev-ui/app/tests/responsive-design.test.ts` (35 tests, all pass).

**19. Dark Mode — COVERED**
- Toggle in header using Moon/Sun icons, persisted via `useColorMode.ts` to
  `localStorage` key `kartograph-color-mode`, `.dark` class toggled on
  `documentElement`.
- `src/dev-ui/app/tests/color-mode.test.ts` (15 tests, all pass).

---

### What Must Be Fixed

**The single blocker is Requirement 12 — Graph Visualizer.** To pass:

1. Add `@cosmograph/cosmograph` to `src/dev-ui/package.json` dependencies.
2. Create `src/dev-ui/app/pages/graph/visualizer.vue` implementing the full
   Cosmograph-based page as specified (lines 221-290 of
   `specs/ui/experience.spec.md`), preserving the exact visual settings from the
   `_VIEWER_TEMPLATE` in `src/api/util/dev_routes.py`.
3. Add a "Graph Visualizer" nav entry in `src/dev-ui/app/layouts/default.vue`
   (Explore section) linking to `/graph/visualizer`.
4. Add spec-alignment tests asserting: `@cosmograph/cosmograph` is in package.json,
   the visualizer page exists and references the required Cosmograph config values,
   and the nav entry is present.

All other 18 requirements are COVERED. Test suite: 2615 tests, 55 files, all pass.