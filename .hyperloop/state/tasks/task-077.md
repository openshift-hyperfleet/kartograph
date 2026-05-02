---
id: task-077
title: Management API — add workspace_id filter to GET /management/knowledge-graphs
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps: []
round: 0
branch: hyperloop/task-077
pr: https://github.com/openshift-hyperfleet/kartograph/pull/541
pr_title: 'feat(management): add optional workspace_id filter to knowledge-graphs
  list endpoint'
pr_description: "## What & Why\n\nThe Mutations Console UI (task-074) must satisfy\
  \ this spec clause:\n\n> AND the selector lists all knowledge graphs the user has\
  \ `edit` permission on\n> **within the current workspace**\n\nThe UI already calls:\n\
  \n```\nGET /management/knowledge-graphs?workspace_id={id}&permission=edit\n```\n\
  \n(`src/dev-ui/app/pages/graph/mutations.vue`, line ~149, includes a `TODO` comment\n\
  acknowledging this backend dependency.)\n\nHowever, the `GET /management/knowledge-graphs`\
  \ route currently only accepts\n`?permission=view|edit`. The `workspace_id` query\
  \ parameter is silently ignored by\nFastAPI (not a declared parameter), so the endpoint\
  \ returns **all editable KGs in the\ntenant** regardless of the workspace filter.\
  \ The spec clause — \"within the current\nworkspace\" — is therefore not satisfied\
  \ end-to-end.\n\nThis PR adds optional `workspace_id` query parameter support to\n\
  `GET /management/knowledge-graphs`. When provided, the response is filtered to\n\
  knowledge graphs belonging to that workspace that the user also has the requested\n\
  permission on.\n\n## Spec Requirements Satisfied\n\n**Requirement: Mutations Console\
  \ — Scenario: Knowledge graph selection**\nfrom `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> AND the selector lists all knowledge graphs the user has `edit` permission on\n\
  > within the current workspace\n\nThe \"within the current workspace\" clause requires\
  \ the backend to support\nworkspace-scoped + permission-filtered KG listing simultaneously.\n\
  \n**Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**\n\
  \nThe UI passes `workspace_id` to this endpoint. Without backend support, the\n\"\
  corresponding backend API call succeeds\" clause fails to return the correct\nworkspace-scoped\
  \ results even when the HTTP status is 200.\n\n## Key Design Decisions\n\n- **New\
  \ service method `list_for_workspace_with_permission`**: Rather than modifying\n\
  \  the existing `list_for_workspace` (which is called from the workspace-scoped\
  \ route\n  and has different semantics — it checks workspace VIEW permission first,\
  \ then returns\n  all KGs in the workspace), a new method combines workspace membership\
  \ discovery with\n  per-KG permission filtering. This preserves the SRP of each\
  \ existing method.\n\n- **Route change is additive (no breaking change)**: The `workspace_id`\
  \ parameter is\n  optional (`Optional[str] = None`). When absent, existing behaviour\
  \ is unchanged\n  (`list_all` is called). When present, the new `list_for_workspace_with_permission`\n\
  \  method is called.\n\n- **Workspace membership check**: The new method reuses\
  \ the same SpiceDB\n  `read_relationships` pattern from `list_for_workspace` to\
  \ discover KG IDs linked to\n  the workspace, then applies per-KG permission filtering\
  \ (same loop as `list_all`).\n  No new SpiceDB calls are added beyond what already\
  \ exists.\n\n- **Authorization model**: The caller does NOT need VIEW permission\
  \ on the workspace\n  (unlike `list_for_workspace`). SpiceDB per-KG permission checks\
  \ are sufficient\n  — a user with `edit` on a KG in workspace W can see that KG\
  \ in the mutations\n  console KG selector regardless of their workspace-level role.\n\
  \n- **Probe instrumentation**: The existing `knowledge_graphs_listed` probe is called\n\
  \  with `workspace_id` so DOO tracing captures the workspace scope.\n\n## Files\
  \ Affected\n\n- `src/api/management/application/services/knowledge_graph_service.py`\
  \ — add\n  `list_for_workspace_with_permission(user_id, workspace_id, permission)`\
  \ method.\n- `src/api/management/presentation/knowledge_graphs/routes.py` — add\n\
  \  `workspace_id: Optional[str] = None` query parameter to\n  `list_knowledge_graphs`;\
  \ route to new service method when workspace_id is provided.\n- `src/api/tests/unit/management/test_knowledge_graph_service.py`\
  \ (or equivalent\n  unit test file) — new tests for `list_for_workspace_with_permission`.\n\
  - `src/api/tests/integration/management/test_knowledge_graphs_routes.py` (or\n \
  \ equivalent integration test file) — new integration tests for the `?workspace_id=`\n\
  \  filter on the list endpoint.\n\n## How to Verify\n\n1. Run `make test-unit` —\
  \ new unit tests for `list_for_workspace_with_permission`\n   pass green.\n2. Start\
  \ the dev instance (`make dev` or `make instance-up`) and run\n   `make test-integration`\
  \ — new route tests pass.\n3. Call `GET /management/knowledge-graphs?workspace_id=<a_real_ws_id>&permission=edit`\n\
  \   — verify only KGs in that workspace with edit permission are returned.\n4. Call\
  \ `GET /management/knowledge-graphs?permission=edit` (no workspace_id) — verify\n\
  \   all tenant-wide editable KGs are returned (unchanged behaviour).\n5. Navigate\
  \ to the Mutations Console in the dev UI, select a workspace — verify the\n   KG\
  \ dropdown is populated only with KGs from that workspace.\n6. Remove the `TODO`\
  \ comment from `mutations.vue` line ~147.\n\n## TDD Cycle\n\n1. Write unit tests\
  \ for `list_for_workspace_with_permission` (RED).\n2. Implement `list_for_workspace_with_permission`\
  \ in the service (GREEN).\n3. Write integration test for the route with `?workspace_id=`\
  \ (RED).\n4. Update the route to accept `workspace_id` and call the new service\
  \ method (GREEN).\n5. Run full test suite: `make test-unit && make test-integration`.\n\
  6. Commit atomically.\n\n## Caveats\n\n- If the `workspace_id` provided does not\
  \ exist or the user has no KGs with the\n  requested permission in that workspace,\
  \ return an empty list (not 403 or 404).\n  This matches the filtering semantics\
  \ of `list_all`: missing or inaccessible items\n  are silently excluded, not rejected.\n\
  - The existing `GET /management/workspaces/{workspace_id}/knowledge-graphs` route\n\
  \  is unchanged. It continues to check VIEW permission on the workspace and return\n\
  \  all visible KGs — suitable for the Workspace Management page. This PR targets\n\
  \  the tenant-level listing route only.\n- This task unblocks task-074 (Mutations\
  \ Console workspace-scoped KG selector).\n  task-074's TODO comment in `mutations.vue`\
  \ can be removed once this PR lands."
---
