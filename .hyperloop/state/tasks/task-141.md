---
id: task-141
title: "UI Query Console — Cypher editor, execution, history, KG scope"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-140]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add Cypher query console with editor, execution, and history"
pr_description: |
  ## What and Why

  The Query Console is the primary tool for power users and developers who want to
  explore their knowledge graph directly with Cypher. It provides a schema-aware
  editor, query execution against the Kartograph backend, tabular results with
  metadata, and a query history panel for recalling past queries.

  This page corresponds to the `Explore → Query Console` sidebar link introduced
  in task-140.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Query Console — Scenario: Query editing**
    "Cypher syntax highlighting, autocomplete based on the current schema, and linting"

  - **Requirement: Query Console — Scenario: Query execution**
    "button or Ctrl/Cmd+Enter executes; results displayed as table with execution time
    and row count"

  - **Requirement: Query Console — Scenario: Query history**
    "browse, re-execute, or insert past queries from a history panel"

  - **Requirement: Query Console — Scenario: Knowledge graph context**
    "optional KG selector to scope queries; when unscoped, spans all accessible KGs"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    Query execution calls the MCP `query_graph` tool via the HTTP+MCP protocol
    (or a dedicated REST endpoint if one is available); 2xx response is required.

  - **Requirement: Interaction Principles — Scenario: Keyboard shortcuts**
    Ctrl/Cmd+Enter executes the query; discoverable via tooltip on the Run button.

  - **Requirement: Interaction Principles — Scenario: Progressive disclosure**
    Results pane collapsed by default when empty; opens automatically on first result.

  ## Key Design Decisions

  - **Editor**: CodeMirror 6 with the `@codemirror/lang-cypher` (or community package)
    extension for Cypher syntax highlighting. Autocomplete against schema labels fetched
    from `GET /graph/schema/nodes` and `GET /graph/schema/edges`.
  - **Execution**: The UI calls the Kartograph REST API at `POST /graph/execute-query`
    (or equivalent) which wraps the backend query execution. If no dedicated REST
    endpoint exists for the UI, the implementation should add a thin REST wrapper
    in the graph presentation layer.
  - **Results table**: Flattened JSON rows from the query response rendered with a
    virtual-scroll table (for large result sets). Columns derived from the first row's
    keys.
  - **History**: Stored in `localStorage` (keyed per user). Max 50 entries. Each
    entry stores query text, execution timestamp, row count, and KG scope.
  - **KG selector**: Dropdown populated from `GET /workspaces/{id}/knowledge-graphs`
    filtered to `view` permission. "All knowledge graphs" is the default (no filter).

  ## What Files Are Affected

  - **New**: `src/ui/pages/explore/query.vue`
  - **New**: `src/ui/components/query/CypherEditor.vue` (CodeMirror wrapper)
  - **New**: `src/ui/components/query/QueryResultsTable.vue`
  - **New**: `src/ui/components/query/QueryHistoryPanel.vue`
  - **New**: `src/ui/components/query/KnowledgeGraphSelector.vue`
  - **New**: `src/ui/composables/useQueryHistory.ts`
  - **New**: `src/ui/composables/useSchemaAutocomplete.ts`
  - **New**: `src/ui/tests/unit/CypherEditor.test.ts`
  - **New**: `src/ui/tests/unit/useQueryHistory.test.ts`

  ## How to Verify

  ```bash
  # Start dev instance
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/ui && npm run dev
  # Navigate to http://localhost:3000/explore/query
  # 1. Type a Cypher query — autocomplete suggests node labels from schema
  # 2. Press Ctrl+Enter — results table appears with row count and execution time
  # 3. Expand history panel — previous query is listed; click to re-run
  # 4. Select a KG from the selector — results are filtered to that KG
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- query
  # useQueryHistory: adds, retrieves, and caps at 50 entries
  # QueryResultsTable: renders rows correctly, handles empty result
  ```

  ## Caveats

  - Apache AGE requires queries to return a single column (map syntax for multiple
    values). A contextual hint about this requirement should appear near the editor.
  - If `@codemirror/lang-cypher` is not available as a maintained package, use
    CodeMirror's SQL mode with Cypher keyword overrides as a fallback.
  - If no REST endpoint exists for direct UI query execution (separate from the MCP
    tool), a lightweight `POST /graph/query` endpoint must be added to the graph
    presentation layer as part of this task. That endpoint must enforce the same
    read-only and timeout constraints as the MCP tool.
---
