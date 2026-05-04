---
id: task-145
title: "UI Mutations Console — file upload, KG selection, and submission with floating indicator"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-144]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add mutations console submission flow with floating progress indicator"
pr_description: |
  ## What and Why

  This task completes the Mutations Console by adding the submission side: knowledge
  graph selection (required before applying), file upload with large-file mode, and
  the floating progress indicator that persists across navigation. The editor and
  preview panel built in task-144 feed directly into this submission flow.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Mutations Console — Scenario: File upload**
    ".jsonl/.json/.ndjson via file picker or drag-and-drop; files >5MB activate
    large-file mode (editing disabled, summary of op counts shown, direct submit)"

  - **Requirement: Mutations Console — Scenario: Knowledge graph selection**
    "KG selector displayed before submit; lists KGs with edit permission in current
    workspace; no submission until KG is selected"

  - **Requirement: Mutations Console — Scenario: Submission**
    "mutations submitted to API scoped to selected KG; floating progress indicator
    bottom-right (submitting/success/failed, op count, elapsed time);
    indicator persists when user navigates away;
    can be minimized to pill or dismissed after completion"

  - **Requirement: Mutations Console — Scenario: Submission failure**
    "floating indicator shows error message; ops applied before failure displayed"

  - **Requirement: Backend API Alignment — Scenario: Resource operations succeed end-to-end**
    Submission calls `POST /graph/mutations/apply` (or equivalent) scoped to the
    selected knowledge graph. 2xx = success.

  ## Key Design Decisions

  - **File upload**: A `<FileDropZone>` component accepts `.jsonl`, `.json`, and
    `.ndjson`. Files ≤ 5MB are loaded into the editor (task-144's store). Files
    > 5MB trigger "large-file mode": the editor is disabled, a summary of op counts
    is shown (parsed from the stream), and the user can submit directly.
  - **KG selector**: A `<Select>` populated from `GET /workspaces/{id}/knowledge-graphs?permission=edit`.
    The selector persists its selection in the mutations console Pinia store.
    The "Apply Mutations" button is disabled (`aria-disabled`) until a KG is selected.
  - **Floating indicator**: A `<MutationProgressIndicator>` component mounted at
    the app root level (via `teleport` to `body`) so it persists across route changes.
    It reads from the mutations console store. States: `idle` (hidden), `submitting`
    (spinner + elapsed), `success` (green check + op count), `failed` (red X + error).
    Controls: minimize toggle (shows compact pill `⬜ n ops`) and dismiss (removes on
    completion).
  - **API call**: `POST /graph/apply-mutations` with `knowledge_graph_id` path/query
    param and JSONL body. The response includes `applied_count` and optional `error`.

  ## What Files Are Affected

  - **New**: `src/ui/components/mutations/FileDropZone.vue`
  - **New**: `src/ui/components/mutations/MutationKgSelector.vue`
  - **New**: `src/ui/components/mutations/MutationProgressIndicator.vue`
  - **Modified**: `src/ui/stores/mutationsConsole.ts` (add submission state)
  - **Modified**: `src/ui/pages/explore/mutations.vue` (integrate selector + dropzone)
  - **Modified**: `src/ui/app.vue` (mount floating indicator at root)
  - **New**: `src/ui/tests/unit/FileDropZone.test.ts`
  - **New**: `src/ui/tests/unit/MutationProgressIndicator.test.ts`
  - **New**: `src/ui/tests/unit/MutationKgSelector.test.ts`

  ## How to Verify

  ```bash
  # Start dev instance with real DB
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/ui && npm run dev
  # 1. Drag a .jsonl file onto the page — content loaded into editor
  # 2. Drag a >5MB file — large-file mode: editing disabled, op summary shown
  # 3. KG selector shows only KGs with edit permission
  # 4. Without selecting a KG: Apply Mutations button is disabled
  # 5. Select a KG and click Apply — floating indicator appears bottom-right
  # 6. Navigate to /explore/query — floating indicator still visible
  # 7. On success: indicator turns green, shows op count, can minimize or dismiss
  # 8. Simulate failure: indicator turns red, shows error + ops applied before failure
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- mutations
  # FileDropZone: accepts .jsonl/.json/.ndjson; rejects other types; triggers
  #   large-file mode for files >5MB
  # MutationProgressIndicator: renders correct state (submitting/success/failed);
  #   minimize reduces to pill; dismiss hides on completion only
  # MutationKgSelector: disabled state when no KGs with edit permission
  ```

  ## Caveats

  - Large-file mode disables the editor to avoid DOM memory pressure for multi-MB
    files. The JSONL must still be streamed to the server, not base64-encoded in
    the request body. Use `fetch` with `ReadableStream` body if the file exceeds 5MB.
  - The floating indicator's `teleport` target must exist before the component
    mounts. Use `teleport to="body"` (Nuxt/Vue 3 Teleport).
  - If the submission API endpoint does not yet exist in the graph presentation
    layer, add a minimal `POST /graph/mutations/apply` endpoint as part of this task.
    It must delegate to the existing `BulkLoader` (or equivalent) and accept the
    `knowledge_graph_id` as a query parameter.
---
