---
id: task-136
title: "UI — Ontology design: intent description, type editing, re-extraction warning"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): implement ontology design UI — intent description, type editing, re-extraction warning"
pr_description: |
  ## What and Why

  The UI Experience spec defines a **Requirement: Ontology Design** with five
  scenarios.  Two of those scenarios (agent-proposed ontology and review/
  approval) depend on the Extraction bounded context (AIHCM-174 spike not yet
  complete) and are intentionally deferred.

  The remaining three scenarios are fully implementable in the UI right now
  without any backend extraction work:

  1. **Scenario: Intent description** — after a data source is saved, the user
     is prompted (in free text) what problems or questions they want to solve
     with this data.  This dialog captures intent that will feed into the
     extraction agent when it is ready.

  4. **Scenario: Individual type editing** — the user can view and edit a
     proposed or existing ontology type: modify the label, description,
     required properties, optional properties, and relationship types.

  5. **Scenario: Ontology change after initial extraction** — when the user
     modifies an ontology after an initial extraction has run, the UI must
     warn that a full re-extraction will be triggered and require explicit
     confirmation before applying the change.

  Without this UI work, users have no path to express their intent after
  connecting a data source, and no way to refine the graph schema — two
  features that are essential for the "get from data source to useful query"
  goal the spec describes.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`

  - **Requirement: Ontology Design — Scenario: Intent description**:
    "GIVEN a user who has connected a data source WHEN the connection is saved
    THEN the user is prompted to describe (in free text) what problems or
    questions they want to solve with this data"

  - **Requirement: Ontology Design — Scenario: Individual type editing**:
    "GIVEN a proposed or existing ontology WHEN the user edits a specific type
    THEN they can modify the label, description, required properties, and
    optional properties AND they can add or remove relationship types AND they
    can specify exact property requirements"

  - **Requirement: Ontology Design — Scenario: Ontology change after initial
    extraction**: "GIVEN a knowledge graph with completed extraction WHEN the
    user modifies the ontology THEN the system warns that this will trigger a
    full re-extraction AND the user must confirm before the change is applied"

  Scenarios 2 (Agent-proposed ontology) and 3 (Ontology review and approval)
  are **excluded** from this task — they depend on the Extraction bounded
  context (AIHCM-174 spike).

  ## What This Change Does

  ### 1. Intent description dialog (Scenario 1)

  After the data source connection wizard completes successfully:
  - Show a step-2 dialog: "What do you want to solve?" with a free-text
    `Textarea` for the user's intent description.
  - Store the intent locally (e.g., in the data source's `description` field
    or a separate metadata field if the backend supports it).
  - Provide a "Save Intent" and "Skip for now" action.
  - The dialog should be non-blocking — users can dismiss it and return later.

  **Files**: extend `src/dev-ui/app/pages/data-sources/index.vue` or the
  `DataSourceConnectionWizard` component; add step to wizard flow.

  ### 2. Type editor panel (Scenario 4)

  Add a `OntologyTypeEditor.vue` component (or integrate into the existing
  data sources / knowledge graph pages) that allows:

  - Editing a type's **label** (display name) and **description**.
  - Viewing and managing **required properties** (add, remove, reorder).
  - Viewing and managing **optional properties** (add, remove, reorder).
  - Viewing and managing **relationship types** (add, remove; direction;
    target type).
  - A "Save changes" button that persists edits (API endpoint TBD based on
    management bounded context schema API).

  **Files**: `src/dev-ui/app/components/graph/OntologyTypeEditor.vue` (new)

  ### 3. Re-extraction confirmation dialog (Scenario 5)

  When the user attempts to save an ontology change on a knowledge graph that
  has at least one completed sync run (i.e., extraction has previously run):

  - Show an `AlertDialog` before committing: "Changing the ontology will
    trigger a full re-extraction of all data sources. This may take a while.
    Proceed?"
  - If user confirms → apply the change.
  - If user cancels → discard edits and close the editor.
  - The "has extraction run" signal can be derived from whether the knowledge
    graph has any data source with a completed sync run (available via the
    management API).

  **Files**: extend the type editor component above; use the existing
  `AlertDialog` primitives from the UI component library.

  ### Tests (TDD — write first)

  For each scenario, write a Vitest unit test **before** implementing the
  component.  Place tests in `src/dev-ui/app/tests/`:

  - `ontology-intent-description.test.ts` — verifies the intent dialog appears
    after data source save and that "Skip for now" closes it without error.
  - `ontology-type-editor.test.ts` — verifies the editor renders label,
    description, required/optional properties fields and that a save call is
    made with the correct payload.
  - `ontology-reextraction-warning.test.ts` — verifies the AlertDialog appears
    when `hasExtraction` is true, that confirming calls the save API, and that
    cancelling does not.

  ## Files / Areas Affected

  - `src/dev-ui/app/pages/data-sources/index.vue` — add intent description
    step after wizard close
  - `src/dev-ui/app/components/graph/OntologyTypeEditor.vue` — new component
  - `src/dev-ui/app/tests/ontology-intent-description.test.ts` — new tests
  - `src/dev-ui/app/tests/ontology-type-editor.test.ts` — new tests
  - `src/dev-ui/app/tests/ontology-reextraction-warning.test.ts` — new tests

  ## How to Verify

  ```bash
  cd src/dev-ui && pnpm test --run
  ```

  All new test files must pass. Manually verify by starting `make dev` and:
  1. Creating a data source — the intent dialog appears after save.
  2. Opening an ontology type — the editor renders and accepts edits.
  3. Saving an ontology change on a KG that has extraction data — the warning
     dialog blocks the save until confirmed.

  ## Caveats

  - **Scenarios 2-3 are excluded**: the agent-proposed ontology and review/
    approval flow require the Extraction bounded context.  Do NOT implement
    those flows in this task.
  - The backend API for storing per-type metadata (label, description,
    properties, relationship types) may already exist in the management
    context's schema endpoints.  Verify `GET /management/knowledge-graphs/
    {kg_id}/schema` or similar before designing the save payload.  If no such
    API exists, store intent as data source `description` and type edits as
    local state only (to be persisted when extraction is wired up).
  - The existing `ontology-add-types.test.ts` covers adding types; do not
    duplicate that coverage.  This task extends, not replaces, existing
    ontology tests.
  - Follow the Kartograph design language: shadcn/vue primitives, Tailwind,
    OKLCH colour tokens, no custom fonts, `rounded-xl` for cards, `rounded-md`
    for inputs/buttons.
---
