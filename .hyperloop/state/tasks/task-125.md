---
id: task-125
title: 'UI: Mutations Console — File Upload, KG Selection & Submission'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: verify
deps:
- task-124
round: 0
branch: hyperloop/task-125
pr: https://github.com/openshift-hyperfleet/kartograph/pull/600
pr_title: 'feat(ui): add mutations console file upload, KG selection, and submission
  workflow'
pr_description: "## What & Why\n\nCompletes the Mutations Console by adding the file\
  \ upload pathway, knowledge graph\nselection, and the full submission workflow including\
  \ the persistent floating progress\nindicator. This PR depends on task-124 (editor\
  \ and preview) and wires the\n`Ctrl/Cmd+Enter` submit shortcut introduced there.\n\
  \n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md` (Requirement:\
  \ Mutations Console):\n- **Scenario: File upload** — `.jsonl`, `.json`, `.ndjson`\
  \ via file picker or\n  drag-and-drop; files > 5 MB activate large-file mode (editing\
  \ disabled, summary\n  only, direct submit available)\n- **Scenario: Knowledge graph\
  \ selection** — selector listing KGs the user has `edit`\n  permission on within\
  \ the current workspace; submission blocked until one is chosen\n- **Scenario: Submission**\
  \ — `POST` to mutations API scoped to the selected KG;\n  floating progress indicator\
  \ (bottom-right): status, operation count, elapsed time;\n  persists when navigating\
  \ away; minimizable to pill / dismissible after completion\n- **Scenario: Submission\
  \ failure** — floating indicator shows error message and\n  count of operations\
  \ applied before failure\n- **Scenario: JSONL editing** (completion) — `Ctrl/Cmd+Enter`\
  \ now wired to the\n  real submit handler\n\n## File Upload\n\n- File picker: `<input\
  \ type=\"file\" accept=\".jsonl,.json,.ndjson\">` triggered by the\n  \"Upload File\"\
  \ action card (from task-124's empty state)\n- Drag-and-drop: `@dragover` + `@drop`\
  \ handlers on the page root; file dropped\n  anywhere on `/graph/mutations` is loaded\n\
  - **Normal mode (≤ 5 MB):** file content loaded into the CodeMirror editor\n- **Large-file\
  \ mode (> 5 MB):** editor is disabled; a summary panel shows operation\n  counts\
  \ (parsed in a Web Worker to avoid blocking the main thread); an \"Apply\n  Mutations\"\
  \ button is available for direct submission\n\n## Knowledge Graph Selector\n\n-\
  \ Rendered prominently above the \"Apply Mutations\" button\n- Fetches KGs via `GET\
  \ /management/knowledge-graphs?workspace_id=…` filtered by\n  `edit` permission\
  \ (the backend returns only permitted KGs per the auth model)\n- Default state:\
  \ \"Select a knowledge graph…\" (placeholder); no KG selected\n- The \"Apply Mutations\"\
  \ button is disabled and shows a tooltip explaining why until\n  a KG is selected\n\
  \n## Submission Workflow\n\n1. User clicks \"Apply Mutations\" (or presses `Ctrl/Cmd+Enter`\
  \ in the editor)\n2. `POST /graph/mutations?knowledge_graph_id={kg_id}` with the\
  \ JSONL body\n3. A **floating progress indicator** appears anchored to the bottom-right\
  \ corner:\n   - Phase: \"Submitting…\" (spinner) → \"Success\" (check) or \"Failed\"\
  \ (warning)\n   - Operation count and elapsed time displayed\n4. The indicator remains\
  \ visible if the user navigates to another page\n5. Dismiss: clicking `×` dismisses\
  \ after completion; users can minimize to a compact\n   pill (the pill shows \"\
  ✓ 42 ops\" or \"✗ Failed\")\n\n## Submission Failure\n\nThe floating indicator transitions\
  \ to an error state showing:\n- Error message from the API response\n- Number of\
  \ operations successfully applied before failure (from API response body)\n\n##\
  \ Backend API Integration\n\n| Action | Endpoint |\n|---|---|\n| Submit mutations\
  \ | `POST /graph/mutations` (or `/graph/{kg_id}/mutations`) |\n| List editable KGs\
  \ | `GET /management/knowledge-graphs?workspace_id=…` |\n\nThe mutations endpoint\
  \ already exists in the Graph context (`src/api/graph/`).\nThe exact endpoint path\
  \ and request schema should be confirmed from\n`src/api/graph/presentation/routes.py`.\n\
  \n## Files / Areas Affected\n\n- `src/ui/src/components/mutations/FileUploadZone.vue`\n\
  - `src/ui/src/components/mutations/LargeFileSummary.vue`\n- `src/ui/src/components/mutations/KgSelector.vue`\n\
  - `src/ui/src/components/mutations/FloatingProgressIndicator.vue`\n- `src/ui/src/stores/mutationProgress.ts`\
  \ — Pinia store for persistent indicator state\n- `src/ui/src/api/graph.ts` — extend\
  \ with mutations endpoint\n\n## How to Verify\n\n1. Drag a `.jsonl` file (< 5 MB)\
  \ onto the page → content appears in editor\n2. Drag a `.jsonl` file (> 5 MB) →\
  \ editor disabled; operation summary shown\n3. KG selector shows only KGs with edit\
  \ permission; \"Apply Mutations\" is disabled\n   without a selection\n4. Select\
  \ a KG → click \"Apply Mutations\" → floating indicator appears; navigate to\n \
  \  another page → indicator persists in the corner\n5. Minimize indicator → compact\
  \ pill visible; dismiss after success → indicator gone\n6. Force a backend error\
  \ → indicator shows error message + partial op count\n\n## Caveats / Follow-up\n\
  \n- The Web Worker for large-file parsing is implemented as a graceful fallback;\n\
  \  if Worker API is unavailable, parsing runs on the main thread with a loading\n\
  \  skeleton"
---
