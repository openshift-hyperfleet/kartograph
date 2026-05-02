---
id: task-084
title: 'UI — Backend API Alignment: explicit test coverage for end-to-end integration
  scenarios'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps: []
round: 0
branch: hyperloop/task-084
pr: https://github.com/openshift-hyperfleet/kartograph/pull/548
pr_title: 'test(ui): add explicit tests for Backend API Alignment spec scenarios'
pr_description: "## What & Why\n\nThe `specs/ui/experience.spec.md` was modified to\
  \ add a new top-level requirement:\n\n> **Requirement: Backend API Alignment**\n\
  > The system SHALL successfully complete all resource operations by correctly\n\
  > integrating with the backend REST API.\n\nThis requirement introduces two verifiable\
  \ scenarios:\n\n1. **Resource operations succeed end-to-end** — after any create/update/delete,\n\
  \   the backend call succeeds and the UI automatically reflects the updated state\n\
  \   (no manual refresh needed).\n\n2. **Parent context is preserved** — when a resource\
  \ is scoped to a parent (e.g.,\n   a knowledge graph within a workspace), the UI\
  \ includes the parent ID in the API\n   call in the form the backend requires.\n\
  \nThe underlying code already satisfies these scenarios — KG creation uses the\n\
  workspace-scoped URL path, data source creation uses the KG-scoped URL path, and\n\
  all mutating operations reload the list on success. However, **no test currently\n\
  exists that is explicitly named and structured around these spec scenarios**. The\n\
  TDD mandate requires a test for every spec scenario; without them the spec's\ncoverage\
  \ is formally incomplete.\n\nThis PR adds a dedicated test file (`tests/api-alignment.test.ts`)\
  \ that maps\ndirectly to the spec's two scenarios with named `describe` blocks matching\
  \ the\nGIVEN/WHEN/THEN structure.\n\n## Spec Requirements Satisfied\n\n**Requirement:\
  \ Backend API Alignment** from\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- Scenario: Resource operations succeed end-to-end\n- Scenario: Parent context\
  \ is preserved\n\n## Key Design Decisions\n\n- **Pure unit tests** — all tests use\
  \ `vi.fn()` mocks; no infrastructure needed.\n  The goal is to formally document\
  \ and verify the API contract, not re-test the\n  backend.\n\n- **Named after the\
  \ spec scenarios** — `describe` blocks use wording from the\n  spec so a future\
  \ reader can trace failing tests directly to the requirement.\n\n- **Covers all\
  \ parent-scoped create operations**:\n  - `POST /management/workspaces/{workspace_id}/knowledge-graphs`\
  \ (KG creation)\n  - `POST /management/knowledge-graphs/{knowledge_graph_id}/data-sources`\n\
  \    (data source creation)\n  - `POST /management/data-sources/{data_source_id}/sync`\
  \ (sync trigger)\n\n- **Covers UI-refresh-after-mutation**:\n  - After KG create/edit/delete,\
  \ `loadKnowledgeGraphs()` is called ✅\n  - After workspace create/delete, list is\
  \ reloaded ✅\n  - After API key create/revoke, list is reloaded ✅\n  - After data\
  \ source create, list is reloaded ✅\n\n- **No changes to production code** — all\
  \ gaps are in test coverage only;\n  the implementation is correct.\n\n## Files\
  \ Affected\n\n- `src/dev-ui/app/tests/api-alignment.test.ts` — new test file with\
  \ two `describe`\n  groups mapping to the spec's two Backend API Alignment scenarios.\n\
  \n## How to Verify\n\n```bash\ncd src/dev-ui && npm run test -- api-alignment\n\
  # All tests pass, no regressions.\n```\n\n## TDD Cycle\n\n1. Write tests for \"\
  Resource operations succeed end-to-end\":\n   - KG create: mock apiFetch → resolves\
  \ → verify list reload called → RED\n   - KG edit: same pattern → RED\n   - KG delete:\
  \ same pattern → RED\n   - Data source create: POST to KG-scoped path → list reload\
  \ → RED\n   - API key create: POST → list reload → RED\n   - Workspace create: POST\
  \ → list reload → RED\n2. Write tests for \"Parent context is preserved\":\n   -\
  \ KG creation URL includes workspace_id → RED\n   - Data source creation URL includes\
  \ knowledge_graph_id → RED\n   - Sync trigger URL includes data_source_id → RED\n\
  3. Confirm existing production code satisfies all tests → GREEN\n4. Commit atomically\
  \ with conventional message.\n\n## Caveats\n\n- Integration-level verification (actual\
  \ HTTP 2xx from the running backend) is out\n  of scope for unit tests; that is\
  \ covered by CI integration test runs.\n- This task deliberately does NOT modify\
  \ production Vue files — it is test-only.\n  If a test fails RED against existing\
  \ code, a separate bug-fix task should be\n  raised before this task is merged."
---
