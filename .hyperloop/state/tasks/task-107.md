---
id: task-107
title: 'Backend API alignment audit: verify and fix all CRUD operations with parent-context
  scoping'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps: []
round: 0
branch: hyperloop/task-107
pr: https://github.com/openshift-hyperfleet/kartograph/pull/572
pr_title: 'fix(ui): backend API alignment — correct parent-context scoping for all
  CRUD operations'
pr_description: "## What & Why\n\nThe **Backend API Alignment** requirement in `specs/ui/experience.spec.md`\
  \ states:\n\n> \"GIVEN a user performs any create, read, update, or delete operation\
  \ via the UI\n> WHEN the operation is submitted THEN the corresponding backend API\
  \ call succeeds\n> (2xx response) AND the UI reflects the updated state without\
  \ requiring a manual\n> refresh\"\n\n> \"GIVEN a resource that is scoped to a parent\
  \ (e.g., a knowledge graph within a\n> workspace) WHEN the user creates or lists\
  \ that resource THEN the UI includes the\n> parent context required by the API AND\
  \ the operation succeeds\"\n\nThe dev-ui frontend has grown organically alongside\
  \ backend API development. Some\npages still use stale endpoint paths, missing required\
  \ request body fields, or\nomit parent-context identifiers (e.g., creating a knowledge\
  \ graph without a\n`workspace_id`, or listing data sources without a `knowledge_graph_id`).\
  \ This\ncauses silent failures or broken UI state.\n\nThis task is a focused audit-and-fix\
  \ pass across all UI CRUD operations to ensure\nevery frontend call matches the\
  \ current backend API contract.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n\
  - **Requirement: Backend API Alignment** — Scenario: *Resource operations succeed\
  \ end-to-end*\n- **Requirement: Backend API Alignment** — Scenario: *Parent context\
  \ is preserved*\n\n## What This Change Does\n\n### Audit Process\n\nFor each page\
  \ and its CRUD operations, verify:\n1. The HTTP method and endpoint path match `GET\
  \ /openapi.json` or backend route\n   definitions in `src/api/`.\n2. All required\
  \ request body fields are sent (check against Pydantic schemas).\n3. All required\
  \ parent-context path parameters are included (e.g.,\n   `workspace_id`, `knowledge_graph_id`).\n\
  4. After a successful write, the UI's reactive state is updated without a full\n\
  \   page reload (optimistic update or re-fetch).\n5. Error responses (4xx, 5xx)\
  \ are caught and surfaced to the user via toast.\n\n### Pages to Audit\n\n| Page\
  \ | Key Operations | Known Risk |\n|------|---------------|------------|\n| `/knowledge-graphs`\
  \ | Create KG, List KGs | `workspace_id` required in create body |\n| `/data-sources`\
  \ | Create DS, List DS, Delete DS | `knowledge_graph_id` scoping |\n| `/workspaces`\
  \ | Create workspace, List workspaces | `parent_workspace_id` (optional) |\n| `/groups`\
  \ | Create group, Add member, Remove member | Member role field |\n| `/api-keys`\
  \ | Create key, Revoke key | `expires_at` format |\n| `/tenants` | List tenants,\
  \ Create tenant | Tenant-level operations |\n| `/query` | Execute query | `knowledge_graph_id`\
  \ optional param |\n| `/graph/mutations` | Submit mutations | `knowledge_graph_id`\
  \ required |\n| `/graph/schema` | Fetch ontology | Tenant-scoped endpoint |\n| `/graph/explorer`\
  \ | Search nodes, Get neighbors | Correct AGE graph param |\n\n### Fixes Expected\n\
  \nBased on prior task history (task-040 fixed KG creation workspace scoping), the\n\
  following are likely still broken:\n- Data source create/list: parent `knowledge_graph_id`\
  \ may be hardcoded or missing\n- Mutations console submit: `knowledge_graph_id`\
  \ body field alignment with backend\n- API key revoke: PATCH vs DELETE method check\n\
  \nEach fix follows the pattern: update the API call in the composable or page,\n\
  confirm the backend accepts the corrected request, add or update a test.\n\n###\
  \ Reactive State After Write\n\nFor each write operation, verify the list/detail\
  \ view updates without a reload:\n- Preferred: mutate the reactive state directly\
  \ after a successful response\n  (e.g., push the new item into the list array, or\
  \ splice the deleted item out)\n- Acceptable: re-fetch the list from the API after\
  \ the write (if the list is\n  small and the extra request is negligible)\n\n##\
  \ Files / Areas Affected\n\n- `src/dev-ui/app/composables/` — API client composables\
  \ (one per resource domain)\n- `src/dev-ui/app/pages/` — page components that call\
  \ CRUD operations\n- `src/dev-ui/app/types/` — TypeScript type definitions (align\
  \ with backend schemas)\n\n## Tests\n\nVitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:\n\
  - One test per CRUD operation verifying the correct HTTP method, path, and body\n\
  \  fields are sent (use `vi.mock` or `msw` to intercept API calls):\n  - `test_kg_create_includes_workspace_id_in_body`\n\
  \  - `test_data_source_list_includes_kg_id_param`\n  - `test_mutations_submit_includes_kg_id`\n\
  \  - `test_api_key_revoke_uses_correct_method_and_path`\n  - _(one test per page/operation\
  \ identified in the audit)_\n- `test_write_operation_updates_reactive_list_without_reload`:\
  \ after a create\n  call, assert the new item appears in the list without navigating\
  \ away or\n  manually refreshing\n\n## How to Verify\n\n1. Start a full dev instance:\
  \ `make dev`\n2. For each page in the audit table above:\n   - Open the browser\
  \ DevTools Network tab\n   - Perform the create, list, update, and delete operations\n\
  \   - Confirm each request returns 2xx\n   - Confirm the UI updates reactively without\
  \ a reload\n3. Check the browser console for any uncaught API errors\n\n## Caveats\n\
  \n- This task is an audit-and-fix pass, not a feature addition. If a bug is\n  discovered\
  \ that requires a new backend endpoint, open a separate task for\n  the backend\
  \ change rather than expanding scope here.\n- Some parent-context scoping depends\
  \ on the active tenant/workspace being\n  set in global state (see task-102). Verify\
  \ that the global state is\n  correctly initialized before making API calls.\n-\
  \ The Ingestion context (sync operations) is intentionally excluded from this\n\
  \  audit since the backend is not yet implemented."
---
