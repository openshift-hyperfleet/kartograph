---
id: task-122
title: 'UI: Schema Browser'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps:
- task-118
- task-119
round: 0
branch: hyperloop/task-122
pr: https://github.com/openshift-hyperfleet/kartograph/pull/594
pr_title: 'feat(ui): add schema browser with type listing, detail expansion, and cross-navigation'
pr_description: "## What & Why\n\nImplements the Schema Browser — the \"Explore\"\
  \ tool for understanding the graph\nontology. Users can see all node and edge types\
  \ defined in the graph, drill into\na specific type to see its properties, and navigate\
  \ directly from a type to related\ntools (Query Console with a pre-filled query,\
  \ Graph Explorer filtered by type,\nor the ontology editor).\n\n## Spec Requirements\
  \ Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n- **Requirement: Schema Browser**\
  \ — all three scenarios: type listing (node + edge\n  types with search/filter),\
  \ type detail (description, required/optional properties),\n  cross-navigation (to\
  \ Query Console, Graph Explorer, ontology editor)\n\n## Type Listing\n\n- Fetches\
  \ type definitions from `GET /graph/schema` (or equivalent endpoint that\n  returns\
  \ `TypeDefinition` objects with `label`, `entity_type`, `description`,\n  `required_properties`,\
  \ `optional_properties`)\n- Renders two tabs: **Node Types** and **Edge Types**\n\
  - Search input filters types by label in real-time (client-side)\n- Each type displayed\
  \ as a compact row: label badge, entity type chip, description\n  excerpt, property\
  \ count\n\n## Type Detail (expanded)\n\n- Clicking a type row expands an inline\
  \ detail panel (progressive disclosure pattern)\n- Shows: full description, required\
  \ properties list (marked with asterisk),\n  optional properties list\n- Type detail\
  \ collapses when clicking the same row again or clicking elsewhere\n\n## Cross-Navigation\n\
  \nFrom any expanded type detail panel, three action links:\n1. **Query Console**\
  \ — navigates to `/explore/query` with the editor pre-populated\n   with `MATCH\
  \ (n:TypeLabel) RETURN n LIMIT 25` (node) or equivalent for edges;\n   implemented\
  \ via a URL query param: `/explore/query?cypher=MATCH…`\n2. **Graph Explorer** —\
  \ navigates to `/explore/graph-explorer?type=TypeLabel`\n   which pre-applies a\
  \ type filter on the explorer (task-123)\n3. **Edit in Ontology** — navigates to\
  \ `/settings/ontology/TypeLabel` (ontology\n   editor from task-128); only shown\
  \ when the user has manage permission on the KG\n\n## Backend API Integration\n\n\
  | Action | Endpoint |\n|---|---|\n| List all type definitions | `GET /graph/schema`\
  \ |\n| List node type labels | `GET /graph/schema/labels?type=node` |\n| List edge\
  \ type labels | `GET /graph/schema/labels?type=edge` |\n\nThese endpoints are already\
  \ implemented in the Graph context\n(`src/api/graph/presentation/routes.py`).\n\n\
  ## Files / Areas Affected\n\n- `src/ui/src/pages/explore/SchemaBrowser.vue`\n- `src/ui/src/components/schema/TypeList.vue`\n\
  - `src/ui/src/components/schema/TypeDetail.vue`\n- `src/ui/src/api/graph.ts` — typed\
  \ API client for Graph context endpoints\n\n## How to Verify\n\n1. Navigate to Schema\
  \ Browser; node and edge type tabs appear; types listed\n2. Type \"Person\" in search\
  \ → list filters to matching types only\n3. Click a type row → detail panel expands\
  \ with description and property lists;\n   required properties visually distinct\
  \ from optional\n4. Click \"Query Console\" cross-nav link → opens Query Console\
  \ with pre-filled query\n5. Click \"Graph Explorer\" cross-nav link → opens Graph\
  \ Explorer with type filter set\n\n## Caveats / Follow-up\n\n- \"Edit in Ontology\"\
  \ link is stubbed (links to ontology editor page) until task-128\n  implements the\
  \ full ontology editor\n- If `GET /graph/schema` does not return descriptions and\
  \ property metadata (only\n  labels), the detail panel shows only the label; full\
  \ metadata requires the complete\n  TypeDefinition endpoint to be confirmed available"
---
