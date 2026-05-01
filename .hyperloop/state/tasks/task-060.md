---
id: task-060
title: Mutations Console — core editor (empty state, JSONL editing, live preview, file upload, templates, deep-link)
spec_ref: specs/ui/experience.spec.md@14b2efabc5d0910e59494fd9b111b00c8a4383b3
status: not-started
phase: null
deps:
  - task-059
round: 0
branch: null
pr: null
pr_title: "feat(ui): implement Mutations Console — JSONL editor, live preview, file upload, templates, deep-link"
pr_description: |
  ## What & Why

  Implements or audits six of the eight Mutations Console scenarios from
  `specs/ui/experience.spec.md`. The Mutations Console is the power-user path for
  authoring and applying graph mutations directly, without going through the ingestion
  pipeline. The page at `/graph/mutations` may already exist; this task verifies every
  scenario line-by-line before writing any new code (TDD audit approach).

  ## Spec Requirements Satisfied

  - **Empty state** — Two primary action buttons (Upload File, Open Editor) plus four
    quick-start template chips (Create Node, Create Edge, Update Properties, Delete Entity).
    Page-level drag-and-drop accepts `.jsonl`, `.json`, `.ndjson`.
  - **JSONL editing** — CodeMirror 6 editor with JSON syntax highlighting, line numbers,
    JSONL-aware linting (per-line parse errors in gutter), and mutation field autocomplete.
    `Ctrl/Cmd+Enter` submits without leaving the editor.
  - **Live preview** — Panel showing op-count breakdown by type (DEFINE/CREATE/UPDATE/DELETE)
    and validation warnings, updating within 300 ms of typing. Parse errors surfaced
    inline in the gutter.
  - **File upload** — File picker and drag-and-drop both populate the editor. Files > 5 MB
    activate large-file mode: editor disabled, op-count summary shown, submit still enabled.
  - **Template insertion** — Content appended to existing editor content; editor activated
    if closed.
  - **Deep-link** — `?view=editor` opens editor on page load; `?template=<content>` inserts
    the decoded content.

  ## Key Design Decisions

  The CodeMirror 6 wrapper (`useCodemirror` composable) is shared with the Query Console.
  The JSONL linter validates each line independently as JSON — blank lines are allowed.
  Large-file mode uses a Web Worker for background parsing to keep the UI responsive.

  ## Files Affected

  - `src/dev-ui/app/pages/graph/mutations.vue` — main page (audit + fix gaps)
  - `src/dev-ui/app/components/graph/MutationPreview.vue` — live preview panel
  - `src/dev-ui/app/components/graph/MutationTemplates.vue` — template chip list
  - `src/dev-ui/app/lib/codemirror/mutation-jsonl/` — linter + autocomplete extensions
  - `src/dev-ui/app/tests/mutations-console.test.ts` — all spec scenario tests (created)

  ## How to Verify

  1. Navigate to `/graph/mutations` → empty state with two buttons and four template chips.
  2. Click "Open Editor" → CodeMirror editor with line numbers appears.
  3. Type invalid JSON on a line → gutter error marker appears.
  4. Upload a `.jsonl` file > 5 MB → large-file mode summary shown.
  5. Navigate to `/graph/mutations?view=editor` → editor opens automatically.
  6. `cd src/dev-ui && pnpm test` passes with all mutations-console scenario tests.

  ## Caveats

  Depends on task-059 (Mutations Console in sidebar nav) landing first. The submission
  flow (floating progress indicator) is handled separately by task-061.
---

## Spec Coverage

**Requirement: Mutations Console** — 6 of 8 scenarios from `specs/ui/experience.spec.md`:

1. **Empty state** — Two primary actions (upload file, open editor) plus quick-start
   templates (Create Node, Create Edge, Update Properties, Delete Entity). Drag and drop
   of `.jsonl`, `.json`, or `.ndjson` files onto the page loads them.

2. **JSONL editing** — Editor provides JSON syntax highlighting, line numbers, JSONL-aware
   linting, and autocomplete for mutation operation fields. Ctrl/Cmd+Enter submits
   mutations without leaving the editor.

3. **Live preview** — A live preview panel shows operation count broken down by type
   (DEFINE, CREATE, UPDATE, DELETE) and any validation warnings. Parse errors are
   surfaced inline in the editor gutter.

