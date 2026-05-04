---
id: task-143
title: "UI Graph Explorer — node search and neighbor traversal"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-140]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add interactive graph explorer with node search and neighbor traversal"
pr_description: |
  ## What and Why

  The Graph Explorer provides an interactive, point-and-click way to navigate the
  knowledge graph. Users can search for nodes by type, name, or slug and then
  progressively expand their neighborhood to discover relationships — without
  needing to write Cypher. It is the exploration-first alternative to the Query
  Console, and particularly valuable for users who are not yet familiar with the
  schema.

  This corresponds to `Explore → Graph Explorer` in the sidebar.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Graph Explorer — Scenario: Node search**
    "search by type, name, or slug; matching nodes displayed as cards with properties"

  - **Requirement: Graph Explorer — Scenario: Neighbor exploration**
    "expand neighbors; connected nodes and edges shown with labels and direction;
    drill into neighbors, building an exploration trail"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    Node search uses `GET /graph/nodes/by-slug?slug=...&label=...`
    Neighbor expansion uses `GET /graph/nodes/{node_id}/neighbors`

  - **Requirement: Interaction Principles — Scenario: Progressive disclosure**
    Node cards show summary (label, name); expand to reveal all properties.

  - **Requirement: Interaction Principles — Scenario: Keyboard shortcuts**
    `/` focuses the search input.

  ## Key Design Decisions

  - **Node search**: Calls `GET /graph/nodes/by-slug?slug={term}&label={type}`.
    The `label` filter is optional and populated from a type selector dropdown
    (labels from `GET /graph/schema/nodes`). Results rendered as `NodeCard` components.
  - **NodeCard**: Displays the node's label (badge), name/slug, and a collapsible
    properties panel. An "Expand neighbors" button triggers the neighbor fetch.
  - **Neighbor expansion**: Calls `GET /graph/nodes/{node_id}/neighbors`. Returns
    `nodes[]` and `edges[]`. Edges are displayed with their label and directional
    arrow (`→` / `←`). Each neighbor renders as a `NodeCard` with its own expand
    button, enabling drill-down traversal.
  - **Exploration trail**: A breadcrumb-style `ExplorationTrail` component tracks
    the path taken (starting node → neighbor → neighbor's neighbor). The user can
    click any crumb to jump back.
  - **Layout**: Vertical stack of expansion panels. No canvas/graph layout (that
    complexity is deferred).

  ## What Files Are Affected

  - **New**: `src/ui/pages/explore/graph.vue`
  - **New**: `src/ui/components/graph/NodeCard.vue`
  - **New**: `src/ui/components/graph/NeighborList.vue`
  - **New**: `src/ui/components/graph/EdgeBadge.vue`
  - **New**: `src/ui/components/graph/ExplorationTrail.vue`
  - **New**: `src/ui/composables/useGraphExplorer.ts`
  - **New**: `src/ui/tests/unit/NodeCard.test.ts`
  - **New**: `src/ui/tests/unit/useGraphExplorer.test.ts`

  ## How to Verify

  ```bash
  cd src/ui && npm run dev
  # Navigate to /explore/graph
  # 1. Type a node name in search — matching nodes appear as cards
  # 2. Filter by type — only nodes of that label show
  # 3. Click "Expand neighbors" on a node — connected nodes and edges appear
  #    with edge labels and direction arrows
  # 4. Click a neighbor's "Expand neighbors" — another level renders
  # 5. Exploration trail updates with each drill-in; clicking a crumb collapses
  #    the trail back to that point
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- graph
  # NodeCard: renders label badge, name, collapsed properties; expand works
  # useGraphExplorer: search fetches nodes; expand fetches neighbors
  # ExplorationTrail: updates on drill-in; clicking crumb resets depth
  ```

  ## Caveats

  - `GET /graph/nodes/by-slug` searches by slug. If users want full-text search
    by name, this may need enhancement or a separate search endpoint. Use the
    available endpoint for now and document the limitation.
  - The `/explore/graph?type={label}` deep-link from the Schema Browser (task-142)
    should pre-populate the type filter and auto-submit the search.
  - No canvas or force-directed graph layout in this task — the list-based
    expansion pattern is sufficient for the spec and avoids heavy dependencies.
---
