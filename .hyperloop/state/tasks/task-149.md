---
id: task-149
title: UI Ontology Design Flow — intent capture, AI-proposed ontology, review and
  approval
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps:
- task-147
round: 1
branch: hyperloop/task-149
pr: https://github.com/openshift-hyperfleet/kartograph/pull/631
pr_title: 'feat(ui): add AI-assisted ontology design flow with review and approval'
pr_description: "## What and Why\n\nAfter connecting a data source, the user needs\
  \ to define what the knowledge graph\nshould represent: what node types exist, what\
  \ edge types connect them, and what\nproperties matter. This flow captures the user's\
  \ intent in free text, triggers a\nlightweight data scan, surfaces an AI-proposed\
  \ ontology for review, and allows\nper-type editing before the user explicitly approves\
  \ and extraction begins.\n\n**Important**: The AI agent that proposes the ontology\
  \ requires the Extraction\nbounded context to be active (blocked on AIHCM-174 spike).\
  \ This task builds the\ncomplete UI shell and wires it to a backend endpoint stub.\
  \ The full AI integration\nwill be completed once the Extraction context is available.\n\
  \n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Ontology Design — Scenario: Intent description**\n  \"user prompted\
  \ to describe problems/questions in free text after data source saved\"\n\n- **Requirement:\
  \ Ontology Design — Scenario: Agent-proposed ontology**\n  \"lightweight scan of\
  \ data source; AI agent proposes node types, edge types,\n  properties; presented\
  \ to user for review\"\n\n- **Requirement: Ontology Design — Scenario: Ontology\
  \ review and approval**\n  \"approve as-is or iterate by editing individual types;\
  \ extraction begins only\n  after explicit approval\"\n\n- **Requirement: Ontology\
  \ Design — Scenario: Individual type editing**\n  \"modify label, description, required\
  \ properties, optional properties;\n  add/remove relationship types; specify exact\
  \ property requirements\"\n\n- **Requirement: Ontology Design — Scenario: Ontology\
  \ change after initial extraction**\n  \"warn that re-extraction will be triggered;\
  \ user must confirm before applying\"\n\n- **Requirement: Backend API Alignment\
  \ — Scenario: Resource operations succeed end-to-end**\n  Ontology save/update:\
  \ `PUT /knowledge-graphs/{kg_id}/ontology`\n  Ontology read: `GET /knowledge-graphs/{kg_id}/ontology`\n\
  \n## Key Design Decisions\n\n- **Flow entry**: After data source creation (task-147),\
  \ the user is prompted to\n  describe their intent. This prompt appears as a full-screen\
  \ modal/page at\n  `/data/knowledge-graphs/{kg_id}/ontology/design`.\n- **Step 1\
  \ — Intent form**: A `<Textarea>` for free-text intent description.\n  \"Analyze\"\
  \ button triggers the backend scan+proposal.\n- **Step 2 — Proposed ontology**:\
  \ A loading state while the backend processes.\n  On completion, renders `OntologyTypeCard`\
  \ components for each proposed type.\n- **Step 3 — Review and approve**: Each `OntologyTypeCard`\
  \ shows the label,\n  description, required/optional properties, and relationships.\
  \ An \"Edit\" button\n  opens `TypeEditorSheet` (side panel) for per-type modifications.\n\
  \  An \"Approve Ontology\" button (disabled until user has reviewed) saves the\n\
  \  ontology and triggers extraction.\n- **TypeEditorSheet**: Fields for label (read-only\
  \ after first use), description,\n  required properties (tag input), optional properties\
  \ (tag input), relationship\n  types (list of outgoing edges with target type selector).\n\
  - **Re-extraction warning**: On any edit to an approved ontology, an AlertDialog\n\
  \  warns \"Changing the ontology will trigger a full re-extraction. Continue?\"\n\
  - **Backend stub**: The intent-to-ontology proposal endpoint\n  (`POST /knowledge-graphs/{kg_id}/ontology/propose`)\
  \ may not exist yet.\n  Build the UI to handle a 503/404 gracefully (\"AI proposal\
  \ is not available yet\")\n  and allow the user to define types manually instead.\n\
  \n## What Files Are Affected\n\n- **New**: `src/ui/pages/data/knowledge-graphs/[id]/ontology/design.vue`\n\
  - **New**: `src/ui/components/ontology/IntentForm.vue`\n- **New**: `src/ui/components/ontology/OntologyTypeCard.vue`\n\
  - **New**: `src/ui/components/ontology/TypeEditorSheet.vue`\n- **New**: `src/ui/components/ontology/OntologyApprovalBar.vue`\n\
  - **New**: `src/ui/composables/useOntologyDesign.ts`\n- **New**: `src/ui/tests/unit/OntologyTypeCard.test.ts`\n\
  - **New**: `src/ui/tests/unit/TypeEditorSheet.test.ts`\n- **New**: `src/ui/tests/unit/useOntologyDesign.test.ts`\n\
  \n## How to Verify\n\n```bash\ncd src/ui && npm run dev\n# 1. After creating a data\
  \ source, navigate to /data/knowledge-graphs/{id}/ontology/design\n# 2. Step 1:\
  \ Intent textarea; type a description; click \"Analyze\"\n# 3. Step 2: Loading spinner\
  \ while backend processes (or stub response)\n# 4. Step 3: Proposed types rendered\
  \ as cards; \"Edit\" opens TypeEditorSheet\n# 5. In TypeEditorSheet: modify label,\
  \ add property tags, specify a relationship\n# 6. Click \"Approve Ontology\" — ontology\
  \ saved, user redirected to KG detail\n# 7. Modify ontology after approval — AlertDialog\
  \ warning appears\n```\n\nUnit tests:\n```bash\ncd src/ui && npm run test:unit --\
  \ ontology\n# OntologyTypeCard: renders label, description, props; edit opens sheet\n\
  # TypeEditorSheet: tag input adds/removes props; relationship list CRUD\n# useOntologyDesign:\
  \ handles 503 from propose endpoint gracefully\n```\n\n## Caveats\n\n- The AI proposal\
  \ feature (`POST /knowledge-graphs/{kg_id}/ontology/propose`) is\n  blocked on the\
  \ Extraction context spike (AIHCM-174). The UI must degrade\n  gracefully to a manual\
  \ type definition flow when this endpoint is unavailable.\n- Property requirements\
  \ spec: \"documentation_page must have source_url\" — this\n  means the `TypeEditorSheet`\
  \ must support specifying per-property constraints,\n  not just listing them. Implement\
  \ as a simple \"required/optional\" toggle per\n  property name.\n- \"Extraction\
  \ begins only after the user explicitly approves\" — the approval\n  button must\
  \ call `PUT /knowledge-graphs/{kg_id}/ontology` with `approved: true`\n  in the\
  \ body, or a separate `POST /knowledge-graphs/{kg_id}/ontology/approve`\n  endpoint\
  \ if that exists."
---
