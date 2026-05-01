---
id: task-045
title: Implement UI — query console knowledge graph scope selector
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps:
  - task-016
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Query Console — Scenario: Knowledge graph context** from `specs/ui/experience.spec.md`:

> GIVEN a query console
> THEN the user can optionally select a specific knowledge graph to scope queries
> AND when unscoped, queries span all knowledge graphs the user can access in the tenant

## Current State

The implementation already exists in `src/dev-ui/app/pages/query/index.vue`:

- `selectedKgId` ref — empty string means unscoped (all KGs); a KG ID means scoped
- `knowledgeGraphs` ref — populated by `loadKnowledgeGraphs()` on mount and on tenant change
- `kgScopeLabel` computed — returns "All knowledge graphs" when unscoped, else the KG name
- Knowledge graph context selector — a `<Select>` dropdown rendered above the query editor
  with "All knowledge graphs" as the first option and individual KGs listed below
- `<Badge>` indicators — "Scoped" (secondary) or "Unscoped" (outline) shown beside the selector
- `executeQuery()` passes `selectedKgId.value || undefined` to `queryGraph()`, which calls
  `buildQueryGraphArgs(cypher, timeout, maxRows, knowledgeGraphId)`.
  When `knowledgeGraphId` is `undefined`, the argument is omitted from the MCP call.

`buildQueryGraphArgs` is exported from `src/dev-ui/app/composables/api/useQueryApi.ts` as a
pure function and tested against real production code (not a stub).

Tests covering this scenario exist in `src/dev-ui/app/tests/knowledge-graphs.test.ts`
under the "FAIL 4: Query Console KG Context Selector" label:
- Populates `knowledgeGraphs` from the API on mount
- Reloads the KG list when the tenant changes
- Computes scope label as "All knowledge graphs" when no KG is selected
- Computes scope label as the KG name when a specific KG is selected
- Resets `knowledgeGraphs` to empty on API error
- `buildQueryGraphArgs` includes `knowledge_graph_id` when a KG is selected
- `buildQueryGraphArgs` omits `knowledge_graph_id` when unscoped (empty string → undefined)
- `selectedKgId.value || undefined` gate ensures an empty string becomes `undefined`

## Acceptance Criteria

- A knowledge graph scope selector is visible above the query editor in the Query Console.
- The selector is populated by `GET /management/knowledge-graphs` on page mount.
- The first option is "All knowledge graphs" (unscoped); subsequent options are named KGs.
- When unscoped, `queryGraph()` is called without `knowledge_graph_id` in the MCP arguments.
- When a specific KG is selected, `queryGraph()` includes `knowledge_graph_id` in the args.
- The selector re-loads available KGs when the user switches tenants.
- All tests in the "Query Console - KG Selector" sections pass: `cd src/dev-ui && pnpm test`.

## UI Location

- `src/dev-ui/app/pages/query/index.vue` — existing page
- KG scope selector is rendered in the `<!-- Knowledge Graph Context Selector -->` block
  above the Query Editor card in the template

## Dependencies

- **task-016** must be complete (the query console scaffold is the foundation for this feature).
  task-016 is already marked complete.

## TDD Cycle

Tests already exist in `tests/knowledge-graphs.test.ts` and import real production code
(`buildQueryGraphArgs` from `useQueryApi.ts`). The implementation cycle is:

1. Run `cd src/dev-ui && pnpm test` — verify all KG selector tests pass against the existing
   implementation.
2. If tests fail, fix the implementation in `pages/query/index.vue` or
   `composables/api/useQueryApi.ts` to satisfy them.
3. If any spec scenario is missing a test, add it to `tests/knowledge-graphs.test.ts` first,
   then fix the implementation.
4. Commit atomically once all tests pass.
