---
id: task-146
title: UI Knowledge Graph Management — list, create, workspace context
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps:
- task-140
round: 0
branch: hyperloop/task-146
pr: https://github.com/openshift-hyperfleet/kartograph/pull/617
pr_title: 'feat(ui): add knowledge graph management pages with workspace-scoped creation'
pr_description: "## What and Why\n\nKnowledge Graphs are the central organizing concept\
  \ of Kartograph. Before users can\nquery, explore, or ingest data, they need at\
  \ least one KG. This task builds the KG\nlist page and the KG creation flow, properly\
  \ scoped to the active workspace. It also\nsurfaces the \"new user\" prompt (no\
  \ KGs yet) that task-140's landing logic redirects\nnew users to.\n\nThis corresponds\
  \ to `Data → Knowledge Graphs` in the sidebar.\n\n## Spec Requirements Satisfied\n\
  \n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\n- **Requirement:\
  \ Knowledge Graph Creation — Scenario: Create knowledge graph**\n  \"user provides\
  \ name and description; KG created within current workspace;\n  user prompted to\
  \ add first data source after creation\"\n\n- **Requirement: Navigation Structure\
  \ — Scenario: New user landing**\n  The `/setup` redirect from task-140 lands here\
  \ — shows an empty state with a\n  prompt to create the first knowledge graph.\n\
  \n- **Requirement: Backend API Alignment — Scenario: Resource operations succeed\
  \ end-to-end**\n  KG creation: `POST /knowledge-graphs` with `workspace_id` from\
  \ tenant context.\n  KG listing: `GET /workspaces/{workspace_id}/knowledge-graphs`.\n\
  \n- **Requirement: Backend API Alignment — Scenario: Parent context is preserved**\n\
  \  `workspace_id` is always passed in create/list operations; derived from\n  `useTenantContext`.\n\
  \n- **Requirement: Interaction Principles — Scenario: Inline actions over navigation**\n\
  \  KG name/description can be edited in-place (inline edit) or via a side Sheet,\n\
  \  not a separate edit page.\n\n- **Requirement: Interaction Principles — Scenario:\
  \ Mutation feedback**\n  Toast confirms KG creation, update, and deletion.\n\n##\
  \ Key Design Decisions\n\n- **KG list page** (`/data/knowledge-graphs`): A card\
  \ grid listing all KGs in the\n  active workspace. Each card shows name, description,\
  \ data source count, and a\n  \"3-dot\" action menu (Edit, Delete). Clicking a card\
  \ navigates to the KG detail.\n- **KG detail page** (`/data/knowledge-graphs/{id}`):\
  \ Shows the KG metadata at top\n  (inline editable name/description), plus tabs\
  \ for Data Sources and Sync Status\n  (wired in task-147 and task-148 respectively).\n\
  - **KG creation flow**: A Sheet (side panel) with a two-field form (name, description).\n\
  \  On submit, `POST /knowledge-graphs` with the active `workspace_id`. On success,\n\
  \  show success toast and prompt \"Add your first data source\" (navigates to\n\
  \  `/data/data-sources/new?kg_id={id}`).\n- **Empty state**: When no KGs exist,\
  \ render a centered call-to-action card with\n  \"Create your first knowledge graph\"\
  \ button. This is the `/setup` target.\n- **Authorization**: The \"Create\" button\
  \ is only shown when the user has\n  `create` permission on the workspace (checked\
  \ via the backend response or\n  SpiceDB-checked list endpoint).\n\n## What Files\
  \ Are Affected\n\n- **New**: `src/ui/pages/data/knowledge-graphs/index.vue`\n- **New**:\
  \ `src/ui/pages/data/knowledge-graphs/[id].vue`\n- **New**: `src/ui/pages/setup.vue`\
  \ (new-user landing, wraps KG create)\n- **New**: `src/ui/components/kg/KgCard.vue`\n\
  - **New**: `src/ui/components/kg/KgCreateSheet.vue`\n- **New**: `src/ui/composables/useKnowledgeGraphs.ts`\n\
  - **New**: `src/ui/tests/unit/KgCard.test.ts`\n- **New**: `src/ui/tests/unit/KgCreateSheet.test.ts`\n\
  - **New**: `src/ui/tests/unit/useKnowledgeGraphs.test.ts`\n\n## How to Verify\n\n\
  ```bash\nmake instance-up\nsource .instances/$(basename $(pwd))/.env.instance\n\
  cd src/ui && npm run dev\n# 1. Navigate to /data/knowledge-graphs — list of KGs\
  \ in active workspace shown\n# 2. Click \"Create Knowledge Graph\" — Sheet opens\
  \ with name + description fields\n# 3. Submit form — KG created, toast appears,\
  \ prompt to add data source shown\n# 4. Navigate to /setup — empty state shown for\
  \ new users\n# 5. Edit KG name inline — patch request fires, UI updates without\
  \ page reload\n# 6. Delete KG — confirmation dialog, then list refreshes\n```\n\n\
  Unit tests:\n```bash\ncd src/ui && npm run test:unit -- kg\n# KgCard: renders name,\
  \ description, action menu\n# KgCreateSheet: validation (name required); submit\
  \ calls POST; success closes sheet\n# useKnowledgeGraphs: fetches from correct workspace\
  \ endpoint; handles 404\n```\n\n## Caveats\n\n- The KG detail page (`/data/knowledge-graphs/{id}`)\
  \ includes tabs for Data Sources\n  and Sync Status. These tabs are added as stubs\
  \ (empty panels) in this task and\n  filled in by task-147 and task-148.\n- KG deletion\
  \ requires a confirmation dialog (shadcn AlertDialog) to prevent\n  accidental data\
  \ loss.\n- The `GET /workspaces/{workspace_id}/knowledge-graphs` endpoint must return\
  \ KGs\n  scoped to the workspace. If this endpoint is not yet available, use\n \
  \ `GET /knowledge-graphs?workspace_id={id}` instead."
---
