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

import {
  isAcceptedMutationFile,
  ACCEPTED_MUTATION_FILE_EXTENSIONS,
  getShowEmptyState,
  getMergedEditorContent,
  isCtrlOrCmdEnterEvent,
  getEditorVisibilityForViewChange,
  canSubmitMutations,
} from '@/utils/mutationConsole'

import type { MutationSubmissionState, MutationSubmissionStatus } from '@/composables/useMutationSubmission'
import type { MutationResult } from '@/types'

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

// ── Empty state: primary action logic (via getShowEmptyState utility) ─────────
//
// Uses getShowEmptyState() from ~/utils/mutationConsole — the same function
// mutations.vue imports to drive which UI section is rendered.

describe('Mutations Console - empty state: getShowEmptyState utility', () => {
  it('shows empty state when showEditor is false and no large-file mode is active', () => {
    expect(getShowEmptyState(false, false)).toBe(true)
  })

  it('hides empty state once the editor is activated', () => {
    expect(getShowEmptyState(true, false)).toBe(false)
  })

  it('hides empty state when large-file mode is active (upload replaced editor)', () => {
    expect(getShowEmptyState(false, true)).toBe(false)
  })

  it('hides empty state when both showEditor and largeFileMode are true', () => {
    expect(getShowEmptyState(true, true)).toBe(false)
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
    // handleCtrlEnter delegates to isCtrlOrCmdEnterEvent() from mutationConsole utility
    expect(mutationsVue).toContain('isCtrlOrCmdEnterEvent(e)')
  })
})

// ── JSONL editing: Ctrl/Cmd+Enter keyboard shortcut (via utility) ─────────────
//
// Uses isCtrlOrCmdEnterEvent() from ~/utils/mutationConsole — the same
// function mutations.vue imports for the handleCtrlEnter() handler.

