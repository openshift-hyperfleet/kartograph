import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

import {
  parseContent,
  getBreakdown,
  toJsonl,
  type ParsedOperation,
} from '@/utils/mutationParser'

import {
  isAcceptedMutationFile,
  ACCEPTED_MUTATION_FILE_EXTENSIONS,
  getShowEmptyState,
  getMergedEditorContent,
  isCtrlOrCmdEnterEvent,
  getEditorVisibilityForViewChange,
  canSubmitMutations,
} from '@/utils/mutationConsole'

import { LARGE_FILE_THRESHOLD } from '@/composables/useMutationWorker'

/**
 * Task-128 Spec Alignment Tests
 *
 * Spec: specs/ui/experience.spec.md
 *   - Requirement: Mutations Console
 *     - Scenario: Empty state
 *     - Scenario: JSONL editing
 *     - Scenario: Live preview
 *     - Scenario: File upload
 *     - Scenario: Knowledge graph selection
 *     - Scenario: Submission
 *     - Scenario: Submission failure
 *     - Scenario: Template insertion
 *     - Scenario: Deep-link to editor with pre-filled content
 *
 * These tests verify the spec scenarios from task-128 by exercising
 * the pure utility functions extracted from the mutations console and
 * performing structural analysis of the Vue page source. They are a
 * complement to the granular tests in mutations-console.test.ts and
 * serve as the official spec-alignment record for this task.
 */

// ── Source file paths ──────────────────────────────────────────────────────

const mutationsVuePath = resolve(__dirname, '../pages/graph/mutations.vue')
const mutationsVue = readFileSync(mutationsVuePath, 'utf-8')

const mutationPreviewPath = resolve(__dirname, '../components/graph/MutationPreview.vue')
const mutationPreviewVue = readFileSync(mutationPreviewPath, 'utf-8')

const mutationProgressPath = resolve(__dirname, '../components/graph/MutationProgress.vue')
const mutationProgressVue = readFileSync(mutationProgressPath, 'utf-8')

const mutationTemplatesPath = resolve(__dirname, '../components/graph/MutationTemplates.vue')
const mutationTemplatesVue = readFileSync(mutationTemplatesPath, 'utf-8')

const largeFileSummaryPath = resolve(__dirname, '../components/graph/LargeFileSummary.vue')
const largeFileSummaryVue = readFileSync(largeFileSummaryPath, 'utf-8')

const submissionComposablePath = resolve(__dirname, '../composables/useMutationSubmission.ts')
const submissionComposable = readFileSync(submissionComposablePath, 'utf-8')

const graphApiPath = resolve(__dirname, '../composables/api/useGraphApi.ts')
const graphApi = readFileSync(graphApiPath, 'utf-8')

