---
id: task-120
title: "UI: Knowledge Graph & Data Source Management"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add knowledge graph creation and data source connection flows"
pr_description: |
  ## What & Why

  Implements the two core setup flows: creating a knowledge graph and connecting a
  data source to it. Together these take a user from "nothing" to "data is connected
  and ready to sync." Both flows integrate with the Management REST API.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md`:
  - **Requirement: Knowledge Graph Creation** — create KG (name + description) within
    the current workspace; prompt to add first data source immediately after
  - **Requirement: Data Source Connection** — adapter type selection, adapter-specific
    fields, inferred defaults, credential handling (sent to backend only, never
    persisted client-side)
  - **Requirement: Backend API Alignment** — all operations complete with 2xx responses
    and the UI reflects updated state; parent workspace context is passed in every
    create request

  ## Knowledge Graph Creation Flow

  1. User navigates to `/data/knowledge-graphs/new`
  2. Form: `name` (required), `description` (optional)
  3. `workspace_id` is injected from the active workspace in app state — never
     requires the user to select it manually (parent context preserved per spec)
  4. `POST /management/knowledge-graphs` with `{ name, description, workspace_id }`
  5. On success → navigate to the new KG's detail page, which shows an empty state
     with a prominent CTA: "Add your first data source"

  ## Data Source Connection Flow

  ### Step 1: Adapter type selection
  - Renders a card grid of supported adapter types (e.g., GitHub; more to follow)
  - Selecting a card advances to step 2

  ### Step 2: Connection configuration (GitHub adapter example)
  - Repository URL (required)
  - Access token / PAT (required for private repos; optional for public)
  - Data source name — auto-populated from repo name slug; user can override
  - Additional adapter-specific fields rendered from an adapter schema

  ### Step 3: Save
  - `POST /management/knowledge-graphs/{kg_id}/data-sources` with credentials
  - Credentials are posted directly to the backend; the plaintext token is never
    stored in `localStorage`, `sessionStorage`, or any global state object
  - On success → redirect to data source detail / KG overview

  ## Backend API Integration

  | Action | Endpoint |
  |---|---|
  | Create KG | `POST /management/knowledge-graphs` |
  | List KGs | `GET /management/knowledge-graphs?workspace_id=…` |
  | Create data source | `POST /management/knowledge-graphs/{kg_id}/data-sources` |
  | List data sources | `GET /management/knowledge-graphs/{kg_id}/data-sources` |

  All requests include the `Authorization: Bearer` header from the auth store.
  The `workspace_id` is automatically appended from the active workspace context —
  users never see a raw ID field (Backend API Alignment spec).

  ## Files / Areas Affected

  - `src/ui/src/pages/data/KnowledgeGraphs.vue` — list page
  - `src/ui/src/pages/data/KnowledgeGraphNew.vue` — creation form
  - `src/ui/src/pages/data/KnowledgeGraphDetail.vue` — detail with data-source list
  - `src/ui/src/pages/data/DataSourceNew.vue` — multi-step adapter connection wizard
  - `src/ui/src/components/data-source/AdapterTypeSelector.vue`
  - `src/ui/src/components/data-source/GithubAdapterForm.vue`
  - `src/ui/src/api/management.ts` — typed API client for Management context

  ## How to Verify

  1. Navigate to Knowledge Graphs → New; fill form → submit → redirects to KG detail
  2. KG detail shows "Add your first data source" CTA
  3. Click CTA → adapter type selector → choose GitHub → fill repo URL + token →
     submit → data source appears in list; network tab shows token sent in POST body
     (not in URL or localStorage)
  4. Open browser DevTools → Application → Local/Session Storage → confirm no token stored

  ## Caveats / Follow-up

  - Ontology Design flow (which begins after data source connection) is implemented
    in task-128; this PR ends at the successful data source creation step
  - Sync monitoring UI (sync status badges on data source list) is in task-129
---
