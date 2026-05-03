---
id: task-124
title: "UI: Mutations Console — Editor, Templates & Live Preview"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-118, task-119]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add mutations console with JSONL editor, live preview, and templates"
pr_description: |
  ## What & Why

  Implements the editing and preview half of the Mutations Console — the power-user
  tool for authoring and previewing graph mutations as JSONL before applying them.
  This PR covers: empty state with quick-start templates, the JSONL editor with syntax
  highlighting and linting, the live preview panel, and template insertion. The
  submission workflow and file upload are covered by task-125.

  ## Spec Requirements Satisfied

  From `specs/ui/experience.spec.md` (Requirement: Mutations Console):
  - **Scenario: Empty state** — two primary actions (upload file, open editor),
    quick-start templates (Create Node, Create Edge, Update Properties, Delete Entity),
    drag-and-drop JSONL/JSON/NDJSON file to load
  - **Scenario: JSONL editing** — JSON syntax highlighting, line numbers,
    JSONL-aware linting, autocomplete for mutation operation fields,
    `Ctrl/Cmd+Enter` triggers submission (wired to the submit handler added in task-125)
  - **Scenario: Live preview** — operation count by type (DEFINE, CREATE, UPDATE,
    DELETE), validation warnings, inline parse errors in editor gutter
  - **Scenario: Template insertion** — template content appended to existing editor
    content; editor activates if not already open
  - **Scenario: Deep-link to editor** — `?view=editor` auto-opens the editor;
    `?template=<content>` inserts content into the editor on load

  ## Empty State

  The page at `/graph/mutations` with no content loaded shows:
  - Two large action cards: **Upload File** (opens file picker) and **Open Editor**
    (activates the JSONL editor panel)
  - A "Quick-start templates" section below with four template cards:
    | Template | Example operation |
    |---|---|
    | Create Node | `{"operation": "CREATE", "type": "node", "label": "Person", "properties": {}}` |
    | Create Edge | `{"operation": "CREATE", "type": "edge", "label": "KNOWS", ...}` |
    | Update Properties | `{"operation": "UPDATE", ...}` |
    | Delete Entity | `{"operation": "DELETE", ...}` |

  ## JSONL Editor

  - **Engine:** CodeMirror 6 with `@codemirror/lang-json`
  - **Line numbers** always visible
  - **JSONL-aware linting:** parses each line as independent JSON; reports parse
    errors on the specific line in the gutter; valid lines are not re-highlighted
  - **Autocomplete:** suggests mutation operation fields
    (`operation`, `type`, `label`, `properties`, `id`, `start_id`, `end_id`)
    as the user types within a JSON object
  - `Ctrl/Cmd+Enter`: calls the submit handler (from task-125); shown as a tooltip
    on the "Apply Mutations" button

  ## Live Preview Panel

  Rendered alongside the editor (split-pane or tab on narrow screens):
  - **Operation count** broken down: `DEFINE: n`, `CREATE: n`, `UPDATE: n`,
    `DELETE: n` — updated on every keystroke (debounced 200ms)
  - **Validation warnings:** e.g., "Line 3: missing required field 'label'"
  - **Parse errors** shown as both gutter markers and summary in the preview panel

  ## Template Insertion

  - Clicking a template card appends the template JSON line(s) to the editor (with a
    newline separator if the editor has existing content)
  - If the editor is not yet open, it is activated first, then the template is inserted

  ## Deep-link

  - `/graph/mutations?view=editor` → immediately opens the editor panel
  - `/graph/mutations?template=<url-encoded-content>` → opens editor and inserts the
    decoded content

  ## Files / Areas Affected

  - `src/ui/src/pages/explore/MutationsConsole.vue` — top-level page
  - `src/ui/src/components/mutations/EmptyState.vue`
  - `src/ui/src/components/mutations/JsonlEditor.vue` — CodeMirror wrapper
  - `src/ui/src/components/mutations/LivePreview.vue`
  - `src/ui/src/components/mutations/TemplateCard.vue`
  - `src/ui/src/composables/useMutationParsing.ts` — JSONL parse + operation counting

  ## How to Verify

  1. Navigate to `/graph/mutations` → empty state with two action cards and templates
  2. Click "Open Editor" → editor panel slides in
  3. Click "Create Node" template card → JSON line appended to editor; line count > 0
  4. Type invalid JSON on a new line → gutter shows error icon; preview shows warning
  5. Type valid JSONL with CREATE and DELETE lines → preview shows `CREATE: 1, DELETE: 1`
  6. Navigate to `/graph/mutations?view=editor` → editor is open immediately
  7. Navigate to `/graph/mutations?template=%7B%22operation%22%3A...%7D` → content pre-inserted

  ## Caveats / Follow-up

  - File upload and submission workflow are in task-125
  - `Ctrl/Cmd+Enter` in this PR calls a no-op stub until task-125 wires the actual
    submit handler
---
