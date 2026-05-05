---
id: task-156
title: 'UI: Ontology Design — Agent-Assisted Flow'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-151
- task-153
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add agent-assisted ontology design flow for data sources'
pr_description: "## What and Why\n\nAfter a data source is connected (task-153), users\
  \ need a way to define\nthe ontology (node types, edge types, properties) that guides\
  \ how the AI\nextraction agent interprets the raw data. This task implements the\n\
  agent-assisted ontology design flow: free-text intent → lightweight scan →\nAI-proposed\
  \ ontology → user review and approval.\n\n**Dependency note**: This task's backend\
  \ counterparts (lightweight scan and\nAI proposal generation) live in the Extraction\
  \ bounded context, which is\npending the AIHCM-174 spike. The UI flow can be built\
  \ using mock/stub API\nresponses so the presentation layer is ready before the backend\
  \ is. The\nAPI client stubs should be replaced with real calls once the Extraction\n\
  API is available.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\n\
  \n### Requirement: Ontology Design — Intent Description\n- Immediately after a data\
  \ source is saved (task-153 step 3 completion),\n  the user is shown a free-text\
  \ prompt: \"What problems or questions do you\n  want to solve with this data?\"\
  \n- A textarea with a minimum character hint and a \"Generate Ontology\" button\n\
  - User can skip this step; skipping leaves the ontology empty and extraction\n \
  \ will not start\n\n### Requirement: Ontology Design — Agent-Proposed Ontology\n\
  - Clicking \"Generate Ontology\" calls `POST /extraction/ontology/propose`\n  (stubbed\
  \ until Extraction is live) with the data source ID and intent text\n- A loading\
  \ state (\"Scanning your data source and thinking…\") while the\n  API processes\
  \ (may take 10–60 s)\n- The proposed ontology is presented as a card grid of node\
  \ types and edge\n  types, each card showing label, description, and key properties\n\
  \n### Requirement: Ontology Design — Review and Approval\n- **Approve as-is**: single\
  \ click → calls `POST /extraction/ontology/approve`\n  and starts extraction\n-\
  \ **Edit and iterate**: user can expand individual type cards to edit them\n  (see\
  \ below); \"Regenerate\" re-runs the proposal with the current edits as\n  hints\n\
  - Extraction starts only after explicit approval; a confirmation button\n  labelled\
  \ \"Approve & Start Extraction\" makes the intent clear\n\n### Requirement: Ontology\
  \ Design — Individual Type Editing\n- Each type card has an \"Edit\" action that\
  \ opens a sheet panel\n- Editable fields: label (text), description (text), required\
  \ properties\n  (list with add/remove), optional properties (list with add/remove)\n\
  - Relationship types tab: add or remove relationship definitions\n  (from-type →\
  \ to-type via edge label)\n- Property requirements: for each property, a \"Required\"\
  \ toggle and a\n  \"Description\" field; example constraint: \"documentation_page\
  \ must have\n  source_url\"\n\n### Requirement: Ontology Design — Ontology Change\
  \ After Extraction\n- On the data source detail page, an \"Edit Ontology\" button\
  \ opens the\n  ontology editor (same sheet as above, pre-populated with existing\
  \ types)\n- If extraction has already completed for this data source, clicking\n\
  \  \"Save Ontology Changes\" shows a warning dialog:\n  \"Changing the ontology\
  \ will trigger a full re-extraction of this data\n  source. This may take a significant\
  \ amount of time. Continue?\"\n- The change is only applied after the user confirms\
  \ the dialog\n\n## Key Design Decisions\n\n- The ontology proposal and approval\
  \ calls are wrapped in API client stubs\n  that return hard-coded mock data until\
  \ the Extraction API is live. A\n  feature flag (`VITE_EXTRACTION_ENABLED=false`)\
  \ gates the stub vs. real\n  implementation so no runtime code branching is needed\
  \ after the flag is\n  removed.\n- Individual type editing uses a right-side sheet\
  \ (not a modal) to preserve\n  context (the full ontology remains visible).\n- The\
  \ \"re-extraction warning\" dialog is a blocking confirmation that cannot\n  be\
  \ dismissed by clicking outside, preventing accidental triggers.\n\n## Files / Areas\
  \ Affected\n\n- `src/ui/src/pages/data/OntologyDesignPage.vue`\n- `src/ui/src/components/IntentDescriptionForm.vue`\n\
  - `src/ui/src/components/OntologyProposalGrid.vue`\n- `src/ui/src/components/OntologyTypeCard.vue`\n\
  - `src/ui/src/components/OntologyTypeEditSheet.vue`\n- `src/ui/src/components/OntologyApprovalBar.vue`\n\
  - `src/ui/src/components/ReExtractionWarningDialog.vue`\n- `src/ui/src/stores/ontology.ts`\n\
  - `src/ui/src/lib/api/extraction.ts` (stubs + real implementation behind\n  feature\
  \ flag)\n\n## How to Verify\n\nWith `VITE_EXTRACTION_ENABLED=false` (stub mode):\n\
  \n1. Complete data source creation (task-153) → intent description form shown\n\
  2. Enter intent text → \"Generate Ontology\" button enables\n3. Click → loading\
  \ spinner for ~2 s (simulated stub delay)\n4. Proposed ontology grid appears with\
  \ 3-4 mock type cards\n5. Click \"Edit\" on a type → sheet opens; edit label, add\
  \ a property, save\n6. Click \"Approve & Start Extraction\" → confirmation, then\
  \ success toast\n7. Navigate to Data Source detail → \"Edit Ontology\" button visible\n\
  8. Click → ontology editor opens pre-populated with approved types\n9. Save → re-extraction\
  \ warning dialog blocks until confirmed\n\nWith `VITE_EXTRACTION_ENABLED=true` (requires\
  \ Extraction API running):\n\n- All of the above but calls the real `POST /extraction/ontology/propose`\n\
  \  and `POST /extraction/ontology/approve` endpoints.\n\n## Caveats\n\n- This task\
  \ is blocked on AIHCM-174 (Extraction spike) for full end-to-end\n  verification\
  \ with real data. Stub mode allows the UI to be merged and\n  tested independently.\n\
  - The Extraction API contract (request/response shapes for `/ontology/propose`\n\
  \  and `/ontology/approve`) must be agreed upon before removing the stubs;\n  the\
  \ API client types in `extraction.ts` should be updated when the\n  Extraction spec\
  \ is finalised."
---
