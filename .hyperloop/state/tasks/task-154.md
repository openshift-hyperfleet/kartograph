---
id: task-154
title: 'UI: Explore — Query Console, Schema Browser & Graph Explorer'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-151
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add explore section — query console, schema browser, graph explorer'
pr_description: "## What and Why\n\nThis task implements the **Explore** section of\
  \ Kartograph: the Cypher query\neditor, the schema browser, and the interactive\
  \ graph explorer. These three\ntools are the primary surfaces that developers use\
  \ to understand and query\ntheir knowledge graphs. They all read from the existing\
  \ Query and Graph REST\nAPIs (no Ingestion or Extraction dependency).\n\n## Spec\
  \ Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\n\
  \n### Requirement: Query Console\n- **Editor**: Monaco Editor (or CodeMirror 6)\
  \ configured for Cypher syntax\n  — keyword highlighting, bracket matching, autocomplete\
  \ from the current\n  schema labels (calls `GET /query/schema/labels` to seed completions),\n\
  \  and linting (rejects mutation keywords client-side before submission)\n- **Execution**:\
  \ Run button and Ctrl/Cmd+Enter keyboard shortcut call\n  `POST /query/execute`\
  \ (or the query REST endpoint); results rendered as\n  a table with column headers,\
  \ execution time, and row count displayed\n  below the editor\n- **KG scope selector**:\
  \ dropdown above the editor listing accessible\n  knowledge graphs from `GET /query/knowledge-graphs`;\
  \ defaults to \"all\";\n  when a specific KG is selected, its `id` is sent with\
  \ the query request\n- **Query history**: a collapsible panel lists previously-executed\
  \ queries\n  (stored in `localStorage`); clicking an entry re-inserts the query\
  \ into\n  the editor; clicking a \"run\" icon re-executes it immediately\n\n###\
  \ Requirement: Schema Browser\n- **Type listing** (`/explore/schema`): lists all\
  \ node types and edge types\n  returned by `GET /query/schema`; includes a search/filter\
  \ input that\n  filters the list client-side; tabs or sections separate node types\
  \ from\n  edge types\n- **Type detail**: clicking a type expands (accordion or sheet)\
  \ to show\n  description, list of required properties, and list of optional properties\n\
  - **Cross-navigation links**: each expanded type shows three quick-action\n  buttons:\n\
  \  1. \"Query\" — opens Query Console with a pre-filled `MATCH` query for\n    \
  \ that type\n  2. \"Explore\" — opens Graph Explorer filtered to that type\n  3.\
  \ \"Edit Ontology\" — navigates to the ontology editor (task-156)\n\n### Requirement:\
  \ Graph Explorer\n- **Node search** (`/explore/graph`): search bar (type-ahead)\
  \ accepts a\n  node type, name, or slug; calls `POST /query/execute` with a fuzzy\n\
  \  `MATCH` query; results rendered as a card grid with the node's label,\n  name,\
  \ and key properties\n- **Neighbor expansion**: each node card has an \"Explore\
  \ neighbors\" button;\n  clicking it runs a `MATCH (n)-[r]-(m)` query and renders\
  \ the connected\n  nodes and edges in an expandable list below the card; \"drill\
  \ in\" replaces\n  the current root node, building a breadcrumb trail of the exploration\
  \ path\n- Edge labels and direction (→ / ←) are shown alongside each neighbor\n\n\
  ### Requirement: Backend API Alignment\n- Query Console results table handles `truncated:\
  \ true` by showing a\n  \"results may be incomplete — add a LIMIT clause\" banner\n\
  - Forbidden and timeout error responses (`error_type`) are displayed as\n  user-facing\
  \ messages (\"Write operations are not allowed\", \"Query timed\n  out — try a more\
  \ specific query or add a LIMIT\")\n- Schema labels are fetched once per session\
  \ and cached in the Pinia store\n\n### Requirement: Interaction Principles\n- Ctrl/Cmd+Enter\
  \ in the editor fires query execution (already registered\n  globally in task-151;\
  \ the Query Console page hooks into it when focused)\n- `/` shortcut focuses the\
  \ Graph Explorer search bar\n- Query results table supports copy-to-clipboard on\
  \ cell values\n\n## Key Design Decisions\n\n- **Editor**: Monaco Editor is preferred\
  \ for Cypher support; CodeMirror 6\n  with `@codemirror/lang-cypher` is the lightweight\
  \ fallback if Monaco's\n  bundle size is prohibitive.\n- **Query history**: stored\
  \ in `localStorage` as a JSON array capped at 50\n  entries (FIFO eviction). Not\
  \ synced to the server.\n- **Graph Explorer** renders as cards (not a force-directed\
  \ graph\n  visualisation) to keep the initial implementation simple and testable.\n\
  \  A canvas-based graph visualisation is a future enhancement.\n- Schema Browser\
  \ and Graph Explorer share the same `useSchema` composable\n  that fetches and caches\
  \ type definitions.\n\n## Files / Areas Affected\n\n- `src/ui/src/pages/explore/QueryConsolePage.vue`\n\
  - `src/ui/src/pages/explore/SchemaBrowserPage.vue`\n- `src/ui/src/pages/explore/GraphExplorerPage.vue`\n\
  - `src/ui/src/components/CypherEditor.vue` (Monaco/CodeMirror wrapper)\n- `src/ui/src/components/QueryResultsTable.vue`\n\
  - `src/ui/src/components/QueryHistoryPanel.vue`\n- `src/ui/src/components/SchemaTypeCard.vue`\n\
  - `src/ui/src/components/NodeCard.vue`\n- `src/ui/src/components/NeighborList.vue`\n\
  - `src/ui/src/composables/useSchema.ts`\n- `src/ui/src/composables/useQueryHistory.ts`\n\
  - `src/ui/src/stores/query.ts`\n- `src/ui/src/lib/api/query.ts` (typed wrappers\
  \ for Query API)\n\n## How to Verify\n\n```bash\nmake instance-up\nsource .instances/$(basename\
  \ $(pwd))/.env.instance\ncd src/ui && npm run dev\n```\n\n**Query Console:**\n1.\
  \ Navigate to Explore → Query Console\n2. Type `MATCH (n) RETURN n LIMIT 5` → Ctrl+Enter\
  \ executes\n3. Results table appears with rows, row count, and execution time\n\
  4. Type `CREATE (n:Test)` → error banner \"Write operations are not allowed\"\n\
  5. History panel shows the previous successful query; click it to re-insert\n6.\
  \ KG scope selector: select a specific KG → re-run same query; results\n   are scoped\
  \ to that KG\n\n**Schema Browser:**\n1. Navigate to Explore → Schema Browser\n2.\
  \ Node types and edge types listed; type in search box to filter\n3. Click a type\
  \ → description, required/optional properties appear\n4. Click \"Query\" → Query\
  \ Console opens with a pre-filled MATCH query\n5. Click \"Explore\" → Graph Explorer\
  \ opens filtered to that type\n\n**Graph Explorer:**\n1. Navigate to Explore → Graph\
  \ Explorer\n2. Search for a node by name → matching cards appear\n3. Click \"Explore\
  \ neighbors\" on a card → connected nodes listed with\n   edge labels and direction\n\
  4. Click \"Drill in\" on a neighbor → that node becomes the root; breadcrumb\n \
  \  shows the path taken\n\n## Caveats\n\n- Cypher autocomplete is seeded from the\
  \ schema label list; property-level\n  autocomplete (e.g., `n.name`) is a follow-up\
  \ enhancement.\n- The Graph Explorer renders neighbors as a list, not a canvas graph.\n\
  \  A force-directed visualisation is out of scope for this task.\n- Schema Browser's\
  \ \"Edit Ontology\" cross-nav link targets a page that is\n  built in task-156;\
  \ it renders as a disabled link until task-156 is merged."
---
