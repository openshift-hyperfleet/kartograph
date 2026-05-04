---
id: task-128
title: 'UI: Ontology Design (shell — requires Extraction spike)'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps:
- task-118
- task-119
- task-120
round: 0
branch: hyperloop/task-128
pr: https://github.com/openshift-hyperfleet/kartograph/pull/601
pr_title: 'feat(ui): add ontology design flow with intent capture and type editor'
pr_description: "## What & Why\n\nImplements the agent-assisted ontology design flow\
  \ that begins after a data source\nis connected. Users describe their intent in\
  \ free text, an AI agent proposes an\nontology, and the user reviews / edits individual\
  \ types before approving and\ntriggering extraction.\n\nThis is a complex multi-step\
  \ flow. The **UI shell** (forms, review panels, type\neditor) can be fully built\
  \ in this task. However, the backend AI agent scan and\nproposal generation require\
  \ the Extraction bounded context, which is pending the\nAIHCM-174 spike. This task\
  \ should wire to a stub/mock proposal endpoint and is\nready to swap in the real\
  \ backend when available.\n\n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n\
  - **Requirement: Ontology Design** — all five scenarios: intent description,\n \
  \ agent-proposed ontology, ontology review and approval, individual type editing,\n\
  \  ontology change after initial extraction (re-extraction warning)\n\n## Flow Overview\n\
  \n```\nData source created (task-120)\n     ↓\nIntent description form\n     ↓ \
  \ (POST /ingestion/data-sources/{id}/scan)\n[Loading: \"Analyzing data source...\"\
  ]\n     ↓\nProposed ontology review\n     ↓ (approve as-is OR iterate)\nIndividual\
  \ type editor (optional)\n     ↓ (POST /ingestion/data-sources/{id}/approve-ontology)\n\
  Extraction begins\n```\n\n## Step 1: Intent Description\n\nShown immediately after\
  \ successful data source creation (step after task-120's flow):\n- Full-width textarea:\
  \ \"Describe what problems or questions you want to solve with\n  this data\" (required)\n\
  - Character limit hint; not a hard limit\n- \"Analyze Data Source\" button → `POST\
  \ /ingestion/data-sources/{id}/analyze`\n  with `{ intent: \"...\" }`\n- Loading\
  \ state: animated progress indicator with rotating messages\n  (\"Scanning repository…\"\
  , \"Discovering entities…\", \"Proposing ontology…\")\n\n## Step 2: Proposed Ontology\
  \ Review\n\nThe API returns a structured ontology proposal:\n```json\n{\n  \"node_types\"\
  : [{ \"label\": \"Service\", \"description\": \"...\", \"properties\": [...] }],\n\
  \  \"edge_types\": [{ \"label\": \"DEPENDS_ON\", \"description\": \"...\", \"properties\"\
  : [...] }]\n}\n```\n\nReview panel layout:\n- Two sections: \"Node Types\" and \"\
  Edge Types\"\n- Each type shown as an expandable card with label, description, required/optional\n\
  \  properties\n- \"Edit\" button on each card (opens type editor — Step 3)\n- Footer:\
  \ \"Approve Ontology\" (primary) and \"Re-analyze\" (secondary) buttons\n\n## Step\
  \ 3: Individual Type Editor (inline or sheet)\n\nOpened when the user clicks \"\
  Edit\" on a proposed type:\n- **Label** — editable text field\n- **Description**\
  \ — textarea\n- **Required properties** — tag input (add/remove property names;\
  \ mark as required)\n- **Optional properties** — tag input (add/remove property\
  \ names)\n- **Relationship types** (for node types) — add/remove edges this node\
  \ participates in\n- **Property requirements** — per-property \"must have\" annotation\n\
  \  (e.g., \"source_url is required for documentation pages\")\n- \"Save\" → updates\
  \ local proposal state (not sent to backend until final approval)\n\n## Step 4:\
  \ Approval\n\n\"Approve Ontology\" button → `POST /ingestion/data-sources/{id}/approve-ontology`\n\
  with the (potentially edited) ontology proposal.\nOn success: navigates to data\
  \ source detail showing sync status as \"Queued\".\n\n## Re-extraction Warning\n\
  \nWhen a user navigates to the ontology editor for an **existing** knowledge graph\n\
  (after extraction has already run):\n- A yellow warning banner appears: \"Modifying\
  \ the ontology will trigger a full\n  re-extraction. All existing graph data will\
  \ be rebuilt.\"\n- The \"Save\" / \"Apply\" button is replaced with a two-step confirmation:\n\
  \  1. \"Apply Changes\" → warning modal: \"This will delete and rebuild all extracted\n\
  \     data. This cannot be undone.\"\n  2. \"Confirm Re-extraction\" → sends the\
  \ update\n\n## Backend API Integration\n\n| Action | Endpoint (stub until Extraction\
  \ spike completes) |\n|---|---|\n| Analyze data source | `POST /ingestion/data-sources/{id}/analyze`\
  \ |\n| Approve ontology | `POST /ingestion/data-sources/{id}/approve-ontology` |\n\
  | Get current ontology | `GET /ingestion/data-sources/{id}/ontology` |\n\n> **Note:**\
  \ These endpoints do not yet exist. This PR should use a mock/stub\n> that returns\
  \ a hardcoded ontology proposal, with a `TODO` comment and a\n> feature flag (`VITE_ENABLE_ONTOLOGY_AGENT=false`)\
  \ to toggle between stub and\n> real endpoint. When AIHCM-174 spike completes, the\
  \ flag is enabled and the\n> real backend is wired in.\n\n## Files / Areas Affected\n\
  \n- `src/ui/src/pages/data/OntologyDesign.vue` — multi-step flow container\n- `src/ui/src/components/ontology/IntentForm.vue`\n\
  - `src/ui/src/components/ontology/ProposedOntologyReview.vue`\n- `src/ui/src/components/ontology/TypeCard.vue`\n\
  - `src/ui/src/components/ontology/TypeEditor.vue`\n- `src/ui/src/components/ontology/ReextractionWarning.vue`\n\
  - `src/ui/src/api/ingestion.ts` — stub API client\n\n## How to Verify\n\n1. After\
  \ creating a data source → redirects to ontology design; intent textarea visible\n\
  2. Enter intent text → click \"Analyze Data Source\" → loading animation → stub\
  \ proposal appears\n3. Expand a proposed node type → properties listed; click \"\
  Edit\" → type editor opens\n4. Edit label and add a property → click \"Save\" →\
  \ card updates with edited label\n5. Click \"Approve Ontology\" → success toast;\
  \ navigates to data source detail\n6. Navigate to ontology editor for a KG with\
  \ existing extractions → re-extraction\n   warning banner visible; confirm dialog\
  \ appears before applying\n\n## Caveats / Follow-up\n\n- Backend Extraction context\
  \ (AIHCM-174 spike) must be completed before removing\n  the stub and enabling real\
  \ agent-assisted proposals\n- The feature flag `VITE_ENABLE_ONTOLOGY_AGENT` gates\
  \ stub vs. real API"
---
