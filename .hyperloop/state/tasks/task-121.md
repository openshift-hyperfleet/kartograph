---
id: task-121
title: UI Knowledge Graph & Data Source Creation Flow
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-119, task-120]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add knowledge graph creation and data source connection flows"
pr_description: |
  ## What and Why

  Implements the primary "set up" path: user creates a knowledge graph within a
  workspace and then connects a data source to it. This is the core user journey
  described in the spec's "I have a data source → I can query a knowledge graph"
  goal. It depends on task-120 because the workspace context (active workspace ID)
  must be available to scope KG creation.

  ## Spec Requirements Satisfied

  All scenarios under **Requirement: Knowledge Graph Creation** and
  **Requirement: Data Source Connection** from `specs/ui/experience.spec.md`.

  Specifically:
  - **Create knowledge graph**: form with name and description; submits to
    `POST /api/management/knowledge-graphs` scoped to the current workspace;
    on success, user is immediately prompted to add their first data source.
  - **Adapter type selection**: step 1 of data source setup — user picks an adapter
    (e.g., GitHub) from a list; form adapts to show adapter-specific fields.
  - **Connection configuration**: adapter-specific fields rendered (e.g., repository
    URL and access token for GitHub); system infers name from repo URL where possible.
  - **Credential handling**: credentials (tokens, passwords) are submitted directly
    to the backend via HTTPS and never stored in `localStorage` or component state
    after the POST completes; backend stores them encrypted in Vault.
  - **Parent context preserved**: all data-source creation calls include the
    `knowledge_graph_id` parent; all KG creation calls include `workspace_id`.

  ## Design Decisions

  - A two-step wizard (KG → Data Source) avoids deep nesting and keeps each step
    focused. The wizard state is local to the page and does not persist across
    navigation.
  - Adapter forms are driven by a schema definition (`ADAPTER_SCHEMAS`) so adding
    a new adapter only requires adding an entry to the schema — no new Vue components.
  - Credentials are handled with `<input type="password">` and cleared from the
    local form model on successful submission (spec: "plaintext is never persisted
    in the browser").
  - Inferred name: a `watch` on the repo URL field populates the name field if it
    is still empty; the user can override at any time.

  ## Backend APIs Required

  - `POST /api/management/knowledge-graphs` — create KG
  - `GET /api/management/knowledge-graphs` — list KGs for workspace
  - `GET /api/management/data-sources/adapter-types` — enumerate available adapters
  - `POST /api/management/data-sources` — create data source

  ## Files / Areas Affected

  - `src/ui/pages/data/KnowledgeGraphsPage.vue`
  - `src/ui/pages/data/KnowledgeGraphDetailPage.vue`
  - `src/ui/components/kg/KnowledgeGraphCreateForm.vue`
  - `src/ui/components/datasource/DataSourceAdapterPicker.vue`
  - `src/ui/components/datasource/DataSourceCreateForm.vue`
  - `src/ui/components/datasource/adapters/GitHubAdapterForm.vue` (initial adapter)
  - `src/ui/composables/useKnowledgeGraphs.ts`
  - `src/ui/composables/useDataSources.ts`
  - `src/ui/constants/adapterSchemas.ts`

  ## How to Verify

  1. Data → Knowledge Graphs → Create: form submits, KG appears in list
  2. After KG creation, user is prompted to add a data source (CTA / wizard step 2)
  3. Adapter picker shows at least GitHub; selecting it renders GitHub-specific fields
  4. Repo URL auto-populates name field if empty
  5. Submitting data source form: network tab shows POST with credentials; after
     response, credentials are not visible in any component state or local storage
  6. Creating KG without workspace context is blocked (workspace selector required)

  ## Caveats

  - The sync and extraction flows triggered after data source creation are out of
    scope for this task (see task-122 for sync monitoring, task-123 for ontology).
  - Only the GitHub adapter form is required for the initial implementation; other
    adapters can follow the same schema-driven pattern.
---
