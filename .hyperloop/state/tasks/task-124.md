---
id: task-124
title: 'UI: Mutations Console — Editor, Templates & Live Preview'
spec_ref: specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da
status: not_started
phase: null
deps:
- task-118
- task-119
round: 0
branch: null
pr: null
pr_title: 'feat(ui): add mutations console with JSONL editor, live preview, and templates'
pr_description: "## What & Why\n\nImplements the editing and preview half of the Mutations\
  \ Console — the power-user\ntool for authoring and previewing graph mutations as\
  \ JSONL before applying them.\nThis PR covers: empty state with quick-start templates,\
  \ the JSONL editor with syntax\nhighlighting and linting, the live preview panel,\
  \ and template insertion. The\nsubmission workflow and file upload are covered by\
  \ task-125.\n\n## Spec Requirements Satisfied\n\nFrom `specs/ui/experience.spec.md`\
  \ (Requirement: Mutations Console):\n- **Scenario: Empty state** — two primary actions\
  \ (upload file, open editor),\n  quick-start templates (Create Node, Create Edge,\
  \ Update Properties, Delete Entity),\n  drag-and-drop JSONL/JSON/NDJSON file to\
  \ load\n- **Scenario: JSONL editing** — JSON syntax highlighting, line numbers,\n\
  \  JSONL-aware linting, autocomplete for mutation operation fields,\n  `Ctrl/Cmd+Enter`\
  \ triggers submission (wired to the submit handler added in task-125)\n- **Scenario:\
  \ Live preview** — operation count by type (DEFINE, CREATE, UPDATE,\n  DELETE),\
  \ validation warnings, inline parse errors in editor gutter\n- **Scenario: Template\
  \ insertion** — template content appended to existing editor\n  content; editor\
  \ activates if not already open\n- **Scenario: Deep-link to editor** — `?view=editor`\
  \ auto-opens the editor;\n  `?template=<content>` inserts content into the editor\
  \ on load\n\n## Empty State\n\nThe page at `/graph/mutations` with no content loaded\
  \ shows:\n- Two large action cards: **Upload File** (opens file picker) and **Open\
  \ Editor**\n  (activates the JSONL editor panel)\n- A \"Quick-start templates\"\
  \ section below with four template cards:\n  | Template | Example operation |\n\
  \  |---|---|\n  | Create Node | `{\"operation\": \"CREATE\", \"type\": \"node\"\
  , \"label\": \"Person\", \"properties\": {}}` |\n  | Create Edge | `{\"operation\"\
  : \"CREATE\", \"type\": \"edge\", \"label\": \"KNOWS\", ...}` |\n  | Update Properties\
  \ | `{\"operation\": \"UPDATE\", ...}` |\n  | Delete Entity | `{\"operation\": \"\
  DELETE\", ...}` |\n\n## JSONL Editor\n\n- **Engine:** CodeMirror 6 with `@codemirror/lang-json`\n\
  - **Line numbers** always visible\n- **JSONL-aware linting:** parses each line as\
  \ independent JSON; reports parse\n  errors on the specific line in the gutter;\
  \ valid lines are not re-highlighted\n- **Autocomplete:** suggests mutation operation\
  \ fields\n  (`operation`, `type`, `label`, `properties`, `id`, `start_id`, `end_id`)\n\
  \  as the user types within a JSON object\n- `Ctrl/Cmd+Enter`: calls the submit\
  \ handler (from task-125); shown as a tooltip\n  on the \"Apply Mutations\" button\n\
  \n## Live Preview Panel\n\nRendered alongside the editor (split-pane or tab on narrow\
  \ screens):\n- **Operation count** broken down: `DEFINE: n`, `CREATE: n`, `UPDATE:\
  \ n`,\n  `DELETE: n` — updated on every keystroke (debounced 200ms)\n- **Validation\
  \ warnings:** e.g., \"Line 3: missing required field 'label'\"\n- **Parse errors**\
  \ shown as both gutter markers and summary in the preview panel\n\n## Template Insertion\n\
  \n- Clicking a template card appends the template JSON line(s) to the editor (with\
  \ a\n  newline separator if the editor has existing content)\n- If the editor is\
  \ not yet open, it is activated first, then the template is inserted\n\n## Deep-link\n\
  \n- `/graph/mutations?view=editor` → immediately opens the editor panel\n- `/graph/mutations?template=<url-encoded-content>`\
  \ → opens editor and inserts the\n  decoded content\n\n## Files / Areas Affected\n\
  \n- `src/ui/src/pages/explore/MutationsConsole.vue` — top-level page\n- `src/ui/src/components/mutations/EmptyState.vue`\n\
  - `src/ui/src/components/mutations/JsonlEditor.vue` — CodeMirror wrapper\n- `src/ui/src/components/mutations/LivePreview.vue`\n\
  - `src/ui/src/components/mutations/TemplateCard.vue`\n- `src/ui/src/composables/useMutationParsing.ts`\
  \ — JSONL parse + operation counting\n\n## How to Verify\n\n1. Navigate to `/graph/mutations`\
  \ → empty state with two action cards and templates\n2. Click \"Open Editor\" →\
  \ editor panel slides in\n3. Click \"Create Node\" template card → JSON line appended\
  \ to editor; line count > 0\n4. Type invalid JSON on a new line → gutter shows error\
  \ icon; preview shows warning\n5. Type valid JSONL with CREATE and DELETE lines\
  \ → preview shows `CREATE: 1, DELETE: 1`\n6. Navigate to `/graph/mutations?view=editor`\
  \ → editor is open immediately\n7. Navigate to `/graph/mutations?template=%7B%22operation%22%3A...%7D`\
  \ → content pre-inserted\n\n## Caveats / Follow-up\n\n- File upload and submission\
  \ workflow are in task-125\n- `Ctrl/Cmd+Enter` in this PR calls a no-op stub until\
  \ task-125 wires the actual\n  submit handler"
---
