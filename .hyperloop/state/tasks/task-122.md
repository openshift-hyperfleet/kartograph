---
id: task-122
title: "UI: Schema Browser"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add schema browser with type listing, detail expansion, and cross-navigation"
pr_description: |
  ## What & Why

  Implements the Schema Browser — the "Explore" tool for understanding the graph
  ontology. Users can see all node and edge types defined in the graph, drill into
  a specific type to see its properties, and navigate directly from a type to related
  tools (Query Console with a pre-filled query, Graph Explorer filtered by type,
  or the ontology editor).

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Schema Browser** — all three scenarios: type listing (node + edge
    types with search/filter), type detail (description, required/optional properties),
    cross-navigation (to Query Console, Graph Explorer, ontology editor)

  ## Type Listing

  - Fetches type definitions from `GET /graph/schema` (or equivalent endpoint that
    returns `TypeDefinition` objects with `label`, `entity_type`, `description`,
    `required_properties`, `optional_properties`)
  - Renders two tabs: **Node Types** and **Edge Types**
  - Search input filters types by label in real-time (client-side)
  - Each type displayed as a compact row: label badge, entity type chip, description
    excerpt, property count

  ## Type Detail (expanded)

  - Clicking a type row expands an inline detail panel (progressive disclosure pattern)
  - Shows: full description, required properties list (marked with asterisk),
    optional properties list
  - Type detail collapses when clicking the same row again or clicking elsewhere

  ## Cross-Navigation

  From any expanded type detail panel, three action links:
  1. **Query Console** — navigates to `/explore/query` with the editor pre-populated
     with `MATCH (n:TypeLabel) RETURN n LIMIT 25` (node) or equivalent for edges;
     implemented via a URL query param: `/explore/query?cypher=MATCH…`
  2. **Graph Explorer** — navigates to `/explore/graph-explorer?type=TypeLabel`
     which pre-applies a type filter on the explorer (task-123)
  3. **Edit in Ontology** — navigates to `/settings/ontology/TypeLabel` (ontology
     editor from task-128); only shown when the user has manage permission on the KG

  ## Backend API Integration

  | Action | Endpoint |
  |---|---|
  | List all type definitions | `GET /graph/schema` |
  | List node type labels | `GET /graph/schema/labels?type=node` |
  | List edge type labels | `GET /graph/schema/labels?type=edge` |

  These endpoints are already implemented in the Graph context
  (`src/api/graph/presentation/routes.py`).

  ## Files / Areas Affected

  - `src/ui/src/pages/explore/SchemaBrowser.vue`
  - `src/ui/src/components/schema/TypeList.vue`
  - `src/ui/src/components/schema/TypeDetail.vue`
  - `src/ui/src/api/graph.ts` — typed API client for Graph context endpoints

  ## How to Verify

  1. Navigate to Schema Browser; node and edge type tabs appear; types listed
  2. Type "Person" in search → list filters to matching types only
  3. Click a type row → detail panel expands with description and property lists;
     required properties visually distinct from optional
  4. Click "Query Console" cross-nav link → opens Query Console with pre-filled query
  5. Click "Graph Explorer" cross-nav link → opens Graph Explorer with type filter set

  ## Caveats / Follow-up

  - "Edit in Ontology" link is stubbed (links to ontology editor page) until task-128
    implements the full ontology editor
  - If `GET /graph/schema` does not return descriptions and property metadata (only
    labels), the detail panel shows only the label; full metadata requires the complete
    TypeDefinition endpoint to be confirmed available
---