4. **File upload** — Files uploaded via file picker or drag-and-drop are loaded into the
   editor. Files larger than 5 MB activate large-file mode: editing is disabled, a
   summary of operation counts is shown, the user can submit directly.

5. **Template insertion** — Template content is appended to any existing editor content.
   The editor is activated if it was not already open.

6. **Deep-link to editor with pre-filled content** — URL `?view=editor` opens the editor
   automatically. URL `?template=<content>` inserts the content into the editor.

*(Submission and submission failure scenarios are covered by task-061.)*

## Current State

The `/graph/mutations` route exists — it is referenced as the schema browser's third
cross-navigation target (task-048). However, no task has formally specified or verified
any of the 8 Mutations Console scenarios. The existing implementation (if any) must be
audited against each scenario line by line before any code is written.

## Audit Step (Before Any Implementation)

Read `src/dev-ui/app/pages/graph/mutations.vue` (or the equivalent file for the
`/graph/mutations` route). For each scenario above, determine PASS or FAIL:

| Scenario | Check |
|----------|-------|
| Empty state — two primary actions | action buttons present? |
| Empty state — quick-start templates | 4 templates listed? |
| Empty state — drag and drop | drag-and-drop handler on the page element? |
| JSONL editing — syntax highlighting | editor library with JSON/JSONL support? |
| JSONL editing — line numbers | line numbers enabled? |
| JSONL editing — linting | JSONL-aware linter configured? |
| JSONL editing — autocomplete | mutation field autocomplete? |
| JSONL editing — Ctrl/Cmd+Enter submits | keyboard handler present? |
| Live preview — op count by type | DEFINE/CREATE/UPDATE/DELETE breakdown? |
| Live preview — validation warnings | inline warnings shown? |
| Live preview — gutter parse errors | gutter decoration for parse errors? |
| File upload — file picker | `<input type="file">` or equivalent? |
| File upload — drag and drop | drag-and-drop on page-level element? |
| File upload — 5 MB large-file mode | size check and large-file state? |
| Template insertion — appends content | appends, does not replace? |
| Template insertion — activates editor | editor opens if closed? |
| Deep-link — `?view=editor` opens editor | route query detected on mount? |
| Deep-link — `?template=<content>` inserts | template content inserted? |

## Changes Required

### 1. `src/dev-ui/app/tests/mutations-console.test.ts`

Create this test file. Write one test per scenario listed above — **before** implementing
any missing feature. Tests for scenarios that already PASS must still be written as
regression coverage.

