---
id: task-155
title: 'UI: Mutations Console'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-151
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add mutations console with JSONL editor, file upload and progress
  tracking'
pr_description: "## What and Why\n\nThe Mutations Console is the power-user surface\
  \ for applying bulk graph\nmutations (DEFINE/CREATE/UPDATE/DELETE operations) without\
  \ going through\nthe Ingestion pipeline. It is the Explore section's fourth page\
  \ and is\nself-contained — it only depends on the Graph bulk-load API and the\n\
  Management knowledge-graph list.\n\n## Spec Requirements Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`\n\
  \n### Requirement: Mutations Console — Empty State\n- When no content is loaded\
  \ the page shows two primary action buttons:\n  **Upload File** and **Open Editor**\n\
  - Four quick-start template buttons: Create Node, Create Edge,\n  Update Properties,\
  \ Delete Entity\n- Drag-and-drop a `.jsonl`, `.json`, or `.ndjson` file onto the\
  \ page\n  activates the editor with the file content\n\n### Requirement: JSONL Editing\n\
  - Editor provides JSON syntax highlighting, line numbers, JSONL-aware\n  linting\
  \ (each line must be a valid JSON object), and autocomplete for\n  mutation operation\
  \ fields (`operation`, `entity_type`, `id`, `properties`,\n  `from_id`, `to_id`,\
  \ etc.)\n- Ctrl/Cmd+Enter submits the mutations without leaving the editor\n\n###\
  \ Requirement: Live Preview\n- A side panel updates in real-time as the user types,\
  \ showing:\n  - Operation count broken down by type (DEFINE / CREATE / UPDATE /\
  \ DELETE)\n  - Validation warnings (duplicate IDs, missing required fields per\n\
  \    operation type, unknown operation names)\n- Parse errors surfaced as gutter\
  \ markers in the editor (red squiggles\n  on the offending line)\n\n### Requirement:\
  \ File Upload\n- File picker button or drag-and-drop accepts `.jsonl`, `.json`,\
  \ `.ndjson`\n- Content loaded into editor; live preview updates immediately\n- Files\
  \ **> 5 MB** activate large-file mode: editor is read-only and\n  disabled, a summary\
  \ banner shows operation counts (DEFINE/CREATE/\n  UPDATE/DELETE), and the \"Apply\
  \ Mutations\" button remains active so\n  the user can still submit\n\n### Requirement:\
  \ Knowledge Graph Selection\n- A KG selector (dropdown) is displayed prominently\
  \ above the action\n  buttons; it lists all KGs the user has `edit` permission on\
  \ in the\n  current workspace (calls `GET /management/knowledge-graphs?permission=edit`)\n\
  - The Apply Mutations button is disabled until a KG is selected\n- The selected\
  \ KG ID is sent with the submission request\n\n### Requirement: Submission\n- \"\
  Apply Mutations\" button (and Ctrl/Cmd+Enter shortcut) calls the bulk\n  mutations\
  \ API scoped to the selected knowledge graph\n- A **floating progress indicator**\
  \ appears in the bottom-right corner:\n  - Shows status: **Submitting** → **Success**\
  \ / **Failed**\n  - Displays operation count and elapsed time\n  - Persists when\
  \ the user navigates away from the mutations console\n  - Can be minimised to a\
  \ compact pill or dismissed after completion\n\n### Requirement: Submission Failure\n\
  - Floating indicator shows the error message from the API on failure\n- If the API\
  \ reports partial success (some operations applied before\n  failure), the count\
  \ of applied operations is shown\n\n### Requirement: Template Insertion\n- Selecting\
  \ a template (from the empty-state quick-start buttons or a\n  \"Templates\" panel\
  \ in the editor toolbar) appends the template JSONL\n  content to any existing editor\
  \ content\n- If the editor was not open (empty state), it opens automatically\n\n\
  ### Requirement: Deep-Link to Editor\n- `?view=editor` in the URL opens the editor\
  \ automatically on page load\n- `?template=<content>` (URL-encoded JSONL) pre-fills\
  \ the editor with\n  the provided content on page load\n\n## Key Design Decisions\n\
  \n- **Editor**: CodeMirror 6 with a custom JSONL language mode (JSON mode\n  applied\
  \ per-line). Monaco is too heavy for this secondary editor.\n- **Live preview parser**:\
  \ runs on every keypress with a 200 ms debounce;\n  parses each non-empty line as\
  \ JSON and accumulates counts + errors.\n- **Floating indicator**: a Pinia store\
  \ (`useMutationSubmission`) tracks\n  submission state so the indicator persists\
  \ across route changes; it\n  renders in `AppLayout.vue` (outside the page router-view).\n\
  - **Large-file mode**: triggered when `file.size > 5 * 1024 * 1024`;\n  editor `readOnly`\
  \ is set to true and a banner replaces the normal\n  editing affordances.\n- Deep-link\
  \ `?template=` is base64-encoded to avoid query-string escaping\n  issues with JSONL\
  \ newlines.\n\n## Files / Areas Affected\n\n- `src/ui/src/pages/explore/MutationsConsolePage.vue`\n\
  - `src/ui/src/components/JsonlEditor.vue` (CodeMirror 6 wrapper)\n- `src/ui/src/components/MutationsPreviewPanel.vue`\n\
  - `src/ui/src/components/MutationsSubmitIndicator.vue` (floating)\n- `src/ui/src/components/MutationTemplates.vue`\n\
  - `src/ui/src/components/KnowledgeGraphSelector.vue`\n- `src/ui/src/composables/useJsonlParser.ts`\n\
  - `src/ui/src/composables/useDragDrop.ts`\n- `src/ui/src/stores/mutationSubmission.ts`\n\
  - `src/ui/src/lib/api/graph.ts` (bulk mutations endpoint wrapper)\n- Updated `src/ui/src/layouts/AppLayout.vue`\
  \ (mounts floating indicator)\n\n## How to Verify\n\n```bash\nmake instance-up\n\
  source .instances/$(basename $(pwd))/.env.instance\ncd src/ui && npm run dev\n```\n\
  \n1. Navigate to Explore → Mutations Console → empty state with two buttons\n  \
  \ and four template cards\n2. Click \"Create Node\" template → editor opens with\
  \ a DEFINE+CREATE\n   template; live preview shows \"1 DEFINE, 1 CREATE\"\n3. Type\
  \ a syntax error on a line → red gutter marker appears\n4. Add a second valid CREATE\
  \ line → preview updates to \"1 DEFINE, 2 CREATE\"\n5. Select a knowledge graph\
  \ from the dropdown → Apply button enables\n6. Ctrl+Enter → floating indicator appears\
  \ in bottom-right \"Submitting…\"\n7. Navigate to Schema Browser → indicator is\
  \ still visible; navigate back\n8. Drag a `.jsonl` file onto the page → content\
  \ loads into editor\n9. Upload a 6 MB file → large-file mode: editor disabled, summary\
  \ shown\n10. Navigate to `/explore/mutations?template=<base64>` → editor opens\n\
  \    pre-filled with the decoded template content\n\n## Caveats\n\n- The bulk mutations\
  \ API endpoint (`POST /graph/mutations` or equivalent)\n  must exist on the backend\
  \ for submission to work; if not yet wired the\n  submit button should show a clear\
  \ \"coming soon\" message rather than\n  silently failing.\n- Ctrl/Cmd+Enter is\
  \ already registered globally in task-151; the mutations\n  console page overrides\
  \ it locally when the editor is focused, then\n  restores the global handler on\
  \ unmount.\n- Template content is hard-coded in the UI (JSON schemas for each\n\
  \  operation type); it does not come from the server."
---
