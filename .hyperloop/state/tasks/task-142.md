---
id: task-142
title: UI Schema Browser — type listing, detail panel, cross-navigation
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-140
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add schema browser for graph ontology navigation'
pr_description: "## What and Why\n\nThe Schema Browser lets users discover what node\
  \ types and edge types exist in\ntheir graph before writing queries. It is the \"\
  read the map before navigating\"\ncompanion to the Query Console and Graph Explorer.\
  \ Users can browse, search, and\nfilter types, expand any type to see its full definition\
  \ (description, required\nand optional properties), and jump directly to related\
  \ tools.\n\nThis corresponds to `Explore → Schema Browser` in the sidebar.\n\n##\
  \ Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Schema Browser — Scenario: Type listing**\n  \"node types and\
  \ edge types listed with search and filtering\"\n\n- **Requirement: Schema Browser\
  \ — Scenario: Type detail**\n  \"description, required properties, and optional\
  \ properties shown on expand\"\n\n- **Requirement: Schema Browser — Scenario: Cross-navigation**\n\
  \  \"navigate to Query Console (pre-filled query), Graph Explorer (filtered by type),\n\
  \  or ontology editor for that type\"\n\n- **Requirement: Backend API Alignment\
  \ — Scenario: Resource operations succeed end-to-end**\n  Types fetched from `GET\
  \ /graph/schema/ontology`, which returns all type definitions.\n\n- **Requirement:\
  \ Interaction Principles — Scenario: Progressive disclosure**\n  Type cards collapsed\
  \ by default; detail revealed on expand/click.\n\n## Key Design Decisions\n\n- **Data\
  \ source**: `GET /graph/schema/ontology` returns `list[TypeDefinition]`\n  with\
  \ `label`, `entity_type` (node/edge), `description`, `required_properties`,\n  and\
  \ `optional_properties`. All filtering/search is client-side on this payload.\n\
  - **Layout**: Two tabs — \"Nodes\" and \"Edges\" — with a search input above. Each\n\
  \  type renders as a collapsible card (`Accordion` from shadcn/vue).\n- **Type detail**:\
  \ Inside the accordion item: description, two columns of badge\n  lists (required\
  \ props in amber, optional in gray).\n- **Cross-navigation**:\n  - \"Query\" button:\
  \ navigates to `/explore/query?prefill=MATCH (n:{label}) RETURN n`\n  - \"Explore\"\
  \ button: navigates to `/explore/graph?type={label}`\n  - \"Edit Ontology\" button:\
  \ navigates to the ontology editor for this KG/type\n    (available when user has\
  \ `edit` permission on the KG).\n\n## What Files Are Affected\n\n- **New**: `src/ui/pages/explore/schema.vue`\n\
  - **New**: `src/ui/components/schema/TypeCard.vue`\n- **New**: `src/ui/components/schema/PropertyBadgeList.vue`\n\
  - **New**: `src/ui/composables/useSchema.ts` (fetches and caches ontology)\n- **New**:\
  \ `src/ui/tests/unit/TypeCard.test.ts`\n- **New**: `src/ui/tests/unit/useSchema.test.ts`\n\
  \n## How to Verify\n\n```bash\ncd src/ui && npm run dev\n# Navigate to /explore/schema\n\
  # 1. Node types and edge types appear in two tabs\n# 2. Search input filters the\
  \ list live\n# 3. Expand a type card — description, required props (amber badges),\n\
  #    optional props (gray badges) are shown\n# 4. Click \"Query\" — lands on Query\
  \ Console with MATCH query pre-filled\n# 5. Click \"Explore\" — lands on Graph Explorer\
  \ filtered by that type\n```\n\nUnit tests:\n```bash\ncd src/ui && npm run test:unit\
  \ -- schema\n# TypeCard: renders label, description, badges; collapsed by default\n\
  # useSchema: fetches ontology, caches result, filters by entity_type\n```\n\n##\
  \ Caveats\n\n- If no ontology has been saved yet, `GET /graph/schema/ontology` returns\
  \ 404.\n  The Schema Browser must show an empty state (\"No type definitions yet\
  \ — define\n  your ontology to see types here\") rather than an error.\n- The \"\
  Edit Ontology\" cross-navigation target (ontology editor) will be wired up\n  properly\
  \ once task-149 (Ontology Design Flow) is complete. Until then, render\n  the button\
  \ as disabled with a tooltip."
---
