---
id: task-108
title: "Query console: knowledge graph context selector to scope queries"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): add knowledge graph context selector to query console"
pr_description: |
  ## What & Why

  The **Query Console** requirement in `specs/ui/experience.spec.md` includes a
  scoping scenario that controls which knowledge graph a query targets:

  > "GIVEN a query console THEN the user can optionally select a specific knowledge
  > graph to scope queries AND when unscoped, queries span all knowledge graphs the
  > user can access in the tenant"

  The backend MCP `query_graph` tool accepts an optional `knowledge_graph_id`
  parameter for exactly this purpose. The current `/pages/query/index.vue` executes
  queries without passing a KG filter, meaning all queries span the entire tenant
  graph. For users with multiple knowledge graphs, this can produce confusing results
  that mix data from unrelated graphs.

  The KG selector also ties directly to the MCP `knowledge_graphs://accessible`
  resource — the same list used to populate the selector in the mutations console
  should power the query console selector.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Query Console** — Scenario: *Knowledge graph context*

  ## What This Change Does

  ### KG Selector Component in Query Console

  Add a `<KnowledgeGraphSelector>` component (or reuse the one from the mutations
  console if it exists) to the query console toolbar, positioned between the query
  editor controls and the Run button.

  Behavior:
  - Populates from `GET /management/knowledge-graphs` (filtered to the active
    tenant/workspace, and only KGs the user has `view` permission on).
  - Shows a placeholder: "All knowledge graphs" when nothing is selected.
  - When a KG is selected, it is stored in a reactive variable and passed as
    `knowledge_graph_id` in the query execution request body.
  - Unselecting resets to the unscoped state (all KGs).
  - The selection persists for the session (reactive state) but does not persist
    across page reloads.
  - The selected KG name is shown in the toolbar so the user always knows the
    current scope.

  ### Query Execution Request Update

  Update the composable or service call that executes queries
  (`src/dev-ui/app/composables/useQueryExecution.ts` or similar) to include
  `knowledge_graph_id` in the request when a KG is selected:

  ```typescript
  // When KG is selected:
  { cypher: query, knowledge_graph_id: selectedKgId, max_rows: maxRows }

  // When unscoped:
  { cypher: query, max_rows: maxRows }
  ```

  Verify the backend MCP tool's request schema accepts this structure.

  ### Cross-Link with Schema Browser

  The KG context selector also improves schema browser integration: when a KG is
  selected, the schema browser (if open in a split or separate tab) should ideally
  show the ontology for that specific KG. This is a desirable enhancement but out
  of scope for this task — do not implement, but add a code comment noting the
  future integration point.

  ## Files / Areas Affected

  - `src/dev-ui/app/pages/query/index.vue` — add KG selector to toolbar
  - `src/dev-ui/app/components/query/KnowledgeGraphSelector.vue` (new or reuse)
  - `src/dev-ui/app/composables/useQueryExecution.ts` (or similar) — pass
    `knowledge_graph_id` when selected

  ## Tests

  Vitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:
  - `test_kg_selector_rendered_in_query_console`: mount `/query`, assert the KG
    selector component is present in the toolbar
  - `test_kg_selector_populates_from_api`: mock `GET /management/knowledge-graphs`
    returning two KGs, assert the selector dropdown contains both options
  - `test_selected_kg_included_in_query_request`: select a specific KG, execute a
    query, assert the API call includes `knowledge_graph_id`
  - `test_no_kg_selected_omits_knowledge_graph_id`: leave selector on "All knowledge
    graphs", execute a query, assert the API call does NOT include `knowledge_graph_id`
  - `test_kg_selector_shows_selected_kg_name_in_toolbar`: select a KG, assert the
    toolbar displays the KG name (not just an ID or placeholder)

  ## How to Verify

  1. Navigate to `/query`
  2. Confirm the toolbar shows a "All knowledge graphs" dropdown
  3. Select a specific knowledge graph from the dropdown
  4. Execute any Cypher query — open DevTools Network tab and confirm the request
     body includes `knowledge_graph_id` with the selected KG's ID
  5. Clear the selection back to "All knowledge graphs"
  6. Execute the same query — confirm `knowledge_graph_id` is absent from the request

  ## Caveats

  - The KG list is fetched from the Management context (`GET /management/knowledge-graphs`),
    not from the MCP `knowledge_graphs://accessible` resource (which is MCP-protocol
    specific). Use the REST API for the dropdown list.
  - If the user has no accessible knowledge graphs, show the selector in a disabled
    state with a message: "No knowledge graphs available — create one in the Data
    section."
  - The selected KG state should NOT be shared with the mutations console selector
    (they are independent scoping contexts). Both can reuse the same Vue component
    but should have separate reactive state instances.
---
