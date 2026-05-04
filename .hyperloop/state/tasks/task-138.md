---
id: task-138
title: UI Experience — Data Source Connection Flow and Schema Browser Cross-Navigation
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat: implement data source connection guided flow and schema browser cross-navigation"
pr_description: |
  ## What and Why

  This PR implements two groups of requirements from `specs/ui/experience.spec.md` that
  are not yet verifiably complete in the dev-UI (`src/dev-ui/`):

  1. **Data Source Connection guided flow** — the spec mandates an adapter-type-first
     UX (the user selects an adapter type *before* filling in connection fields, and the
     form adapts to show adapter-specific required fields). It also requires that credential
     fields give the user clear feedback that secrets are never persisted in the browser.

  2. **Schema Browser cross-navigation** — when the user is viewing a node or edge type
     in the Schema Browser (`/graph/schema`), they must be able to jump directly to:
     - the **Query Console** (`/query`) with a pre-filled `MATCH` query for that type
     - the **Graph Explorer** (`/graph/explorer`) filtered to that type
     (The third target — the Ontology Editor — is deferred; the Extraction bounded context
     required for agent-assisted ontology work has not yet been implemented, per the
     AIHCM-174 spike gate.)

  ## Spec Requirements Satisfied

  ### Requirement: Data Source Connection (`experience.spec.md` §Data Source Connection)

  - **Adapter type selection** — user selects adapter type first; form adapts to show
    adapter-specific fields only for the selected type (e.g. `repository_url` +
    `access_token` for GitHub; no irrelevant fields rendered).
  - **Connection configuration** — minimum required fields shown with inferred defaults
    where possible (e.g. data source name inferred from repository URL).
  - **Credential handling** — plaintext secrets are never persisted in the browser; the
    form makes this visually clear (e.g. password-type inputs, no localStorage writes).

  ### Requirement: Schema Browser (`experience.spec.md` §Schema Browser)

  - **Cross-navigation** — each type card/row in `/graph/schema` exposes action links:
    - "Run Query" → navigates to `/query?query=MATCH+%28n%3ATypeName%29+RETURN+n+LIMIT+25`
    - "Explore" → navigates to `/graph/explorer?label=TypeName`
    (The "Edit Ontology" link is intentionally omitted until the Ontology Design flow is
    unblocked by the Extraction context spike.)

  ### Requirement: Backend API Alignment (`experience.spec.md` §Backend API Alignment)

  Incidental fix: verify that the Data Sources page passes the correct `knowledge_graph_id`
  parent context when creating a data source, matching the backend `POST
  /management/data-sources` contract.

  ## Key Design Decisions

  - The adapter-type selector uses an existing shadcn/vue `Select` component; it is the
    first control rendered in the "Add Data Source" dialog, and subsequent fields are
    conditionally rendered via `v-if="selectedAdapterType === 'github'"` etc.
  - Cross-navigation links in the Schema Browser are rendered as icon-buttons (Lucide
    `Terminal` and `Share2`) adjacent to each type label, consistent with the inline-actions
    interaction principle from the spec.
  - URL query params for cross-navigation use the existing router conventions already
    present in `/query/index.vue` (`?query=`) and the globals search handler.

  ## Files / Areas Affected

  - `src/dev-ui/app/pages/data-sources/index.vue` — adapter-type step in Add dialog
  - `src/dev-ui/app/pages/graph/schema.vue` — add cross-navigation action buttons
  - `src/dev-ui/app/components/query/SchemaPanel.vue` — if cross-nav lives in the panel

  ## How to Verify

  1. Open `/data-sources` → "Add Data Source" dialog: confirm the first step is adapter
     type selection and that the form fields change based on the selected type.
  2. Select GitHub adapter → fill in a repository URL → confirm the data source name is
     auto-populated from the URL.
  3. Open `/graph/schema` → expand any type → click the "Run Query" icon → confirm the
     Query Console opens with a pre-filled `MATCH` query for that type.
  4. Click the "Explore" icon → confirm the Graph Explorer opens filtered to that label.

  ## Caveats and Follow-up

  - Ontology Design scenarios (intent description, AI-proposed ontology, re-extraction
    warning) are explicitly out of scope until the Extraction bounded context is
    implemented (AIHCM-174 spike).
  - Sync Monitoring scenarios (active progress, history, logs, manual trigger) are
    explicitly out of scope until the Ingestion bounded context is implemented.
---
