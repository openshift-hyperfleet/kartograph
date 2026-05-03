---
id: task-128
title: UI Mutations Console — JSONL Editor, Live Preview, and Templates
spec_ref: "specs/ui/experience.spec.md@e77913c2cc6d8b719291e2dbb6870519a94d50da"
status: not-started
phase: null
deps: [task-119, task-120]
round: 0
branch: null
pr: null
pr_title: "feat(ui): add mutations console with JSONL editor, live preview, and templates"
pr_description: |
  ## What and Why

  The Mutations Console is the fourth page in the "Explore" group and the primary
  UI for loading structured graph data. It provides a JSONL editor for authoring
  mutation operations and a live preview panel that validates and summarises the
  content before submission.

  This task covers the editor experience and validation. Submission, file upload
  and the floating progress indicator are in task-129 (they share data through the
  same composable but are cleanly separable).

  The workspace context (task-120) is required because the KG selector must list
  KGs the user has `edit` permission on within the current workspace.

  ## Spec Requirements Satisfied

  The following scenarios from **Requirement: Mutations Console** in
  `specs/ui/experience.spec.md`:

  - **Empty state**: two primary actions (Upload File, Open Editor) + four
    quick-start template buttons (Create Node, Create Edge, Update Properties,
    Delete Entity); drag-and-drop of .jsonl/.json/.ndjson activates the editor.
  - **JSONL editing**: JSON syntax highlighting, line numbers, JSONL-aware linting
    (each line must be valid JSON; non-JSON lines flagged), autocomplete for mutation
    operation field names (`operation`, `type`, `id`, `properties`, etc.);
    Ctrl/Cmd+Enter submits without leaving the editor (wired via the submission
    composable from task-129).
  - **Live preview**: side panel updates on each editor change showing:
    operation count by type (DEFINE / CREATE / UPDATE / DELETE); validation
    warnings (duplicate IDs, unknown operation types); parse errors rendered as
    inline gutter markers in the editor.
  - **Knowledge graph selector**: rendered above the editor; lists all KGs the
    user has `edit` permission on; submission is blocked until a KG is selected.
  - **Template insertion**: selecting a quick-start template appends its JSONL
    to existing editor content (not overwrite); editor is activated if the empty
    state was showing.
  - **Deep-link**: `?view=editor` auto-opens the editor; `?template=<content>`
    inserts the URL-decoded template content on mount.

  ## Design Decisions

  - **Editor**: CodeMirror 6 with JSON language support + a custom JSONL linting
    extension that validates each line independently.
  - **Live preview**: debounced (300 ms) parse of the editor content on each change;
    runs in a Web Worker to avoid blocking the main thread for large files.
  - **Gutter markers**: CodeMirror's `gutter` extension renders error icons on
    invalid JSONL lines; clicking the icon shows the error message in a tooltip.
  - **Templates**: defined as a constant (`MUTATION_TEMPLATES`) containing the JSONL
    string for each template; inserted via CodeMirror's `replaceRange` API.
  - **KG selector**: uses the same `useKnowledgeGraphs` composable as task-121
    but filtered to `edit` permission rather than `view`.

  ## Backend APIs Required

  - `GET /api/management/knowledge-graphs?permission=edit` — list editable KGs for selector
  - *(Submission API used in task-129)*

  ## Files / Areas Affected

  - `src/ui/pages/explore/MutationsConsolePage.vue`
  - `src/ui/components/mutations/MutationsEmptyState.vue`
  - `src/ui/components/mutations/JsonlEditor.vue` — CodeMirror wrapper with JSONL linting
  - `src/ui/components/mutations/MutationsPreviewPanel.vue`
  - `src/ui/components/mutations/KnowledgeGraphSelector.vue`
  - `src/ui/composables/useMutations.ts` — shared state (editor content, selected KG, parse results)
  - `src/ui/constants/mutationTemplates.ts`
  - `src/ui/workers/jsonlParser.worker.ts` — Web Worker for live preview parsing

  ## How to Verify

  1. Navigate to `/explore/mutations`: empty state shows Upload + Editor + 4 templates
  2. Click "Open Editor": editor appears with line numbers and JSON highlighting
  3. Type invalid JSON on a line: gutter error marker appears immediately
  4. Type valid JSONL: live preview updates with operation counts per type
  5. Ctrl/Cmd+Enter in editor: submission is triggered (or blocked if no KG selected)
  6. KG selector: lists only KGs with `edit` permission; submission blocked until selected
  7. Click a template: content appended to editor; editor activated if empty state was showing
  8. Navigate to `/explore/mutations?view=editor`: editor opens automatically
  9. Navigate to `/explore/mutations?template=<encoded-json>`: template content inserted

  ## Caveats

  The Web Worker approach for live preview requires a Vite worker import (`?worker`
  suffix). If the build environment doesn't support workers, fall back to synchronous
  parsing on the main thread with a 5 MB document size guard.
---
