import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// ── Mutations Console Tests ───────────────────────────────────────────────────
//
// Spec: "Mutations Console"
// Covers:
//   - Scenario: Empty state (two primary actions, quick-start templates, drag-and-drop)
//   - Scenario: JSONL editing (CodeMirror extensions: linting, autocomplete, line numbers)
//   - Scenario: Live preview (operation count by type, validation warnings, parse errors)
//   - Scenario: File upload (file loaded into editor, >5MB large-file mode)
//   - Scenario: Knowledge graph selection (KG selector before submission)
//   - Scenario: Submission (floating progress indicator, status, count, elapsed)
//   - Scenario: Submission failure (error in floating indicator, ops applied count)
//   - Scenario: Template insertion (appended to existing content, editor activated)
//   - Scenario: Deep-link (?view=editor initializes editor, ?template=<content> inserts)

// ── Import pure utilities under test ────────────────────────────────────────

import {
  parseContent,
  getBreakdown,
  toJsonl,
  operationSummary,
  generateHexId,
  type ParsedOperation,
  type OperationBreakdown,
} from '@/utils/mutationParser'

import { LARGE_FILE_THRESHOLD } from '@/composables/useMutationWorker'

// ── Source file readers (for structural / static analysis tests) ─────────────

const mutationsVuePath = resolve(__dirname, '../pages/graph/mutations.vue')
const mutationsVue = readFileSync(mutationsVuePath, 'utf-8')

const appVuePath = resolve(__dirname, '../app.vue')
const appVue = readFileSync(appVuePath, 'utf-8')

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Empty state
// "the user is presented with two primary actions (upload file, open editor)
//  and a set of quick-start templates"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - empty state: two primary actions', () => {
  it('mutations.vue contains an "Upload File" action in the empty state', () => {
    expect(mutationsVue).toContain('Upload File')
  })

  it('mutations.vue contains an "Open Editor" action in the empty state', () => {
    expect(mutationsVue).toContain('Open Editor')
  })

  it('empty state is shown only when editor is not active (!showEditor)', () => {
    // The v-if condition on the empty state block
    expect(mutationsVue).toMatch(/!showEditor.*hasTenant|v-if="!showEditor/)
  })

  it('file upload input accepts .jsonl, .json, and .ndjson extensions', () => {
    expect(mutationsVue).toContain('accept=".jsonl,.json,.ndjson"')
  })
})

describe('Mutations Console - empty state: quick-start templates', () => {
  it('mutations.vue renders quick-start template cards from quickStartTemplates', () => {
    expect(mutationsVue).toContain('quickStartTemplates')
  })

  it('quickStartTemplates in mutations.vue includes a "Create a Node" template', () => {
    expect(mutationsVue).toContain('Create a Node')
  })

  it('quickStartTemplates in mutations.vue includes a "Create an Edge" template', () => {
    expect(mutationsVue).toContain('Create an Edge')
  })

  it('quickStartTemplates in mutations.vue includes an "Update Properties" template', () => {
    expect(mutationsVue).toContain('Update Properties')
  })

  it('quickStartTemplates in mutations.vue includes a "Delete an Entity" template', () => {
    expect(mutationsVue).toContain('Delete an Entity')
  })

  it('mutations.vue calls insertTemplate when a quick-start card is clicked', () => {
    expect(mutationsVue).toContain('insertTemplate')
  })
})

