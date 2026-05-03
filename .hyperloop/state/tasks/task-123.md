---
id: task-123
title: UI Ontology Design — Intent Capture, Agent Proposal, and Review Flow
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-121]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add agent-assisted ontology design flow with review and approval"
pr_description: |
  ## What and Why

  Implements the ontology design wizard that appears after a data source is
  connected. Users describe what questions they want to answer with their data;
  an AI agent proposes an ontology (node types, edge types, properties); and the
  user reviews and approves before extraction begins.

  This is a high-value differentiating feature — it removes the need for manual
  schema design and makes the platform accessible to non-experts.

  **⚠️ Backend dependency**: The "agent-proposed ontology" scenario requires the
  Extraction bounded context (AIHCM-174 spike must complete first). The intent
  capture step and the review/approval UI can be built now; the agentic proposal
  step will be wired up once the backend API is available.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Ontology Design** from
  `specs/ui/experience.spec.md`.

  Specifically:
  - **Intent description**: free-text area where the user describes the problems
    or questions they want to solve; shown immediately after data source save.
  - **Agent-proposed ontology**: the backend scans the data source and returns a
    proposed ontology via `POST /api/extraction/ontology/propose`; the UI displays
    a loading state while the agent works, then renders the proposal.
  - **Ontology review and approval**: user can approve as-is (→ triggers extraction)
    or iterate; the UI lists node types and edge types with expandable detail rows.
  - **Individual type editing**: inline editor (Sheet or Dialog) for each type —
    modify label, description, required properties, optional properties, and
    relationship types; changes update the local proposal before final approval.
  - **Ontology change after initial extraction**: modifying an approved ontology
    that already has graph data triggers a confirmation dialog warning that a full
    re-extraction will be required; extraction only begins after explicit confirmation.

  ## Design Decisions

  - The ontology proposal is a long-running operation; the UI shows an animated
    "Agent is analyzing your data source…" state with a progress hint.
  - The proposal is stored in local component state until the user approves; no
    intermediate saves to the backend (avoids partial-ontology confusion).
  - Type editing uses a Sheet (slide-over panel) so the user can see the full
    ontology list while editing a single type.
  - The re-extraction warning is a blocking `<Dialog>` with explicit "Yes, re-extract"
    and "Cancel" actions — no implicit confirmation.

  ## Backend APIs Required (partial — pending Extraction context)

  - `POST /api/extraction/ontology/propose` — submit intent + data source for
    agent-driven proposal (BLOCKED on AIHCM-174)
  - `GET /api/management/knowledge-graphs/{id}/ontology` — fetch approved ontology
  - `PUT /api/management/knowledge-graphs/{id}/ontology` — save approved/edited ontology
  - `POST /api/extraction/jobs` — trigger extraction (BLOCKED on AIHCM-174)

  ## Files / Areas Affected

  - `src/ui/pages/data/OntologyDesignPage.vue`
  - `src/ui/components/ontology/IntentDescriptionStep.vue`
  - `src/ui/components/ontology/OntologyProposalViewer.vue`
  - `src/ui/components/ontology/OntologyTypeEditor.vue`
  - `src/ui/components/ontology/ReExtractionWarningDialog.vue`
  - `src/ui/composables/useOntology.ts`
  - `src/ui/mocks/ontologyApi.ts` — mock for proposal API until backend lands

  ## How to Verify

  1. After data source creation, user is shown the intent description step
  2. Submitting intent shows loading state (mock or real backend)
  3. Proposed ontology renders with node types and edge types
  4. Editing a type opens the Sheet editor; changes persist in local state
  5. Approving triggers extraction (or mock confirmation)
  6. Modifying an ontology after extraction shows re-extraction warning dialog;
     cancel aborts, confirm proceeds

  ## Caveats

  The agentic proposal step (`POST /api/extraction/ontology/propose`) must be
  mocked until AIHCM-174 is resolved. The intent capture, display, review, editing,
  and re-extraction warning are fully implementable today without the backend.
---
