---
id: task-128
title: "UI: Ontology Design (shell — requires Extraction spike)"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119, task-120]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add ontology design flow with intent capture and type editor"
pr_description: |
  ## What & Why

  Implements the agent-assisted ontology design flow that begins after a data source
  is connected. Users describe their intent in free text, an AI agent proposes an
  ontology, and the user reviews / edits individual types before approving and
  triggering extraction.

  This is a complex multi-step flow. The **UI shell** (forms, review panels, type
  editor) can be fully built in this task. However, the backend AI agent scan and
  proposal generation require the Extraction bounded context, which is pending the
  AIHCM-174 spike. This task should wire to a stub/mock proposal endpoint and is
  ready to swap in the real backend when available.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Ontology Design** — all five scenarios: intent description,
    agent-proposed ontology, ontology review and approval, individual type editing,
    ontology change after initial extraction (re-extraction warning)

  ## Flow Overview

  ```
  Data source created (task-120)
       ↓
  Intent description form
       ↓  (POST /ingestion/data-sources/{id}/scan)
  [Loading: "Analyzing data source..."]
       ↓
  Proposed ontology review
       ↓ (approve as-is OR iterate)
  Individual type editor (optional)
       ↓ (POST /ingestion/data-sources/{id}/approve-ontology)
  Extraction begins
  ```

  ## Step 1: Intent Description

  Shown immediately after successful data source creation (step after task-120's flow):
  - Full-width textarea: "Describe what problems or questions you want to solve with
    this data" (required)
  - Character limit hint; not a hard limit
  - "Analyze Data Source" button → `POST /ingestion/data-sources/{id}/analyze`
    with `{ intent: "..." }`
  - Loading state: animated progress indicator with rotating messages
    ("Scanning repository…", "Discovering entities…", "Proposing ontology…")

  ## Step 2: Proposed Ontology Review

  The API returns a structured ontology proposal:
  ```json
  {
    "node_types": [{ "label": "Service", "description": "...", "properties": [...] }],
    "edge_types": [{ "label": "DEPENDS_ON", "description": "...", "properties": [...] }]
  }
  ```

  Review panel layout:
  - Two sections: "Node Types" and "Edge Types"
  - Each type shown as an expandable card with label, description, required/optional
    properties
  - "Edit" button on each card (opens type editor — Step 3)
  - Footer: "Approve Ontology" (primary) and "Re-analyze" (secondary) buttons

  ## Step 3: Individual Type Editor (inline or sheet)

  Opened when the user clicks "Edit" on a proposed type:
  - **Label** — editable text field
  - **Description** — textarea
  - **Required properties** — tag input (add/remove property names; mark as required)
  - **Optional properties** — tag input (add/remove property names)
  - **Relationship types** (for node types) — add/remove edges this node participates in
  - **Property requirements** — per-property "must have" annotation
    (e.g., "source_url is required for documentation pages")
  - "Save" → updates local proposal state (not sent to backend until final approval)

  ## Step 4: Approval

  "Approve Ontology" button → `POST /ingestion/data-sources/{id}/approve-ontology`
  with the (potentially edited) ontology proposal.
  On success: navigates to data source detail showing sync status as "Queued".

  ## Re-extraction Warning

  When a user navigates to the ontology editor for an **existing** knowledge graph
  (after extraction has already run):
  - A yellow warning banner appears: "Modifying the ontology will trigger a full
    re-extraction. All existing graph data will be rebuilt."
  - The "Save" / "Apply" button is replaced with a two-step confirmation:
    1. "Apply Changes" → warning modal: "This will delete and rebuild all extracted
       data. This cannot be undone."
    2. "Confirm Re-extraction" → sends the update

  ## Backend API Integration

  | Action | Endpoint (stub until Extraction spike completes) |
  |---|---|
  | Analyze data source | `POST /ingestion/data-sources/{id}/analyze` |
  | Approve ontology | `POST /ingestion/data-sources/{id}/approve-ontology` |
  | Get current ontology | `GET /ingestion/data-sources/{id}/ontology` |

  > **Note:** These endpoints do not yet exist. This PR should use a mock/stub
  > that returns a hardcoded ontology proposal, with a `TODO` comment and a
  > feature flag (`VITE_ENABLE_ONTOLOGY_AGENT=false`) to toggle between stub and
  > real endpoint. When AIHCM-174 spike completes, the flag is enabled and the
  > real backend is wired in.

  ## Files / Areas Affected

  - `src/ui/src/pages/data/OntologyDesign.vue` — multi-step flow container
  - `src/ui/src/components/ontology/IntentForm.vue`
  - `src/ui/src/components/ontology/ProposedOntologyReview.vue`
  - `src/ui/src/components/ontology/TypeCard.vue`
  - `src/ui/src/components/ontology/TypeEditor.vue`
  - `src/ui/src/components/ontology/ReextractionWarning.vue`
  - `src/ui/src/api/ingestion.ts` — stub API client

  ## How to Verify

  1. After creating a data source → redirects to ontology design; intent textarea visible
  2. Enter intent text → click "Analyze Data Source" → loading animation → stub proposal appears
  3. Expand a proposed node type → properties listed; click "Edit" → type editor opens
  4. Edit label and add a property → click "Save" → card updates with edited label
  5. Click "Approve Ontology" → success toast; navigates to data source detail
  6. Navigate to ontology editor for a KG with existing extractions → re-extraction
     warning banner visible; confirm dialog appears before applying

  ## Caveats / Follow-up

  - Backend Extraction context (AIHCM-174 spike) must be completed before removing
    the stub and enabling real agent-assisted proposals
  - The feature flag `VITE_ENABLE_ONTOLOGY_AGENT` gates stub vs. real API
---
