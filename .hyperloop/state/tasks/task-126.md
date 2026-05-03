---
id: task-126
title: UI Schema Browser — Ontology Explorer with Type Detail and Cross-Navigation
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add schema browser with type listing, detail, and cross-navigation"
pr_description: |
  ## What and Why

  The Schema Browser lets users discover the shape of their knowledge graph — what
  node and edge types exist, what properties they carry, and how to query them.
  It is the second page in the "Explore" group and is especially useful before
  writing queries. It also provides cross-navigation links into the Query Console
  and Graph Explorer.

  Only navigation (task-119) is required as a prerequisite; the browser can be
  built independently of the Query Console (task-125) and Graph Explorer (task-127),
  though the cross-navigation links will only be functional once those pages exist.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Schema Browser** from
  `specs/ui/experience.spec.md`.

  Specifically:
  - **Type listing**: all node types and edge types fetched from the schema API
    are rendered in a searchable, filterable list (search by label name; filter
    by entity type: node vs. edge).
  - **Type detail**: clicking/expanding a type shows its description, required
    properties (with type annotations if available), and optional properties.
    Progressive disclosure: summary visible in the list, full detail on expand.
  - **Cross-navigation**:
    - "Query" button → navigates to `/explore/query` with a pre-filled
      `MATCH (n:<Label>) RETURN n LIMIT 25` query.
    - "Explore" button → navigates to `/explore/graph` with the type pre-selected
      as the search filter.
    - "Edit Ontology" button → navigates to the ontology editor for this type
      (requires task-123 to be functional).

  ## Design Decisions

  - Type list uses an accordion (`<Accordion>`) component from the design system:
    collapsed row shows label + entity type badge; expanded row shows full detail.
  - Search is client-side (filter the fetched list) to avoid a round-trip per
    keystroke; the full label list is small enough to hold in memory.
  - Cross-navigation uses Vue Router's `query` params to pass the pre-filled query
    or type filter; the target pages read these params on mount.
  - Property display uses a two-column table: property name (monospace) | type/note.
    Required properties are marked with a * indicator.

  ## Backend APIs Required

  - `GET /api/query/schema/types` — list all type definitions with description,
    required properties, and optional properties

  ## Files / Areas Affected

  - `src/ui/pages/explore/SchemaBrowserPage.vue`
  - `src/ui/components/schema/TypeAccordionList.vue`
  - `src/ui/components/schema/TypeDetailPanel.vue`
  - `src/ui/components/schema/TypeCrossNavButtons.vue`
  - `src/ui/composables/useSchemaTypes.ts`

  ## How to Verify

  1. Explore → Schema Browser: list renders all node and edge types
  2. Search input filters list by label name in real time
  3. Filter (node/edge) reduces list correctly
  4. Expanding a type shows description, required properties, optional properties
  5. "Query" button opens Query Console with pre-filled MATCH query for that label
  6. "Explore" button opens Graph Explorer with the type pre-selected
  7. "Edit Ontology" button navigates to the ontology type editor

  ## Caveats

  Cross-navigation to the Graph Explorer (task-127) and Ontology Editor (task-123)
  will produce 404s until those tasks are complete. The Schema Browser itself is
  fully functional regardless.
---