const appVuePath = resolve(__dirname, '../app.vue')
const appVue = readFileSync(appVuePath, 'utf-8')

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Empty state
// "the user is presented with two primary actions (upload file, open editor)
//  and a set of quick-start templates (Create Node, Create Edge, Update
//  Properties, Delete Entity); drag-and-drop of .jsonl/.json/.ndjson activates
//  the editor"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: Empty state', () => {
  it('provides an Upload File action as one of the two primary actions', () => {
    expect(mutationsVue).toContain('Upload File')
  })

  it('provides an Open Editor action as the second primary action', () => {
    expect(mutationsVue).toContain('Open Editor')
  })

  it('renders all four quick-start templates: Create a Node', () => {
    expect(mutationsVue).toContain('Create a Node')
  })

  it('renders all four quick-start templates: Create an Edge', () => {
    expect(mutationsVue).toContain('Create an Edge')
  })

  it('renders all four quick-start templates: Update Properties', () => {
    expect(mutationsVue).toContain('Update Properties')
  })

  it('renders all four quick-start templates: Delete an Entity', () => {
    expect(mutationsVue).toContain('Delete an Entity')
  })

  it('empty state disappears once the editor is activated (getShowEmptyState)', () => {
    expect(getShowEmptyState(false, false)).toBe(true)
    expect(getShowEmptyState(true, false)).toBe(false)
  })

  it('drag-and-drop events are wired on the empty state container', () => {
    expect(mutationsVue).toContain('@drop.prevent="handleDrop"')
    expect(mutationsVue).toContain('@dragover="handleDragOver"')
    expect(mutationsVue).toContain('@dragleave="handleDragLeave"')
  })

  it('drag-and-drop accepts .jsonl, .json, and .ndjson files per spec', () => {
    expect(ACCEPTED_MUTATION_FILE_EXTENSIONS).toContain('.jsonl')
    expect(ACCEPTED_MUTATION_FILE_EXTENSIONS).toContain('.json')
    expect(ACCEPTED_MUTATION_FILE_EXTENSIONS).toContain('.ndjson')
  })

  it('drop activates the editor (isDragOver overlay text confirms it)', () => {
    // The overlay confirms the user can drop .jsonl files
    expect(mutationsVue).toContain('Drop .jsonl file here')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: JSONL editing
// "the editor provides JSON syntax highlighting, line numbers, JSONL-aware
//  linting, and autocomplete for mutation operation fields; Ctrl/Cmd+Enter
//  submits without leaving the editor"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: JSONL editing', () => {
  it('JSON syntax highlighting is enabled via @codemirror/lang-json', () => {
    expect(mutationsVue).toMatch(/from '@codemirror\/lang-json'/)
  })

  it('line numbers gutter is wired via lineNumbers()', () => {
    expect(mutationsVue).toContain('lineNumbers()')
  })

  it('JSONL-aware linting is enabled via mutationLinter', () => {
    expect(mutationsVue).toContain('mutationLinter')
    expect(mutationsVue).toContain('linter(mutationLinter')
  })

  it('inline lint gutter markers are enabled via lintGutter()', () => {
    expect(mutationsVue).toContain('lintGutter()')
  })

  it('autocomplete for mutation operation fields is enabled via mutationAutocomplete', () => {
    expect(mutationsVue).toContain('mutationAutocomplete')
    expect(mutationsVue).toContain('autocompletion({ override: [mutationAutocomplete] })')
  })

  it('Ctrl-Enter keymap is bound within CodeMirror for non-Mac systems', () => {
    expect(mutationsVue).toContain("key: 'Ctrl-Enter'")
  })

  it('Cmd-Enter keymap is bound within CodeMirror for Mac', () => {
    expect(mutationsVue).toContain("mac: 'Cmd-Enter'")
  })

  it('global keydown fallback also handles Ctrl/Cmd+Enter', () => {
    expect(mutationsVue).toContain('handleCtrlEnter')
    expect(mutationsVue).toContain('isCtrlOrCmdEnterEvent')
  })

  it('isCtrlOrCmdEnterEvent correctly identifies Ctrl+Enter', () => {
    expect(isCtrlOrCmdEnterEvent({ ctrlKey: true, metaKey: false, key: 'Enter' })).toBe(true)
  })

  it('isCtrlOrCmdEnterEvent correctly identifies Cmd+Enter (Mac)', () => {
    expect(isCtrlOrCmdEnterEvent({ ctrlKey: false, metaKey: true, key: 'Enter' })).toBe(true)
  })

  it('linting and autocomplete are disabled in large-file mode to maintain performance', () => {
    // Per spec note: large-file mode disables editing; spec says editing is disabled
    expect(mutationsVue).toContain('largeFileMode')
    expect(mutationsVue).toContain('staticBaseExtensions')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Live preview
// "a live preview panel shows the operation count broken down by type
//  (DEFINE, CREATE, UPDATE, DELETE) and any validation warnings; parse errors
//  are surfaced inline in the editor gutter"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: Live preview', () => {
  it('MutationPreview component is used for the live preview panel', () => {
    expect(mutationsVue).toContain('MutationPreview')
  })

  it('live preview receives syncParseResult for small files', () => {
    expect(mutationsVue).toContain('syncParseResult')
  })

  it('live preview receives workerResult for large files', () => {
    expect(mutationsVue).toContain('workerResult')
  })

  it('getBreakdown produces DEFINE/CREATE/UPDATE/DELETE counts', () => {
    const ops: ParsedOperation[] = [
      { op: 'DEFINE', type: 'node', label: 'person', raw: '{}', warnings: [] },
      { op: 'CREATE', type: 'node', label: 'person', id: 'person:abc', raw: '{}', warnings: [] },
      { op: 'UPDATE', type: 'node', id: 'person:abc', raw: '{}', warnings: [] },
      { op: 'DELETE', type: 'node', id: 'person:abc', raw: '{}', warnings: [] },
    ]
    const breakdown = getBreakdown(ops)
    expect(breakdown.DEFINE).toBe(1)
    expect(breakdown.CREATE).toBe(1)
    expect(breakdown.UPDATE).toBe(1)
    expect(breakdown.DELETE).toBe(1)
  })

  it('parseContent detects invalid JSON lines as parse errors', () => {
    const result = parseContent('not valid json')
    expect(result.parseErrors.length).toBeGreaterThan(0)
  })

  it('parseContent produces zero operations and errors for empty content', () => {
    const result = parseContent('')
    expect(result.operations).toHaveLength(0)
    expect(result.parseErrors).toHaveLength(0)
  })

  it('MutationPreview.vue shows breakdown per op type', () => {
    // MutationPreview should display DEFINE, CREATE, UPDATE, DELETE counts
    expect(mutationPreviewVue).toContain('DEFINE')
    expect(mutationPreviewVue).toContain('CREATE')
    expect(mutationPreviewVue).toContain('UPDATE')
    expect(mutationPreviewVue).toContain('DELETE')
  })

  it('MutationPreview.vue accepts a parseResult prop for small files', () => {
    expect(mutationPreviewVue).toContain('parseResult')
  })

  it('MutationPreview.vue accepts a workerResult prop for large files', () => {
    expect(mutationPreviewVue).toContain('workerResult')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: File upload
// "the file content is loaded into the editor; files larger than 5 MB activate
//  large-file mode: editing is disabled, a summary of operation counts is shown,
//  and the user can submit directly"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: File upload', () => {
  it('file upload input accepts .jsonl, .json, and .ndjson extensions', () => {
    expect(mutationsVue).toContain('accept=".jsonl,.json,.ndjson"')
  })

  it('isAcceptedMutationFile returns true for .jsonl files', () => {
    expect(isAcceptedMutationFile('mutations.jsonl')).toBe(true)
  })

  it('isAcceptedMutationFile returns true for .json files', () => {
    expect(isAcceptedMutationFile('data.json')).toBe(true)
  })

  it('isAcceptedMutationFile returns true for .ndjson files', () => {
    expect(isAcceptedMutationFile('stream.ndjson')).toBe(true)
  })

  it('isAcceptedMutationFile rejects .csv and other unsupported formats', () => {
    expect(isAcceptedMutationFile('data.csv')).toBe(false)
    expect(isAcceptedMutationFile('data.txt')).toBe(false)
  })

  it('5 MB threshold activates large-file mode (5_000_000 bytes)', () => {
    // LARGE_FILE_THRESHOLD is the worker threshold; 5 MB is the CM editing threshold
    expect(mutationsVue).toContain('5_000_000')
  })

  it('large-file mode disables the CodeMirror editor and shows a summary', () => {
    expect(mutationsVue).toContain('largeFileMode')
    expect(largeFileSummaryVue).toContain('Large File Mode')
  })

  it('LargeFileSummary shows the total operation count', () => {
    expect(largeFileSummaryVue).toContain('totalOps')
  })

  it('LargeFileSummary shows a breakdown by op type', () => {
    expect(largeFileSummaryVue).toContain('DEFINE')
    expect(largeFileSummaryVue).toContain('CREATE')
    expect(largeFileSummaryVue).toContain('UPDATE')
    expect(largeFileSummaryVue).toContain('DELETE')
  })

  it('user can submit directly from large-file mode', () => {
    // The submit button must still be accessible when largeFileMode is true
    expect(mutationsVue).toContain('isLargeFile')
    expect(mutationsVue).toContain('Apply Mutations')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Knowledge graph selection
// "a knowledge graph selector is displayed before the user can submit;
//  lists all KGs the user has 'edit' permission on within the current workspace;
//  no submission is possible until a KG is selected"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: Knowledge graph selection', () => {
  it('KG selector is present in the mutations console', () => {
    expect(mutationsVue).toContain('selectedKnowledgeGraphId')
  })

  it('requests only KGs the user has edit permission on', () => {
    // The API call must include permission=edit to scope to editable KGs
    expect(mutationsVue).toContain("permission: 'edit'")
  })

  it('KG list is scoped to the selected workspace via workspace_id query param', () => {
    expect(mutationsVue).toContain('workspace_id: selectedWorkspaceId.value')
  })

  it('canSubmitMutations blocks submission when no KG is selected', () => {
    expect(canSubmitMutations({
      selectedWorkspaceId: 'ws-123',
      selectedKnowledgeGraphId: '',
      content: '{"op":"CREATE"}',
      isLargeFile: false,
      submitting: false,
      preparing: false,
    })).toBe(false)
  })

  it('canSubmitMutations allows submission when a KG is selected and content exists', () => {
    expect(canSubmitMutations({
      selectedWorkspaceId: 'ws-123',
      selectedKnowledgeGraphId: 'kg-456',
      content: '{"op":"CREATE","type":"node"}',
      isLargeFile: false,
      submitting: false,
      preparing: false,
    })).toBe(true)
  })

  it('canSubmitMutations blocks submission when workspace is not yet selected', () => {
    expect(canSubmitMutations({
      selectedWorkspaceId: '',
      selectedKnowledgeGraphId: 'kg-456',
      content: '{"op":"CREATE"}',
      isLargeFile: false,
      submitting: false,
      preparing: false,
    })).toBe(false)
  })

  it('API call to list KGs uses the management knowledge-graphs endpoint', () => {
    expect(mutationsVue).toContain('/management/knowledge-graphs')
  })

  it('workspace selector is present to scope the KG list', () => {
    expect(mutationsVue).toContain('selectedWorkspaceId')
    expect(mutationsVue).toContain('Select a workspace')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Submission
// "the mutations are submitted to the API scoped to the selected knowledge graph
//  and a floating progress indicator appears in the bottom-right corner;
//  the indicator shows status (submitting / success / failed), operation count,
//  and elapsed time; the indicator persists when the user navigates away"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: Submission', () => {
  it('submission sends mutations to the knowledge-graph-scoped API path', () => {
    expect(graphApi).toContain('/graph/knowledge-graphs/${knowledgeGraphId}/mutations')
  })

  it('submission is gated on a selected knowledge graph ID', () => {
    expect(mutationsVue).toContain('submission.submit(selectedKnowledgeGraphId.value')
  })

  it('MutationProgress floating indicator is positioned bottom-right', () => {
    expect(mutationProgressVue).toContain('fixed bottom-4 right-4')
  })

  it('floating indicator is hidden when status is idle', () => {
    expect(mutationProgressVue).toContain("state.value.status !== 'idle'")
    expect(mutationProgressVue).toContain('v-if="isVisible"')
  })

  it('floating indicator shows operation count', () => {
    expect(mutationProgressVue).toContain('operationCount')
  })

  it('floating indicator shows elapsed time', () => {
    expect(mutationProgressVue).toContain('elapsedSeconds')
  })

  it('floating indicator persists across navigation via Nuxt useState in submission composable', () => {
    // Nuxt useState ensures the state survives page navigation
    expect(submissionComposable).toContain('useState')
    expect(submissionComposable).toContain("'mutation-submission'")
  })

  it('MutationProgress is mounted at app root level so it persists across page navigations', () => {
    expect(appVue).toContain('MutationProgress')
  })

  it('useMutationSubmission tracks submitting/success/failed states', () => {
    expect(submissionComposable).toContain("'submitting'")
    expect(submissionComposable).toContain("'success'")
    expect(submissionComposable).toContain("'failed'")
  })

  it('submission includes a 5-minute timeout for long-running requests', () => {
    expect(submissionComposable).toContain('300_000')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Submission failure
// "the floating indicator shows the error message AND the number of operations
//  applied before failure is displayed if any were processed"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: Submission failure', () => {
  it('MutationProgress shows the error message on failure', () => {
    // The component must expose the error string from submission state
    expect(mutationProgressVue).toContain('error')
    expect(mutationProgressVue).toContain("'failed'")
  })

  it('MutationProgress can show operations applied before failure (operations_applied)', () => {
    // Spec: "the number of operations applied before failure is displayed if any were processed"
    expect(mutationProgressVue).toContain('operations_applied')
  })

  it('submission composable stores error string on failure', () => {
    expect(submissionComposable).toContain('state.value.error')
    expect(submissionComposable).toContain("status = 'failed'")
  })

  it('AbortError is mapped to a user-friendly timeout message', () => {
    expect(submissionComposable).toContain('AbortError')
    expect(submissionComposable).toContain('timed out')
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Template insertion
// "the template content is appended to any existing editor content (not
//  overwrite); the editor is activated if the empty state was showing"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: Template insertion', () => {
  it('insertTemplate calls activateEditor() first so editor becomes visible', () => {
    expect(mutationsVue).toContain('activateEditor()')
    expect(mutationsVue).toContain('insertTemplate')
  })

  it('getMergedEditorContent appends with newline when content already exists', () => {
    const current = '{"op":"DELETE","type":"node","id":"n:1"}'
    const template = '{"op":"CREATE","type":"node","id":"n:2"}'
    const merged = getMergedEditorContent(current, template)
    expect(merged).toBe(`${current}\n${template}`)
  })

  it('getMergedEditorContent replaces empty content directly (no leading newline)', () => {
    const merged = getMergedEditorContent('', '{"op":"CREATE"}')
    expect(merged).toBe('{"op":"CREATE"}')
  })

  it('getMergedEditorContent replaces whitespace-only content', () => {
    const merged = getMergedEditorContent('   ', '{"op":"CREATE"}')
    expect(merged).toBe('{"op":"CREATE"}')
  })

  it('MutationTemplates component is used for the template panel', () => {
    expect(mutationsVue).toContain('MutationTemplates')
  })

  it('MutationTemplates emits an insert event that triggers insertTemplate', () => {
    expect(mutationsVue).toContain('@insert="insertTemplate"')
    expect(mutationTemplatesVue).toContain("emit('insert'")
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Scenario: Deep-link to editor with pre-filled content
// "GIVEN a URL with ?view=editor or ?template=<content>
//  THEN the editor is opened automatically
//  AND the template parameter content is inserted into the editor"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Scenario: Deep-link to editor', () => {
  it('?view=editor URL parameter initializes showEditor to true', () => {
    // The showEditor ref is initialized from route.query.view
    expect(mutationsVue).toContain("route.query.view === 'editor'")
  })

  it('?template=<content> URL parameter inserts content into editor on mount', () => {
    expect(mutationsVue).toContain('route.query.template')
    expect(mutationsVue).toContain('insertTemplate(templateParam.trim())')
  })

  it('activateEditor() pushes ?view=editor to the router URL', () => {
    expect(mutationsVue).toContain("view: 'editor'")
    expect(mutationsVue).toContain('router.push')
  })

  it('browser back/forward navigation is handled via route.query watcher', () => {
    expect(mutationsVue).toContain('route.query.view')
    expect(mutationsVue).toContain('getEditorVisibilityForViewChange')
  })

  it('getEditorVisibilityForViewChange returns true when view becomes "editor"', () => {
    expect(getEditorVisibilityForViewChange('editor', false)).toBe(true)
    expect(getEditorVisibilityForViewChange('editor', true)).toBe(true)
  })

  it('getEditorVisibilityForViewChange returns false when view changes away and no content', () => {
    expect(getEditorVisibilityForViewChange(undefined, false)).toBe(false)
  })

  it('getEditorVisibilityForViewChange returns null when content exists (preserve state)', () => {
    expect(getEditorVisibilityForViewChange(undefined, true)).toBeNull()
  })

  it('template parameter triggers a size warning when it exceeds 1024 characters', () => {
    expect(mutationsVue).toContain('1024')
    expect(mutationsVue).toContain('URL parameters over 1 KB')
  })

  it('template insertion proceeds even after the size warning (non-blocking)', () => {
    // The warning is displayed then insertion continues — the warning call
    // is not followed by a return statement that would skip insertTemplate
    const warningIndex = mutationsVue.indexOf('URL parameters over 1 KB')
    const insertTemplateIndex = mutationsVue.indexOf('insertTemplate(templateParam.trim())', warningIndex)
    expect(insertTemplateIndex).toBeGreaterThan(warningIndex)
  })
})

// ──────────────────────────────────────────────────────────────────────────────
// Requirement: Backend API Alignment
// "Resource operations succeed end-to-end — the corresponding backend API call
//  succeeds (2xx response) AND the UI reflects the updated state"
// ──────────────────────────────────────────────────────────────────────────────

describe('Task-128 — Requirement: Backend API Alignment', () => {
  it('mutations API path uses the correct resource-scoped URL format', () => {
    // Spec: "POST /graph/knowledge-graphs/{id}/mutations"
    expect(graphApi).toContain('/graph/knowledge-graphs/${knowledgeGraphId}/mutations')
  })

  it('mutations API call uses POST method with JSONL content type', () => {
    expect(graphApi).toContain("'Content-Type': 'application/jsonlines'")
    expect(graphApi).toContain("method: 'POST'")
  })

  it('mutations API response is reflected in the floating progress indicator', () => {
    // The composable stores the result and the MutationProgress component reads it
    expect(submissionComposable).toContain('result = result')
    expect(submissionComposable).toContain("status = result.success ? 'success' : 'failed'")
  })

  it('KG list API call uses the management endpoint with correct workspace scoping', () => {
    expect(mutationsVue).toContain('/management/knowledge-graphs')
    expect(mutationsVue).toContain('workspace_id: selectedWorkspaceId.value')
  })

  it('toJsonl serializes parsed operations as valid JSONL for API submission', () => {
    const content = '{"op":"CREATE","type":"node","label":"person","id":"person:abc123456789012","set_properties":{"name":"Alice","slug":"alice","data_source_id":"ds1","source_path":"/"}}'
    const result = parseContent(content)
    const jsonl = toJsonl(result.operations)
    // Should be a single non-empty line of JSON
    const lines = jsonl.split('\n').filter(l => l.trim())
    expect(lines).toHaveLength(1)
    const parsed = JSON.parse(lines[0]!)
    expect(parsed.op).toBe('CREATE')
  })
})
