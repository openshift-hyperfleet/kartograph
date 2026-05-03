---
id: task-113
title: "UI tests: query console knowledge graph scope selector passes knowledge_graph_id to API"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): verify query console KG scope selector passes knowledge_graph_id to queryGraph API"
pr_description: |
  ## What & Why

  The `specs/ui/experience.spec.md` **Query Console** requirement includes:

  > **Scenario: Knowledge graph context**
  > GIVEN a query console
  > THEN the user can optionally select a specific knowledge graph to scope queries
  > AND when unscoped, queries span all knowledge graphs the user can access in the tenant

  The implementation in `src/dev-ui/app/pages/query/index.vue` satisfies this:

  ```typescript
  const selectedKgId = ref('')          // empty = unscoped (all KGs)

  const res = await queryGraph(
    query.value,
    Number(timeout.value),
    Number(maxRows.value),
    selectedKgId.value || undefined,    // undefined = no KG filter
  )
  ```

  A `<Select>` component bound to `selectedKgId` lets the user pick a KG, and the
  `kgScopeLabel` computed shows "All knowledge graphs" when nothing is selected.

  **What is missing**: Vitest component tests in `src/dev-ui/app/tests/query.test.ts`
  that verify the KG scope selector's behaviour end-to-end within the component:

  1. When `selectedKgId` is empty, `queryGraph` is called with `knowledge_graph_id`
     **omitted** (or `undefined`), so queries span all KGs.
  2. When the user selects a specific KG, `queryGraph` is called with that KG's ID
     as `knowledge_graph_id`.
  3. The "Scoped" badge appears when a KG is selected.
  4. The KG selector is populated from the management API (`/management/knowledge-graphs`).

  Without these tests, a refactor of the query execution path or the selector binding
  could silently drop the `knowledge_graph_id` parameter, causing queries to always span
  all KGs regardless of the user's selection — violating the spec's scoping guarantee.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Query Console** — Scenario: *Knowledge graph context*
    - "the user can optionally select a specific knowledge graph to scope queries"
    - "when unscoped, queries span all knowledge graphs the user can access in the tenant"

  ## What This Change Does

  ### Test File

  Create or extend `src/dev-ui/app/tests/query.test.ts` with a
  `describe("Query Console — Knowledge Graph Scope Selector")` block:

  **Write these tests BEFORE any code changes (TDD):**

  #### Test 1: Unscoped query omits knowledge_graph_id
  ```
  GIVEN the query console loads with no KG selected
  WHEN the user executes a query
  THEN queryGraph is called with knowledge_graph_id = undefined
  ```

  #### Test 2: Scoped query passes selected KG ID
  ```
  GIVEN the user selects KG with id "kg-abc123" from the selector
  WHEN the user executes a query
  THEN queryGraph is called with knowledge_graph_id = "kg-abc123"
  ```

  #### Test 3: Scoped badge visible when KG selected
  ```
  GIVEN the user has selected a KG
  THEN a "Scoped" badge is rendered in the toolbar
  AND the badge is absent when no KG is selected
  ```

  #### Test 4: KG selector populated from API
  ```
  GIVEN the management API returns [{id: "kg-1", name: "My Graph"}]
  WHEN the query console mounts
  THEN the KG selector dropdown contains the option "My Graph"
  ```

  #### Test 5: Clearing KG selection restores unscoped mode
  ```
  GIVEN a KG has been selected
  WHEN the user clears the selection (selects the "All knowledge graphs" option)
  THEN the next query execution omits knowledge_graph_id
  ```

  ### Mocking Strategy

  - Mock `useQueryApi` to capture `queryGraph` call arguments.
  - Mock `useApiClient` / `apiFetch` to return a controlled KG list.
  - Mount the page with `@nuxt/test-utils` or plain Vitest + `@vue/test-utils`.
  - Simulate user interactions with `wrapper.get('[data-testid="kg-selector"]').setValue(...)`.

  Note: Add `data-testid="kg-selector"` attribute to the `<Select>` in `query/index.vue`
  if not already present (this is acceptable — test IDs are not production behaviour).

  ## Files / Areas Affected

  - `src/dev-ui/app/tests/query.test.ts` (create or extend) — Vitest component tests
  - `src/dev-ui/app/pages/query/index.vue` — add `data-testid` attributes if needed for
    selector targeting (no logic changes expected)

  ## How to Verify

  1. Write failing tests in `tests/query.test.ts` first (TDD).
  2. Run `cd src/dev-ui && pnpm test -- --run query` — tests fail because they don't
     exist yet.
  3. Add `data-testid` attributes if required.
  4. Re-run tests — all 5 pass.
  5. `pnpm test` — no regressions in other test suites.

  ## Caveats

  - The query console page also loads schema labels (`listNodeLabels`, `listEdgeLabels`)
    on mount — mock these to return empty arrays to keep tests focused on the KG selector.
  - The `queryGraph` call signature is `queryGraph(cypher, timeout, maxRows, kgId?)` —
    confirm the argument order in `useQueryApi` before asserting call arguments.
  - The "All knowledge graphs" selector option (empty string / undefined) is distinct
    from the API returning zero KGs. Test both: no KGs available (empty dropdown) and
    KGs available but none selected (unscoped mode).
  - Keyboard shortcut `Ctrl/Cmd+Enter` should also trigger `queryGraph` with the same
    `knowledge_graph_id` binding — add a test for the keyboard path if time allows
    (lower priority).
---
