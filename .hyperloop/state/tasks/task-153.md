---
id: task-153
title: 'UI: Knowledge Graph & Data Source CRUD'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-151
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add knowledge graph and data source management pages'
pr_description: "## What and Why\n\nThis task builds the **Data** section of the Kartograph\
  \ UI: knowledge graph\ncreation (scoped to a workspace) and data source connection.\
  \ Credentials are\nsubmitted to the server and never persisted in the browser. The\
  \ ontology\ndesign flow and sync monitoring are handled in separate tasks (task-156\
  \ and\ntask-157) because they depend on backends that are not yet implemented.\n\
  \n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\n\
  \n### Requirement: Knowledge Graph Creation\n- **Knowledge Graphs** list page (`/data/knowledge-graphs`):\
  \ lists all KGs\n  in the current workspace with name, description, and status;\
  \ calls\n  `GET /management/knowledge-graphs?workspace_id={id}`\n- **Create knowledge\
  \ graph** flow: modal/sheet with name + description\n  inputs; calls `POST /management/knowledge-graphs`\
  \ with `workspace_id`;\n  on success, user is prompted to add their first data source\
  \ (navigates\n  to the data source creation flow for the new KG)\n- New-user landing\
  \ (from task-151 stub) is fully wired: if the API returns\n  an empty list of KGs,\
  \ the page shows the \"create your first knowledge\n  graph\" CTA\n\n### Requirement:\
  \ Data Source Connection\n- **Data Sources** list page (`/data/data-sources`): lists\
  \ all data sources\n  in the current workspace with name, adapter type, and sync\
  \ status badge;\n  calls `GET /management/data-sources?workspace_id={id}`\n- **Add\
  \ data source** flow:\n  1. Adapter type selection step — radio/card grid showing\
  \ supported\n     adapter types (e.g., GitHub); form adapts to show adapter-specific\n\
  \     fields\n  2. Connection configuration step — minimum required fields for the\n\
  \     selected adapter (e.g., repository URL for GitHub); system infers\n     defaults\
  \ where possible (e.g., data source name from repo name)\n  3. Credentials step\
  \ — sensitive fields (access token, etc.) shown as\n     password inputs; calls\
  \ `POST /management/data-sources` with the\n     credential payload; server encrypts\
  \ and stores them\n- The \"add data source\" button is accessible from both the\
  \ KG detail page\n  and the top-level Data Sources list\n\n### Requirement: Backend\
  \ API Alignment\n- All list/create operations call the correct Management REST endpoints\n\
  - The workspace ID (from the current workspace context in Pinia) is\n  included\
  \ in every request that requires it\n- 201 Created responses update the list without\
  \ a manual refresh\n- Validation errors from the API (422) are mapped to inline\
  \ field errors\n\n### Requirement: Credential Handling\n- Password-type inputs for\
  \ sensitive fields\n- Credentials are POSTed once and never stored in component\
  \ state after\n  the form is submitted\n- No credential value is readable after\
  \ successful save (confirmed by\n  the fact that the Management API returns the\
  \ data source without\n  plaintext credentials on subsequent GET requests)\n\n##\
  \ Key Design Decisions\n\n- A **multi-step sheet** (not a full-page route) is used\
  \ for both the\n  knowledge graph creation and data source creation flows to match\
  \ the\n  \"inline actions over navigation\" interaction principle.\n- Adapter type\
  \ metadata (available types, required fields, defaults) is\n  fetched from `GET\
  \ /management/adapter-types` (or equivalent); if the\n  endpoint is not yet implemented,\
  \ the adapter list is hard-coded to\n  `[\"github\"]` until the API catches up.\n\
  - The data source name field auto-fills from the repository URL using a\n  watcher\
  \ but can be overridden.\n\n## Files / Areas Affected\n\n- `src/ui/src/pages/data/KnowledgeGraphsPage.vue`\n\
  - `src/ui/src/pages/data/KnowledgeGraphDetailPage.vue`\n- `src/ui/src/pages/data/DataSourcesPage.vue`\n\
  - `src/ui/src/pages/data/DataSourceDetailPage.vue`\n- `src/ui/src/components/KnowledgeGraphCreateSheet.vue`\n\
  - `src/ui/src/components/DataSourceCreateSheet.vue`\n- `src/ui/src/components/AdapterTypeSelector.vue`\n\
  - `src/ui/src/stores/knowledgeGraphs.ts`\n- `src/ui/src/stores/dataSources.ts`\n\
  - `src/ui/src/lib/api/management.ts` (typed wrappers for Management API)\n\n## How\
  \ to Verify\n\n```bash\nmake instance-up\nsource .instances/$(basename $(pwd))/.env.instance\n\
  cd src/ui && npm run dev\n```\n\n1. Navigate to Data → Knowledge Graphs → list is\
  \ empty for a new tenant\n2. Click \"Create Knowledge Graph\" → sheet opens with\
  \ name + description\n3. Submit → KG appears in the list; prompt to add first data\
  \ source appears\n4. Click \"Add Data Source\" → adapter selection step shown\n\
  5. Select GitHub → form shows repository URL + access token fields\n6. Repo URL\
  \ \"https://github.com/acme/docs\" → name auto-fills \"docs\"\n7. Submit → data\
  \ source appears in the list; no plaintext token visible\n8. Navigate away and back\
  \ → list persists (Pinia cache or re-fetch)\n9. Verify API calls in browser network\
  \ tab: `POST /management/knowledge-graphs`\n   includes `workspace_id`; `POST /management/data-sources`\
  \ does not echo\n   the token back\n\n## Caveats\n\n- Ontology design (AI-assisted\
  \ flow after data source creation) is in\n  task-156 — this task only covers the\
  \ bare connection setup.\n- Sync monitoring (progress, history, logs, manual trigger)\
  \ is in task-157\n  — this task shows a static \"No syncs yet\" placeholder on the\
  \ data source\n  detail page.\n- Knowledge graph editing (rename/description update)\
  \ is a follow-up; the\n  list page shows the name but does not support inline editing\
  \ in this task."
---
