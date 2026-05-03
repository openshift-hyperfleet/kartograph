---
id: task-129
title: UI Mutations Console — File Upload, Submission, and Floating Progress Indicator
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-128]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add mutations console file upload, submission, and floating progress"
pr_description: |
  ## What and Why

  Completes the Mutations Console by adding the file upload path (including
  large-file mode), the actual mutation submission API call, and the floating
  progress indicator that persists when the user navigates away from the page.

  This task builds on the editor and composable from task-128. The `useMutations`
  composable already holds the JSONL content and selected KG — task-129 adds the
  submission state machine and the portal-rendered floating indicator.

  ## Spec Requirements Satisfied

  The remaining scenarios from **Requirement: Mutations Console** in
  `specs/ui/experience.spec.md`:

  - **File upload**: file picker button AND drag-and-drop zone accept .jsonl,
    .json, and .ndjson; file content is loaded into the editor; for files > 5 MB,
    large-file mode activates: editing is disabled, a summary of operation counts
    (from a read-only parse) is shown, and the user can submit directly without
    editing.
  - **Submission**: clicking "Apply Mutations" (or Ctrl/Cmd+Enter) submits the
    JSONL content to `POST /api/graph/mutations` scoped to the selected KG;
    a floating progress indicator appears immediately in the bottom-right corner.
  - **Floating indicator**: shows status (submitting / success / failed), operation
    count, and elapsed time; persists when the user navigates away from the
    Mutations Console page; can be minimized to a compact pill or dismissed after
    completion.
  - **Submission failure**: the floating indicator transitions to a failed state
    showing the error message; if some operations completed before the failure,
    the count of applied operations is displayed.

  ## Design Decisions

  - **File upload**: `<input type="file" accept=".jsonl,.json,.ndjson">` hidden
    behind the "Upload File" button; drag-and-drop implemented on the page root
    element via `dragover` + `drop` event handlers.
  - **Large-file mode threshold**: 5 MB (`file.size > 5 * 1024 * 1024`); in this
    mode the editor is replaced with a read-only summary view.
  - **Floating indicator**: rendered via Vue's `<Teleport to="body">` so it
    remains visible regardless of route changes; its state lives in a Pinia store
    (`useMutationSubmissionStore`) so it survives component unmounts.
  - **Submission progress**: the backend may return progress updates via SSE or
    may return a job ID to poll; implement polling initially (consistent with
    task-122's polling approach) with a 1 s interval.
  - **Minimize/dismiss**: the indicator has a collapse chevron (→ compact pill
    showing status icon + elapsed time) and a dismiss X (only after completion).

  ## Backend APIs Required

  - `POST /api/graph/mutations` — submit JSONL mutations scoped to a KG
  - `GET /api/graph/mutations/{job_id}` — poll submission status (if async)

  ## Files / Areas Affected

  - `src/ui/components/mutations/FileUploadZone.vue`
  - `src/ui/components/mutations/LargeFileSummary.vue`
  - `src/ui/components/mutations/FloatingMutationProgress.vue` — teleported component
  - `src/ui/stores/mutationSubmission.ts` — Pinia store for floating indicator state
  - `src/ui/composables/useMutations.ts` — extended with submit action + file load
  - `src/ui/pages/explore/MutationsConsolePage.vue` — wire file upload + submit button

  ## How to Verify

  1. Drag a .jsonl file onto the page: content loads into editor (or large-file summary)
  2. File picker button: same behavior as drag-and-drop
  3. File > 5 MB: editor replaced by read-only summary with operation counts
  4. Click "Apply Mutations" with valid JSONL and KG selected:
     - Network tab shows POST to `/api/graph/mutations`
     - Floating indicator appears in bottom-right corner with "Submitting…" state
  5. Navigate away from Mutations Console: floating indicator still visible
  6. Successful submission: indicator shows "Success" + operation count + elapsed time
  7. Failed submission: indicator shows error message; applied-before-failure count shown
  8. Minimize button: indicator collapses to compact pill; maximize restores it
  9. Dismiss X: only available after completion; removes indicator

  ## Caveats

  The `POST /api/graph/mutations` endpoint must exist in the Graph bounded context.
  Verify it is implemented before wiring up the real API call; if absent, coordinate
  with the Graph context implementer to add it. The UI should fail gracefully
  (toast error) if the endpoint returns an unexpected status code.
---
