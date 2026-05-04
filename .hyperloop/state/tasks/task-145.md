---
id: task-145
title: UI Mutations Console — file upload, KG selection, and submission with floating
  indicator
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: spec-review
deps:
- task-144
round: 1
branch: hyperloop/task-145
pr: https://github.com/openshift-hyperfleet/kartograph/pull/620
pr_title: 'feat(ui): add mutations console submission flow with floating progress
  indicator'
pr_description: "## What and Why\n\nThis task completes the Mutations Console by adding\
  \ the submission side: knowledge\ngraph selection (required before applying), file\
  \ upload with large-file mode, and\nthe floating progress indicator that persists\
  \ across navigation. The editor and\npreview panel built in task-144 feed directly\
  \ into this submission flow.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Mutations Console — Scenario: File upload**\n  \".jsonl/.json/.ndjson\
  \ via file picker or drag-and-drop; files >5MB activate\n  large-file mode (editing\
  \ disabled, summary of op counts shown, direct submit)\"\n\n- **Requirement: Mutations\
  \ Console — Scenario: Knowledge graph selection**\n  \"KG selector displayed before\
  \ submit; lists KGs with edit permission in current\n  workspace; no submission\
  \ until KG is selected\"\n\n- **Requirement: Mutations Console — Scenario: Submission**\n\
  \  \"mutations submitted to API scoped to selected KG; floating progress indicator\n\
  \  bottom-right (submitting/success/failed, op count, elapsed time);\n  indicator\
  \ persists when user navigates away;\n  can be minimized to pill or dismissed after\
  \ completion\"\n\n- **Requirement: Mutations Console — Scenario: Submission failure**\n\
  \  \"floating indicator shows error message; ops applied before failure displayed\"\
  \n\n- **Requirement: Backend API Alignment — Scenario: Resource operations succeed\
  \ end-to-end**\n  Submission calls `POST /graph/mutations/apply` (or equivalent)\
  \ scoped to the\n  selected knowledge graph. 2xx = success.\n\n## Key Design Decisions\n\
  \n- **File upload**: A `<FileDropZone>` component accepts `.jsonl`, `.json`, and\n\
  \  `.ndjson`. Files ≤ 5MB are loaded into the editor (task-144's store). Files\n\
  \  > 5MB trigger \"large-file mode\": the editor is disabled, a summary of op counts\n\
  \  is shown (parsed from the stream), and the user can submit directly.\n- **KG\
  \ selector**: A `<Select>` populated from `GET /workspaces/{id}/knowledge-graphs?permission=edit`.\n\
  \  The selector persists its selection in the mutations console Pinia store.\n \
  \ The \"Apply Mutations\" button is disabled (`aria-disabled`) until a KG is selected.\n\
  - **Floating indicator**: A `<MutationProgressIndicator>` component mounted at\n\
  \  the app root level (via `teleport` to `body`) so it persists across route changes.\n\
  \  It reads from the mutations console store. States: `idle` (hidden), `submitting`\n\
  \  (spinner + elapsed), `success` (green check + op count), `failed` (red X + error).\n\
  \  Controls: minimize toggle (shows compact pill `⬜ n ops`) and dismiss (removes\
  \ on\n  completion).\n- **API call**: `POST /graph/apply-mutations` with `knowledge_graph_id`\
  \ path/query\n  param and JSONL body. The response includes `applied_count` and\
  \ optional `error`.\n\n## What Files Are Affected\n\n- **New**: `src/ui/components/mutations/FileDropZone.vue`\n\
  - **New**: `src/ui/components/mutations/MutationKgSelector.vue`\n- **New**: `src/ui/components/mutations/MutationProgressIndicator.vue`\n\
  - **Modified**: `src/ui/stores/mutationsConsole.ts` (add submission state)\n- **Modified**:\
  \ `src/ui/pages/explore/mutations.vue` (integrate selector + dropzone)\n- **Modified**:\
  \ `src/ui/app.vue` (mount floating indicator at root)\n- **New**: `src/ui/tests/unit/FileDropZone.test.ts`\n\
  - **New**: `src/ui/tests/unit/MutationProgressIndicator.test.ts`\n- **New**: `src/ui/tests/unit/MutationKgSelector.test.ts`\n\
  \n## How to Verify\n\n```bash\n# Start dev instance with real DB\nmake instance-up\n\
  source .instances/$(basename $(pwd))/.env.instance\ncd src/ui && npm run dev\n#\
  \ 1. Drag a .jsonl file onto the page — content loaded into editor\n# 2. Drag a\
  \ >5MB file — large-file mode: editing disabled, op summary shown\n# 3. KG selector\
  \ shows only KGs with edit permission\n# 4. Without selecting a KG: Apply Mutations\
  \ button is disabled\n# 5. Select a KG and click Apply — floating indicator appears\
  \ bottom-right\n# 6. Navigate to /explore/query — floating indicator still visible\n\
  # 7. On success: indicator turns green, shows op count, can minimize or dismiss\n\
  # 8. Simulate failure: indicator turns red, shows error + ops applied before failure\n\
  ```\n\nUnit tests:\n```bash\ncd src/ui && npm run test:unit -- mutations\n# FileDropZone:\
  \ accepts .jsonl/.json/.ndjson; rejects other types; triggers\n#   large-file mode\
  \ for files >5MB\n# MutationProgressIndicator: renders correct state (submitting/success/failed);\n\
  #   minimize reduces to pill; dismiss hides on completion only\n# MutationKgSelector:\
  \ disabled state when no KGs with edit permission\n```\n\n## Caveats\n\n- Large-file\
  \ mode disables the editor to avoid DOM memory pressure for multi-MB\n  files. The\
  \ JSONL must still be streamed to the server, not base64-encoded in\n  the request\
  \ body. Use `fetch` with `ReadableStream` body if the file exceeds 5MB.\n- The floating\
  \ indicator's `teleport` target must exist before the component\n  mounts. Use `teleport\
  \ to=\"body\"` (Nuxt/Vue 3 Teleport).\n- If the submission API endpoint does not\
  \ yet exist in the graph presentation\n  layer, add a minimal `POST /graph/mutations/apply`\
  \ endpoint as part of this task.\n  It must delegate to the existing `BulkLoader`\
  \ (or equivalent) and accept the\n  `knowledge_graph_id` as a query parameter."
---
