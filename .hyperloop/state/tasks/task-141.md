---
id: task-141
title: UI Query Console — Cypher editor, execution, history, KG scope
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps:
- task-140
round: 8
branch: hyperloop/task-141
pr: https://github.com/openshift-hyperfleet/kartograph/pull/616
pr_title: 'feat(ui): add Cypher query console with editor, execution, and history'
pr_description: "## What and Why\n\nThe Query Console is the primary tool for power\
  \ users and developers who want to\nexplore their knowledge graph directly with\
  \ Cypher. It provides a schema-aware\neditor, query execution against the Kartograph\
  \ backend, tabular results with\nmetadata, and a query history panel for recalling\
  \ past queries.\n\nThis page corresponds to the `Explore → Query Console` sidebar\
  \ link introduced\nin task-140.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Query Console — Scenario: Query editing**\n  \"Cypher syntax\
  \ highlighting, autocomplete based on the current schema, and linting\"\n\n- **Requirement:\
  \ Query Console — Scenario: Query execution**\n  \"button or Ctrl/Cmd+Enter executes;\
  \ results displayed as table with execution time\n  and row count\"\n\n- **Requirement:\
  \ Query Console — Scenario: Query history**\n  \"browse, re-execute, or insert past\
  \ queries from a history panel\"\n\n- **Requirement: Query Console — Scenario: Knowledge\
  \ graph context**\n  \"optional KG selector to scope queries; when unscoped, spans\
  \ all accessible KGs\"\n\n- **Requirement: Backend API Alignment — Scenario: Resource\
  \ operations succeed end-to-end**\n  Query execution calls the MCP `query_graph`\
  \ tool via the HTTP+MCP protocol\n  (or a dedicated REST endpoint if one is available);\
  \ 2xx response is required.\n\n- **Requirement: Interaction Principles — Scenario:\
  \ Keyboard shortcuts**\n  Ctrl/Cmd+Enter executes the query; discoverable via tooltip\
  \ on the Run button.\n\n- **Requirement: Interaction Principles — Scenario: Progressive\
  \ disclosure**\n  Results pane collapsed by default when empty; opens automatically\
  \ on first result.\n\n## Key Design Decisions\n\n- **Editor**: CodeMirror 6 with\
  \ the `@codemirror/lang-cypher` (or community package)\n  extension for Cypher syntax\
  \ highlighting. Autocomplete against schema labels fetched\n  from `GET /graph/schema/nodes`\
  \ and `GET /graph/schema/edges`.\n- **Execution**: The UI calls the Kartograph REST\
  \ API at `POST /graph/execute-query`\n  (or equivalent) which wraps the backend\
  \ query execution. If no dedicated REST\n  endpoint exists for the UI, the implementation\
  \ should add a thin REST wrapper\n  in the graph presentation layer.\n- **Results\
  \ table**: Flattened JSON rows from the query response rendered with a\n  virtual-scroll\
  \ table (for large result sets). Columns derived from the first row's\n  keys.\n\
  - **History**: Stored in `localStorage` (keyed per user). Max 50 entries. Each\n\
  \  entry stores query text, execution timestamp, row count, and KG scope.\n- **KG\
  \ selector**: Dropdown populated from `GET /workspaces/{id}/knowledge-graphs`\n\
  \  filtered to `view` permission. \"All knowledge graphs\" is the default (no filter).\n\
  \n## What Files Are Affected\n\n- **New**: `src/ui/pages/explore/query.vue`\n- **New**:\
  \ `src/ui/components/query/CypherEditor.vue` (CodeMirror wrapper)\n- **New**: `src/ui/components/query/QueryResultsTable.vue`\n\
  - **New**: `src/ui/components/query/QueryHistoryPanel.vue`\n- **New**: `src/ui/components/query/KnowledgeGraphSelector.vue`\n\
  - **New**: `src/ui/composables/useQueryHistory.ts`\n- **New**: `src/ui/composables/useSchemaAutocomplete.ts`\n\
  - **New**: `src/ui/tests/unit/CypherEditor.test.ts`\n- **New**: `src/ui/tests/unit/useQueryHistory.test.ts`\n\
  \n## How to Verify\n\n```bash\n# Start dev instance\nmake instance-up\nsource .instances/$(basename\
  \ $(pwd))/.env.instance\ncd src/ui && npm run dev\n# Navigate to http://localhost:3000/explore/query\n\
  # 1. Type a Cypher query — autocomplete suggests node labels from schema\n# 2. Press\
  \ Ctrl+Enter — results table appears with row count and execution time\n# 3. Expand\
  \ history panel — previous query is listed; click to re-run\n# 4. Select a KG from\
  \ the selector — results are filtered to that KG\n```\n\nUnit tests:\n```bash\n\
  cd src/ui && npm run test:unit -- query\n# useQueryHistory: adds, retrieves, and\
  \ caps at 50 entries\n# QueryResultsTable: renders rows correctly, handles empty\
  \ result\n```\n\n## Caveats\n\n- Apache AGE requires queries to return a single\
  \ column (map syntax for multiple\n  values). A contextual hint about this requirement\
  \ should appear near the editor.\n- If `@codemirror/lang-cypher` is not available\
  \ as a maintained package, use\n  CodeMirror's SQL mode with Cypher keyword overrides\
  \ as a fallback.\n- If no REST endpoint exists for direct UI query execution (separate\
  \ from the MCP\n  tool), a lightweight `POST /graph/query` endpoint must be added\
  \ to the graph\n  presentation layer as part of this task. That endpoint must enforce\
  \ the same\n  read-only and timeout constraints as the MCP tool."
---
