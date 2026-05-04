---
id: task-146
title: "UI Knowledge Graph Management — list, create, workspace context"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-140]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add knowledge graph management pages with workspace-scoped creation"
pr_description: |
  ## What and Why

  Knowledge Graphs are the central organizing concept of Kartograph. Before users can
  query, explore, or ingest data, they need at least one KG. This task builds the KG
  list page and the KG creation flow, properly scoped to the active workspace. It also
  surfaces the "new user" prompt (no KGs yet) that task-140's landing logic redirects
  new users to.

  This corresponds to `Data → Knowledge Graphs` in the sidebar.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Knowledge Graph Creation — Scenario: Create knowledge graph**
    "user provides name and description; KG created within current workspace;
    user prompted to add first data source after creation"

  - **Requirement: Navigation Structure — Scenario: New user landing**
    The `/setup` redirect from task-140 lands here — shows an empty state with a
    prompt to create the first knowledge graph.

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    KG creation: `POST /knowledge-graphs` with `workspace_id` from tenant context.
    KG listing: `GET /workspaces/{workspace_id}/knowledge-graphs`.

  - **Requirement: Backend API Alignment — Scenario: Parent context is preserved**
    `workspace_id` is always passed in create/list operations; derived from
    `useTenantContext`.

  - **Requirement: Interaction Principles — Scenario: Inline actions over navigation**
    KG name/description can be edited in-place (inline edit) or via a side Sheet,
    not a separate edit page.

  - **Requirement: Interaction Principles — Scenario: Mutation feedback**
    Toast confirms KG creation, update, and deletion.

  ## Key Design Decisions

  - **KG list page** (`/data/knowledge-graphs`): A card grid listing all KGs in the
    active workspace. Each card shows name, description, data source count, and a
    "3-dot" action menu (Edit, Delete). Clicking a card navigates to the KG detail.
  - **KG detail page** (`/data/knowledge-graphs/{id}`): Shows the KG metadata at top
    (inline editable name/description), plus tabs for Data Sources and Sync Status
    (wired in task-147 and task-148 respectively).
  - **KG creation flow**: A Sheet (side panel) with a two-field form (name, description).
    On submit, `POST /knowledge-graphs` with the active `workspace_id`. On success,
    show success toast and prompt "Add your first data source" (navigates to
    `/data/data-sources/new?kg_id={id}`).
  - **Empty state**: When no KGs exist, render a centered call-to-action card with
    "Create your first knowledge graph" button. This is the `/setup` target.
  - **Authorization**: The "Create" button is only shown when the user has
    `create` permission on the workspace (checked via the backend response or
    SpiceDB-checked list endpoint).

  ## What Files Are Affected

  - **New**: `src/ui/pages/data/knowledge-graphs/index.vue`
  - **New**: `src/ui/pages/data/knowledge-graphs/[id].vue`
  - **New**: `src/ui/pages/setup.vue` (new-user landing, wraps KG create)
  - **New**: `src/ui/components/kg/KgCard.vue`
  - **New**: `src/ui/components/kg/KgCreateSheet.vue`
  - **New**: `src/ui/composables/useKnowledgeGraphs.ts`
  - **New**: `src/ui/tests/unit/KgCard.test.ts`
  - **New**: `src/ui/tests/unit/KgCreateSheet.test.ts`
  - **New**: `src/ui/tests/unit/useKnowledgeGraphs.test.ts`

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/ui && npm run dev
  # 1. Navigate to /data/knowledge-graphs — list of KGs in active workspace shown
  # 2. Click "Create Knowledge Graph" — Sheet opens with name + description fields
  # 3. Submit form — KG created, toast appears, prompt to add data source shown
  # 4. Navigate to /setup — empty state shown for new users
  # 5. Edit KG name inline — patch request fires, UI updates without page reload
  # 6. Delete KG — confirmation dialog, then list refreshes
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- kg
  # KgCard: renders name, description, action menu
  # KgCreateSheet: validation (name required); submit calls POST; success closes sheet
  # useKnowledgeGraphs: fetches from correct workspace endpoint; handles 404
  ```

  ## Caveats

  - The KG detail page (`/data/knowledge-graphs/{id}`) includes tabs for Data Sources
    and Sync Status. These tabs are added as stubs (empty panels) in this task and
    filled in by task-147 and task-148.
  - KG deletion requires a confirmation dialog (shadcn AlertDialog) to prevent
    accidental data loss.
  - The `GET /workspaces/{workspace_id}/knowledge-graphs` endpoint must return KGs
    scoped to the workspace. If this endpoint is not yet available, use
    `GET /knowledge-graphs?workspace_id={id}` instead.
---
