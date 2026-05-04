---
id: task-142
title: "UI Schema Browser — type listing, detail panel, cross-navigation"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-140]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add schema browser for graph ontology navigation"
pr_description: |
  ## What and Why

  The Schema Browser lets users discover what node types and edge types exist in
  their graph before writing queries. It is the "read the map before navigating"
  companion to the Query Console and Graph Explorer. Users can browse, search, and
  filter types, expand any type to see its full definition (description, required
  and optional properties), and jump directly to related tools.

  This corresponds to `Explore → Schema Browser` in the sidebar.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Schema Browser — Scenario: Type listing**
    "node types and edge types listed with search and filtering"

  - **Requirement: Schema Browser — Scenario: Type detail**
    "description, required properties, and optional properties shown on expand"

  - **Requirement: Schema Browser — Scenario: Cross-navigation**
    "navigate to Query Console (pre-filled query), Graph Explorer (filtered by type),
    or ontology editor for that type"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    Types fetched from `GET /graph/schema/ontology`, which returns all type definitions.

  - **Requirement: Interaction Principles — Scenario: Progressive disclosure**
    Type cards collapsed by default; detail revealed on expand/click.

  ## Key Design Decisions

  - **Data source**: `GET /graph/schema/ontology` returns `list[TypeDefinition]`
    with `label`, `entity_type` (node/edge), `description`, `required_properties`,
    and `optional_properties`. All filtering/search is client-side on this payload.
  - **Layout**: Two tabs — "Nodes" and "Edges" — with a search input above. Each
    type renders as a collapsible card (`Accordion` from shadcn/vue).
  - **Type detail**: Inside the accordion item: description, two columns of badge
    lists (required props in amber, optional in gray).
  - **Cross-navigation**:
    - "Query" button: navigates to `/explore/query?prefill=MATCH (n:{label}) RETURN n`
    - "Explore" button: navigates to `/explore/graph?type={label}`
    - "Edit Ontology" button: navigates to the ontology editor for this KG/type
      (available when user has `edit` permission on the KG).

  ## What Files Are Affected

  - **New**: `src/ui/pages/explore/schema.vue`
  - **New**: `src/ui/components/schema/TypeCard.vue`
  - **New**: `src/ui/components/schema/PropertyBadgeList.vue`
  - **New**: `src/ui/composables/useSchema.ts` (fetches and caches ontology)
  - **New**: `src/ui/tests/unit/TypeCard.test.ts`
  - **New**: `src/ui/tests/unit/useSchema.test.ts`

  ## How to Verify

  ```bash
  cd src/ui && npm run dev
  # Navigate to /explore/schema
  # 1. Node types and edge types appear in two tabs
  # 2. Search input filters the list live
  # 3. Expand a type card — description, required props (amber badges),
  #    optional props (gray badges) are shown
  # 4. Click "Query" — lands on Query Console with MATCH query pre-filled
  # 5. Click "Explore" — lands on Graph Explorer filtered by that type
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- schema
  # TypeCard: renders label, description, badges; collapsed by default
  # useSchema: fetches ontology, caches result, filters by entity_type
  ```

  ## Caveats

  - If no ontology has been saved yet, `GET /graph/schema/ontology` returns 404.
    The Schema Browser must show an empty state ("No type definitions yet — define
    your ontology to see types here") rather than an error.
  - The "Edit Ontology" cross-navigation target (ontology editor) will be wired up
    properly once task-149 (Ontology Design Flow) is complete. Until then, render
    the button as disabled with a tooltip.
---
