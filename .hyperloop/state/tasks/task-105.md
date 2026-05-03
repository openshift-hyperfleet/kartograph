---
id: task-105
title: "Mutations console: deep-link URL parameter support and large-file mode (>5 MB)"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(ui): add mutations console deep-link parameters and large-file mode"
pr_description: |
  ## What & Why

  The **Mutations Console** requirement in `specs/ui/experience.spec.md` defines two
  scenarios not yet implemented in `/pages/graph/mutations.vue`:

  **Deep-link to editor with pre-filled content:**
  > "GIVEN a URL with ?view=editor or ?template=<content> WHEN the user navigates
  > to /graph/mutations THEN the editor is opened automatically AND the template
  > parameter content (if present) is inserted into the editor"

  **Large-file mode:**
  > "GIVEN a .jsonl, .json, or .ndjson file WHEN the user uploads it via the file
  > picker or drag and drop THEN ... files larger than 5 MB activate large-file mode:
  > editing is disabled, a summary of operation counts is shown, and the user can
  > submit directly"

  Both are currently absent. The deep-link scenario is important for integration
  with external tooling (e.g., a CI pipeline generating a JSONL file can link
  directly to the mutations console with the content pre-loaded via URL). The
  large-file mode prevents the browser from hanging when editing multi-MB JSONL files.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md`:
  - **Requirement: Mutations Console** — Scenario: *Deep-link to editor with pre-filled content*
  - **Requirement: Mutations Console** — Scenario: *File upload* (large-file mode portion)

  ## What This Change Does

  ### Deep-Link: `?view=editor`

  When the user navigates to `/graph/mutations?view=editor`:
  - The UI automatically opens the editor view (skipping the empty-state "upload or
    edit" prompt).
  - The editor is focused and ready for input.
  - This is equivalent to the user clicking "Open Editor" from the empty state.

  ### Deep-Link: `?template=<url-encoded-content>`

  When the user navigates to `/graph/mutations?template=<content>`:
  - The editor is opened automatically (implies `?view=editor` behavior).
  - The URL-decoded `template` parameter value is inserted into the editor as
    initial content.
  - Content is appended to existing editor content if any (spec: "appended to any
    existing editor content").
  - The live preview panel updates to reflect the new content.

  ### Large-File Mode (>5 MB)

  When a file larger than 5 MB is loaded (via file picker or drag-and-drop):
  1. The standard editor view is NOT activated.
  2. Instead, a **large-file summary panel** is shown:
     - File name and size
     - Operation count breakdown by type (DEFINE, CREATE, UPDATE, DELETE) parsed
       from the JSONL without loading it into the editor DOM
     - Any top-level parse errors (first N lines only to avoid scanning the full file)
     - A single **"Apply Mutations"** button that submits the file content directly
       to the API (using the selected knowledge graph)
     - A note: "File is too large for in-browser editing. Submit directly or
       download and edit locally."
  3. The KG selector is still required before submission (same as normal mode).

  Implementation note: parse large files in a Web Worker to avoid blocking the
  main thread during the operation count scan.

  ## Files / Areas Affected

  - `src/dev-ui/app/pages/graph/mutations.vue` — URL parameter handling on mount,
    large-file mode branch in file upload handler
  - `src/dev-ui/app/components/graph/MutationPreview.vue` — drive from URL parameter
    content on init
  - `src/dev-ui/app/workers/` — extend or add a JSONL parser worker for large-file
    operation count scanning
  - `src/dev-ui/app/components/graph/LargeFileSummary.vue` (new) — summary panel
    for large files

  ## Tests

  Vitest / Vue Test Utils tests in `src/dev-ui/app/tests/`:
  - `test_view_editor_param_opens_editor_directly`: mount `/graph/mutations?view=editor`,
    assert editor component is rendered (not empty-state)
  - `test_template_param_inserts_content_into_editor`: mount with
    `?template={"op":"CREATE_NODE","label":"Test"}`, assert editor content contains
    the decoded template
  - `test_template_param_implies_editor_view`: mount with `?template=<content>`,
    assert editor is active (not empty-state)
  - `test_large_file_activates_large_file_mode`: simulate uploading a file >5 MB,
    assert editor is NOT rendered, assert `LargeFileSummary` component IS rendered
  - `test_large_file_shows_operation_count_summary`: provide a large JSONL with
    known operation counts, assert the summary displays correct counts per type
  - `test_small_file_does_not_activate_large_file_mode`: file ≤5 MB loads into editor
    normally

  ## How to Verify

  1. Navigate to `/graph/mutations?view=editor` — confirm editor opens immediately
  2. Navigate to `/graph/mutations?template=%7B%22op%22%3A%22CREATE_NODE%22%7D` —
     confirm editor opens with the decoded template content
  3. Upload a file ≤5 MB — confirm it loads into the editor
  4. Upload a file >5 MB — confirm the large-file summary panel appears with
     operation counts, editing is disabled, and submit works

  ## Caveats

  - The `template` parameter value should be URL-encoded; the page must URL-decode
    it before inserting. Test with JSONL content containing `+`, `&`, and `=` chars.
  - Very large `template` URL parameters (>2KB) may be truncated by some browsers.
    Add a soft warning in the UI if the template parameter exceeds 1KB, suggesting
    file upload instead.
  - The Web Worker for large-file scanning must gracefully handle malformed JSONL
    (count valid lines separately from errors).
  - Large-file submission uses the same `POST /graph/mutations` endpoint; ensure
    the file is streamed rather than held in memory as a JS string.
---
