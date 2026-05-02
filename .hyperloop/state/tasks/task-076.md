---
id: task-076
title: Mutations Console — test that permission=edit is passed to KG list API
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps:
- task-074
round: 0
branch: hyperloop/task-076
pr: https://github.com/openshift-hyperfleet/kartograph/pull/540
pr_title: 'test(ui): verify permission=edit query param in Mutations Console KG list
  API call'
pr_description: "## What & Why\n\nThe **Mutations Console — Scenario: Knowledge graph\
  \ selection** requirement in\n`experience.spec.md` states explicitly:\n\n> AND the\
  \ selector lists all knowledge graphs the user has `edit` permission on\n> within\
  \ the current workspace\n\nTask-074 added a workspace selector and verified that\
  \ `workspace_id` is passed\nas a query parameter to the KG list API call. The production\
  \ code at\n`src/dev-ui/app/pages/graph/mutations.vue` (line ~150) already passes\
  \ both\nparameters correctly:\n\n```typescript\n{ query: { permission: 'edit', workspace_id:\
  \ selectedWorkspaceId.value } },\n```\n\nHowever, `src/dev-ui/app/tests/mutations-workspace-selector.test.ts`\
  \ only\nverifies `workspace_id`:\n\n```typescript\nit('passes workspace_id to the\
  \ knowledge-graphs API call', () => {\n  // Spec: \"within the current workspace\"\
  \ — must filter the KG list by workspace\n  expect(mutVue).toMatch(/workspace_id|workspaceId/)\n\
  })\n```\n\nThe `permission: 'edit'` parameter is never verified in any test. Without\
  \ this\ntest, a developer could remove or change the permission parameter without\
  \ a failing\ntest — silently breaking the spec requirement that only KGs the user\
  \ can *edit* are\nshown (not all KGs they can *read*).\n\n## Spec Requirements Satisfied\n\
  \n**Requirement: Mutations Console — Scenario: Knowledge graph selection**\nfrom\
  \ `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\n> AND\
  \ the selector lists all knowledge graphs the user has `edit` permission on\n> within\
  \ the current workspace\n\nSpecifically the \"edit permission\" clause, which task-074\
  \ acknowledged in its\ndescription (`GET /management/knowledge-graphs?workspace_id={id}&permission=edit`)\n\
  but did not test.\n\n## Key Design Decisions\n\n- **Test file**: Extend `src/dev-ui/app/tests/mutations-workspace-selector.test.ts`\n\
  \  with one additional structural assertion in the existing\n  \"Mutations Console\
  \ — workspace selector structural checks\" describe block.\n\n- **Assertion**: `expect(mutVue).toContain(\"\
  permission: 'edit'\")` or\n  `expect(mutVue).toMatch(/permission.*edit|edit.*permission/)`\
  \ — either form\n  verifies the parameter is present in the source.\n\n- **No production\
  \ code change required**: The production code in `mutations.vue`\n  already passes\
  \ `permission: 'edit'`. This task adds only the missing test.\n\n- **Why `permission:\
  \ 'edit'` matters at the UI layer**: The backend uses SpiceDB\n  to enforce authorization\
  \ at submission time. But passing `permission: 'edit'` to\n  the management API\
  \ allows the backend to filter the returned list at *query* time\n  (showing only\
  \ editable KGs), which provides a better UX and prevents the user from\n  selecting\
  \ a KG they cannot edit only to receive a 403 at submission. The UI is\n  responsible\
  \ for sending this parameter correctly.\n\n## Files Affected\n\n- `src/dev-ui/app/tests/mutations-workspace-selector.test.ts`\
  \ — add one test\n  assertion to the \"workspace selector structural checks\" describe\
  \ block:\n\n  ```typescript\n  it('passes permission=edit to the knowledge-graphs\
  \ API call', () => {\n    // Spec: \"the selector lists all knowledge graphs the\
  \ user has `edit` permission on\"\n    // The UI must pass permission=edit so the\
  \ backend returns only KGs the user can edit.\n    expect(mutVue).toMatch(/permission.*edit|edit.*permission/)\n\
  \  })\n  ```\n\nNo other files are changed.\n\n## How to Verify\n\n1. Run `cd src/dev-ui\
  \ && pnpm test` — new test passes green.\n2. Temporarily change `permission: 'edit'`\
  \ in `mutations.vue` to `permission: 'read'`\n   — the new test turns red.\n3. Restore\
  \ the original value — test goes green again.\n\n## TDD Cycle\n\n1. Add the test\
  \ to `mutations-workspace-selector.test.ts` (GREEN immediately,\n   since the production\
  \ code already has `permission: 'edit'`).\n2. Optionally do a mutation test (change\
  \ to `'read'` → red; restore → green).\n3. Commit atomically.\n\n## Caveats\n\n\
  - This task depends on task-074 landing first, as this task extends the test\n \
  \ file that task-074 introduces.\n- If a future task changes the permission model\
  \ (e.g., removes client-side\n  permission filtering entirely), this test will serve\
  \ as an explicit reminder\n  that removing `permission: 'edit'` is a spec-breaking\
  \ change.\n- The change is a single test assertion (< 10 lines). No architectural\
  \ review needed."
---
