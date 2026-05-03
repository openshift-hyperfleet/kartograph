---
id: task-104
title: "Schema browser cross-navigation to query console, graph explorer, and ontology editor"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): add cross-navigation from schema browser to query console and graph explorer"
pr_description: |
  ## What & Why

  The **Schema Browser** requirement in `specs/ui/experience.spec.md` specifies a
  cross-navigation scenario that connects the schema browser to other tools:

  > "GIVEN a type in the schema browser THEN the user can navigate directly to the
  > query console (pre-filled query), graph explorer (filtered by type), or ontology
  > editor for that type"

  The current `/graph/schema` page lists types and shows their properties when
  expanded, but provides no links to the query console or graph explorer. Users
  must manually write the Cypher query or navigate to the explorer with no context.
  This creates friction for the primary discovery workflow.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Schema Browser** — Scenario: *Cross-navigation*

  ## What This Change Does

  ### Per-Type Action Buttons

  In the schema browser type detail panel (expanded state), add three inline action
  buttons for each type:

  1. **"Query this type"** (icon: terminal/code)
     - Navigates to `/query?cypher=MATCH+(n%3A{TypeLabel})+RETURN+n+LIMIT+25`
     - The query console reads the `cypher` query parameter and pre-fills the editor
     - Triggers immediate execution if the parameter is present

  2. **"Explore in Graph"** (icon: network/nodes)
     - Navigates to `/graph/explorer?type={TypeLabel}`
     - The graph explorer reads the `type` parameter and pre-populates the search
       with that type filter, running the search automatically

  3. **"Edit Ontology"** (icon: pencil/settings)
     - Navigates to the ontology editor for that type (future feature)
     - Until the ontology editor is implemented, this button is shown but disabled
       with a tooltip: "Coming soon — ontology editing is not yet available"
     - This ensures the UI slot exists and is discoverable without depending on
       blocked Extraction context work

  ### Query Console — cypher URL Parameter

  Update `/pages/query/index.vue` to:
  - On mount, read `route.query.cypher` and pre-fill the Cypher editor with the
    decoded value
  - Auto-execute the query if the parameter is present (or show a "Run this query"
    button as an alternative to avoid surprising the user)

  ### Graph Explorer — type URL Parameter

  Update `/pages/graph/explorer.vue` to:
  - On mount, read `route.query.type` and pre-populate the type filter input
  - Auto-trigger the search with the type filter applied

  ## Files / Areas Affected

  - `src/dev-ui/app/pages/graph/schema.vue` — add cross-navigation buttons per type
  - `src/dev-ui/app/components/query/SchemaPanel.vue` (or similar) — add action
    buttons to the type detail expansion
  - `src/dev-ui/app/pages/query/index.vue` — handle `?cypher=` URL parameter
  - `src/dev-ui/app/pages/graph/explorer.vue` — handle `?type=` URL parameter

  ## Tests

  Vitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:
  - `test_schema_type_shows_cross_navigation_buttons`: mount schema browser with a
    mocked type, expand type detail, assert "Query this type" and "Explore in Graph"
    buttons exist
  - `test_query_this_type_navigates_with_prefilled_cypher`: click "Query this type"
    for type "Service", assert router push to `/query` with `cypher` param containing
    `MATCH (n:Service) RETURN n LIMIT 25`
  - `test_explore_in_graph_navigates_with_type_filter`: click "Explore in Graph",
    assert router push to `/graph/explorer?type=Service`
  - `test_query_console_prefills_from_url_param`: mount `/query` with
    `?cypher=MATCH+(n%3AService)+RETURN+n`, assert editor content equals the decoded
    Cypher string
  - `test_explorer_prefills_type_filter_from_url_param`: mount `/graph/explorer`
    with `?type=Service`, assert type filter input contains "Service"

  ## How to Verify

  1. Navigate to `/graph/schema`
  2. Expand any node or edge type
  3. Confirm three action buttons appear: "Query this type", "Explore in Graph",
     "Edit Ontology" (disabled)
  4. Click "Query this type" — confirm the query console opens with a pre-filled
     `MATCH (n:<Type>) RETURN n LIMIT 25` query
  5. Click "Explore in Graph" — confirm the explorer opens with the type filter
     pre-populated and the search executed

  ## Caveats

  - The "Edit Ontology" button is intentionally disabled/greyed until the Extraction
    context is implemented. Do not wire it up or leave a TODO comment — show the
    disabled state with a tooltip so it is discoverable.
  - The `cypher` URL parameter should be URL-encoded; test encoding/decoding for
    special characters in type names (spaces, hyphens).
  - Auto-executing the pre-filled query is desirable UX but could surprise users if
    the query returns many results. Consider showing a "Run ▶" prompt instead of
    auto-running, or auto-running with max_rows=25 to keep it safe.
---
