---
id: task-123
title: "UI: Graph Explorer"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add interactive graph explorer with node search and neighbor traversal"
pr_description: |
  ## What & Why

  Implements the Graph Explorer — an interactive node browser that allows users to
  search for nodes by type or name and progressively explore their neighbors, building
  an exploration trail without writing Cypher.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Graph Explorer** — both scenarios: node search (by type, name, slug)
    returning card view, neighbor exploration (connected nodes/edges with labels and
    direction, drill-into-neighbor trail)

  ## Node Search

  - Search bar at the top of the page with two optional filter inputs: **Type** (from
    schema labels) and **Name / Slug** (free text)
  - Submitting the search executes a Cypher query via the query execution endpoint:
    ```cypher
    MATCH (n:TypeLabel) WHERE n.name CONTAINS $term RETURN n LIMIT 50
    ```
    (omitting `TypeLabel` when no type is selected)
  - Results rendered as cards: node label badge, key properties (name, slug, id),
    a "Explore neighbors" expansion toggle

  ## Neighbor Exploration

  - Clicking "Explore neighbors" on a node card expands an inline sub-panel showing:
    - Outgoing edges: `→ [EDGE_LABEL] → TargetNode`
    - Incoming edges: `← [EDGE_LABEL] ← SourceNode`
    - Each neighbor shown as a compact card with its label and key properties
  - Clicking a neighbor card makes it the new focal node: its neighbors can in turn
    be expanded (drill-in)
  - A **breadcrumb trail** above the explorer tracks the drill-in path; clicking any
    crumb returns to that level

  ## Type Pre-filter (Cross-navigation from Schema Browser)

  - When the page is reached via `/explore/graph-explorer?type=Person`, the Type filter
    is pre-populated and a search is triggered automatically

  ## Backend API Integration

  Node search and neighbor traversal both use the same query execution endpoint
  (`POST /query/execute`) — the UI constructs appropriate Cypher queries internally.
  No additional endpoints required beyond what task-121 introduces.

  ## Files / Areas Affected

  - `src/ui/src/pages/explore/GraphExplorer.vue`
  - `src/ui/src/components/explorer/NodeSearchBar.vue`
  - `src/ui/src/components/explorer/NodeCard.vue`
  - `src/ui/src/components/explorer/NeighborPanel.vue`
  - `src/ui/src/components/explorer/ExplorationTrail.vue`

  ## How to Verify

  1. Open Graph Explorer; type "Alice" in the name field → cards appear with matching
     nodes
  2. Click "Explore neighbors" on a node → inline sub-panel shows outgoing and incoming
     edges with labeled target nodes
  3. Click a neighbor node → it becomes the focal node; breadcrumb trail shows the
     drill path
  4. Click a breadcrumb → returns to that level

  ## Caveats / Follow-up

  - This PR uses Cypher-based search (via the query endpoint); a future enhancement
    could add full-text search using Apache AGE full-text indexes for better performance
  - No graph visualization (force-directed canvas) in this PR — cards-and-panels UI is
    sufficient for the spec; a canvas view is a potential future enhancement
---
