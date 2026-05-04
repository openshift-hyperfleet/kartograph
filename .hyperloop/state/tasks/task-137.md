---
id: task-137
title: Schema browser cross-navigation — test receiving side for data-sources ontology
  editor deep-link
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: complete
phase: null
deps: []
round: 1
branch: hyperloop/task-137
pr: https://github.com/openshift-hyperfleet/kartograph/pull/607
pr_title: 'test(ui): add receiving-side test for schema browser → ontology editor
  cross-navigation'
pr_description: "## What and Why\n\nThe **Schema Browser — Cross-navigation** spec\
  \ scenario requires:\n\n> \"THEN the user can navigate directly to the query console\
  \ (pre-filled query),\n> graph explorer (filtered by type), **or ontology editor\
  \ for that type**\"\n\nTask-104 implemented the full cross-navigation feature. The\
  \ accompanying test\nfile (`schema-crossnav-deeplink.test.ts`) covers three of four\
  \ contract sides:\n\n1. ✅ **Sending side** — `schema.vue` dispatches `?query=`,\
  \ `?type=`, and\n   `?openOntologyType=` to the correct destinations.\n2. ✅ **Receiving\
  \ side** — `query/index.vue` reads `?query=` and pre-fills the\n   Cypher editor\
  \ (Part 2 of the test).\n3. ✅ **Receiving side** — `graph/explorer.vue` reads `?type=`\
  \ and pre-populates\n   the search filter, auto-triggering the search (Part 3).\n\
  4. ❌ **Receiving side** — `data-sources/index.vue` reading `?openOntologyType=`\n\
  \   and opening the ontology editor is **not tested**.\n\nAdditionally, the end-to-end\
  \ param name contract (Part 4 of the test) verifies\nmatching param names for query\
  \ console and graph explorer but has no matching\nassertion for the `openOntologyType`\
  \ contract between `schema.vue` and\n`data-sources/index.vue`.\n\nWithout this test:\n\
  - A rename of `openOntologyType` in either file would silently break the\n  ontology\
  \ editor deep-link with no CI gate.\n- The \"for that type\" requirement (the param\
  \ is actually consumed and the editor\n  opens) is entirely unverified.\n\n## Spec\
  \ Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Schema Browser — Scenario: Cross-navigation**\n  \"THEN the user\
  \ can navigate directly to the query console (pre-filled query),\n  graph explorer\
  \ (filtered by type), or ontology editor for that type\"\n\nThe existing tests satisfy\
  \ the query console and graph explorer arms of this\nscenario; this task satisfies\
  \ the ontology editor arm.\n\n## What This Change Does\n\n### Extension to `schema-crossnav-deeplink.test.ts`\n\
  \nAdds two new describe groups to the existing test file:\n\n**Part 3b (new): Receiving\
  \ side — `data-sources/index.vue` reads `?openOntologyType=`**\n\n```typescript\n\
  describe('Cross-navigation receiving side — data-sources (data-sources/index.vue)',\
  \ () => {\n  describe('?openOntologyType= URL parameter triggers the ontology editor',\
  \ () => {\n    it('data-sources/index.vue reads route.query.openOntologyType on\
  \ mount', () => {\n      expect(dataSourcesContent).toContain('route.query.openOntologyType')\n\
  \    })\n\n    it('data-sources/index.vue calls requestOntologyEdit when param is\
  \ present', () => {\n      // The handler must call requestOntologyEdit (not just\
  \ read the param silently)\n      // Read the block guarded by openOntologyType\
  \ and verify requestOntologyEdit is inside it\n      const paramIdx = dataSourcesContent.indexOf('openOntologyType')\n\
  \      const editIdx = dataSourcesContent.indexOf('requestOntologyEdit', paramIdx)\n\
  \      expect(paramIdx).toBeGreaterThan(-1)\n      expect(editIdx).toBeGreaterThan(-1)\n\
  \      expect(editIdx).toBeGreaterThan(paramIdx)\n    })\n\n    it('data-sources/index.vue\
  \ type-guards the openOntologyType param before using it', () => {\n      // Must\
  \ handle the case where the param is undefined (page opened without param)\n   \
  \   expect(dataSourcesContent).toContain('openOntologyType')\n      // Guard: if\
  \ (openOntologyType ...) — ensures no crash on normal navigation\n      const paramSection\
  \ = dataSourcesContent.slice(\n        dataSourcesContent.indexOf('openOntologyType'),\n\
  \        dataSourcesContent.indexOf('openOntologyType') + 300,\n      )\n      expect(paramSection).toMatch(/if\\\
  s*\\(openOntologyType/)\n    })\n  })\n})\n```\n\n**Extension to Part 4 (existing):\
  \ End-to-end param name contract**\n\n```typescript\nit('schema.vue and data-sources/index.vue\
  \ use matching \"openOntologyType\" param name', () => {\n  // schema.vue sends:\
  \           query: { openOntologyType: label }\n  // data-sources/index.vue reads:\
  \ route.query.openOntologyType\n  // These must match — a rename in either file\
  \ silently breaks the deep-link\n  expect(schemaContent).toContain('openOntologyType')\n\
  \  expect(dataSourcesContent).toContain('route.query.openOntologyType')\n})\n```\n\
  \n### Verify (and fix if needed) param reading in `data-sources/index.vue`\n\nThe\
  \ current implementation reads `openOntologyType` but uses it only as a\ntrigger\
  \ — it opens the *first* data source regardless of which type was clicked.\nThis\
  \ satisfies the minimum spec requirement (the ontology editor *does* open),\nbut\
  \ review whether the type label should be used to:\n\n1. Scroll to / highlight the\
  \ matching type in the ontology editor panel (preferred),\n   OR\n2. Accept the\
  \ current behavior (open editor, user sees all types) as sufficient,\n   with a\
  \ comment explaining why.\n\nIf the implementation is changed to improve type-level\
  \ focus, the new behavior\nmust also be covered by the test.\n\n## Files / Areas\
  \ Affected\n\n- `src/dev-ui/app/tests/schema-crossnav-deeplink.test.ts` — extend\
  \ with Part 3b\n  and the openOntologyType assertion in Part 4\n- `src/dev-ui/app/pages/data-sources/index.vue`\
  \ — read-only inspection; fix only\n  if the type-guard or requestOntologyEdit wiring\
  \ is incorrect\n\n## How to Verify\n\n```bash\ncd src/dev-ui && pnpm test schema-crossnav-deeplink\n\
  ```\n\nAll existing tests (Parts 1–4) plus the new tests must pass.\n\nManual smoke\
  \ test:\n1. Navigate to `/graph/schema`.\n2. Expand any node type (e.g., \"Service\"\
  ).\n3. Click the \"Edit Ontology\" button.\n4. Confirm the Data Sources page opens\
  \ and the ontology editor panel activates.\n\n## Implementation Notes\n\n- Follow\
  \ the source-inspection pattern already used in `schema-crossnav-deeplink.test.ts`:\n\
  \  read file contents with `readFileSync` and assert on string presence/position.\n\
  - The `dataSourcesContent` variable can be added alongside `schemaContent`,\n  `queryContent`,\
  \ and `explorerContent` at the top of the test file.\n- Write tests FIRST (TDD).\
  \ If the test for `requestOntologyEdit` wiring fails,\n  inspect `data-sources/index.vue`\
  \ (around the `openOntologyType` block, line ~693)\n  to understand the current\
  \ implementation before fixing.\n\n## Caveats\n\n- The \"Edit Ontology\" feature\
  \ links to the data-sources ontology wizard, which is\n  partially simulated (hardcoded\
  \ GITHUB_PROPOSAL_NODES for the AI proposal step).\n  The test only needs to verify\
  \ the deep-link contract, not the proposal step.\n- Do not modify the existing tests\
  \ in Parts 1–4; only add new describe groups or\n  extend the existing Part 4 contract\
  \ suite."
---
