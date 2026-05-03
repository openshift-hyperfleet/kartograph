---
id: task-125
title: "UI: Mutations Console — File Upload, KG Selection & Submission"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-124]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add mutations console file upload, KG selection, and submission workflow"
pr_description: |
  ## What & Why

  Completes the Mutations Console by adding the file upload pathway, knowledge graph
  selection, and the full submission workflow including the persistent floating progress
  indicator. This PR depends on task-124 (editor and preview) and wires the
  `Ctrl/Cmd+Enter` submit shortcut introduced there.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md` (Requirement: Mutations Console):
  - **Scenario: File upload** — `.jsonl`, `.json`, `.ndjson` via file picker or
    drag-and-drop; files > 5 MB activate large-file mode (editing disabled, summary
    only, direct submit available)
  - **Scenario: Knowledge graph selection** — selector listing KGs the user has `edit`
    permission on within the current workspace; submission blocked until one is chosen
  - **Scenario: Submission** — `POST` to mutations API scoped to the selected KG;
    floating progress indicator (bottom-right): status, operation count, elapsed time;
    persists when navigating away; minimizable to pill / dismissible after completion
  - **Scenario: Submission failure** — floating indicator shows error message and
    count of operations applied before failure
  - **Scenario: JSONL editing** (completion) — `Ctrl/Cmd+Enter` now wired to the
    real submit handler

  ## File Upload

  - File picker: `<input type="file" accept=".jsonl,.json,.ndjson">` triggered by the
    "Upload File" action card (from task-124's empty state)
  - Drag-and-drop: `@dragover` + `@drop` handlers on the page root; file dropped
    anywhere on `/graph/mutations` is loaded
  - **Normal mode (≤ 5 MB):** file content loaded into the CodeMirror editor
  - **Large-file mode (> 5 MB):** editor is disabled; a summary panel shows operation
    counts (parsed in a Web Worker to avoid blocking the main thread); an "Apply
    Mutations" button is available for direct submission

  ## Knowledge Graph Selector

  - Rendered prominently above the "Apply Mutations" button
  - Fetches KGs via `GET /management/knowledge-graphs?workspace_id=…` filtered by
    `edit` permission (the backend returns only permitted KGs per the auth model)
  - Default state: "Select a knowledge graph…" (placeholder); no KG selected
  - The "Apply Mutations" button is disabled and shows a tooltip explaining why until
    a KG is selected

  ## Submission Workflow

  1. User clicks "Apply Mutations" (or presses `Ctrl/Cmd+Enter` in the editor)
  2. `POST /graph/mutations?knowledge_graph_id={kg_id}` with the JSONL body
  3. A **floating progress indicator** appears anchored to the bottom-right corner:
     - Phase: "Submitting…" (spinner) → "Success" (check) or "Failed" (warning)
     - Operation count and elapsed time displayed
  4. The indicator remains visible if the user navigates to another page
  5. Dismiss: clicking `×` dismisses after completion; users can minimize to a compact
     pill (the pill shows "✓ 42 ops" or "✗ Failed")

  ## Submission Failure

  The floating indicator transitions to an error state showing:
  - Error message from the API response
  - Number of operations successfully applied before failure (from API response body)

  ## Backend API Integration

  | Action | Endpoint |
  |---|---|
  | Submit mutations | `POST /graph/mutations` (or `/graph/{kg_id}/mutations`) |
  | List editable KGs | `GET /management/knowledge-graphs?workspace_id=…` |

  The mutations endpoint already exists in the Graph context (`src/api/graph/`).
  The exact endpoint path and request schema should be confirmed from
  `src/api/graph/presentation/routes.py`.

  ## Files / Areas Affected

  - `src/ui/src/components/mutations/FileUploadZone.vue`
  - `src/ui/src/components/mutations/LargeFileSummary.vue`
  - `src/ui/src/components/mutations/KgSelector.vue`
  - `src/ui/src/components/mutations/FloatingProgressIndicator.vue`
  - `src/ui/src/stores/mutationProgress.ts` — Pinia store for persistent indicator state
  - `src/ui/src/api/graph.ts` — extend with mutations endpoint

  ## How to Verify

  1. Drag a `.jsonl` file (< 5 MB) onto the page → content appears in editor
  2. Drag a `.jsonl` file (> 5 MB) → editor disabled; operation summary shown
  3. KG selector shows only KGs with edit permission; "Apply Mutations" is disabled
     without a selection
  4. Select a KG → click "Apply Mutations" → floating indicator appears; navigate to
     another page → indicator persists in the corner
  5. Minimize indicator → compact pill visible; dismiss after success → indicator gone
  6. Force a backend error → indicator shows error message + partial op count

  ## Caveats / Follow-up

  - The Web Worker for large-file parsing is implemented as a graceful fallback;
    if Worker API is unavailable, parsing runs on the main thread with a loading
    skeleton
---
