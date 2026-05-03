---
id: task-120
title: 'UI: Knowledge Graph & Data Source Management'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps:
- task-118
- task-119
round: 0
branch: hyperloop/task-120
pr: null
pr_title: 'feat(ui): add knowledge graph creation and data source connection flows'
pr_description: "## What & Why\n\nImplements the two core setup flows: creating a\
  \ knowledge graph and connecting a\ndata source to it. Together these take a user\
  \ from \"nothing\" to \"data is connected\nand ready to sync.\" Both flows integrate\
  \ with the Management REST API.\n\n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`:\n\
  - **Requirement: Knowledge Graph Creation** — create KG (name + description) within\n\
  \  the current workspace; prompt to add first data source immediately after\n- **Requirement:\
  \ Data Source Connection** — adapter type selection, adapter-specific\n  fields,\
  \ inferred defaults, credential handling (sent to backend only, never\n  persisted\
  \ client-side)\n- **Requirement: Backend API Alignment** — all operations complete\
  \ with 2xx responses\n  and the UI reflects updated state; parent workspace context\
  \ is passed in every\n  create request\n\n## Knowledge Graph Creation Flow\n\n1.\
  \ User navigates to `/data/knowledge-graphs/new`\n2. Form: `name` (required), `description`\
  \ (optional)\n3. `workspace_id` is injected from the active workspace in app state\
  \ — never\n   requires the user to select it manually (parent context preserved\
  \ per spec)\n4. `POST /management/knowledge-graphs` with `{ name, description, workspace_id\
  \ }`\n5. On success → navigate to the new KG's detail page, which shows an empty\
  \ state\n   with a prominent CTA: \"Add your first data source\"\n\n## Data Source\
  \ Connection Flow\n\n### Step 1: Adapter type selection\n- Renders a card grid of\
  \ supported adapter types (e.g., GitHub; more to follow)\n- Selecting a card advances\
  \ to step 2\n\n### Step 2: Connection configuration (GitHub adapter example)\n-\
  \ Repository URL (required)\n- Access token / PAT (required for private repos; optional\
  \ for public)\n- Data source name — auto-populated from repo name slug; user can\
  \ override\n- Additional adapter-specific fields rendered from an adapter schema\n\
  \n### Step 3: Save\n- `POST /management/knowledge-graphs/{kg_id}/data-sources` with\
  \ credentials\n- Credentials are posted directly to the backend; the plaintext token\
  \ is never\n  stored in `localStorage`, `sessionStorage`, or any global state object\n\
  - On success → redirect to data source detail / KG overview\n\n## Backend API Integration\n\
  \n| Action | Endpoint |\n|---|---|\n| Create KG | `POST /management/knowledge-graphs`\
  \ |\n| List KGs | `GET /management/knowledge-graphs?workspace_id=…` |\n| Create\
  \ data source | `POST /management/knowledge-graphs/{kg_id}/data-sources` |\n| List\
  \ data sources | `GET /management/knowledge-graphs/{kg_id}/data-sources` |\n\nAll\
  \ requests include the `Authorization: Bearer` header from the auth store.\nThe\
  \ `workspace_id` is automatically appended from the active workspace context —\n\
  users never see a raw ID field (Backend API Alignment spec).\n\n## Files / Areas\
  \ Affected\n\n- `src/ui/src/pages/data/KnowledgeGraphs.vue` — list page\n- `src/ui/src/pages/data/KnowledgeGraphNew.vue`\
  \ — creation form\n- `src/ui/src/pages/data/KnowledgeGraphDetail.vue` — detail with\
  \ data-source list\n- `src/ui/src/pages/data/DataSourceNew.vue` — multi-step adapter\
  \ connection wizard\n- `src/ui/src/components/data-source/AdapterTypeSelector.vue`\n\
  - `src/ui/src/components/data-source/GithubAdapterForm.vue`\n- `src/ui/src/api/management.ts`\
  \ — typed API client for Management context\n\n## How to Verify\n\n1. Navigate to\
  \ Knowledge Graphs → New; fill form → submit → redirects to KG detail\n2. KG detail\
  \ shows \"Add your first data source\" CTA\n3. Click CTA → adapter type selector\
  \ → choose GitHub → fill repo URL + token →\n   submit → data source appears in\
  \ list; network tab shows token sent in POST body\n   (not in URL or localStorage)\n\
  4. Open browser DevTools → Application → Local/Session Storage → confirm no token\
  \ stored\n\n## Caveats / Follow-up\n\n- Ontology Design flow (which begins after\
  \ data source connection) is implemented\n  in task-128; this PR ends at the successful\
  \ data source creation step\n- Sync monitoring UI (sync status badges on data source\
  \ list) is in task-129"
---
