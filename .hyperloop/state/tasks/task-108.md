---
id: task-108
title: 'Query console: knowledge graph context selector to scope queries'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps: []
round: 0
branch: hyperloop/task-108
pr: https://github.com/openshift-hyperfleet/kartograph/pull/573
pr_title: 'feat(ui): add knowledge graph context selector to query console'
pr_description: "## What & Why\n\nThe **Query Console** requirement in `specs/ui/experience.spec.md`\
  \ includes a\nscoping scenario that controls which knowledge graph a query targets:\n\
  \n> \"GIVEN a query console THEN the user can optionally select a specific knowledge\n\
  > graph to scope queries AND when unscoped, queries span all knowledge graphs the\n\
  > user can access in the tenant\"\n\nThe backend MCP `query_graph` tool accepts\
  \ an optional `knowledge_graph_id`\nparameter for exactly this purpose. The current\
  \ `/pages/query/index.vue` executes\nqueries without passing a KG filter, meaning\
  \ all queries span the entire tenant\ngraph. For users with multiple knowledge graphs,\
  \ this can produce confusing results\nthat mix data from unrelated graphs.\n\nThe\
  \ KG selector also ties directly to the MCP `knowledge_graphs://accessible`\nresource\
  \ — the same list used to populate the selector in the mutations console\nshould\
  \ power the query console selector.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n\
  - **Requirement: Query Console** — Scenario: *Knowledge graph context*\n\n## What\
  \ This Change Does\n\n### KG Selector Component in Query Console\n\nAdd a `<KnowledgeGraphSelector>`\
  \ component (or reuse the one from the mutations\nconsole if it exists) to the query\
  \ console toolbar, positioned between the query\neditor controls and the Run button.\n\
  \nBehavior:\n- Populates from `GET /management/knowledge-graphs` (filtered to the\
  \ active\n  tenant/workspace, and only KGs the user has `view` permission on).\n\
  - Shows a placeholder: \"All knowledge graphs\" when nothing is selected.\n- When\
  \ a KG is selected, it is stored in a reactive variable and passed as\n  `knowledge_graph_id`\
  \ in the query execution request body.\n- Unselecting resets to the unscoped state\
  \ (all KGs).\n- The selection persists for the session (reactive state) but does\
  \ not persist\n  across page reloads.\n- The selected KG name is shown in the toolbar\
  \ so the user always knows the\n  current scope.\n\n### Query Execution Request\
  \ Update\n\nUpdate the composable or service call that executes queries\n(`src/dev-ui/app/composables/useQueryExecution.ts`\
  \ or similar) to include\n`knowledge_graph_id` in the request when a KG is selected:\n\
  \n```typescript\n// When KG is selected:\n{ cypher: query, knowledge_graph_id: selectedKgId,\
  \ max_rows: maxRows }\n\n// When unscoped:\n{ cypher: query, max_rows: maxRows }\n\
  ```\n\nVerify the backend MCP tool's request schema accepts this structure.\n\n\
  ### Cross-Link with Schema Browser\n\nThe KG context selector also improves schema\
  \ browser integration: when a KG is\nselected, the schema browser (if open in a\
  \ split or separate tab) should ideally\nshow the ontology for that specific KG.\
  \ This is a desirable enhancement but out\nof scope for this task — do not implement,\
  \ but add a code comment noting the\nfuture integration point.\n\n## Files / Areas\
  \ Affected\n\n- `src/dev-ui/app/pages/query/index.vue` — add KG selector to toolbar\n\
  - `src/dev-ui/app/components/query/KnowledgeGraphSelector.vue` (new or reuse)\n\
  - `src/dev-ui/app/composables/useQueryExecution.ts` (or similar) — pass\n  `knowledge_graph_id`\
  \ when selected\n\n## Tests\n\nVitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:\n\
  - `test_kg_selector_rendered_in_query_console`: mount `/query`, assert the KG\n\
  \  selector component is present in the toolbar\n- `test_kg_selector_populates_from_api`:\
  \ mock `GET /management/knowledge-graphs`\n  returning two KGs, assert the selector\
  \ dropdown contains both options\n- `test_selected_kg_included_in_query_request`:\
  \ select a specific KG, execute a\n  query, assert the API call includes `knowledge_graph_id`\n\
  - `test_no_kg_selected_omits_knowledge_graph_id`: leave selector on \"All knowledge\n\
  \  graphs\", execute a query, assert the API call does NOT include `knowledge_graph_id`\n\
  - `test_kg_selector_shows_selected_kg_name_in_toolbar`: select a KG, assert the\n\
  \  toolbar displays the KG name (not just an ID or placeholder)\n\n## How to Verify\n\
  \n1. Navigate to `/query`\n2. Confirm the toolbar shows a \"All knowledge graphs\"\
  \ dropdown\n3. Select a specific knowledge graph from the dropdown\n4. Execute any\
  \ Cypher query — open DevTools Network tab and confirm the request\n   body includes\
  \ `knowledge_graph_id` with the selected KG's ID\n5. Clear the selection back to\
  \ \"All knowledge graphs\"\n6. Execute the same query — confirm `knowledge_graph_id`\
  \ is absent from the request\n\n## Caveats\n\n- The KG list is fetched from the\
  \ Management context (`GET /management/knowledge-graphs`),\n  not from the MCP `knowledge_graphs://accessible`\
  \ resource (which is MCP-protocol\n  specific). Use the REST API for the dropdown\
  \ list.\n- If the user has no accessible knowledge graphs, show the selector in\
  \ a disabled\n  state with a message: \"No knowledge graphs available — create one\
  \ in the Data\n  section.\"\n- The selected KG state should NOT be shared with the\
  \ mutations console selector\n  (they are independent scoping contexts). Both can\
  \ reuse the same Vue component\n  but should have separate reactive state instances."
---
