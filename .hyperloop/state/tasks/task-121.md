---
id: task-121
title: 'UI: Query Console'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps:
- task-118
- task-119
round: 0
branch: hyperloop/task-121
pr: https://github.com/openshift-hyperfleet/kartograph/pull/593
pr_title: 'feat(ui): add Cypher query console with editor, results table, and history'
pr_description: "## What & Why\n\nImplements the Query Console — the primary \"Explore\"\
  \ tool for developers querying\nthe knowledge graph. Provides a Cypher editor with\
  \ schema-aware assistance, one-click\n/ keyboard execution, a results table, and\
  \ a history panel for re-use of past queries.\n\n## Spec Requirements Satisfied\n\
  \nFrom `specs/ui/experience.spec.md`:\n- **Requirement: Query Console** — all four\
  \ scenarios: query editing (highlighting,\n  autocomplete, linting), query execution\
  \ (button + Ctrl/Cmd+Enter), query history\n  (browse, re-execute, insert), knowledge\
  \ graph context selector\n\n## Editor\n\n- **Engine:** CodeMirror 6 (or Monaco)\
  \ configured for Cypher syntax\n- **Syntax highlighting:** Cypher keyword, label,\
  \ property tokens\n- **Autocomplete:** populated from the active KG's schema labels\n\
  \  (`GET /graph/schema/labels`); falls back to keyword-only completion when no schema\n\
  \  is loaded\n- **Linting:** basic structural checks (unclosed parentheses, missing\
  \ RETURN, etc.)\n- **Keyboard shortcut:** `Ctrl/Cmd+Enter` submits the query without\
  \ leaving the editor\n  (tooltip in the editor gutter/footer to make it discoverable)\n\
  \n## Execution & Results\n\n- **Execute button** → `POST /query/execute` (see note\
  \ below) with `{ cypher, knowledge_graph_id? }`\n- Results rendered as a responsive\
  \ data table: columns auto-detected from the first\n  row's keys; node/edge values\
  \ expanded inline\n- Status bar below editor: row count, execution time in ms, truncation\
  \ warning if\n  results were limited\n- Loading state: spinner overlay on the results\
  \ panel; editor remains interactive\n\n## Knowledge Graph Scope Selector\n\n- Dropdown\
  \ in the toolbar above the editor; populated from accessible KGs\n  (`GET /management/knowledge-graphs`\
  \ filtered by user access)\n- \"All knowledge graphs\" is the default (no `knowledge_graph_id`\
  \ sent)\n- Selecting a specific KG passes its ID in the execute request\n\n## Query\
  \ History\n\n- Last 50 queries stored in `localStorage` (per-tenant key)\n- History\
  \ panel: slide-in sidebar or inline collapsible; shows query text (truncated),\n\
  \  timestamp, row count\n- Each history item: \"Re-run\" button (replaces editor\
  \ content and executes),\n  \"Insert\" button (replaces editor content without executing)\n\
  \n## Backend API Integration\n\n| Action | Endpoint |\n|---|---|\n| Execute Cypher\
  \ | `POST /query/execute` |\n| Fetch schema labels | `GET /graph/schema/labels`\
  \ |\n| List accessible KGs | `GET /management/knowledge-graphs` |\n\n> **Note on\
  \ query execution endpoint:** The existing backend exposes Cypher execution\n> exclusively\
  \ via the MCP server (`POST /mcp` using JSON-RPC `query_graph` tool call).\n> This\
  \ task requires a new REST endpoint `POST /query/execute` (or equivalent) in the\n\
  > Query context presentation layer (`src/api/query/presentation/`) to be available\
  \ for\n> browser consumption with Bearer-token auth. If that endpoint does not yet\
  \ exist when\n> this task runs, a minimal stub returning a hardcoded empty result\
  \ is acceptable while\n> the backend endpoint is added as a follow-up task targeting\
  \ the query-execution spec.\n\n## Files / Areas Affected\n\n- `src/ui/src/pages/explore/QueryConsole.vue`\n\
  - `src/ui/src/components/query/CypherEditor.vue` — CodeMirror wrapper\n- `src/ui/src/components/query/ResultsTable.vue`\n\
  - `src/ui/src/components/query/QueryHistory.vue`\n- `src/ui/src/components/query/KgScopeSelector.vue`\n\
  - `src/ui/src/api/query.ts` — typed API client for query execution\n\n## How to\
  \ Verify\n\n1. Open Query Console; type `MATCH (n) RETURN n LIMIT 5`; press Ctrl+Enter\
  \ →\n   results table appears with row count and execution time\n2. Run the same\
  \ query again; open history panel → previous query visible; \"Insert\"\n   populates\
  \ editor\n3. Select a specific KG from the scope selector → subsequent queries are\
  \ scoped\n4. Type an invalid Cypher fragment → linting warning shown in editor gutter\n\
  \n## Caveats / Follow-up\n\n- Full Cypher-aware autocomplete (property names, node\
  \ types) requires a schema\n  endpoint returning full type definitions, not just\
  \ labels; this can be layered on\n  after the initial Schema Browser integration\
  \ (task-122) exposes the needed data\n- Query execution endpoint may need to be\
  \ added to the backend Query context if it\n  does not already exist"
---