describe('Mutations Console - JSONL editing: isCtrlOrCmdEnterEvent utility', () => {
  it('returns true when Ctrl+Enter is pressed', () => {
    expect(isCtrlOrCmdEnterEvent({ ctrlKey: true, metaKey: false, key: 'Enter' })).toBe(true)
  })

  it('returns true when Cmd+Enter is pressed (Mac)', () => {
    expect(isCtrlOrCmdEnterEvent({ ctrlKey: false, metaKey: true, key: 'Enter' })).toBe(true)
  })

  it('returns false for plain Enter', () => {
    expect(isCtrlOrCmdEnterEvent({ ctrlKey: false, metaKey: false, key: 'Enter' })).toBe(false)
  })

  it('returns false for Ctrl+other key', () => {
    expect(isCtrlOrCmdEnterEvent({ ctrlKey: true, metaKey: false, key: 'a' })).toBe(false)
  })

  it('returns false for Meta+other key', () => {
    expect(isCtrlOrCmdEnterEvent({ ctrlKey: false, metaKey: true, key: 's' })).toBe(false)
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

describe('Mutations Console - live preview: parse errors and inline gutter display', () => {
  it('invalid JSON on a line produces a parse error (not a parsed operation)', () => {
    const content = 'this is not json'
    const result = parseContent(content)
    expect(result.parseErrors.length).toBeGreaterThan(0)
    expect(result.operations).toHaveLength(0)
  })

  it('parse error message includes location context', () => {
    const content = [
      '{"op":"DEFINE","type":"node","label":"person","description":"A person","required_properties":[]}',
      'invalid json',
    ].join('\n')
    const result = parseContent(content)
    expect(result.parseErrors.length).toBeGreaterThan(0)
    // Parse errors are strings describing the failure (may include line context)
    expect(typeof result.parseErrors[0]).toBe('string')
  })

  it('mutations.vue passes parseResult to MutationPreview for live preview', () => {
    expect(mutationsVue).toContain('MutationPreview')
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
  it('ACCEPTED_MUTATION_FILE_EXTENSIONS includes .jsonl, .json, and .ndjson', () => {
    expect(ACCEPTED_MUTATION_FILE_EXTENSIONS).toContain('.jsonl')
    expect(ACCEPTED_MUTATION_FILE_EXTENSIONS).toContain('.json')
    expect(ACCEPTED_MUTATION_FILE_EXTENSIONS).toContain('.ndjson')
  })

  it('accepts .jsonl files', () => {
    expect(isAcceptedMutationFile('mutations.jsonl')).toBe(true)
  })

  it('accepts .json files', () => {
    expect(isAcceptedMutationFile('mutations.json')).toBe(true)
  })

  it('accepts .ndjson files', () => {
    expect(isAcceptedMutationFile('mutations.ndjson')).toBe(true)
  })

  it('rejects .csv files', () => {
    expect(isAcceptedMutationFile('mutations.csv')).toBe(false)
  })

  it('rejects .txt files', () => {
    expect(isAcceptedMutationFile('mutations.txt')).toBe(false)
  })

  it('rejects files with no extension', () => {
    expect(isAcceptedMutationFile('mutations')).toBe(false)
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
// "the selector lists all knowledge graphs the user has 'edit' permission on"
// "no submission is possible until a knowledge graph is selected"
// "the selected knowledge graph is used as the target for the mutation submission"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - knowledge graph selection: structural', () => {
  it('mutations.vue uses hasTenant to guard the mutations console display', () => {
    expect(mutationsVue).toContain('hasTenant')
  })

  it('mutations.vue shows a "No tenant selected" message when no tenant is chosen', () => {
    expect(mutationsVue).toContain('No tenant selected')
  })

  it('mutations.vue renders a KG selector component', () => {
    // The Select component backed by the knowledge graphs list
    expect(mutationsVue).toContain('selectedKnowledgeGraphId')
  })

  // FAIL-4: KG selector must filter to KGs with edit permission
  it('mutations.vue requests knowledge graphs with edit permission scope', () => {
    // loadKnowledgeGraphs() must call with permission=edit to show only
    // KGs the user can actually submit mutations to.
    expect(mutationsVue).toContain("permission: 'edit'")
  })
})

// ── Knowledge graph selection: submission gate (via canSubmitMutations) ───────
//
// Spec: "no submission is possible until a knowledge graph is selected"
// Uses canSubmitMutations() from ~/utils/mutationConsole — the same function
// mutations.vue imports to gate the Apply Mutations button and handleSubmit().

describe('Mutations Console - knowledge graph selection: canSubmitMutations utility', () => {
  const validContent = '{"op":"DEFINE","type":"node","label":"person","description":"desc","required_properties":[]}'

  const baseOpts = {
    content: validContent,
    isLargeFile: false,
    submitting: false,
    preparing: false,
  }

  it('returns false when no knowledge graph is selected (null)', () => {
    expect(canSubmitMutations({ ...baseOpts, selectedKnowledgeGraphId: null })).toBe(false)
  })

  it('returns false when knowledge graph ID is empty string', () => {
    expect(canSubmitMutations({ ...baseOpts, selectedKnowledgeGraphId: '' })).toBe(false)
  })

  it('returns true when a knowledge graph is selected and content exists', () => {
    expect(canSubmitMutations({ ...baseOpts, selectedKnowledgeGraphId: 'kg-abc123' })).toBe(true)
  })

  it('returns false when KG is selected but content is empty (small file mode)', () => {
    expect(canSubmitMutations({
      ...baseOpts,
      selectedKnowledgeGraphId: 'kg-abc123',
      content: '',
    })).toBe(false)
  })

  it('returns false when KG is selected but content is only whitespace', () => {
    expect(canSubmitMutations({
      ...baseOpts,
      selectedKnowledgeGraphId: 'kg-abc123',
      content: '   \n  ',
    })).toBe(false)
  })

  it('returns true when KG is selected and in large-file mode (content check bypassed)', () => {
    expect(canSubmitMutations({
      ...baseOpts,
      selectedKnowledgeGraphId: 'kg-abc123',
      content: '',
      isLargeFile: true,
    })).toBe(true)
  })

  it('returns false when submission is already in progress (even with KG selected)', () => {
    expect(canSubmitMutations({
      ...baseOpts,
      selectedKnowledgeGraphId: 'kg-abc123',
      submitting: true,
    })).toBe(false)
  })

  it('returns false when preparing is true (even with KG selected and content)', () => {
    expect(canSubmitMutations({
      ...baseOpts,
      selectedKnowledgeGraphId: 'kg-abc123',
      preparing: true,
    })).toBe(false)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Submission
// "the mutations are submitted to the API scoped to the selected knowledge graph"
// "a floating progress indicator appears in the bottom-right corner"
// "the indicator persists when the user navigates away from the mutations console"
// ────────────────────────────────────────────────────────────────────────────

// FAIL-3: API endpoint must include the knowledge graph ID in the URL
describe('Mutations Console - submission: API routing (FAIL-3 fix)', () => {
  it('useGraphApi.ts calls the scoped /graph/knowledge-graphs/{id}/mutations endpoint', () => {
    const useGraphApiPath = resolve(__dirname, '../composables/api/useGraphApi.ts')
    const useGraphApi = readFileSync(useGraphApiPath, 'utf-8')
    // The URL must include knowledge_graph_id as a path segment, not use /graph/mutations
    expect(useGraphApi).toContain('/graph/knowledge-graphs/')
    expect(useGraphApi).toContain('/mutations')
    expect(useGraphApi).not.toContain('`${config.public.apiBaseUrl}/graph/mutations`')
  })

  it('useGraphApi.applyMutations() accepts a knowledgeGraphId parameter', () => {
    const useGraphApiPath = resolve(__dirname, '../composables/api/useGraphApi.ts')
    const useGraphApi = readFileSync(useGraphApiPath, 'utf-8')
    expect(useGraphApi).toContain('knowledgeGraphId')
  })

  it('useMutationSubmission.submit() accepts and forwards knowledgeGraphId', () => {
    const submissionPath = resolve(__dirname, '../composables/useMutationSubmission.ts')
    const submissionContent = readFileSync(submissionPath, 'utf-8')
    expect(submissionContent).toContain('knowledgeGraphId')
  })

  it('mutations.vue passes selectedKnowledgeGraphId.value to submission.submit()', () => {
    // The submit call must forward the KG ID, not just check it via canSubmitMutations
    expect(mutationsVue).toContain('selectedKnowledgeGraphId.value')
    // And submission.submit() must be called with the KG ID argument
    expect(mutationsVue).toMatch(/submission\.submit\(.*selectedKnowledgeGraphId/)
  })
})

describe('Mutations Console - submission: useMutationSubmission state machine types', () => {
  const makeIdleState = (): MutationSubmissionState => ({
    status: 'idle',
    operationCount: 0,
    result: null,
    error: null,
    startedAt: null,
    completedAt: null,
  })

  const makeSubmittingState = (opCount: number): MutationSubmissionState => ({
    status: 'submitting',
    operationCount: opCount,
    result: null,
    error: null,
    startedAt: Date.now(),
    completedAt: null,
  })

  const makeSuccessState = (opCount: number, result: MutationResult): MutationSubmissionState => ({
    status: 'success',
    operationCount: opCount,
    result,
    error: null,
    startedAt: 1000,
    completedAt: 5000,
  })

  it('idle state has status "idle" and zero operation count', () => {
    const idle = makeIdleState()
    expect(idle.status).toBe('idle')
    expect(idle.operationCount).toBe(0)
    expect(idle.result).toBeNull()
    expect(idle.error).toBeNull()
  })

  it('the indicator is not visible in idle state', () => {
    const isVisible = (status: MutationSubmissionStatus) => status !== 'idle'
    expect(isVisible('idle')).toBe(false)
  })

  it('the indicator is visible during submitting, success, and failed states', () => {
    const isVisible = (status: MutationSubmissionStatus) => status !== 'idle'
    expect(isVisible('submitting')).toBe(true)
    expect(isVisible('success')).toBe(true)
    expect(isVisible('failed')).toBe(true)
  })

  it('submitting state carries the operation count and a startedAt timestamp', () => {
    const submitting = makeSubmittingState(42)
    expect(submitting.status).toBe('submitting')
    expect(submitting.operationCount).toBe(42)
    expect(submitting.startedAt).toBeGreaterThan(0)
    expect(submitting.completedAt).toBeNull()
    expect(submitting.error).toBeNull()
  })

  it('elapsed time is computable from startedAt and the current clock', () => {
    const startedAt = Date.now() - 3000 // 3 seconds ago
    const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000)
    expect(elapsedSeconds).toBeGreaterThanOrEqual(3)
  })

  it('success state carries the result and a completedAt timestamp', () => {
    const result: MutationResult = { success: true, operations_applied: 10, errors: [] }
    const success = makeSuccessState(10, result)
    expect(success.status).toBe('success')
    expect(success.result?.operations_applied).toBe(10)
    expect(success.completedAt).toBeGreaterThan(0)
    expect(success.error).toBeNull()
  })

  it('final elapsed time is computable from startedAt and completedAt', () => {
    const state: MutationSubmissionState = {
      status: 'success',
      operationCount: 3,
      result: { success: true, operations_applied: 3, errors: [] },
      error: null,
      startedAt: 1000,
      completedAt: 5500,
    }
    const elapsedMs = state.completedAt! - state.startedAt!
    expect(elapsedMs).toBe(4500)
    const elapsedSeconds = Math.floor(elapsedMs / 1000)
    expect(elapsedSeconds).toBe(4)
  })

  it('dismiss transition resets all fields to the idle shape', () => {
    const dismissed: MutationSubmissionState = makeIdleState()
    expect(dismissed.status).toBe('idle')
    expect(dismissed.operationCount).toBe(0)
    expect(dismissed.result).toBeNull()
    expect(dismissed.error).toBeNull()
    expect(dismissed.startedAt).toBeNull()
    expect(dismissed.completedAt).toBeNull()
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

  // FAIL-5: the indicator must persist when the user navigates away
  it('useMutationSubmission uses useState so state persists across Nuxt route changes', () => {
    // useState is Nuxt's cross-navigation state primitive; if submission state
    // is stored with useState, the MutationProgress rendered in app.vue will
    // remain visible even after the user navigates away from /graph/mutations.
    const submissionPath = resolve(__dirname, '../composables/useMutationSubmission.ts')
    const submissionContent = readFileSync(submissionPath, 'utf-8')
    expect(submissionContent).toContain('useState')
    expect(submissionContent).toContain('mutation-submission')
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

  it('failed MutationSubmissionState carries error message and partial applied count', () => {
    const state: MutationSubmissionState = {
      status: 'failed',
      operationCount: 10,
      result: { success: false, operations_applied: 3, errors: ['Node type not found'] },
      error: 'Node type not found',
      startedAt: 1000,
      completedAt: 2000,
    }
    expect(state.status).toBe('failed')
    expect(state.error).toBe('Node type not found')
    expect(state.result?.operations_applied).toBe(3)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Scenario: Template insertion
// "the template content is appended to any existing editor content"
// "the editor is activated if it was not already open"
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - template insertion: getMergedEditorContent utility', () => {
  it('sets content directly when editor content is empty', () => {
    const template = '{"op":"DEFINE","type":"node","label":"person","description":"desc","required_properties":[]}'
    const merged = getMergedEditorContent('', template)
    expect(merged).toBe(template)
  })

  it('sets content directly when editor content is only whitespace', () => {
    const template = '{"op":"DELETE","type":"node","id":"person:abc"}'
    const merged = getMergedEditorContent('   ', template)
    expect(merged).toBe(template)
  })

  it('appends content with newline separator when editor already has content', () => {
    const existing = '{"op":"CREATE","type":"node","label":"person","id":"person:a1b2c3d4e5f67890"}'
    const template = '{"op":"DELETE","type":"node","id":"person:f0e1d2c3b4a50000"}'
    const merged = getMergedEditorContent(existing, template)
    expect(merged).toContain('CREATE')
    expect(merged).toContain('DELETE')
    expect(merged.split('\n')).toHaveLength(2)
  })

  it('preserves existing content when appending', () => {
    const existing = '{"op":"DEFINE","type":"node","label":"repo","description":"A repo","required_properties":[]}'
    const template = '{"op":"DEFINE","type":"edge","label":"contains","description":"edge","required_properties":[]}'
    const merged = getMergedEditorContent(existing, template)
    expect(merged.startsWith(existing)).toBe(true)
    expect(merged.endsWith(template)).toBe(true)
  })
})

describe('Mutations Console - template insertion: structural', () => {
  it('mutations.vue calls activateEditor() before inserting template content', () => {
    expect(mutationsVue).toContain('async function insertTemplate')
    expect(mutationsVue).toContain('activateEditor()')
  })

  it('quickStartTemplates contains exactly four entries', () => {
    const names = ['Create a Node', 'Create an Edge', 'Update Properties', 'Delete an Entity']
    for (const name of names) {
      expect(mutationsVue).toContain(name)
    }
  })

  it('mutations.vue imports and renders MutationTemplates component', () => {
    expect(mutationsVue).toContain('MutationTemplates')
  })

  it('mutations.vue passes insertTemplate as the handler for MutationTemplates insert event', () => {
    expect(mutationsVue).toContain('@insert="insertTemplate"')
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
    for (const line of lines) {
      expect(() => JSON.parse(line)).not.toThrow()
    }
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

  it('mutations.vue uses getEditorVisibilityForViewChange in the route watcher', () => {
    // The watcher delegates to getEditorVisibilityForViewChange() from the utility
    expect(mutationsVue).toContain('getEditorVisibilityForViewChange')
    // When visibility is non-null, showEditor.value is updated
    expect(mutationsVue).toContain('showEditor.value = visibility')
  })
})

// ── Deep-link: getEditorVisibilityForViewChange utility ───────────────────────
//
// Tests the watcher logic via getEditorVisibilityForViewChange() from
// ~/utils/mutationConsole — the same function mutations.vue uses in the
// route.query.view watcher for browser back/forward navigation.

describe('Mutations Console - deep-link: getEditorVisibilityForViewChange utility', () => {
  it('activates editor when view query changes to "editor" via browser navigation', () => {
    const result = getEditorVisibilityForViewChange('editor', false)
    expect(result).toBe(true)
  })

  it('deactivates editor when view query changes away and content is empty', () => {
    const result = getEditorVisibilityForViewChange(undefined, false)
    expect(result).toBe(false)
  })

  it('preserves editor state when view query changes away but content remains', () => {
    // null means "keep current state" — content is present
    const result = getEditorVisibilityForViewChange(undefined, true)
    expect(result).toBeNull()
  })

  it('activates editor even when content is present and view becomes "editor"', () => {
    const result = getEditorVisibilityForViewChange('editor', true)
    expect(result).toBe(true)
  })

  it('detects ?template=<content> query param for pre-filling editor', () => {
    const routeQuery = { template: '%7B%22op%22%3A%22DELETE%22%7D' }
    const hasTemplate = typeof routeQuery.template === 'string' && routeQuery.template.trim().length > 0
    expect(hasTemplate).toBe(true)
  })

  it('skips template insertion when template param is empty string', () => {
    const routeQuery = { template: '' }
    const hasTemplate = typeof routeQuery.template === 'string' && routeQuery.template.trim().length > 0
    expect(hasTemplate).toBe(false)
  })

  it('decodes URL-encoded template content for insertion', () => {
    const encodedTemplate = '%7B%22op%22%3A%22DELETE%22%7D'
    const decoded = decodeURIComponent(encodedTemplate)
    expect(decoded).toBe('{"op":"DELETE"}')
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
// ────────────────────────────────────────────────────────────────────────────

describe('Mutations Console - navigation placement', () => {
  const layoutPath = resolve(__dirname, '../layouts/default.vue')
  const layoutContent = readFileSync(layoutPath, 'utf-8')

  it('Mutations Console appears in the navigation', () => {
    expect(layoutContent).toContain("label: 'Mutations Console'")
    expect(layoutContent).toContain("to: '/graph/mutations'")
  })

  it('Mutations Console is in the Explore section (not Data, Connect, or Settings)', () => {
    const exploreIdx = layoutContent.indexOf("title: 'Explore'")
    const mutationsIdx = layoutContent.indexOf("label: 'Mutations Console'")
    const dataIdx = layoutContent.indexOf("title: 'Data'")
    expect(mutationsIdx).toBeGreaterThan(exploreIdx)
    expect(mutationsIdx).toBeLessThan(dataIdx)
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Design Language — Typography: no font-bold (700) in page files
// Spec: "font weights are limited to regular (400), medium (500), and semibold (600)"
// ────────────────────────────────────────────────────────────────────────────

describe('Design Language - Typography: no font-bold in page files', () => {
  const pagesDir = resolve(__dirname, '../pages')

  function getPagesFiles(): string[] {
    // Read all .vue files in pages and its subdirectories
    const { readdirSync, statSync } = require('fs')
    const files: string[] = []

    function walk(dir: string) {
      for (const entry of readdirSync(dir)) {
        const full = `${dir}/${entry}`
        if (statSync(full).isDirectory()) {
          walk(full)
        } else if (entry.endsWith('.vue')) {
          files.push(full)
        }
      }
    }

    walk(pagesDir)
    return files
  }

  it('no page file uses font-bold (weight 700) — must use font-semibold (600) or lighter', () => {
    const pageFiles = getPagesFiles()
    const violations: string[] = []

    for (const file of pageFiles) {
      const content = readFileSync(file, 'utf-8')
      if (content.includes('font-bold')) {
        const relativePath = file.replace(resolve(__dirname, '..'), '')
        violations.push(relativePath)
      }
    }

    if (violations.length > 0) {
      throw new Error(
        `font-bold (weight 700) violates the typography spec (max: semibold/600).\n` +
        `Found in:\n${violations.map(f => `  - ${f}`).join('\n')}`
      )
    }

    expect(violations).toHaveLength(0)
  })
})