**Editor library recommendation:** Use [CodeMirror 6](https://codemirror.net/) with the
`@codemirror/lang-json` package for syntax highlighting, linting, and autocomplete.
Wrap it in a `<MutationsEditor>` component to simplify testing via mocking.

**Key test patterns:**

```typescript
// Empty state — two primary actions
it('shows Upload File and Open Editor buttons when editor is empty and closed', () => {
  const wrapper = mount(MutationsConsole)
  expect(wrapper.find('[data-testid="btn-upload-file"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="btn-open-editor"]').exists()).toBe(true)
})

// File upload — 5 MB large-file mode
it('activates large-file mode for files over 5 MB', async () => {
  const bigFile = new File([new ArrayBuffer(5 * 1024 * 1024 + 1)], 'large.jsonl', {
    type: 'application/x-ndjson',
  })
  await wrapper.find('[data-testid="file-input"]').trigger('change', { target: { files: [bigFile] } })
  expect(wrapper.find('[data-testid="large-file-mode"]').exists()).toBe(true)
  expect(wrapper.find('[data-testid="editor"]').attributes('disabled')).toBeTruthy()
})

// Deep-link — ?view=editor
it('opens editor automatically when ?view=editor is in the URL', async () => {
  const wrapper = mount(MutationsConsole, {
    global: { plugins: [createRouter({ history: createMemoryHistory(), routes })] },
  })
  await router.push('/graph/mutations?view=editor')
  expect(wrapper.find('[data-testid="editor"]').exists()).toBe(true)
})

// Template insertion — appends
it('appends template content to existing editor content', async () => {
  const wrapper = mountWithEditorContent('{"op":"CREATE"}\n')
  await wrapper.vm.insertTemplate('{"op":"DEFINE"}\n')
  expect(getEditorContent(wrapper)).toBe('{"op":"CREATE"}\n{"op":"DEFINE"}\n')
})
```

### 2. `src/dev-ui/app/pages/graph/mutations.vue`

Implement or fix each failing scenario:

**Empty state:**
- Two clearly labelled primary action buttons: "Upload File" and "Open Editor"
- Four quick-start template chips: Create Node, Create Edge, Update Properties, Delete Entity
- Page-level drag-and-drop zone with `@dragover.prevent` and `@drop` handler
  that accepts `.jsonl`, `.json`, `.ndjson` — calls the same `loadFile()` function
  used by the file picker

**JSONL editor (CodeMirror 6 wrapper):**
- JSON highlighting via `@codemirror/lang-json`
- Line numbers via `lineNumbers()` extension
- JSONL-aware linting: each line is independently parsed as JSON; lines that fail
  parse produce a gutter error marker; blank lines are allowed
- Autocomplete: suggest `op`, `type`, `id`, `labels`, `properties`, `source`, `target`
  for mutation objects
- Keyboard: `Ctrl/Cmd+Enter` triggers `submitMutations()` without closing the editor

**Live preview panel:**
- Parse editor content as JSONL on every change (debounced 300 ms)
- Count ops by type (DEFINE, CREATE, UPDATE, DELETE) and display the breakdown
- Show validation warnings (e.g., CREATE without required `id` field)
- Propagate parse errors back to the editor as gutter decorations

**File upload:**
- `<input type="file" accept=".jsonl,.json,.ndjson">` hidden input triggered by "Upload File" button
- Drag-and-drop on the page root element (not just the editor area)
- Read file as text via `FileReader`
- If `file.size > 5 * 1024 * 1024`: set `isLargeFile = true`, set editor `readOnly = true`,
  show op-count summary only, keep "Apply Mutations" button enabled

**Template insertion:**
- `insertTemplate(content: string)` appends to the current editor content (does not replace)
- If the editor is closed (`editorOpen === false`): set `editorOpen = true` first, then append
- Clicking a quick-start template chip calls `insertTemplate` with the appropriate boilerplate

**Deep-link:**
- In `onMounted` (or a `watch` on `route.query`): check for `?view=editor` → set `editorOpen = true`
- Check for `?template=<content>` → call `insertTemplate(decodeURIComponent(route.query.template))`

### 3. Component structure (if not already separated)

```
src/dev-ui/app/
  components/
    mutations/
      MutationsEditor.vue     — CodeMirror 6 wrapper
      LivePreview.vue          — op-count breakdown + validation warnings
      TemplateChip.vue         — single quick-start template button
  pages/
    graph/
      mutations.vue            — orchestrates all of the above
  tests/
    mutations-console.test.ts  — all spec scenarios
```

## Acceptance Criteria

- Empty state shows two primary action buttons and four quick-start template chips.
- Page-level drag-and-drop loads `.jsonl`, `.json`, `.ndjson` files.
- Editor provides JSON syntax highlighting, line numbers, JSONL linting, and autocomplete.
- Ctrl/Cmd+Enter inside the editor triggers submission (not tab-out or form submit).
- Live preview updates within 300 ms of typing; shows op breakdown and validation warnings.
- Parse errors appear in the editor gutter.
- File picker and drag-and-drop both populate the editor.
- Files > 5 MB activate large-file mode (read-only editor, op-count summary, submit enabled).
- Template insertion appends content; activates editor if closed.
- `?view=editor` query param opens the editor on load.
- `?template=<content>` query param inserts content on load.
- All tests in `src/dev-ui/app/tests/mutations-console.test.ts` pass.
- No regressions: `cd src/dev-ui && pnpm test`

## UI Location

- `src/dev-ui/app/pages/graph/mutations.vue` — Mutations Console page
- `src/dev-ui/app/components/mutations/` — sub-components (editor, preview, templates)
- `src/dev-ui/app/tests/mutations-console.test.ts` — spec scenario tests

## Dependencies

- **task-059** must be complete: the Mutations Console must appear in the sidebar
  Explore group before this page is the formal target of navigation.

## TDD Cycle

1. Read `pages/graph/mutations.vue` — audit each scenario (PASS/FAIL table above).
2. Create `tests/mutations-console.test.ts` — write one failing test per scenario gap.
3. Implement missing features in `mutations.vue` and sub-components.
4. Run `cd src/dev-ui && pnpm test` — all tests pass.
5. Commit atomically per conventional commit conventions.
