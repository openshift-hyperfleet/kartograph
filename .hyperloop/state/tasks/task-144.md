---
id: task-144
title: UI Mutations Console — JSONL editor, live preview, templates, deep-link
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: in_progress
phase: implement
deps:
- task-140
round: 0
branch: hyperloop/task-144
pr: null
pr_title: 'feat(ui): add mutations console editor with JSONL editing, live preview,
  and templates'
pr_description: "## What and Why\n\nThe Mutations Console lets power users author\
  \ and apply bulk graph mutations\ndirectly using a structured JSONL format (DEFINE,\
  \ CREATE, UPDATE, DELETE\noperations). This task implements the authoring side:\
  \ the empty state, the\nJSONL editor with live validation, the preview panel, template\
  \ quick-starts,\nand deep-link support. The submission flow (KG selection, progress\
  \ indicator,\nfile upload) is handled separately in task-145 to keep each task focused.\n\
  \nThis corresponds to `Explore → Mutations Console` in the sidebar.\n\n## Spec Requirements\
  \ Satisfied\n\n`specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:\n\
  \n- **Requirement: Mutations Console — Scenario: Empty state**\n  \"two primary\
  \ actions (upload file, open editor); quick-start templates\n  (Create Node, Create\
  \ Edge, Update Properties, Delete Entity);\n  drag and drop .jsonl/.json/.ndjson\
  \ onto the page\"\n\n- **Requirement: Mutations Console — Scenario: JSONL editing**\n\
  \  \"JSON syntax highlighting, line numbers, JSONL-aware linting, autocomplete for\n\
  \  mutation operation fields; Ctrl/Cmd+Enter submits without leaving editor\"\n\n\
  - **Requirement: Mutations Console — Scenario: Live preview**\n  \"operation count\
  \ by type (DEFINE, CREATE, UPDATE, DELETE); validation warnings;\n  parse errors\
  \ inline in editor gutter\"\n\n- **Requirement: Mutations Console — Scenario: Template\
  \ insertion**\n  \"template content appended to existing editor content; editor\
  \ activated if not open\"\n\n- **Requirement: Mutations Console — Scenario: Deep-link\
  \ to editor with pre-filled content**\n  \"?view=editor opens editor automatically;\
  \ ?template=<content> inserts template content\"\n\n- **Requirement: Interaction\
  \ Principles — Scenario: Keyboard shortcuts**\n  Ctrl/Cmd+Enter in the editor triggers\
  \ submission (wired to task-145's submit action).\n\n## Key Design Decisions\n\n\
  - **Editor**: CodeMirror 6 with JSON language support. A custom JSONL linter\n \
  \ validates each line as a valid JSON object and checks that the `op` field\n  is\
  \ one of `DEFINE`, `CREATE`, `UPDATE`, `DELETE`. Parse errors are surfaced\n  as\
  \ gutter markers (red dot + tooltip).\n- **Live preview panel**: A reactive computed\
  \ property re-parses the editor\n  content on every keystroke (debounced 300ms).\
  \ Output: a breakdown card showing\n  counts per op type and a list of validation\
  \ warnings (e.g., missing `id` field).\n- **Empty state**: Two large action cards\
  \ side-by-side (\"Upload File\" and \"Open\n  Editor\") plus four quick-start template\
  \ buttons below.\n- **Template system**: `src/ui/data/mutation-templates.ts` exports\n\
  \  `CREATE_NODE`, `CREATE_EDGE`, `UPDATE_PROPERTIES`, `DELETE_ENTITY` template\n\
  \  strings. Selecting one appends the content to the editor buffer.\n- **Deep-link**:\
  \ `onMounted` reads `?view=editor` (opens editor) and\n  `?template=<base64>` (decodes\
  \ and inserts into editor).\n- **State management**: Editor content stored in a\
  \ Pinia store so the floating\n  progress indicator (task-145) can persist across\
  \ page navigation.\n\n## What Files Are Affected\n\n- **New**: `src/ui/pages/explore/mutations.vue`\n\
  - **New**: `src/ui/components/mutations/JsonlEditor.vue` (CodeMirror wrapper)\n\
  - **New**: `src/ui/components/mutations/MutationPreviewPanel.vue`\n- **New**: `src/ui/components/mutations/MutationEmptyState.vue`\n\
  - **New**: `src/ui/components/mutations/TemplateSelector.vue`\n- **New**: `src/ui/data/mutation-templates.ts`\n\
  - **New**: `src/ui/stores/mutationsConsole.ts` (Pinia store)\n- **New**: `src/ui/tests/unit/JsonlEditor.test.ts`\n\
  - **New**: `src/ui/tests/unit/MutationPreviewPanel.test.ts`\n- **New**: `src/ui/tests/unit/mutationsConsole.store.test.ts`\n\
  \n## How to Verify\n\n```bash\ncd src/ui && npm run dev\n# Navigate to /explore/mutations\n\
  # 1. Empty state shows Upload and Open Editor cards, plus 4 template buttons\n#\
  \ 2. Click \"Open Editor\" — editor panel appears with cursor in JSON mode\n# 3.\
  \ Type a valid CREATE mutation line — preview panel shows \"CREATE: 1\"\n# 4. Introduce\
  \ a syntax error — red gutter marker appears with tooltip\n# 5. Click a template\
  \ button — template appended to editor content\n# 6. Navigate to /explore/mutations?view=editor\
  \ — editor opens automatically\n# 7. Navigate to /explore/mutations?template=<base64>\
  \ — content pre-filled\n```\n\nUnit tests:\n```bash\ncd src/ui && npm run test:unit\
  \ -- mutations\n# MutationPreviewPanel: correctly counts op types; surfaces validation\
  \ warnings\n# JsonlEditor linter: flags invalid JSON lines; flags unknown op values\n\
  # mutationsConsole store: content persists across component unmount/remount\n```\n\
  \n## Caveats\n\n- The `?template=<content>` query param should be base64-encoded\
  \ to handle\n  newlines and special characters cleanly. Document the encoding in\
  \ the\n  component's JSDoc.\n- Ctrl/Cmd+Enter in the editor should emit a `submit`\
  \ event that task-145's\n  submission wrapper listens to. Do not couple the editor\
  \ component to the\n  submission logic directly."
---
