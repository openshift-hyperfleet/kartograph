---
id: task-065
title: Mutations Console — knowledge graph selector and scoped API submission
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-060
- task-061
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add knowledge graph selector to Mutations Console and fix scoped
  API submission'
pr_description: "## What & Why\n\nThe `experience.spec.md` spec was updated to add\
  \ a new **Scenario: Knowledge graph\nselection** under the Mutations Console requirement.\
  \ The spec requires:\n\n> GIVEN the mutations console\n> THEN a knowledge graph\
  \ selector is displayed before the user can submit\n> AND the selector lists all\
  \ knowledge graphs the user has `edit` permission on\n>   within the current workspace\n\
  > AND no submission is possible until a knowledge graph is selected\n> AND the selected\
  \ knowledge graph is used as the target for the mutation submission\n\nNo existing\
  \ task covers this scenario. Critically, the current implementation is also\nbroken\
  \ at the API level: `applyMutations()` posts to `POST /graph/mutations`, but the\n\
  backend only exposes `POST /graph/knowledge-graphs/{knowledge_graph_id}/mutations`.\n\
  Mutations submitted without a KG ID will always fail with a 404.\n\n## Spec Requirements\
  \ Satisfied\n\n**Requirement: Mutations Console — Scenario: Knowledge graph selection**\n\
  from `specs/ui/experience.spec.md`:\n\n- A knowledge graph selector is rendered\
  \ in the mutations console before the\n  submit button.\n- The selector lists all\
  \ knowledge graphs available in the current tenant\n  (filtered to those the user\
  \ can access — the backend enforces the `edit`\n  permission check at submission\
  \ time via SpiceDB).\n- The Apply Mutations button and `Ctrl/Cmd+Enter` shortcut\
  \ are disabled until\n  a knowledge graph is selected.\n- When the user submits,\
  \ the selected KG ID is passed through the entire\n  submission chain and used in\
  \ the API path.\n\n**Requirement: Backend API Alignment — Scenario: Resource operations\
  \ succeed end-to-end**\n\nFixes the broken API call so mutations actually reach\
  \ the correct backend endpoint.\n\n## Key Design Decisions\n\n- **Selector placement**:\
  \ Above the Apply Mutations action bar in the active editor\n  view. Also visible\
  \ in large-file mode. Hidden in the empty state (no point selecting\n  a KG before\
  \ there's content).\n- **Selector population**: `GET /management/knowledge-graphs`\
  \ — same endpoint used by\n  the Query Console's KG scope selector (task-045). On\
  \ tenant switch, the list reloads\n  and the selection clears.\n- **Blocking gate**:\
  \ The Apply Mutations button's `:disabled` condition is expanded to\n  also require\
  \ `!!selectedKgId`. `Ctrl/Cmd+Enter` performs the same check.\n- **API path change**:\
  \ `applyMutations(jsonlContent, options)` gains a required\n  `knowledgeGraphId:\
  \ string` parameter. The URL changes from `/graph/mutations` to\n  `/graph/knowledge-graphs/${knowledgeGraphId}/mutations`.\
  \ No query-string or body\n  change — the KG ID is path-only (matching the backend\
  \ route).\n- **`useMutationSubmission` update**: `submit(jsonlContent, opCount)`\
  \ gains a required\n  `knowledgeGraphId: string` parameter forwarded to `applyMutations`.\
  \ Nuxt `useState`\n  key (`mutation-submission`) is unchanged — no state shape change\
  \ needed.\n\n## Files Affected\n\n- `src/dev-ui/app/composables/api/useGraphApi.ts`\
  \ — add `knowledgeGraphId: string`\n  parameter to `applyMutations`; update the\
  \ fetch URL.\n- `src/dev-ui/app/composables/useMutationSubmission.ts` — add `knowledgeGraphId:\n\
  \  string` parameter to `submit`; forward to `applyMutations`.\n- `src/dev-ui/app/pages/graph/mutations.vue`\
  \ — add KG selector state + UI; gate\n  submit button on selection; pass `selectedKgId`\
  \ to `submission.submit()`.\n- `src/dev-ui/app/tests/mutations-kg-selector.test.ts`\
  \ — new TDD-first test file.\n\n## How to Verify\n\n1. Navigate to `/graph/mutations`\
  \ and open the editor.\n2. The Apply Mutations button is **disabled** with no KG\
  \ selected.\n3. `Ctrl/Cmd+Enter` does not submit when no KG is selected.\n4. After\
  \ selecting a KG from the dropdown, the button becomes enabled.\n5. Click Apply\
  \ Mutations — the request goes to\n   `POST /graph/knowledge-graphs/{selected_kg_id}/mutations`\
  \ (verify in network tab).\n6. Large-file mode: KG selector is visible and gating\
  \ works the same way.\n7. Switching tenants clears the KG selection and reloads\
  \ the list.\n8. Run `cd src/dev-ui && pnpm test` — all tests in\n   `mutations-kg-selector.test.ts`\
  \ pass; no regressions in\n   `mutations-console.test.ts`.\n\n## Caveats\n\n- Depends\
  \ on task-060 (core editor implementation) and task-061 (submission\n  composable\
  \ implementation) landing first, since this task modifies both.\n- The backend enforces\
  \ `edit` permission on the KG at submission time via SpiceDB.\n  The UI lists all\
  \ KGs accessible to the user (no client-side permission filtering\n  needed — wrong\
  \ selection will surface as a 403, which the floating error indicator\n  will display).\n\
  - TypeScript callers of `useMutationSubmission().submit()` outside the mutations\n\
  \  page (if any) will need updating to pass `knowledgeGraphId`."
---
