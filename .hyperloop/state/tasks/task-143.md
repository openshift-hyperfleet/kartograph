---
id: task-143
title: UI Graph Explorer — node search and neighbor traversal
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps:
- task-140
round: 0
branch: hyperloop/task-143
pr: https://github.com/openshift-hyperfleet/kartograph/pull/614
pr_title: 'feat(ui): add interactive graph explorer with node search and neighbor
  traversal'
pr_description: "## What and Why\n\nThe Graph Explorer provides an interactive, point-and-click\
  \ way to navigate the\nknowledge graph. Users can search for nodes by type, name,\
  \ or slug and then\nprogressively expand their neighborhood to discover relationships\
  \ — without\nneeding to write Cypher. It is the exploration-first alternative to\
  \ the Query\nConsole, and particularly valuable for users who are not yet familiar\
  \ with the\nschema.\n\nThis corresponds to `Explore → Graph Explorer` in the sidebar.\n\
  \n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Graph Explorer — Scenario: Node search**\n  \"search by type,\
  \ name, or slug; matching nodes displayed as cards with properties\"\n\n- **Requirement:\
  \ Graph Explorer — Scenario: Neighbor exploration**\n  \"expand neighbors; connected\
  \ nodes and edges shown with labels and direction;\n  drill into neighbors, building\
  \ an exploration trail\"\n\n- **Requirement: Backend API Alignment — Scenario: Resource\
  \ operations succeed end-to-end**\n  Node search uses `GET /graph/nodes/by-slug?slug=...&label=...`\n\
  \  Neighbor expansion uses `GET /graph/nodes/{node_id}/neighbors`\n\n- **Requirement:\
  \ Interaction Principles — Scenario: Progressive disclosure**\n  Node cards show\
  \ summary (label, name); expand to reveal all properties.\n\n- **Requirement: Interaction\
  \ Principles — Scenario: Keyboard shortcuts**\n  `/` focuses the search input.\n\
  \n## Key Design Decisions\n\n- **Node search**: Calls `GET /graph/nodes/by-slug?slug={term}&label={type}`.\n\
  \  The `label` filter is optional and populated from a type selector dropdown\n\
  \  (labels from `GET /graph/schema/nodes`). Results rendered as `NodeCard` components.\n\
  - **NodeCard**: Displays the node's label (badge), name/slug, and a collapsible\n\
  \  properties panel. An \"Expand neighbors\" button triggers the neighbor fetch.\n\
  - **Neighbor expansion**: Calls `GET /graph/nodes/{node_id}/neighbors`. Returns\n\
  \  `nodes[]` and `edges[]`. Edges are displayed with their label and directional\n\
  \  arrow (`→` / `←`). Each neighbor renders as a `NodeCard` with its own expand\n\
  \  button, enabling drill-down traversal.\n- **Exploration trail**: A breadcrumb-style\
  \ `ExplorationTrail` component tracks\n  the path taken (starting node → neighbor\
  \ → neighbor's neighbor). The user can\n  click any crumb to jump back.\n- **Layout**:\
  \ Vertical stack of expansion panels. No canvas/graph layout (that\n  complexity\
  \ is deferred).\n\n## What Files Are Affected\n\n- **New**: `src/ui/pages/explore/graph.vue`\n\
  - **New**: `src/ui/components/graph/NodeCard.vue`\n- **New**: `src/ui/components/graph/NeighborList.vue`\n\
  - **New**: `src/ui/components/graph/EdgeBadge.vue`\n- **New**: `src/ui/components/graph/ExplorationTrail.vue`\n\
  - **New**: `src/ui/composables/useGraphExplorer.ts`\n- **New**: `src/ui/tests/unit/NodeCard.test.ts`\n\
  - **New**: `src/ui/tests/unit/useGraphExplorer.test.ts`\n\n## How to Verify\n\n\
  ```bash\ncd src/ui && npm run dev\n# Navigate to /explore/graph\n# 1. Type a node\
  \ name in search — matching nodes appear as cards\n# 2. Filter by type — only nodes\
  \ of that label show\n# 3. Click \"Expand neighbors\" on a node — connected nodes\
  \ and edges appear\n#    with edge labels and direction arrows\n# 4. Click a neighbor's\
  \ \"Expand neighbors\" — another level renders\n# 5. Exploration trail updates with\
  \ each drill-in; clicking a crumb collapses\n#    the trail back to that point\n\
  ```\n\nUnit tests:\n```bash\ncd src/ui && npm run test:unit -- graph\n# NodeCard:\
  \ renders label badge, name, collapsed properties; expand works\n# useGraphExplorer:\
  \ search fetches nodes; expand fetches neighbors\n# ExplorationTrail: updates on\
  \ drill-in; clicking crumb resets depth\n```\n\n## Caveats\n\n- `GET /graph/nodes/by-slug`\
  \ searches by slug. If users want full-text search\n  by name, this may need enhancement\
  \ or a separate search endpoint. Use the\n  available endpoint for now and document\
  \ the limitation.\n- The `/explore/graph?type={label}` deep-link from the Schema\
  \ Browser (task-142)\n  should pre-populate the type filter and auto-submit the\
  \ search.\n- No canvas or force-directed graph layout in this task — the list-based\n\
  \  expansion pattern is sufficient for the spec and avoids heavy dependencies."
---
