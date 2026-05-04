---
id: task-136
title: 'UI — Ontology design: intent description, type editing, re-extraction warning'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps: []
round: 1
branch: hyperloop/task-136
pr: https://github.com/openshift-hyperfleet/kartograph/pull/606
pr_title: 'feat(ui): implement ontology design UI — intent description, type editing,
  re-extraction warning'
pr_description: "## What and Why\n\nThe UI Experience spec defines a **Requirement:\
  \ Ontology Design** with five\nscenarios.  Two of those scenarios (agent-proposed\
  \ ontology and review/\napproval) depend on the Extraction bounded context (AIHCM-174\
  \ spike not yet\ncomplete) and are intentionally deferred.\n\nThe remaining three\
  \ scenarios are fully implementable in the UI right now\nwithout any backend extraction\
  \ work:\n\n1. **Scenario: Intent description** — after a data source is saved, the\
  \ user\n   is prompted (in free text) what problems or questions they want to solve\n\
  \   with this data.  This dialog captures intent that will feed into the\n   extraction\
  \ agent when it is ready.\n\n4. **Scenario: Individual type editing** — the user\
  \ can view and edit a\n   proposed or existing ontology type: modify the label,\
  \ description,\n   required properties, optional properties, and relationship types.\n\
  \n5. **Scenario: Ontology change after initial extraction** — when the user\n  \
  \ modifies an ontology after an initial extraction has run, the UI must\n   warn\
  \ that a full re-extraction will be triggered and require explicit\n   confirmation\
  \ before applying the change.\n\nWithout this UI work, users have no path to express\
  \ their intent after\nconnecting a data source, and no way to refine the graph schema\
  \ — two\nfeatures that are essential for the \"get from data source to useful query\"\
  \ngoal the spec describes.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\n\
  \n- **Requirement: Ontology Design — Scenario: Intent description**:\n  \"GIVEN\
  \ a user who has connected a data source WHEN the connection is saved\n  THEN the\
  \ user is prompted to describe (in free text) what problems or\n  questions they\
  \ want to solve with this data\"\n\n- **Requirement: Ontology Design — Scenario:\
  \ Individual type editing**:\n  \"GIVEN a proposed or existing ontology WHEN the\
  \ user edits a specific type\n  THEN they can modify the label, description, required\
  \ properties, and\n  optional properties AND they can add or remove relationship\
  \ types AND they\n  can specify exact property requirements\"\n\n- **Requirement:\
  \ Ontology Design — Scenario: Ontology change after initial\n  extraction**: \"\
  GIVEN a knowledge graph with completed extraction WHEN the\n  user modifies the\
  \ ontology THEN the system warns that this will trigger a\n  full re-extraction\
  \ AND the user must confirm before the change is applied\"\n\nScenarios 2 (Agent-proposed\
  \ ontology) and 3 (Ontology review and approval)\nare **excluded** from this task\
  \ — they depend on the Extraction bounded\ncontext (AIHCM-174 spike).\n\n## What\
  \ This Change Does\n\n### 1. Intent description dialog (Scenario 1)\n\nAfter the\
  \ data source connection wizard completes successfully:\n- Show a step-2 dialog:\
  \ \"What do you want to solve?\" with a free-text\n  `Textarea` for the user's intent\
  \ description.\n- Store the intent locally (e.g., in the data source's `description`\
  \ field\n  or a separate metadata field if the backend supports it).\n- Provide\
  \ a \"Save Intent\" and \"Skip for now\" action.\n- The dialog should be non-blocking\
  \ — users can dismiss it and return later.\n\n**Files**: extend `src/dev-ui/app/pages/data-sources/index.vue`\
  \ or the\n`DataSourceConnectionWizard` component; add step to wizard flow.\n\n###\
  \ 2. Type editor panel (Scenario 4)\n\nAdd a `OntologyTypeEditor.vue` component\
  \ (or integrate into the existing\ndata sources / knowledge graph pages) that allows:\n\
  \n- Editing a type's **label** (display name) and **description**.\n- Viewing and\
  \ managing **required properties** (add, remove, reorder).\n- Viewing and managing\
  \ **optional properties** (add, remove, reorder).\n- Viewing and managing **relationship\
  \ types** (add, remove; direction;\n  target type).\n- A \"Save changes\" button\
  \ that persists edits (API endpoint TBD based on\n  management bounded context schema\
  \ API).\n\n**Files**: `src/dev-ui/app/components/graph/OntologyTypeEditor.vue` (new)\n\
  \n### 3. Re-extraction confirmation dialog (Scenario 5)\n\nWhen the user attempts\
  \ to save an ontology change on a knowledge graph that\nhas at least one completed\
  \ sync run (i.e., extraction has previously run):\n\n- Show an `AlertDialog` before\
  \ committing: \"Changing the ontology will\n  trigger a full re-extraction of all\
  \ data sources. This may take a while.\n  Proceed?\"\n- If user confirms → apply\
  \ the change.\n- If user cancels → discard edits and close the editor.\n- The \"\
  has extraction run\" signal can be derived from whether the knowledge\n  graph has\
  \ any data source with a completed sync run (available via the\n  management API).\n\
  \n**Files**: extend the type editor component above; use the existing\n`AlertDialog`\
  \ primitives from the UI component library.\n\n### Tests (TDD — write first)\n\n\
  For each scenario, write a Vitest unit test **before** implementing the\ncomponent.\
  \  Place tests in `src/dev-ui/app/tests/`:\n\n- `ontology-intent-description.test.ts`\
  \ — verifies the intent dialog appears\n  after data source save and that \"Skip\
  \ for now\" closes it without error.\n- `ontology-type-editor.test.ts` — verifies\
  \ the editor renders label,\n  description, required/optional properties fields\
  \ and that a save call is\n  made with the correct payload.\n- `ontology-reextraction-warning.test.ts`\
  \ — verifies the AlertDialog appears\n  when `hasExtraction` is true, that confirming\
  \ calls the save API, and that\n  cancelling does not.\n\n## Files / Areas Affected\n\
  \n- `src/dev-ui/app/pages/data-sources/index.vue` — add intent description\n  step\
  \ after wizard close\n- `src/dev-ui/app/components/graph/OntologyTypeEditor.vue`\
  \ — new component\n- `src/dev-ui/app/tests/ontology-intent-description.test.ts`\
  \ — new tests\n- `src/dev-ui/app/tests/ontology-type-editor.test.ts` — new tests\n\
  - `src/dev-ui/app/tests/ontology-reextraction-warning.test.ts` — new tests\n\n##\
  \ How to Verify\n\n```bash\ncd src/dev-ui && pnpm test --run\n```\n\nAll new test\
  \ files must pass. Manually verify by starting `make dev` and:\n1. Creating a data\
  \ source — the intent dialog appears after save.\n2. Opening an ontology type —\
  \ the editor renders and accepts edits.\n3. Saving an ontology change on a KG that\
  \ has extraction data — the warning\n   dialog blocks the save until confirmed.\n\
  \n## Caveats\n\n- **Scenarios 2-3 are excluded**: the agent-proposed ontology and\
  \ review/\n  approval flow require the Extraction bounded context.  Do NOT implement\n\
  \  those flows in this task.\n- The backend API for storing per-type metadata (label,\
  \ description,\n  properties, relationship types) may already exist in the management\n\
  \  context's schema endpoints.  Verify `GET /management/knowledge-graphs/\n  {kg_id}/schema`\
  \ or similar before designing the save payload.  If no such\n  API exists, store\
  \ intent as data source `description` and type edits as\n  local state only (to\
  \ be persisted when extraction is wired up).\n- The existing `ontology-add-types.test.ts`\
  \ covers adding types; do not\n  duplicate that coverage.  This task extends, not\
  \ replaces, existing\n  ontology tests.\n- Follow the Kartograph design language:\
  \ shadcn/vue primitives, Tailwind,\n  OKLCH colour tokens, no custom fonts, `rounded-xl`\
  \ for cards, `rounded-md`\n  for inputs/buttons."
---
