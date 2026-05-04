---
id: task-149
title: "UI Ontology Design Flow — intent capture, AI-proposed ontology, review and approval"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-147]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add AI-assisted ontology design flow with review and approval"
pr_description: |
  ## What and Why

  After connecting a data source, the user needs to define what the knowledge graph
  should represent: what node types exist, what edge types connect them, and what
  properties matter. This flow captures the user's intent in free text, triggers a
  lightweight data scan, surfaces an AI-proposed ontology for review, and allows
  per-type editing before the user explicitly approves and extraction begins.

  **Important**: The AI agent that proposes the ontology requires the Extraction
  bounded context to be active (blocked on AIHCM-174 spike). This task builds the
  complete UI shell and wires it to a backend endpoint stub. The full AI integration
  will be completed once the Extraction context is available.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Ontology Design — Scenario: Intent description**
    "user prompted to describe problems/questions in free text after data source saved"

  - **Requirement: Ontology Design — Scenario: Agent-proposed ontology**
    "lightweight scan of data source; AI agent proposes node types, edge types,
    properties; presented to user for review"

  - **Requirement: Ontology Design — Scenario: Ontology review and approval**
    "approve as-is or iterate by editing individual types; extraction begins only
    after explicit approval"

  - **Requirement: Ontology Design — Scenario: Individual type editing**
    "modify label, description, required properties, optional properties;
    add/remove relationship types; specify exact property requirements"

  - **Requirement: Ontology Design — Scenario: Ontology change after initial extraction**
    "warn that re-extraction will be triggered; user must confirm before applying"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    Ontology save/update: `PUT /knowledge-graphs/{kg_id}/ontology`
    Ontology read: `GET /knowledge-graphs/{kg_id}/ontology`

  ## Key Design Decisions

  - **Flow entry**: After data source creation (task-147), the user is prompted to
    describe their intent. This prompt appears as a full-screen modal/page at
    `/data/knowledge-graphs/{kg_id}/ontology/design`.
  - **Step 1 — Intent form**: A `<Textarea>` for free-text intent description.
    "Analyze" button triggers the backend scan+proposal.
  - **Step 2 — Proposed ontology**: A loading state while the backend processes.
    On completion, renders `OntologyTypeCard` components for each proposed type.
  - **Step 3 — Review and approve**: Each `OntologyTypeCard` shows the label,
    description, required/optional properties, and relationships. An "Edit" button
    opens `TypeEditorSheet` (side panel) for per-type modifications.
    An "Approve Ontology" button (disabled until user has reviewed) saves the
    ontology and triggers extraction.
  - **TypeEditorSheet**: Fields for label (read-only after first use), description,
    required properties (tag input), optional properties (tag input), relationship
    types (list of outgoing edges with target type selector).
  - **Re-extraction warning**: On any edit to an approved ontology, an AlertDialog
    warns "Changing the ontology will trigger a full re-extraction. Continue?"
  - **Backend stub**: The intent-to-ontology proposal endpoint
    (`POST /knowledge-graphs/{kg_id}/ontology/propose`) may not exist yet.
    Build the UI to handle a 503/404 gracefully ("AI proposal is not available yet")
    and allow the user to define types manually instead.

  ## What Files Are Affected

  - **New**: `src/ui/pages/data/knowledge-graphs/[id]/ontology/design.vue`
  - **New**: `src/ui/components/ontology/IntentForm.vue`
  - **New**: `src/ui/components/ontology/OntologyTypeCard.vue`
  - **New**: `src/ui/components/ontology/TypeEditorSheet.vue`
  - **New**: `src/ui/components/ontology/OntologyApprovalBar.vue`
  - **New**: `src/ui/composables/useOntologyDesign.ts`
  - **New**: `src/ui/tests/unit/OntologyTypeCard.test.ts`
  - **New**: `src/ui/tests/unit/TypeEditorSheet.test.ts`
  - **New**: `src/ui/tests/unit/useOntologyDesign.test.ts`

  ## How to Verify

  ```bash
  cd src/ui && npm run dev
  # 1. After creating a data source, navigate to /data/knowledge-graphs/{id}/ontology/design
  # 2. Step 1: Intent textarea; type a description; click "Analyze"
  # 3. Step 2: Loading spinner while backend processes (or stub response)
  # 4. Step 3: Proposed types rendered as cards; "Edit" opens TypeEditorSheet
  # 5. In TypeEditorSheet: modify label, add property tags, specify a relationship
  # 6. Click "Approve Ontology" — ontology saved, user redirected to KG detail
  # 7. Modify ontology after approval — AlertDialog warning appears
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- ontology
  # OntologyTypeCard: renders label, description, props; edit opens sheet
  # TypeEditorSheet: tag input adds/removes props; relationship list CRUD
  # useOntologyDesign: handles 503 from propose endpoint gracefully
  ```

  ## Caveats

  - The AI proposal feature (`POST /knowledge-graphs/{kg_id}/ontology/propose`) is
    blocked on the Extraction context spike (AIHCM-174). The UI must degrade
    gracefully to a manual type definition flow when this endpoint is unavailable.
  - Property requirements spec: "documentation_page must have source_url" — this
    means the `TypeEditorSheet` must support specifying per-property constraints,
    not just listing them. Implement as a simple "required/optional" toggle per
    property name.
  - "Extraction begins only after the user explicitly approves" — the approval
    button must call `PUT /knowledge-graphs/{kg_id}/ontology` with `approved: true`
    in the body, or a separate `POST /knowledge-graphs/{kg_id}/ontology/approve`
    endpoint if that exists.
---
