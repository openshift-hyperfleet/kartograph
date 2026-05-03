---
id: task-104
title: Schema browser cross-navigation to query console, graph explorer, and ontology
  editor
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps: []
round: 6
branch: hyperloop/task-104
pr: https://github.com/openshift-hyperfleet/kartograph/pull/569
pr_title: 'feat(ui): add cross-navigation from schema browser to query console and
  graph explorer'
pr_description: "## What & Why\n\nThe **Schema Browser** requirement in `specs/ui/experience.spec.md`\
  \ specifies a\ncross-navigation scenario that connects the schema browser to other\
  \ tools:\n\n> \"GIVEN a type in the schema browser THEN the user can navigate directly\
  \ to the\n> query console (pre-filled query), graph explorer (filtered by type),\
  \ or ontology\n> editor for that type\"\n\nThe current `/graph/schema` page lists\
  \ types and shows their properties when\nexpanded, but provides no links to the\
  \ query console or graph explorer. Users\nmust manually write the Cypher query or\
  \ navigate to the explorer with no context.\nThis creates friction for the primary\
  \ discovery workflow.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n\
  - **Requirement: Schema Browser** — Scenario: *Cross-navigation*\n\n## What This\
  \ Change Does\n\n### Per-Type Action Buttons\n\nIn the schema browser type detail\
  \ panel (expanded state), add three inline action\nbuttons for each type:\n\n1.\
  \ **\"Query this type\"** (icon: terminal/code)\n   - Navigates to `/query?cypher=MATCH+(n%3A{TypeLabel})+RETURN+n+LIMIT+25`\n\
  \   - The query console reads the `cypher` query parameter and pre-fills the editor\n\
  \   - Triggers immediate execution if the parameter is present\n\n2. **\"Explore\
  \ in Graph\"** (icon: network/nodes)\n   - Navigates to `/graph/explorer?type={TypeLabel}`\n\
  \   - The graph explorer reads the `type` parameter and pre-populates the search\n\
  \     with that type filter, running the search automatically\n\n3. **\"Edit Ontology\"\
  ** (icon: pencil/settings)\n   - Navigates to the ontology editor for that type\
  \ (future feature)\n   - Until the ontology editor is implemented, this button is\
  \ shown but disabled\n     with a tooltip: \"Coming soon — ontology editing is not\
  \ yet available\"\n   - This ensures the UI slot exists and is discoverable without\
  \ depending on\n     blocked Extraction context work\n\n### Query Console — cypher\
  \ URL Parameter\n\nUpdate `/pages/query/index.vue` to:\n- On mount, read `route.query.cypher`\
  \ and pre-fill the Cypher editor with the\n  decoded value\n- Auto-execute the query\
  \ if the parameter is present (or show a \"Run this query\"\n  button as an alternative\
  \ to avoid surprising the user)\n\n### Graph Explorer — type URL Parameter\n\nUpdate\
  \ `/pages/graph/explorer.vue` to:\n- On mount, read `route.query.type` and pre-populate\
  \ the type filter input\n- Auto-trigger the search with the type filter applied\n\
  \n## Files / Areas Affected\n\n- `src/dev-ui/app/pages/graph/schema.vue` — add cross-navigation\
  \ buttons per type\n- `src/dev-ui/app/components/query/SchemaPanel.vue` (or similar)\
  \ — add action\n  buttons to the type detail expansion\n- `src/dev-ui/app/pages/query/index.vue`\
  \ — handle `?cypher=` URL parameter\n- `src/dev-ui/app/pages/graph/explorer.vue`\
  \ — handle `?type=` URL parameter\n\n## Tests\n\nVitest / Vue Test Utils tests in\
  \ `src/dev-ui/app/tests/`:\n- `test_schema_type_shows_cross_navigation_buttons`:\
  \ mount schema browser with a\n  mocked type, expand type detail, assert \"Query\
  \ this type\" and \"Explore in Graph\"\n  buttons exist\n- `test_query_this_type_navigates_with_prefilled_cypher`:\
  \ click \"Query this type\"\n  for type \"Service\", assert router push to `/query`\
  \ with `cypher` param containing\n  `MATCH (n:Service) RETURN n LIMIT 25`\n- `test_explore_in_graph_navigates_with_type_filter`:\
  \ click \"Explore in Graph\",\n  assert router push to `/graph/explorer?type=Service`\n\
  - `test_query_console_prefills_from_url_param`: mount `/query` with\n  `?cypher=MATCH+(n%3AService)+RETURN+n`,\
  \ assert editor content equals the decoded\n  Cypher string\n- `test_explorer_prefills_type_filter_from_url_param`:\
  \ mount `/graph/explorer`\n  with `?type=Service`, assert type filter input contains\
  \ \"Service\"\n\n## How to Verify\n\n1. Navigate to `/graph/schema`\n2. Expand any\
  \ node or edge type\n3. Confirm three action buttons appear: \"Query this type\"\
  , \"Explore in Graph\",\n   \"Edit Ontology\" (disabled)\n4. Click \"Query this\
  \ type\" — confirm the query console opens with a pre-filled\n   `MATCH (n:<Type>)\
  \ RETURN n LIMIT 25` query\n5. Click \"Explore in Graph\" — confirm the explorer\
  \ opens with the type filter\n   pre-populated and the search executed\n\n## Caveats\n\
  \n- The \"Edit Ontology\" button is intentionally disabled/greyed until the Extraction\n\
  \  context is implemented. Do not wire it up or leave a TODO comment — show the\n\
  \  disabled state with a tooltip so it is discoverable.\n- The `cypher` URL parameter\
  \ should be URL-encoded; test encoding/decoding for\n  special characters in type\
  \ names (spaces, hyphens).\n- Auto-executing the pre-filled query is desirable UX\
  \ but could surprise users if\n  the query returns many results. Consider showing\
  \ a \"Run ▶\" prompt instead of\n  auto-running, or auto-running with max_rows=25\
  \ to keep it safe."
---
