---
id: task-123
title: 'UI: Graph Explorer'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps:
- task-118
- task-119
round: 0
branch: hyperloop/task-123
pr: https://github.com/openshift-hyperfleet/kartograph/pull/595
pr_title: 'feat(ui): add interactive graph explorer with node search and neighbor
  traversal'
pr_description: "## What & Why\n\nImplements the Graph Explorer — an interactive node\
  \ browser that allows users to\nsearch for nodes by type or name and progressively\
  \ explore their neighbors, building\nan exploration trail without writing Cypher.\n\
  \n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n- **Requirement:\
  \ Graph Explorer** — both scenarios: node search (by type, name, slug)\n  returning\
  \ card view, neighbor exploration (connected nodes/edges with labels and\n  direction,\
  \ drill-into-neighbor trail)\n\n## Node Search\n\n- Search bar at the top of the\
  \ page with two optional filter inputs: **Type** (from\n  schema labels) and **Name\
  \ / Slug** (free text)\n- Submitting the search executes a Cypher query via the\
  \ query execution endpoint:\n  ```cypher\n  MATCH (n:TypeLabel) WHERE n.name CONTAINS\
  \ $term RETURN n LIMIT 50\n  ```\n  (omitting `TypeLabel` when no type is selected)\n\
  - Results rendered as cards: node label badge, key properties (name, slug, id),\n\
  \  a \"Explore neighbors\" expansion toggle\n\n## Neighbor Exploration\n\n- Clicking\
  \ \"Explore neighbors\" on a node card expands an inline sub-panel showing:\n  -\
  \ Outgoing edges: `→ [EDGE_LABEL] → TargetNode`\n  - Incoming edges: `← [EDGE_LABEL]\
  \ ← SourceNode`\n  - Each neighbor shown as a compact card with its label and key\
  \ properties\n- Clicking a neighbor card makes it the new focal node: its neighbors\
  \ can in turn\n  be expanded (drill-in)\n- A **breadcrumb trail** above the explorer\
  \ tracks the drill-in path; clicking any\n  crumb returns to that level\n\n## Type\
  \ Pre-filter (Cross-navigation from Schema Browser)\n\n- When the page is reached\
  \ via `/explore/graph-explorer?type=Person`, the Type filter\n  is pre-populated\
  \ and a search is triggered automatically\n\n## Backend API Integration\n\nNode\
  \ search and neighbor traversal both use the same query execution endpoint\n(`POST\
  \ /query/execute`) — the UI constructs appropriate Cypher queries internally.\n\
  No additional endpoints required beyond what task-121 introduces.\n\n## Files /\
  \ Areas Affected\n\n- `src/ui/src/pages/explore/GraphExplorer.vue`\n- `src/ui/src/components/explorer/NodeSearchBar.vue`\n\
  - `src/ui/src/components/explorer/NodeCard.vue`\n- `src/ui/src/components/explorer/NeighborPanel.vue`\n\
  - `src/ui/src/components/explorer/ExplorationTrail.vue`\n\n## How to Verify\n\n\
  1. Open Graph Explorer; type \"Alice\" in the name field → cards appear with matching\n\
  \   nodes\n2. Click \"Explore neighbors\" on a node → inline sub-panel shows outgoing\
  \ and incoming\n   edges with labeled target nodes\n3. Click a neighbor node → it\
  \ becomes the focal node; breadcrumb trail shows the\n   drill path\n4. Click a\
  \ breadcrumb → returns to that level\n\n## Caveats / Follow-up\n\n- This PR uses\
  \ Cypher-based search (via the query endpoint); a future enhancement\n  could add\
  \ full-text search using Apache AGE full-text indexes for better performance\n-\
  \ No graph visualization (force-directed canvas) in this PR — cards-and-panels UI\
  \ is\n  sufficient for the spec; a canvas view is a potential future enhancement"
---
