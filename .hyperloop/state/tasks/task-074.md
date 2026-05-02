---
id: task-074
title: Mutations Console — workspace-scoped KG selector (workspace picker before KG
  picker)
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps:
- task-065
round: 0
branch: hyperloop/task-074
pr: null
pr_title: 'feat(ui): add workspace selector to Mutations Console — scope KG list to
  current workspace'
pr_description: "## What & Why\n\nThe **Mutations Console — Scenario: Knowledge graph\
  \ selection** in `experience.spec.md`\ncontains a precision requirement that task-065\
  \ does not address:\n\n> AND the selector lists all knowledge graphs the user has\
  \ `edit` permission on\n> **within the current workspace**\n\nTask-065 populates\
  \ the KG dropdown using `GET /management/knowledge-graphs?permission=edit`,\nwhich\
  \ is a tenant-wide listing (all KGs the user can edit across every workspace in\
  \ the\ntenant). This matches the **Query Console** scope (\"span all knowledge graphs\
  \ the user can\naccess in the tenant\") but does NOT match the Mutations Console\
  \ spec, which explicitly\nconstrains the listing to \"within the current workspace.\"\
  \n\nWithout workspace scoping, a user with access to KGs in five different workspaces\
  \ would\nsee all five in the dropdown and could submit mutations to a KG in the\
  \ wrong workspace\n— a potentially dangerous cross-context mutation.\n\nThis task\
  \ adds a workspace selector that appears **before** the KG dropdown in the Mutations\n\
  Console and filters the KG list to only those belonging to the selected workspace.\n\
  \n## Spec Requirements Satisfied\n\n**Requirement: Mutations Console — Scenario:\
  \ Knowledge graph selection**\nfrom `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> GIVEN the mutations console\n> THEN a knowledge graph selector is displayed\
  \ before the user can submit\n> AND the selector lists all knowledge graphs the\
  \ user has `edit` permission on\n>   **within the current workspace**\n> AND no\
  \ submission is possible until a knowledge graph is selected\n> AND the selected\
  \ knowledge graph is used as the target for the mutation submission\n\nThe \"within\
  \ the current workspace\" clause is the specific constraint addressed here.\n\n\
  ## Key Design Decisions\n\n- **Two-selector flow**: A workspace dropdown appears\
  \ above the KG dropdown. Until a\n  workspace is selected the KG list is empty and\
  \ disabled. Once a workspace is selected\n  the KG list is populated with `GET /management/knowledge-graphs?workspace_id={id}&permission=edit`.\n\
  \  Selecting a workspace resets the KG selection (prevents stale cross-workspace\
  \ selection).\n\n- **Workspace list source**: `GET /management/workspaces` — the\
  \ same endpoint used by\n  the Workspaces management page. The list is filtered\
  \ to workspaces the user belongs to.\n  The workspace list reloads on tenant switch\
  \ (mirrors the KG list behaviour from task-065).\n\n- **API endpoint**: The management\
  \ API for knowledge graphs is expected to accept a\n  `workspace_id` query parameter.\
  \ If the backend does not yet support this filter, the\n  composable should be written\
  \ with the query param in place and the task notes this as\n  a backend dependency.\
  \ The UI should NOT fall back to unfiltered results silently — it\n  should show\
  \ the workspace-filtered list (or an empty list if no KGs exist in that workspace).\n\
  \n- **Submit gating**: Submission requires BOTH workspace AND KG to be selected.\n\
  \  `canSubmitMutations` is updated to include `!!selectedWorkspaceId && !!selectedKgId`.\n\
  \  The tooltip/toast for the disabled state distinguishes \"select a workspace first\"\
  \ from\n  \"select a knowledge graph\".\n\n- **UX label**: The workspace selector\
  \ appears above the KG selector with label\n  \"Workspace\" and placeholder \"Select\
  \ a workspace\". The KG selector label changes to\n  \"Knowledge Graph\" with placeholder\
  \ \"Select a knowledge graph\" (no change). This matches\n  the two-step Create\
  \ Knowledge Graph flow (task-040).\n\n- **Tenant switch**: Both workspace and KG\
  \ selections are cleared on tenant switch.\n\n- **Interaction principles**: Progressive\
  \ disclosure — KG selector is rendered but\n  disabled until a workspace is chosen,\
  \ communicating the dependency without hiding elements.\n\n## Files Affected\n\n\
  - `src/dev-ui/app/pages/graph/mutations.vue` — add `selectedWorkspaceId` / `workspaces`\n\
  \  state; add workspace `<Select>` above KG selector; gate KG list on workspace\
  \ selection;\n  update `canSubmitMutations` call and toast messages.\n- `src/dev-ui/app/composables/api/useIamApi.ts`\
  \ — verify `listWorkspaces()` is usable\n  here (it already exists for the layout);\
  \ expose or import for the mutations page.\n- `src/dev-ui/app/utils/mutationConsole.ts`\
  \ — update `canSubmitMutations` signature to\n  require `selectedWorkspaceId: string`\
  \ and gate on it alongside `selectedKnowledgeGraphId`.\n- `src/dev-ui/app/tests/mutations-workspace-selector.test.ts`\
  \ — new TDD-first test file\n  covering all scenario clauses.\n\n## How to Verify\n\
  \n1. Navigate to `/graph/mutations` with mutations content ready.\n2. Verify the\
  \ Apply Mutations button is **disabled** with no workspace selected.\n3. Open the\
  \ workspace dropdown — workspaces from the current tenant appear.\n4. Select a workspace\
  \ — the KG dropdown becomes enabled and lists only KGs in that workspace.\n5. Select\
  \ a KG — Apply Mutations becomes enabled.\n6. Submit — verify the API call uses\
  \ the selected KG ID (network tab).\n7. Switch tenant — both workspace and KG selections\
  \ are cleared.\n8. Select workspace A, then switch to workspace B — KG selection\
  \ is cleared and the KG\n   list reloads.\n9. Run `cd src/dev-ui && pnpm test` —\
  \ all tests in `mutations-workspace-selector.test.ts`\n   pass; no regressions in\
  \ `mutations-console.test.ts` or `mutations-kg-selector.test.ts`.\n\n## Caveats\n\
  \n- Depends on task-065 landing first, as this task modifies the same KG selector\
  \ state\n  and `canSubmitMutations` utility that task-065 introduces.\n- If the\
  \ backend management API does not yet support `?workspace_id=` filtering on\n  `GET\
  \ /management/knowledge-graphs`, the API composable should be written with the\n\
  \  parameter in place (ready for when the backend adds it). A TODO comment should\
  \ be left\n  so the backend team knows this filter is expected.\n- The workspace\
  \ list is the full list of workspaces accessible to the user in the tenant.\n  If\
  \ workspace-level permission checking is needed (e.g., only workspaces where the\
  \ user\n  has `edit` on at least one KG), that can be addressed in a follow-up task.\
  \ For now,\n  show all workspaces and let the KG list naturally be empty if none\
  \ are accessible.\n"
---
