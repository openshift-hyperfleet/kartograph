---
id: task-063
title: Ontology wizard and editor — add new node and edge types from scratch
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps:
- task-043
round: 0
branch: hyperloop/task-063
pr: https://github.com/openshift-hyperfleet/kartograph/pull/525
pr_title: 'feat(ui): add new-type buttons to ontology wizard step 4 and post-extraction
  editor'
pr_description: "## What & Why\n\nThe Ontology Design spec requires that users can\
  \ **add** relationship types (edge types)\nand node types during both the initial\
  \ review wizard and subsequent ontology edits. The\ncurrent implementation only\
  \ renders AI-proposed types and allows editing or removing them;\nthere is no path\
  \ to add a brand-new type from scratch.\n\nWithout this capability, a user whose\
  \ data source has an unusual entity the AI did not\npropose (e.g., a `Milestone`\
  \ or `Dependency` node) is stuck — they cannot extend the\nontology beyond what\
  \ the AI returned.\n\n## Spec Requirements Satisfied\n\n**Requirement: Ontology\
  \ Design — Scenario: Individual type editing**\n> GIVEN a proposed or existing ontology\n\
  > WHEN the user edits a specific type\n> THEN they can modify the label, description,\
  \ required properties, and optional properties\n> AND **they can add or remove relationship\
  \ types**\n> AND they can specify exact property requirements\n\n**Requirement:\
  \ Ontology Design — Scenario: Ontology review and approval**\n> THEN they can approve\
  \ the ontology as-is\n> OR **iterate by editing individual types and relationships**\n\
  \nThe \"add\" path for both node types and edge types is not present in the current\
  \ wizard\n(step 4 of `src/dev-ui/app/pages/data-sources/index.vue`) or the post-extraction\
  \ ontology\neditor dialog.\n\n## Key Design Decisions\n\n- **\"Add Node Type\" button**\
  \ appears below the Node Types list in both the wizard and the\n  ontology editor;\
  \ it inserts a new blank `ProposedNodeType` entry and immediately opens it\n  in\
  \ edit mode so the user can fill in label, description, and properties.\n- **\"\
  Add Edge Type\" button** appears below the Edge Types list in both the wizard and\
  \ the\n  ontology editor; it inserts a new blank `ProposedEdgeType` entry (from/to\
  \ fields editable)\n  and opens it in edit mode.\n- New types open in edit mode\
  \ immediately so the user cannot accidentally approve a type\n  with an empty label.\n\
  - Empty label on Save is rejected with an inline validation error.\n- Duplicate\
  \ label detection: if a type with the same label already exists, show a warning.\n\
  - Consistent UI: the Add buttons use the same card/badge/icon design as existing\
  \ type cards.\n- Design language: `Button` with `variant=\"outline\"` and a `Plus`\
  \ Lucide icon. Cards use\n  `rounded-xl`, buttons `rounded-md`, consistent with\
  \ the Kartograph design system.\n\n## Files Affected\n\n- `src/dev-ui/app/pages/data-sources/index.vue`\
  \ — wizard step 4 Node/Edge sections and\n  the post-extraction ontology editor\
  \ dialog: add \"Add Node Type\" / \"Add Edge Type\" buttons,\n  `addNode()` / `addEdge()`\
  \ composable functions, and inline validation for empty labels and\n  duplicate\
  \ detection.\n- `src/dev-ui/app/tests/ontology-add-types.test.ts` — new test file\
  \ (TDD-first) covering:\n  1. Add Node Type button renders in wizard step 4 and\
  \ editor dialog\n  2. Clicking Add Node Type inserts a new entry in edit mode\n\
  \  3. Saving with empty label shows validation error, does not close edit mode\n\
  \  4. Duplicate label shows warning\n  5. Saving with valid label adds type to the\
  \ list in view mode\n  6. Add Edge Type button renders and inserts a blank edge\
  \ with editable from/to\n  7. Saving a new edge type with valid data adds it to\
  \ the edge list\n\n## How to Verify\n\n1. Open the data source wizard. On step 4\
  \ (Ontology Review), below the \"Node Types\" section,\n   a \"+ Add Node Type\"\
  \ button is visible.\n2. Click it — a new card appears in edit mode with empty label/description/properties.\n\
  3. Type a label (e.g. \"Milestone\"), description, required props, click Save —\
  \ card appears\n   in view mode with the new type.\n4. Repeat for Edge Type — the\
  \ new edge type card shows editable \"From\" and \"To\" fields.\n5. Try saving with\
  \ an empty label — inline error \"Label is required\" appears.\n6. Approve the ontology\
  \ including the user-added types — all types (AI-proposed + added)\n   are included\
  \ in the `createDataSource` payload.\n7. Open the post-extraction ontology editor\
  \ (Edit Ontology button on a data source card)\n   and confirm the same Add buttons\
  \ appear there.\n8. Run `cd src/dev-ui && pnpm test` — all tests in `ontology-add-types.test.ts`\
  \ pass.\n\n## Caveats\n\n- Depends on task-043 (which implements the individual\
  \ type editor structure, TDD tests,\n  and the `ProposedNodeType` / `ProposedEdgeType`\
  \ interfaces). task-063 extends that work\n  by adding the \"Add\" path.\n- The\
  \ ontology is currently front-end only (AI proposal is mocked). When the real AI\n\
  \  endpoint lands (AIHCM-174), the Add buttons will still work because they operate\
  \ on\n  the `proposedNodes` / `proposedEdges` reactive refs, not on the API response.\n\
  - Re-extraction warning (task-043 scenario 5) should fire after adding types to\
  \ an\n  existing ontology with completed extraction, exactly as it does for edits\
  \ — no additional\n  changes needed here."
---
