---
id: task-137
title: "Schema browser cross-navigation — test receiving side for data-sources ontology editor deep-link"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(ui): add receiving-side test for schema browser → ontology editor cross-navigation"
pr_description: |
  ## What and Why

  The **Schema Browser — Cross-navigation** spec scenario requires:

  > "THEN the user can navigate directly to the query console (pre-filled query),
  > graph explorer (filtered by type), **or ontology editor for that type**"

  Task-104 implemented the full cross-navigation feature. The accompanying test
  file (`schema-crossnav-deeplink.test.ts`) covers three of four contract sides:

  1. ✅ **Sending side** — `schema.vue` dispatches `?query=`, `?type=`, and
     `?openOntologyType=` to the correct destinations.
  2. ✅ **Receiving side** — `query/index.vue` reads `?query=` and pre-fills the
     Cypher editor (Part 2 of the test).
  3. ✅ **Receiving side** — `graph/explorer.vue` reads `?type=` and pre-populates
     the search filter, auto-triggering the search (Part 3).
  4. ❌ **Receiving side** — `data-sources/index.vue` reading `?openOntologyType=`
     and opening the ontology editor is **not tested**.

  Additionally, the end-to-end param name contract (Part 4 of the test) verifies
  matching param names for query console and graph explorer but has no matching
  assertion for the `openOntologyType` contract between `schema.vue` and
  `data-sources/index.vue`.

  Without this test:
  - A rename of `openOntologyType` in either file would silently break the
    ontology editor deep-link with no CI gate.
  - The "for that type" requirement (the param is actually consumed and the editor
    opens) is entirely unverified.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Schema Browser — Scenario: Cross-navigation**
    "THEN the user can navigate directly to the query console (pre-filled query),
    graph explorer (filtered by type), or ontology editor for that type"

  The existing tests satisfy the query console and graph explorer arms of this
  scenario; this task satisfies the ontology editor arm.

  ## What This Change Does

  ### Extension to `schema-crossnav-deeplink.test.ts`

  Adds two new describe groups to the existing test file:

  **Part 3b (new): Receiving side — `data-sources/index.vue` reads `?openOntologyType=`**

  ```typescript
  describe('Cross-navigation receiving side — data-sources (data-sources/index.vue)', () => {
    describe('?openOntologyType= URL parameter triggers the ontology editor', () => {
      it('data-sources/index.vue reads route.query.openOntologyType on mount', () => {
        expect(dataSourcesContent).toContain('route.query.openOntologyType')
      })

      it('data-sources/index.vue calls requestOntologyEdit when param is present', () => {
        // The handler must call requestOntologyEdit (not just read the param silently)
        // Read the block guarded by openOntologyType and verify requestOntologyEdit is inside it
        const paramIdx = dataSourcesContent.indexOf('openOntologyType')
        const editIdx = dataSourcesContent.indexOf('requestOntologyEdit', paramIdx)
        expect(paramIdx).toBeGreaterThan(-1)
        expect(editIdx).toBeGreaterThan(-1)
        expect(editIdx).toBeGreaterThan(paramIdx)
      })

      it('data-sources/index.vue type-guards the openOntologyType param before using it', () => {
        // Must handle the case where the param is undefined (page opened without param)
        expect(dataSourcesContent).toContain('openOntologyType')
        // Guard: if (openOntologyType ...) — ensures no crash on normal navigation
        const paramSection = dataSourcesContent.slice(
          dataSourcesContent.indexOf('openOntologyType'),
          dataSourcesContent.indexOf('openOntologyType') + 300,
        )
        expect(paramSection).toMatch(/if\s*\(openOntologyType/)
      })
    })
  })
  ```

  **Extension to Part 4 (existing): End-to-end param name contract**

  ```typescript
  it('schema.vue and data-sources/index.vue use matching "openOntologyType" param name', () => {
    // schema.vue sends:           query: { openOntologyType: label }
    // data-sources/index.vue reads: route.query.openOntologyType
    // These must match — a rename in either file silently breaks the deep-link
    expect(schemaContent).toContain('openOntologyType')
    expect(dataSourcesContent).toContain('route.query.openOntologyType')
  })
  ```

  ### Verify (and fix if needed) param reading in `data-sources/index.vue`

  The current implementation reads `openOntologyType` but uses it only as a
  trigger — it opens the *first* data source regardless of which type was clicked.
  This satisfies the minimum spec requirement (the ontology editor *does* open),
  but review whether the type label should be used to:

  1. Scroll to / highlight the matching type in the ontology editor panel (preferred),
     OR
  2. Accept the current behavior (open editor, user sees all types) as sufficient,
     with a comment explaining why.

  If the implementation is changed to improve type-level focus, the new behavior
  must also be covered by the test.

  ## Files / Areas Affected

  - `src/dev-ui/app/tests/schema-crossnav-deeplink.test.ts` — extend with Part 3b
    and the openOntologyType assertion in Part 4
  - `src/dev-ui/app/pages/data-sources/index.vue` — read-only inspection; fix only
    if the type-guard or requestOntologyEdit wiring is incorrect

  ## How to Verify

  ```bash
  cd src/dev-ui && pnpm test schema-crossnav-deeplink
  ```

  All existing tests (Parts 1–4) plus the new tests must pass.

  Manual smoke test:
  1. Navigate to `/graph/schema`.
  2. Expand any node type (e.g., "Service").
  3. Click the "Edit Ontology" button.
  4. Confirm the Data Sources page opens and the ontology editor panel activates.

  ## Implementation Notes

  - Follow the source-inspection pattern already used in `schema-crossnav-deeplink.test.ts`:
    read file contents with `readFileSync` and assert on string presence/position.
  - The `dataSourcesContent` variable can be added alongside `schemaContent`,
    `queryContent`, and `explorerContent` at the top of the test file.
  - Write tests FIRST (TDD). If the test for `requestOntologyEdit` wiring fails,
    inspect `data-sources/index.vue` (around the `openOntologyType` block, line ~693)
    to understand the current implementation before fixing.

  ## Caveats

  - The "Edit Ontology" feature links to the data-sources ontology wizard, which is
    partially simulated (hardcoded GITHUB_PROPOSAL_NODES for the AI proposal step).
    The test only needs to verify the deep-link contract, not the proposal step.
  - Do not modify the existing tests in Parts 1–4; only add new describe groups or
    extend the existing Part 4 contract suite.
---
