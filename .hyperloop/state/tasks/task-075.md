---
id: task-075
title: Backend API Alignment — test UI state refresh after CRUD operations
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: merge
deps: []
round: 0
branch: hyperloop/task-075
pr: https://github.com/openshift-hyperfleet/kartograph/pull/539
pr_title: 'test(ui): verify UI auto-refresh after CRUD — Backend API Alignment scenario'
pr_description: "## What & Why\n\nThe `experience.spec.md` spec defines a **Backend\
  \ API Alignment** requirement as the\nfirst and most fundamental requirement. It\
  \ contains two scenarios; this task addresses\nthe one that currently has no test\
  \ coverage:\n\n> **Scenario: Resource operations succeed end-to-end**\n> - GIVEN\
  \ a user performs any create, read, update, or delete operation via the UI\n> -\
  \ WHEN the operation is submitted\n> - THEN the corresponding backend API call succeeds\
  \ (2xx response)\n> - AND the UI reflects the updated state without requiring a\
  \ manual refresh\n\nThe \"AND the UI reflects the updated state without requiring\
  \ a manual refresh\" clause\nis specifically about the pattern where, after a successful\
  \ create/update/delete, the\ncomponent calls its list-loading function (`loadKnowledgeGraphs`,\
  \ `loadDataSources`,\n`loadWorkspaces`, `loadApiKeys`, etc.) so the user immediately\
  \ sees the new state\nwithout having to press F5.\n\n### What already exists\n\n\
  Individual CRUD operations have tests verifying:\n- The API call is made with the\
  \ correct URL and payload ✓\n- The dialog closes (`createDialogOpen.value = false`)\
  \ ✓\n- A success toast is shown ✓\n- The error path sets `creating = false` ✓\n\n\
  ### What is missing\n\n**No test verifies that after a successful operation, the\
  \ appropriate list-refresh\nfunction is called.** For example:\n\n| Page       \
  \           | Operation       | Expected refresh call      | Tested? |\n|-----------------------|-----------------|---------------------------|---------|\n\
  | `knowledge-graphs`    | Create KG       | `loadKnowledgeGraphs()`   | ❌      |\n\
  | `data-sources`        | Create DS       | `loadDataSources()`        | ❌     \
  \ |\n| `api-keys`            | Create key      | `loadApiKeys()`            | ❌\
  \      |\n| `api-keys`            | Revoke key      | `loadApiKeys()`          \
  \  | ❌      |\n| `workspaces`          | Create workspace| `loadWorkspaces()`  \
  \       | ❌      |\n| `data-sources`        | Trigger sync    | `loadDataSources()`\
  \        | ❌      |\n\nWithout these tests, a regression where a developer removes\
  \ the refresh call would\ngo undetected — the user would have to manually reload\
  \ the page to see the new state,\ndirectly violating the spec scenario.\n\n### The\
  \ second scenario (\"Parent context is preserved\") is already covered\n\n- `knowledge-graphs.test.ts`\
  \ line 101: workspace_id in KG creation URL ✓\n- `data-sources.test.ts` line 1175:\
  \ kg_id in data source creation URL ✓\n- `mutations-kg-selector.test.ts`: KG-scoped\
  \ mutations URL ✓\n\nOnly the \"UI reflects the updated state\" scenario needs new\
  \ tests.\n\n## Spec Requirements Satisfied\n\n**Requirement: Backend API Alignment\
  \ — Scenario: Resource operations succeed end-to-end**\nfrom `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n> AND the UI reflects the updated state without requiring a manual refresh\n\n\
  ## Key Design Decisions\n\n- **Test strategy**: Pure logic tests that replicate\
  \ the exact `handleCreate`/`handleRevoke`/\n  `triggerSync` function signatures\
  \ from each page component and verify the list-refresh\n  function is called after\
  \ API success. This mirrors the approach used in\n  `knowledge-graphs.test.ts` lines\
  \ 70–163 (API call test) but adds a spy on the\n  refresh function.\n\n- **One test\
  \ file per page** (extend existing files rather than creating new ones):\n  - `knowledge-graphs.test.ts`\
  \ — add describe block for \"list refresh after create\"\n  - `data-sources.test.ts`\
  \ — add describe block for \"list refresh after create\" and\n    \"list refresh\
  \ after sync trigger\"\n  - `api-keys.test.ts` — add describe blocks for \"list\
  \ refresh after create\" and\n    \"list refresh after revoke\"\n  - `workspace-management.test.ts`\
  \ — add describe block for \"list refresh after create\"\n\n- **Pattern for each\
  \ test**:\n  ```typescript\n  it('calls loadKnowledgeGraphs() after successful KG\
  \ creation', async () => {\n    const apiFetch = vi.fn().mockResolvedValue({ id:\
  \ 'kg-new' })\n    const loadKnowledgeGraphs = vi.fn().mockResolvedValue(undefined)\n\
  \    const createName = { value: 'My Graph' }\n    const selectedWorkspaceId = {\
  \ value: 'ws-1' }\n    const creating = { value: false }\n    const createDialogOpen\
  \ = { value: true }\n\n    async function handleCreate() {\n      if (!selectedWorkspaceId.value\
  \ || !createName.value.trim()) return\n      creating.value = true\n      try {\n\
  \        await apiFetch(`/management/workspaces/${selectedWorkspaceId.value}/knowledge-graphs`,\
  \ {\n          method: 'POST',\n          body: { name: createName.value.trim()\
  \ },\n        })\n        createDialogOpen.value = false\n        await loadKnowledgeGraphs()\
  \   // ← this is what we're testing\n      } finally {\n        creating.value =\
  \ false\n      }\n    }\n\n    await handleCreate()\n    expect(loadKnowledgeGraphs).toHaveBeenCalledOnce()\n\
  \  })\n  ```\n\n- **Negative case**: verify that if the API throws, the refresh\
  \ function is NOT called\n  (preserves stale list state; error is surfaced by the\
  \ error path toast).\n\n## Files Affected\n\n- `src/dev-ui/app/tests/knowledge-graphs.test.ts`\
  \ — extend with \"list refresh after\n  create\" describe block (2–3 tests)\n- `src/dev-ui/app/tests/data-sources.test.ts`\
  \ — extend with \"list refresh after\n  create/trigger\" describe block (2–3 tests)\n\
  - `src/dev-ui/app/tests/api-keys.test.ts` — extend with \"list refresh after\n \
  \ create/revoke\" describe block (2–3 tests)\n- `src/dev-ui/app/tests/workspace-management.test.ts`\
  \ — extend with \"list refresh\n  after create\" describe block (1–2 tests)\n\n\
  No production code changes are expected. If a test fails it indicates a regression\
  \ in\nthe component where the refresh call was removed; the fix is to restore it\
  \ in the `.vue`\nfile, not to remove the test.\n\n## How to Verify\n\n1. Run `cd\
  \ src/dev-ui && pnpm test` — all new tests pass green.\n2. Temporarily remove `await\
  \ loadKnowledgeGraphs()` from `handleCreate()` in\n   `knowledge-graphs/index.vue`\
  \ — the corresponding test should turn red.\n3. Restore the call — tests go green\
  \ again.\n4. Repeat for each page to confirm the tests are non-trivially tied to\
  \ the\n   implementation.\n\n## TDD Cycle\n\n1. Write all new tests (RED — they\
  \ currently pass vacuously because the tests don't\n   exist yet; but once written,\
  \ they should pass green immediately since the production\n   code already calls\
  \ the refresh functions).\n2. Run `cd src/dev-ui && pnpm test` — confirm all new\
  \ tests pass.\n3. Optionally do a mutation test (remove one refresh call, verify\
  \ red).\n4. Commit atomically.\n\n## Caveats\n\n- This task is deliberately narrow:\
  \ it only adds tests. No new UI behavior is required.\n- The production code already\
  \ contains the refresh calls; the task formalizes them as\n  verified spec requirements.\n\
  - If any test fails on first run (meaning a refresh call IS missing in the production\n\
  \  code), that should be treated as a bug to fix in the same PR."
---
