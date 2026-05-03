---
id: task-113
title: 'UI tests: query console knowledge graph scope selector passes knowledge_graph_id
  to API'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps: []
round: 0
branch: hyperloop/task-113
pr: https://github.com/openshift-hyperfleet/kartograph/pull/580
pr_title: 'test(ui): verify query console KG scope selector passes knowledge_graph_id
  to queryGraph API'
pr_description: "## What & Why\n\nThe `specs/ui/experience.spec.md` **Query Console**\
  \ requirement includes:\n\n> **Scenario: Knowledge graph context**\n> GIVEN a query\
  \ console\n> THEN the user can optionally select a specific knowledge graph to scope\
  \ queries\n> AND when unscoped, queries span all knowledge graphs the user can access\
  \ in the tenant\n\nThe implementation in `src/dev-ui/app/pages/query/index.vue`\
  \ satisfies this:\n\n```typescript\nconst selectedKgId = ref('')          // empty\
  \ = unscoped (all KGs)\n\nconst res = await queryGraph(\n  query.value,\n  Number(timeout.value),\n\
  \  Number(maxRows.value),\n  selectedKgId.value || undefined,    // undefined =\
  \ no KG filter\n)\n```\n\nA `<Select>` component bound to `selectedKgId` lets the\
  \ user pick a KG, and the\n`kgScopeLabel` computed shows \"All knowledge graphs\"\
  \ when nothing is selected.\n\n**What is missing**: Vitest component tests in `src/dev-ui/app/tests/query.test.ts`\n\
  that verify the KG scope selector's behaviour end-to-end within the component:\n\
  \n1. When `selectedKgId` is empty, `queryGraph` is called with `knowledge_graph_id`\n\
  \   **omitted** (or `undefined`), so queries span all KGs.\n2. When the user selects\
  \ a specific KG, `queryGraph` is called with that KG's ID\n   as `knowledge_graph_id`.\n\
  3. The \"Scoped\" badge appears when a KG is selected.\n4. The KG selector is populated\
  \ from the management API (`/management/knowledge-graphs`).\n\nWithout these tests,\
  \ a refactor of the query execution path or the selector binding\ncould silently\
  \ drop the `knowledge_graph_id` parameter, causing queries to always span\nall KGs\
  \ regardless of the user's selection — violating the spec's scoping guarantee.\n\
  \n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n- **Requirement:\
  \ Query Console** — Scenario: *Knowledge graph context*\n  - \"the user can optionally\
  \ select a specific knowledge graph to scope queries\"\n  - \"when unscoped, queries\
  \ span all knowledge graphs the user can access in the tenant\"\n\n## What This\
  \ Change Does\n\n### Test File\n\nCreate or extend `src/dev-ui/app/tests/query.test.ts`\
  \ with a\n`describe(\"Query Console — Knowledge Graph Scope Selector\")` block:\n\
  \n**Write these tests BEFORE any code changes (TDD):**\n\n#### Test 1: Unscoped\
  \ query omits knowledge_graph_id\n```\nGIVEN the query console loads with no KG\
  \ selected\nWHEN the user executes a query\nTHEN queryGraph is called with knowledge_graph_id\
  \ = undefined\n```\n\n#### Test 2: Scoped query passes selected KG ID\n```\nGIVEN\
  \ the user selects KG with id \"kg-abc123\" from the selector\nWHEN the user executes\
  \ a query\nTHEN queryGraph is called with knowledge_graph_id = \"kg-abc123\"\n```\n\
  \n#### Test 3: Scoped badge visible when KG selected\n```\nGIVEN the user has selected\
  \ a KG\nTHEN a \"Scoped\" badge is rendered in the toolbar\nAND the badge is absent\
  \ when no KG is selected\n```\n\n#### Test 4: KG selector populated from API\n```\n\
  GIVEN the management API returns [{id: \"kg-1\", name: \"My Graph\"}]\nWHEN the\
  \ query console mounts\nTHEN the KG selector dropdown contains the option \"My Graph\"\
  \n```\n\n#### Test 5: Clearing KG selection restores unscoped mode\n```\nGIVEN a\
  \ KG has been selected\nWHEN the user clears the selection (selects the \"All knowledge\
  \ graphs\" option)\nTHEN the next query execution omits knowledge_graph_id\n```\n\
  \n### Mocking Strategy\n\n- Mock `useQueryApi` to capture `queryGraph` call arguments.\n\
  - Mock `useApiClient` / `apiFetch` to return a controlled KG list.\n- Mount the\
  \ page with `@nuxt/test-utils` or plain Vitest + `@vue/test-utils`.\n- Simulate\
  \ user interactions with `wrapper.get('[data-testid=\"kg-selector\"]').setValue(...)`.\n\
  \nNote: Add `data-testid=\"kg-selector\"` attribute to the `<Select>` in `query/index.vue`\n\
  if not already present (this is acceptable — test IDs are not production behaviour).\n\
  \n## Files / Areas Affected\n\n- `src/dev-ui/app/tests/query.test.ts` (create or\
  \ extend) — Vitest component tests\n- `src/dev-ui/app/pages/query/index.vue` — add\
  \ `data-testid` attributes if needed for\n  selector targeting (no logic changes\
  \ expected)\n\n## How to Verify\n\n1. Write failing tests in `tests/query.test.ts`\
  \ first (TDD).\n2. Run `cd src/dev-ui && pnpm test -- --run query` — tests fail\
  \ because they don't\n   exist yet.\n3. Add `data-testid` attributes if required.\n\
  4. Re-run tests — all 5 pass.\n5. `pnpm test` — no regressions in other test suites.\n\
  \n## Caveats\n\n- The query console page also loads schema labels (`listNodeLabels`,\
  \ `listEdgeLabels`)\n  on mount — mock these to return empty arrays to keep tests\
  \ focused on the KG selector.\n- The `queryGraph` call signature is `queryGraph(cypher,\
  \ timeout, maxRows, kgId?)` —\n  confirm the argument order in `useQueryApi` before\
  \ asserting call arguments.\n- The \"All knowledge graphs\" selector option (empty\
  \ string / undefined) is distinct\n  from the API returning zero KGs. Test both:\
  \ no KGs available (empty dropdown) and\n  KGs available but none selected (unscoped\
  \ mode).\n- Keyboard shortcut `Ctrl/Cmd+Enter` should also trigger `queryGraph`\
  \ with the same\n  `knowledge_graph_id` binding — add a test for the keyboard path\
  \ if time allows\n  (lower priority)."
---
