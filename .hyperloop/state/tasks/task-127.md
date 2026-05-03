---
id: task-127
title: UI Graph Explorer — Node Search and Neighbor Traversal
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add graph explorer with node search and neighbor traversal"
pr_description: |
  ## What and Why

  The Graph Explorer provides an interactive, card-based way to navigate the
  knowledge graph without writing Cypher. Users search for nodes by type or name,
  then expand their neighbors to traverse the graph visually. This is the third
  page in the "Explore" group and is intended for exploratory, non-technical users
  or quick graph navigation tasks.

  Only navigation (task-119) is a hard prerequisite. The explorer calls the same
  query execution backend as the Query Console but through a higher-level composable.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Graph Explorer** from
  `specs/ui/experience.spec.md`.

  Specifically:
  - **Node search**: search bar with type selector and free-text name/slug input;
    submits a Cypher query (`MATCH (n:<Type>) WHERE n.name CONTAINS $term RETURN n`)
    via the query API; results render as cards showing label, key properties, and ID.
  - **Neighbor exploration**: each node card has an "Expand Neighbors" button that
    fetches connected nodes and edges (`MATCH (n)-[r]-(m) WHERE id(n) = $id RETURN {rel: r, neighbor: m}`);
    neighbors appear as child cards with edge label and direction shown.
  - **Exploration trail**: breadcrumb or back-navigation so the user can drill into
    neighbors and then return to a prior level; the trail is maintained in component
    state.

  ## Design Decisions

  - Cards are rendered in a vertical list (not a force-directed graph visualization)
    to keep the implementation scope reasonable. A graph canvas (D3/Cytoscape) can
    be added as a follow-up.
  - Neighbor expansion is lazy (fetched on click) with a loading spinner per card.
  - The exploration trail is a stack of `{nodeId, nodeLabel, nodeName}` items;
    clicking a breadcrumb item pops back to that depth.
  - The type selector in the search bar is populated from the schema labels
    composable (shared with the Query Console and Schema Browser).
  - Node cards show at most 5 properties in the collapsed view; a "More" expander
    reveals the rest.

  ## Backend APIs Required

  - `POST /api/query/execute` — execute Cypher for node search and neighbor fetch
  - `GET /api/query/schema/labels` — populate the type selector

  ## Files / Areas Affected

  - `src/ui/pages/explore/GraphExplorerPage.vue`
  - `src/ui/components/explorer/NodeSearchBar.vue`
  - `src/ui/components/explorer/NodeCard.vue`
  - `src/ui/components/explorer/NeighborList.vue`
  - `src/ui/components/explorer/ExplorationTrail.vue`
  - `src/ui/composables/useGraphExplorer.ts`

  ## How to Verify

  1. Explore → Graph Explorer: search bar and type selector render
  2. Search by type + name term: matching node cards appear with key properties
  3. Clicking "Expand Neighbors" on a card: neighbor cards appear with edge label
     and direction (→ or ←)
  4. Drilling into a neighbor updates the exploration trail breadcrumb
  5. Clicking a breadcrumb level pops back to that depth and removes deeper levels
  6. Node card with > 5 properties: first 5 shown; "More" reveals rest

  ## Caveats

  The Graph Explorer does not implement a visual graph canvas in this task —
  that is a separate enhancement. The card-based exploration covers all spec scenarios
  without a rendering library dependency.
---