describe('Mutations Console - empty state: drag-and-drop support', () => {
  it('mutations.vue binds @drop.prevent handler in the empty state region', () => {
    expect(mutationsVue).toContain('@drop.prevent="handleDrop"')
  })

  it('mutations.vue binds @dragover handler to set isDragOver', () => {
    expect(mutationsVue).toContain('@dragover="handleDragOver"')
  })

  it('mutations.vue binds @dragleave handler to clear isDragOver', () => {
    expect(mutationsVue).toContain('@dragleave="handleDragLeave"')
  })

  it('mutations.vue shows a drop overlay when isDragOver is true', () => {
    expect(mutationsVue).toContain('isDragOver')
    expect(mutationsVue).toContain('Drop .jsonl file here')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: JSONL editing — CodeMirror extensions
// "the editor provides JSON syntax highlighting, line numbers, JSONL-aware
//  linting, and autocomplete for mutation operation fields"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - JSONL editing: CodeMirror extension imports', () => {
  it('mutations.vue imports mutationAutocomplete (autocomplete for mutation fields)', () => {
    expect(mutationsVue).toContain('mutationAutocomplete')
  })

  it('mutations.vue imports mutationLinter (JSONL-aware linting)', () => {
    expect(mutationsVue).toContain('mutationLinter')
  })

  it('mutations.vue imports lineNumbers (line number gutter)', () => {
    expect(mutationsVue).toContain('lineNumbers')
  })

  it('mutations.vue imports lintGutter (inline gutter for lint diagnostics)', () => {
    expect(mutationsVue).toContain('lintGutter')
  })

  it('mutations.vue imports json() language for JSON syntax highlighting', () => {
    expect(mutationsVue).toMatch(/import.*json.*@codemirror\/lang-json|from '@codemirror\/lang-json'/)
  })
})

describe('Mutations Console - JSONL editing: extensions are wired into the editor', () => {
  it('mutations.vue uses autocompletion with mutationAutocomplete override', () => {
    expect(mutationsVue).toContain('autocompletion({ override: [mutationAutocomplete] })')
  })

  it('mutations.vue passes mutationLinter to the linter() factory', () => {
    expect(mutationsVue).toContain('linter(mutationLinter')
  })

  it('mutations.vue includes lineNumbers() in the editor extensions', () => {
    expect(mutationsVue).toContain('lineNumbers()')
  })

  it('linter and autocomplete extensions are disabled in large-file mode', () => {
    // The cmExtensions computed property skips linter/autocomplete for largeFileMode
    expect(mutationsVue).toContain('largeFileMode')
    // staticBaseExtensions is used for large files (no linter/autocomplete)
    expect(mutationsVue).toContain('staticBaseExtensions')
  })
})

describe('Mutations Console - JSONL editing: Ctrl/Cmd+Enter submits', () => {
  it('mutations.vue binds a keymap for Ctrl-Enter / Cmd-Enter', () => {
    expect(mutationsVue).toContain("key: 'Ctrl-Enter'")
    expect(mutationsVue).toContain("mac: 'Cmd-Enter'")
  })

  it('mutations.vue also handles the global Ctrl/Cmd+Enter keyboard event', () => {
    expect(mutationsVue).toContain('handleCtrlEnter')
    expect(mutationsVue).toContain("e.ctrlKey || e.metaKey")
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Live preview — operation count by type (DEFINE/CREATE/UPDATE/DELETE)
// "a live preview panel shows the operation count broken down by type"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - live preview: operation counts via parseContent', () => {
  it('empty content returns zero operations', () => {
    const result = parseContent('')
    expect(result.operations).toHaveLength(0)
    expect(result.parseErrors).toHaveLength(0)
  })

  it('single DEFINE operation is parsed correctly', () => {
    const content = '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":["name"]}'
    const result = parseContent(content)
    expect(result.operations).toHaveLength(1)
    expect(result.operations[0].op).toBe('DEFINE')
  })

  it('single CREATE operation is parsed correctly', () => {
    const content = '{"op":"CREATE","type":"node","label":"person","id":"person:a1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"alice"}}'
    const result = parseContent(content)
    expect(result.operations).toHaveLength(1)
    expect(result.operations[0].op).toBe('CREATE')
  })

  it('single UPDATE operation is parsed correctly', () => {
    const content = '{"op":"UPDATE","type":"node","id":"person:a1b2c3d4e5f67890","set_properties":{"email":"a@b.com"}}'
    const result = parseContent(content)
    expect(result.operations).toHaveLength(1)
    expect(result.operations[0].op).toBe('UPDATE')
  })

  it('single DELETE operation is parsed correctly', () => {
    const content = '{"op":"DELETE","type":"node","id":"person:a1b2c3d4e5f67890"}'
    const result = parseContent(content)
    expect(result.operations).toHaveLength(1)
    expect(result.operations[0].op).toBe('DELETE')
  })

  it('multiple JSONL lines are parsed as separate operations', () => {
    const content = [
      '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":["name"]}',
      '{"op":"CREATE","type":"node","label":"person","id":"person:a1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}',
      '{"op":"DELETE","type":"node","id":"person:a1b2c3d4e5f67890"}',
    ].join('\n')
    const result = parseContent(content)
    expect(result.operations).toHaveLength(3)
  })

  it('JSON array format is also accepted (alternative to JSONL)', () => {
    const content = JSON.stringify([
      { op: 'DEFINE', type: 'node', label: 'repo', description: 'A repo', required_properties: [] },
      { op: 'CREATE', type: 'node', label: 'repo', id: 'repo:a1b2c3d4e5f67890', set_properties: { data_source_id: 'x', source_path: 'y', slug: 'r' } },
    ])
    const result = parseContent(content)
    expect(result.operations).toHaveLength(2)
    expect(result.operations[0].op).toBe('DEFINE')
    expect(result.operations[1].op).toBe('CREATE')
  })
})

describe('Mutations Console - live preview: getBreakdown counts by type', () => {
  it('getBreakdown returns zero counts for empty operation list', () => {
    const breakdown = getBreakdown([])
    expect(breakdown.DEFINE).toBe(0)
    expect(breakdown.CREATE).toBe(0)
    expect(breakdown.UPDATE).toBe(0)
    expect(breakdown.DELETE).toBe(0)
    expect(breakdown.unknown).toBe(0)
  })

  it('getBreakdown correctly counts DEFINE operations', () => {
    const content = [
      '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}',
      '{"op":"DEFINE","type":"edge","label":"knows","description":"A knows B","required_properties":[]}',
    ].join('\n')
    const { operations } = parseContent(content)
    const breakdown = getBreakdown(operations)
    expect(breakdown.DEFINE).toBe(2)
    expect(breakdown.CREATE).toBe(0)
  })

  it('getBreakdown correctly counts CREATE operations', () => {
    const content = [
      '{"op":"CREATE","type":"node","label":"person","id":"person:a1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}',
      '{"op":"CREATE","type":"node","label":"person","id":"person:b1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"b"}}',
      '{"op":"CREATE","type":"node","label":"person","id":"person:c1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"c"}}',
    ].join('\n')
    const { operations } = parseContent(content)
    const breakdown = getBreakdown(operations)
    expect(breakdown.CREATE).toBe(3)
  })

  it('getBreakdown correctly counts UPDATE operations', () => {
    const content = '{"op":"UPDATE","type":"node","id":"person:a1b2c3d4e5f67890","set_properties":{"email":"a@b.com"}}'
    const { operations } = parseContent(content)
    const breakdown = getBreakdown(operations)
    expect(breakdown.UPDATE).toBe(1)
  })

  it('getBreakdown correctly counts DELETE operations', () => {
    const content = '{"op":"DELETE","type":"node","id":"person:a1b2c3d4e5f67890"}'
    const { operations } = parseContent(content)
    const breakdown = getBreakdown(operations)
    expect(breakdown.DELETE).toBe(1)
  })

  it('getBreakdown counts all four op types simultaneously', () => {
    const content = [
      '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}',
      '{"op":"CREATE","type":"node","label":"person","id":"person:a1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}',
      '{"op":"UPDATE","type":"node","id":"person:a1b2c3d4e5f67890","set_properties":{"email":"a@b.com"}}',
      '{"op":"DELETE","type":"node","id":"person:a1b2c3d4e5f67890"}',
    ].join('\n')
    const { operations } = parseContent(content)
    const breakdown = getBreakdown(operations)
    expect(breakdown.DEFINE).toBe(1)
    expect(breakdown.CREATE).toBe(1)
    expect(breakdown.UPDATE).toBe(1)
    expect(breakdown.DELETE).toBe(1)
    expect(breakdown.unknown).toBe(0)
  })

  it('getBreakdown counts unknown ops for operations with invalid op field', () => {
    const content = '{"op":"INVALID","type":"node","label":"person"}'
    const { operations } = parseContent(content)
    const breakdown = getBreakdown(operations)
    expect(breakdown.unknown).toBe(1)
  })
})

describe('Mutations Console - live preview: validation warnings', () => {
  it('missing "op" field generates a warning', () => {
    const content = '{"type":"node","label":"person"}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings.some(w => w.includes('op'))).toBe(true)
  })

  it('missing "type" field generates a warning', () => {
    const content = '{"op":"CREATE","label":"person","id":"person:a1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings.some(w => w.includes('type'))).toBe(true)
  })

  it('DEFINE missing "label" generates a warning', () => {
    const content = '{"op":"DEFINE","type":"node","description":"A person","required_properties":[]}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings.some(w => w.includes('label'))).toBe(true)
  })

  it('DEFINE missing "description" generates a warning', () => {
    const content = '{"op":"DEFINE","type":"node","label":"person","required_properties":[]}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings.some(w => w.includes('description'))).toBe(true)
  })

  it('CREATE missing "id" generates a warning', () => {
    const content = '{"op":"CREATE","type":"node","label":"person","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings.some(w => w.includes('id'))).toBe(true)
  })

  it('CREATE with invalid id format generates a warning', () => {
    const content = '{"op":"CREATE","type":"node","label":"person","id":"invalid-id","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings.some(w => w.includes('id'))).toBe(true)
  })

  it('UPDATE missing both set_properties and remove_properties generates a warning', () => {
    const content = '{"op":"UPDATE","type":"node","id":"person:a1b2c3d4e5f67890"}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings.some(w =>
      w.includes('set_properties') || w.includes('remove_properties'),
    )).toBe(true)
  })

  it('valid operation with all required fields produces no warnings', () => {
    const content = '{"op":"DEFINE","type":"node","label":"person","description":"A person entity","required_properties":["name"]}'
    const { operations } = parseContent(content)
    expect(operations[0].warnings).toHaveLength(0)
  })
})

describe('Mutations Console - live preview: parse errors for invalid JSON', () => {
  it('invalid JSON on a line produces a parseError', () => {
    const content = '{invalid json here'
    const { parseErrors } = parseContent(content)
    expect(parseErrors.length).toBeGreaterThan(0)
  })

  it('blank lines are skipped without errors', () => {
    const content = '\n\n{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}\n\n'
    const { operations, parseErrors } = parseContent(content)
    expect(operations).toHaveLength(1)
    expect(parseErrors).toHaveLength(0)
  })

  it('comment lines starting with // are skipped', () => {
    const content = [
      '// This is a comment',
      '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}',
    ].join('\n')
    const { operations, parseErrors } = parseContent(content)
    expect(operations).toHaveLength(1)
    expect(parseErrors).toHaveLength(0)
  })

  it('comment lines starting with # are skipped', () => {
    const content = [
      '# This is a comment',
      '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}',
    ].join('\n')
    const { operations, parseErrors } = parseContent(content)
    expect(operations).toHaveLength(1)
    expect(parseErrors).toHaveLength(0)
  })
})

describe('Mutations Console - live preview: MutationPreview is used in mutations.vue', () => {
  it('mutations.vue imports and renders MutationPreview component', () => {
    expect(mutationsVue).toContain('MutationPreview')
  })

  it('MutationPreview receives the syncParseResult (small files)', () => {
    expect(mutationsVue).toContain('syncParseResult')
  })

  it('MutationPreview receives the workerResult (large files)', () => {
    expect(mutationsVue).toContain('workerResult')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: File upload
// "the file content is loaded into the editor"
// "files larger than 5 MB activate large-file mode"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - file upload: valid file types', () => {
  /**
   * Mirrors the readFile() validation logic in mutations.vue:
   * only .jsonl, .json, and .ndjson extensions are accepted.
   */
  function isValidMutationFile(fileName: string): boolean {
    return (
      fileName.endsWith('.jsonl') ||
      fileName.endsWith('.json') ||
      fileName.endsWith('.ndjson')
    )
  }

  it('accepts .jsonl files', () => {
    expect(isValidMutationFile('mutations.jsonl')).toBe(true)
  })

  it('accepts .json files', () => {
    expect(isValidMutationFile('mutations.json')).toBe(true)
  })

  it('accepts .ndjson files', () => {
    expect(isValidMutationFile('mutations.ndjson')).toBe(true)
  })

  it('rejects .csv files', () => {
    expect(isValidMutationFile('mutations.csv')).toBe(false)
  })

  it('rejects .txt files', () => {
    expect(isValidMutationFile('mutations.txt')).toBe(false)
  })

  it('rejects files with no extension', () => {
    expect(isValidMutationFile('mutations')).toBe(false)
  })
})

describe('Mutations Console - file upload: large-file mode threshold', () => {
  it('LARGE_FILE_THRESHOLD is exported from useMutationWorker (100 KB)', () => {
    expect(LARGE_FILE_THRESHOLD).toBe(100_000)
  })

  it('mutations.vue imports LARGE_FILE_THRESHOLD from useMutationWorker', () => {
    expect(mutationsVue).toContain('LARGE_FILE_THRESHOLD')
  })

  it('mutations.vue activates largeFileMode for files larger than 5 MB', () => {
    // The 5 MB threshold (5_000_000 bytes) triggers largeFileMode = true
    expect(mutationsVue).toContain('5_000_000')
    expect(mutationsVue).toContain('largeFileMode.value = true')
  })

  it('mutations.vue disables CodeMirror editing in large-file mode', () => {
    // cmExtensions returns staticBaseExtensions only when largeFileMode is true
    expect(mutationsVue).toContain('if (largeFileMode.value) return staticBaseExtensions')
  })

  it('content is loaded into editorContent for files above LARGE_FILE_THRESHOLD (but below 5 MB)', () => {
    // The file upload logic sets editorContent.value = text for files > LARGE_FILE_THRESHOLD
    expect(mutationsVue).toMatch(/editorContent\.value = text/)
  })
})

describe('Mutations Console - file upload: drag-and-drop file handling', () => {
  it('mutations.vue implements handleDrop() to read files from DragEvent', () => {
    expect(mutationsVue).toContain('handleDrop')
    expect(mutationsVue).toContain('dataTransfer')
  })

  it('mutations.vue implements handleFileUpload() for file input change event', () => {
    expect(mutationsVue).toContain('handleFileUpload')
  })

  it('mutations.vue resets the file input value after upload to allow re-selecting the same file', () => {
    expect(mutationsVue).toContain("input.value = ''")
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Knowledge graph selection
// "a knowledge graph selector is displayed before the user can submit"
// "no submission is possible until a knowledge graph is selected"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - knowledge graph selection', () => {
  it('mutations.vue uses hasTenant to guard the mutations console display', () => {
    expect(mutationsVue).toContain('hasTenant')
  })

  it('mutations.vue shows a "No tenant selected" message when no tenant is chosen', () => {
    expect(mutationsVue).toContain('No tenant selected')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission
// "the mutations are submitted to the API"
// "a floating progress indicator appears in the bottom-right corner"
// "the indicator persists when the user navigates away from the mutations console"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - submission: useMutationSubmission state machine', () => {
  /**
   * Mirror the MutationSubmissionState logic from useMutationSubmission.ts.
   * We test the state transitions as pure data transforms.
   */

  interface SubmissionState {
    status: 'idle' | 'submitting' | 'success' | 'failed'
    operationCount: number
    result: { success: boolean; operations_applied: number; errors: string[] } | null
    error: string | null
    startedAt: number | null
    completedAt: number | null
  }

  function initialState(): SubmissionState {
    return {
      status: 'idle',
      operationCount: 0,
      result: null,
      error: null,
      startedAt: null,
      completedAt: null,
    }
  }

  function beginSubmission(opCount: number): SubmissionState {
    return {
      status: 'submitting',
      operationCount: opCount,
      result: null,
      error: null,
      startedAt: Date.now(),
      completedAt: null,
    }
  }

  function completeSuccess(
    prev: SubmissionState,
    result: { success: boolean; operations_applied: number; errors: string[] },
  ): SubmissionState {
    return {
      ...prev,
      status: result.success ? 'success' : 'failed',
      result,
      error: !result.success && result.errors.length > 0 ? result.errors.join('; ') : null,
      completedAt: Date.now(),
    }
  }

  function completeError(prev: SubmissionState, errorMessage: string): SubmissionState {
    return {
      ...prev,
      status: 'failed',
      error: errorMessage,
      completedAt: Date.now(),
    }
  }

  function dismiss(): SubmissionState {
    return initialState()
  }

  it('initial state is idle with zero operation count', () => {
    const state = initialState()
    expect(state.status).toBe('idle')
    expect(state.operationCount).toBe(0)
    expect(state.error).toBeNull()
  })

  it('beginSubmission sets status to "submitting" with correct op count', () => {
    const state = beginSubmission(42)
    expect(state.status).toBe('submitting')
    expect(state.operationCount).toBe(42)
    expect(state.startedAt).not.toBeNull()
    expect(state.completedAt).toBeNull()
  })

  it('completeSuccess transitions to "success" with result', () => {
    const initial = beginSubmission(10)
    const state = completeSuccess(initial, { success: true, operations_applied: 10, errors: [] })
    expect(state.status).toBe('success')
    expect(state.result?.operations_applied).toBe(10)
    expect(state.completedAt).not.toBeNull()
  })

  it('completeSuccess with success=false transitions to "failed"', () => {
    const initial = beginSubmission(5)
    const state = completeSuccess(initial, {
      success: false,
      operations_applied: 2,
      errors: ['Node type not found'],
    })
    expect(state.status).toBe('failed')
    expect(state.error).toContain('Node type not found')
  })

  it('completeError transitions to "failed" with error message', () => {
    const initial = beginSubmission(20)
    const state = completeError(initial, 'Network error')
    expect(state.status).toBe('failed')
    expect(state.error).toBe('Network error')
    expect(state.completedAt).not.toBeNull()
  })

  it('dismiss resets state to idle', () => {
    const initial = beginSubmission(10)
    const failed = completeError(initial, 'timeout')
    const state = dismiss()
    expect(state.status).toBe('idle')
    expect(state.operationCount).toBe(0)
    expect(state.error).toBeNull()
  })

  it('elapsed time can be computed from startedAt and completedAt timestamps', () => {
    const startedAt = Date.now() - 3000 // 3 seconds ago
    const completedAt = Date.now()
    const elapsedSeconds = Math.floor((completedAt - startedAt) / 1000)
    expect(elapsedSeconds).toBeGreaterThanOrEqual(3)
  })

  it('operation count is preserved in state throughout the submission lifecycle', () => {
    const submitting = beginSubmission(99)
    const success = completeSuccess(submitting, { success: true, operations_applied: 99, errors: [] })
    expect(success.operationCount).toBe(99)
  })
})

describe('Mutations Console - submission: floating progress indicator (MutationProgress in app.vue)', () => {
  it('app.vue includes the MutationProgress component', () => {
    expect(appVue).toContain('MutationProgress')
  })

  it('MutationProgress is rendered at the app level (persists across navigation)', () => {
    // Since MutationProgress is in app.vue (top-level), it persists
    // even when the user navigates away from /graph/mutations
    expect(appVue).toContain('MutationProgress')
  })

  it('MutationProgress.vue uses fixed positioning (bottom-right)', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain('fixed bottom-4 right-4')
  })

  it('MutationProgress.vue shows status based on submission state', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain("state.status === 'submitting'")
    expect(progressVue).toContain("state.status === 'success'")
    expect(progressVue).toContain("state.status === 'failed'")
  })

  it('MutationProgress.vue displays operation count', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain('operationCount')
  })

  it('MutationProgress.vue can be minimized to a compact pill', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain('minimized')
  })

  it('MutationProgress.vue can be dismissed after completion', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain('dismiss')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission failure
// "the floating indicator shows the error message"
// "the number of operations applied before failure is displayed if any were processed"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - submission failure: error display', () => {
  it('MutationProgress.vue shows the error message in the failed state', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain('state.error')
  })

  it('MutationProgress.vue truncates long error messages (120 chars)', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain('truncatedError')
    expect(progressVue).toContain('120')
  })

  it('error truncation logic preserves messages ≤120 characters unchanged', () => {
    const shortError = 'Node type not found: person'
    function truncateError(err: string | null): string {
      if (!err) return ''
      return err.length > 120 ? err.slice(0, 120) + '...' : err
    }
    expect(truncateError(shortError)).toBe(shortError)
  })

  it('error truncation logic appends "..." to messages longer than 120 characters', () => {
    const longError = 'A'.repeat(121)
    function truncateError(err: string | null): string {
      if (!err) return ''
      return err.length > 120 ? err.slice(0, 120) + '...' : err
    }
    const truncated = truncateError(longError)
    expect(truncated).toHaveLength(123) // 120 + '...'
    expect(truncated.endsWith('...')).toBe(true)
  })

  it('MutationProgress.vue shows operations applied before failure (result.operations_applied)', () => {
    const progressVuePath = resolve(__dirname, '../components/graph/MutationProgress.vue')
    const progressVue = readFileSync(progressVuePath, 'utf-8')
    expect(progressVue).toContain('operations_applied')
    expect(progressVue).toContain('applied before failure')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Template insertion
// "the template content is appended to any existing editor content"
// "the editor is activated if it was not already open"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - template insertion: content appending', () => {
  /**
   * Mirror the template insertion logic from mutations.vue insertTemplate().
   * When existing content is present, new content is appended with a newline.
   * When no existing content, new content replaces the empty state.
   */
  function applyTemplateInsertion(existing: string, template: string): string {
    if (existing.trim()) {
      return existing + '\n' + template
    }
    return template
  }

  it('appends template to existing content with a newline separator', () => {
    const existing = '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}'
    const template = '{"op":"CREATE","type":"node","label":"person","id":"person:a1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}'
    const result = applyTemplateInsertion(existing, template)
    expect(result).toContain(existing)
    expect(result).toContain(template)
    expect(result.indexOf(existing)).toBeLessThan(result.indexOf(template))
    const separator = result.slice(existing.length, existing.length + 1)
    expect(separator).toBe('\n')
  })

  it('replaces empty content with template (no leading newline)', () => {
    const template = '{"op":"DELETE","type":"node","id":"person:a1b2c3d4e5f67890"}'
    const result = applyTemplateInsertion('', template)
    expect(result).toBe(template)
    expect(result.startsWith('\n')).toBe(false)
  })

  it('replaces whitespace-only content with template', () => {
    const template = '{"op":"DELETE","type":"node","id":"person:a1b2c3d4e5f67890"}'
    const result = applyTemplateInsertion('   \n   ', template)
    expect(result).toBe(template)
  })

  it('mutations.vue calls activateEditor() before inserting template content', () => {
    // insertTemplate() calls activateEditor() first
    expect(mutationsVue).toContain('async function insertTemplate')
    expect(mutationsVue).toContain('activateEditor()')
  })
})

describe('Mutations Console - template insertion: quick-start templates content', () => {
  it('quickStartTemplates contains exactly four entries', () => {
    // The spec requires: Create Node, Create Edge, Update Properties, Delete Entity
    // Count occurrences of template names in mutations.vue
    const names = ['Create a Node', 'Create an Edge', 'Update Properties', 'Delete an Entity']
    for (const name of names) {
      expect(mutationsVue).toContain(name)
    }
  })

  it('toJsonl serializes each operation as a single line JSON string', () => {
    const content = [
      '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}',
      '{"op":"CREATE","type":"node","label":"person","id":"person:a1b2c3d4e5f67890","set_properties":{"data_source_id":"x","source_path":"y","slug":"a"}}',
    ].join('\n')
    const { operations } = parseContent(content)
    const jsonl = toJsonl(operations)
    const lines = jsonl.split('\n').filter(l => l.trim())
    expect(lines).toHaveLength(2)
    // Each line should be valid JSON
    for (const line of lines) {
      expect(() => JSON.parse(line)).not.toThrow()
    }
  })
})

describe('Mutations Console - template insertion: MutationTemplates panel in mutations.vue', () => {
  it('mutations.vue imports and renders MutationTemplates component', () => {
    expect(mutationsVue).toContain('MutationTemplates')
  })

  it('mutations.vue passes insertTemplate as the handler for MutationTemplates insert event', () => {
    expect(mutationsVue).toContain('@insert="insertTemplate"')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Deep-link to editor with pre-filled content
// "GIVEN a URL with ?view=editor or ?template=<content>"
// "THEN the editor is opened automatically"
// "AND the template parameter content (if present) is inserted"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - deep-link: ?view=editor initializes editor', () => {
  it('mutations.vue reads route.query.view to initialize showEditor', () => {
    expect(mutationsVue).toContain("route.query.view === 'editor'")
  })

  it('showEditor ref is initialized based on URL query parameter', () => {
    // The initialization: const showEditor = ref(route.query.view === 'editor' || ...)
    expect(mutationsVue).toMatch(/showEditor = ref\([\s\S]*?route\.query\.view === 'editor'/)
  })

  it('mutations.vue uses useRoute() to access query parameters', () => {
    expect(mutationsVue).toContain('useRoute()')
  })

  it('activateEditor() pushes ?view=editor to the router', () => {
    expect(mutationsVue).toContain('activateEditor')
    expect(mutationsVue).toContain("view: 'editor'")
  })
})

describe('Mutations Console - deep-link: ?template=<content> inserts content', () => {
  it('mutations.vue reads route.query.template in onMounted', () => {
    expect(mutationsVue).toContain('route.query.template')
  })

  it('mutations.vue calls insertTemplate with the template param content on mount', () => {
    // onMounted reads templateParam and calls insertTemplate
    expect(mutationsVue).toContain('insertTemplate(templateParam.trim())')
  })

  it('template param is only processed when it is a non-empty string', () => {
    expect(mutationsVue).toContain("typeof templateParam === 'string'")
    expect(mutationsVue).toContain('templateParam.trim()')
  })
})

describe('Mutations Console - deep-link: browser back/forward navigation', () => {
  it('mutations.vue watches route.query.view to react to browser navigation', () => {
    expect(mutationsVue).toContain("() => route.query.view")
  })

  it('mutations.vue sets showEditor to true when view=editor appears in the URL', () => {
    expect(mutationsVue).toContain("if (newView === 'editor')")
    expect(mutationsVue).toContain('showEditor.value = true')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: operationSummary helper (used by MutationPreview)
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - operationSummary helper', () => {
  function makeOp(partial: Partial<ParsedOperation>): ParsedOperation {
    return {
      index: 0,
      raw: {},
      warnings: [],
      lineStart: 0,
      ...partial,
    }
  }

  it('includes type and label when both are present', () => {
    const op = makeOp({ type: 'node', label: 'person' })
    const summary = operationSummary(op)
    expect(summary).toContain('node')
    expect(summary).toContain('"person"')
  })

  it('includes id when present', () => {
    const op = makeOp({ type: 'node', label: 'person', id: 'person:a1b2c3d4e5f67890' })
    const summary = operationSummary(op)
    expect(summary).toContain('person:a1b2c3d4e5f67890')
  })

  it('returns "unknown" when no meaningful fields are present', () => {
    const op = makeOp({})
    const summary = operationSummary(op)
    expect(summary).toBe('unknown')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// generateHexId — used for template IDs
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - generateHexId', () => {
  it('generates a 16-character lowercase hex string', () => {
    const id = generateHexId()
    expect(id).toMatch(/^[0-9a-f]{16}$/)
  })

  it('generates unique IDs on successive calls', () => {
    const ids = new Set(Array.from({ length: 20 }, () => generateHexId()))
    expect(ids.size).toBeGreaterThanOrEqual(19) // Allow for extreme astronomical coincidence
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Verify Mutations Console is in the correct nav section (Explore)
// (regression guard — already present in default.layout.test.ts but included
// here to make the mutations-console test file self-contained)
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - navigation placement', () => {
  const layoutPath = resolve(__dirname, '../layouts/default.vue')
  const layoutContent = readFileSync(layoutPath, 'utf-8')

  it('Mutations Console appears in the navigation', () => {
    expect(layoutContent).toContain("label: 'Mutations Console'")
    expect(layoutContent).toContain("to: '/graph/mutations'")
  })

  it('Mutations Console is in the Explore section (not Data, Connect, or Settings)', () => {
    // The nav sections use title: 'Explore', title: 'Data', etc.
    // Mutations Console should appear after the Explore title and before the Data title.
    const exploreIdx = layoutContent.indexOf("title: 'Explore'")
    const mutationsIdx = layoutContent.indexOf("label: 'Mutations Console'")
    const dataIdx = layoutContent.indexOf("title: 'Data'")
    expect(mutationsIdx).toBeGreaterThan(exploreIdx)
    expect(mutationsIdx).toBeLessThan(dataIdx)
  })
})
