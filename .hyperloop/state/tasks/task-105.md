---
id: task-105
title: 'Mutations console: deep-link URL parameter support and large-file mode (>5
  MB)'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: mark-ready
deps: []
round: 0
branch: hyperloop/task-105
pr: https://github.com/openshift-hyperfleet/kartograph/pull/570
pr_title: 'feat(ui): add mutations console deep-link parameters and large-file mode'
pr_description: "## What & Why\n\nThe **Mutations Console** requirement in `specs/ui/experience.spec.md`\
  \ defines two\nscenarios not yet implemented in `/pages/graph/mutations.vue`:\n\n\
  **Deep-link to editor with pre-filled content:**\n> \"GIVEN a URL with ?view=editor\
  \ or ?template=<content> WHEN the user navigates\n> to /graph/mutations THEN the\
  \ editor is opened automatically AND the template\n> parameter content (if present)\
  \ is inserted into the editor\"\n\n**Large-file mode:**\n> \"GIVEN a .jsonl, .json,\
  \ or .ndjson file WHEN the user uploads it via the file\n> picker or drag and drop\
  \ THEN ... files larger than 5 MB activate large-file mode:\n> editing is disabled,\
  \ a summary of operation counts is shown, and the user can\n> submit directly\"\n\
  \nBoth are currently absent. The deep-link scenario is important for integration\n\
  with external tooling (e.g., a CI pipeline generating a JSONL file can link\ndirectly\
  \ to the mutations console with the content pre-loaded via URL). The\nlarge-file\
  \ mode prevents the browser from hanging when editing multi-MB JSONL files.\n\n\
  ## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md`:\n- **Requirement:\
  \ Mutations Console** — Scenario: *Deep-link to editor with pre-filled content*\n\
  - **Requirement: Mutations Console** — Scenario: *File upload* (large-file mode\
  \ portion)\n\n## What This Change Does\n\n### Deep-Link: `?view=editor`\n\nWhen\
  \ the user navigates to `/graph/mutations?view=editor`:\n- The UI automatically\
  \ opens the editor view (skipping the empty-state \"upload or\n  edit\" prompt).\n\
  - The editor is focused and ready for input.\n- This is equivalent to the user clicking\
  \ \"Open Editor\" from the empty state.\n\n### Deep-Link: `?template=<url-encoded-content>`\n\
  \nWhen the user navigates to `/graph/mutations?template=<content>`:\n- The editor\
  \ is opened automatically (implies `?view=editor` behavior).\n- The URL-decoded\
  \ `template` parameter value is inserted into the editor as\n  initial content.\n\
  - Content is appended to existing editor content if any (spec: \"appended to any\n\
  \  existing editor content\").\n- The live preview panel updates to reflect the\
  \ new content.\n\n### Large-File Mode (>5 MB)\n\nWhen a file larger than 5 MB is\
  \ loaded (via file picker or drag-and-drop):\n1. The standard editor view is NOT\
  \ activated.\n2. Instead, a **large-file summary panel** is shown:\n   - File name\
  \ and size\n   - Operation count breakdown by type (DEFINE, CREATE, UPDATE, DELETE)\
  \ parsed\n     from the JSONL without loading it into the editor DOM\n   - Any top-level\
  \ parse errors (first N lines only to avoid scanning the full file)\n   - A single\
  \ **\"Apply Mutations\"** button that submits the file content directly\n     to\
  \ the API (using the selected knowledge graph)\n   - A note: \"File is too large\
  \ for in-browser editing. Submit directly or\n     download and edit locally.\"\n\
  3. The KG selector is still required before submission (same as normal mode).\n\n\
  Implementation note: parse large files in a Web Worker to avoid blocking the\nmain\
  \ thread during the operation count scan.\n\n## Files / Areas Affected\n\n- `src/dev-ui/app/pages/graph/mutations.vue`\
  \ — URL parameter handling on mount,\n  large-file mode branch in file upload handler\n\
  - `src/dev-ui/app/components/graph/MutationPreview.vue` — drive from URL parameter\n\
  \  content on init\n- `src/dev-ui/app/workers/` — extend or add a JSONL parser worker\
  \ for large-file\n  operation count scanning\n- `src/dev-ui/app/components/graph/LargeFileSummary.vue`\
  \ (new) — summary panel\n  for large files\n\n## Tests\n\nVitest / Vue Test Utils\
  \ tests in `src/dev-ui/app/tests/`:\n- `test_view_editor_param_opens_editor_directly`:\
  \ mount `/graph/mutations?view=editor`,\n  assert editor component is rendered (not\
  \ empty-state)\n- `test_template_param_inserts_content_into_editor`: mount with\n\
  \  `?template={\"op\":\"CREATE_NODE\",\"label\":\"Test\"}`, assert editor content\
  \ contains\n  the decoded template\n- `test_template_param_implies_editor_view`:\
  \ mount with `?template=<content>`,\n  assert editor is active (not empty-state)\n\
  - `test_large_file_activates_large_file_mode`: simulate uploading a file >5 MB,\n\
  \  assert editor is NOT rendered, assert `LargeFileSummary` component IS rendered\n\
  - `test_large_file_shows_operation_count_summary`: provide a large JSONL with\n\
  \  known operation counts, assert the summary displays correct counts per type\n\
  - `test_small_file_does_not_activate_large_file_mode`: file ≤5 MB loads into editor\n\
  \  normally\n\n## How to Verify\n\n1. Navigate to `/graph/mutations?view=editor`\
  \ — confirm editor opens immediately\n2. Navigate to `/graph/mutations?template=%7B%22op%22%3A%22CREATE_NODE%22%7D`\
  \ —\n   confirm editor opens with the decoded template content\n3. Upload a file\
  \ ≤5 MB — confirm it loads into the editor\n4. Upload a file >5 MB — confirm the\
  \ large-file summary panel appears with\n   operation counts, editing is disabled,\
  \ and submit works\n\n## Caveats\n\n- The `template` parameter value should be URL-encoded;\
  \ the page must URL-decode\n  it before inserting. Test with JSONL content containing\
  \ `+`, `&`, and `=` chars.\n- Very large `template` URL parameters (>2KB) may be\
  \ truncated by some browsers.\n  Add a soft warning in the UI if the template parameter\
  \ exceeds 1KB, suggesting\n  file upload instead.\n- The Web Worker for large-file\
  \ scanning must gracefully handle malformed JSONL\n  (count valid lines separately\
  \ from errors).\n- Large-file submission uses the same `POST /graph/mutations` endpoint;\
  \ ensure\n  the file is streamed rather than held in memory as a JS string."
---
