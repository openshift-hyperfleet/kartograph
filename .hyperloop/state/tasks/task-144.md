---
id: task-144
title: "UI Mutations Console — JSONL editor, live preview, templates, deep-link"
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-140]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add mutations console editor with JSONL editing, live preview, and templates"
pr_description: |
  ## What and Why

  The Mutations Console lets power users author and apply bulk graph mutations
  directly using a structured JSONL format (DEFINE, CREATE, UPDATE, DELETE
  operations). This task implements the authoring side: the empty state, the
  JSONL editor with live validation, the preview panel, template quick-starts,
  and deep-link support. The submission flow (KG selection, progress indicator,
  file upload) is handled separately in task-145 to keep each task focused.

  This corresponds to `Explore → Mutations Console` in the sidebar.

  ## Spec Requirements Satisfied

  `specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da`:

  - **Requirement: Mutations Console — Scenario: Empty state**
    "two primary actions (upload file, open editor); quick-start templates
    (Create Node, Create Edge, Update Properties, Delete Entity);
    drag and drop .jsonl/.json/.ndjson onto the page"

  - **Requirement: Mutations Console — Scenario: JSONL editing**
    "JSON syntax highlighting, line numbers, JSONL-aware linting, autocomplete for
    mutation operation fields; Ctrl/Cmd+Enter submits without leaving editor"

  - **Requirement: Mutations Console — Scenario: Live preview**
    "operation count by type (DEFINE, CREATE, UPDATE, DELETE); validation warnings;
    parse errors inline in editor gutter"

  - **Requirement: Mutations Console — Scenario: Template insertion**
    "template content appended to existing editor content; editor activated if not open"

  - **Requirement: Mutations Console — Scenario: Deep-link to editor with pre-filled content**
    "?view=editor opens editor automatically; ?template=<content> inserts template content"

  - **Requirement: Interaction Principles — Scenario: Keyboard shortcuts**
    Ctrl/Cmd+Enter in the editor triggers submission (wired to task-145's submit action).

  ## Key Design Decisions

  - **Editor**: CodeMirror 6 with JSON language support. A custom JSONL linter
    validates each line as a valid JSON object and checks that the `op` field
    is one of `DEFINE`, `CREATE`, `UPDATE`, `DELETE`. Parse errors are surfaced
    as gutter markers (red dot + tooltip).
  - **Live preview panel**: A reactive computed property re-parses the editor
    content on every keystroke (debounced 300ms). Output: a breakdown card showing
    counts per op type and a list of validation warnings (e.g., missing `id` field).
  - **Empty state**: Two large action cards side-by-side ("Upload File" and "Open
    Editor") plus four quick-start template buttons below.
  - **Template system**: `src/ui/data/mutation-templates.ts` exports
    `CREATE_NODE`, `CREATE_EDGE`, `UPDATE_PROPERTIES`, `DELETE_ENTITY` template
    strings. Selecting one appends the content to the editor buffer.
  - **Deep-link**: `onMounted` reads `?view=editor` (opens editor) and
    `?template=<base64>` (decodes and inserts into editor).
  - **State management**: Editor content stored in a Pinia store so the floating
    progress indicator (task-145) can persist across page navigation.

  ## What Files Are Affected

  - **New**: `src/ui/pages/explore/mutations.vue`
  - **New**: `src/ui/components/mutations/JsonlEditor.vue` (CodeMirror wrapper)
  - **New**: `src/ui/components/mutations/MutationPreviewPanel.vue`
  - **New**: `src/ui/components/mutations/MutationEmptyState.vue`
  - **New**: `src/ui/components/mutations/TemplateSelector.vue`
  - **New**: `src/ui/data/mutation-templates.ts`
  - **New**: `src/ui/stores/mutationsConsole.ts` (Pinia store)
  - **New**: `src/ui/tests/unit/JsonlEditor.test.ts`
  - **New**: `src/ui/tests/unit/MutationPreviewPanel.test.ts`
  - **New**: `src/ui/tests/unit/mutationsConsole.store.test.ts`

  ## How to Verify

  ```bash
  cd src/ui && npm run dev
  # Navigate to /explore/mutations
  # 1. Empty state shows Upload and Open Editor cards, plus 4 template buttons
  # 2. Click "Open Editor" — editor panel appears with cursor in JSON mode
  # 3. Type a valid CREATE mutation line — preview panel shows "CREATE: 1"
  # 4. Introduce a syntax error — red gutter marker appears with tooltip
  # 5. Click a template button — template appended to editor content
  # 6. Navigate to /explore/mutations?view=editor — editor opens automatically
  # 7. Navigate to /explore/mutations?template=<base64> — content pre-filled
  ```

  Unit tests:
  ```bash
  cd src/ui && npm run test:unit -- mutations
  # MutationPreviewPanel: correctly counts op types; surfaces validation warnings
  # JsonlEditor linter: flags invalid JSON lines; flags unknown op values
  # mutationsConsole store: content persists across component unmount/remount
  ```

  ## Caveats

  - The `?template=<content>` query param should be base64-encoded to handle
    newlines and special characters cleanly. Document the encoding in the
    component's JSDoc.
  - Ctrl/Cmd+Enter in the editor should emit a `submit` event that task-145's
    submission wrapper listens to. Do not couple the editor component to the
    submission logic directly.
---
