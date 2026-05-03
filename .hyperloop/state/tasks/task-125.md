---
id: task-125
title: UI Query Console — Cypher Editor with Schema-Aware Assistance
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-119, task-120]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add Cypher query console with editor, results, and history"
pr_description: |
  ## What and Why

  The Query Console is the primary tool for technical users to explore their
  knowledge graph. It provides a Cypher editor with syntax awareness and displays
  results in a tabular format. It is the first page in the "Explore" sidebar group
  and the default landing page for returning users.

  The workspace context from task-120 is needed to resolve which knowledge graphs
  are available for the KG scope selector.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Query Console** from
  `specs/ui/experience.spec.md`.

  Specifically:
  - **Query editing**: Cypher syntax highlighting, autocomplete based on current
    schema labels and property keys, and linting (red underlines for obvious errors).
  - **Query execution**: "Run" button and Ctrl/Cmd+Enter keyboard shortcut both
    execute the query; results render as a table with columns derived from the
    returned row keys; execution time and row count are displayed below the table.
  - **Query history**: a collapsible history panel lists past queries (up to 50,
    stored in `localStorage`) with timestamps; clicking a history entry inserts it
    into the editor; re-execute button runs it directly.
  - **Knowledge graph context**: a dropdown above the editor lets the user optionally
    scope queries to a specific KG (calls `query_graph` with `knowledge_graph_id`);
    when unscoped, queries span all accessible KGs.

  ## Design Decisions

  - **Editor**: CodeMirror 6 with `@codemirror/lang-lezer` or a Cypher grammar
    extension; chosen over Monaco for its smaller bundle size and better Vue
    integration.
  - **Autocomplete**: schema labels and property keys are fetched from
    `GET /api/query/schema/labels` on page load and fed into a custom CodeMirror
    completion source.
  - **Query execution**: calls the backend REST endpoint that wraps the MCP
    `query_graph` logic (or directly hits the FastAPI query route if exposed).
    Note: the UI calls the REST API, not the MCP protocol directly.
  - **Results table**: `<table>` with sticky header; for large result sets (rows
    with many columns), the table scrolls horizontally. A "truncated" badge appears
    when the backend signals the result was cut off.
  - **History**: stored in `localStorage` keyed by tenant+user to prevent cross-
    contamination; max 50 entries with LRU eviction.

  ## Backend APIs Required

  - `GET /api/query/schema/labels` — node and edge type labels for autocomplete
  - `POST /api/query/execute` — execute Cypher query (REST wrapper over MCP logic)

  ## Files / Areas Affected

  - `src/ui/pages/explore/QueryConsolePage.vue`
  - `src/ui/components/query/CypherEditor.vue` — CodeMirror wrapper
  - `src/ui/components/query/QueryResultsTable.vue`
  - `src/ui/components/query/QueryHistoryPanel.vue`
  - `src/ui/components/query/KnowledgeGraphScopeSelector.vue`
  - `src/ui/composables/useQueryExecution.ts`
  - `src/ui/composables/useQueryHistory.ts`
  - `src/ui/composables/useSchemaLabels.ts`

  ## How to Verify

  1. Query console loads with empty editor; schema labels available in autocomplete
  2. Write a valid MATCH query; Ctrl/Cmd+Enter executes it; results table renders
  3. Execution time and row count shown below the table
  4. "Truncated" badge appears when the backend returns `truncated: true`
  5. History panel shows past queries; clicking re-populates editor; timestamps shown
  6. KG scope selector: selecting a KG sends `knowledge_graph_id`; leaving blank spans all
  7. Write query with CREATE keyword; execution returns forbidden error with toast

  ## Caveats

  The REST query execution endpoint (`POST /api/query/execute`) may need to be
  added to the FastAPI app if it doesn't already exist as a non-MCP route.
  The existing `query_graph` MCP tool logic should be reused; it should not be
  duplicated.
---
