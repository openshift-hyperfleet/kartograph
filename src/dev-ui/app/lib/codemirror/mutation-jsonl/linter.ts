import type { Diagnostic } from '@codemirror/lint'
import type { EditorView } from '@codemirror/view'

// ── Schema constants ────────────────────────────────────────────────────────

const VALID_OPS = new Set(['DEFINE', 'CREATE', 'UPDATE', 'DELETE'])
const VALID_TYPES = new Set(['node', 'edge'])
const ID_PATTERN = /^[0-9a-z_]+:[0-9a-f]{16}$/

/** Valid field names per operation type. */
const FIELDS_BY_OP: Record<string, ReadonlySet<string>> = {
  DEFINE: new Set(['op', 'type', 'label', 'description', 'required_properties', 'optional_properties']),
  CREATE: new Set(['op', 'type', 'id', 'label', 'set_properties', 'start_id', 'end_id']),
  UPDATE: new Set(['op', 'type', 'id', 'set_properties', 'remove_properties']),
  DELETE: new Set(['op', 'type', 'id']),
}

/** All valid field names across every operation. */
const ALL_FIELDS = new Set([
  'op', 'type', 'id', 'label', 'description',
  'required_properties', 'optional_properties',
  'set_properties', 'remove_properties',
  'start_id', 'end_id',
])

// ── Helpers ─────────────────────────────────────────────────────────────────

function isCommentLine(line: string): boolean {
  const trimmed = line.trimStart()
  return trimmed.startsWith('//') || trimmed.startsWith('#')
}

/**
 * Find the position of a JSON value for a given key within a line.
 * Returns { from, to } offsets relative to the line start, or null.
 */
function findValueSpan(
  lineText: string,
  key: string,
): { from: number; to: number } | null {
  // Match "key" : "value" or "key" : value
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`"${escaped}"\\s*:\\s*`)
  const match = regex.exec(lineText)
  if (!match) return null

  const valueStart = match.index + match[0].length
  const rest = lineText.slice(valueStart)

  if (rest.startsWith('"')) {
    // Scan for closing quote, respecting backslash escapes
    let i = 1
    while (i < rest.length) {
      if (rest[i] === '\\') { i += 2; continue }
      if (rest[i] === '"') {
        return { from: valueStart, to: valueStart + i + 1 }
      }
      i++
    }
    // Unclosed quote — underline to end
    return { from: valueStart, to: lineText.length }
  }

  // Non-string value: find the next comma, brace, or bracket
  const endMatch = rest.match(/[,}\]]/)
  const end = endMatch ? valueStart + endMatch.index! : lineText.length
  return { from: valueStart, to: end }
}

/**
 * Find the span of a JSON key (including its quotes) in the line.
 */
function findKeySpan(
  lineText: string,
  key: string,
): { from: number; to: number } | null {
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`"${escaped}"`)
  const match = regex.exec(lineText)
  if (!match) return null
  return { from: match.index, to: match.index + match[0].length }
}

// ── Lint rules ──────────────────────────────────────────────────────────────

function lintLine(
  lineText: string,
  lineFrom: number,
  lineTo: number,
): Diagnostic[] {
  const diagnostics: Diagnostic[] = []

  // ── 1. JSON parse ─────────────────────────────────────────────────────
  let obj: Record<string, unknown>
  try {
    const parsed = JSON.parse(lineText)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      diagnostics.push({
        from: lineFrom,
        to: lineTo,
        severity: 'error',
        message: 'Each line must be a JSON object',
      })
      return diagnostics
    }
    obj = parsed as Record<string, unknown>
  }
  catch (err) {
    const message = err instanceof Error ? err.message : 'Invalid JSON'
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'error',
      message: `Invalid JSON: ${message}`,
    })
    return diagnostics
  }

  // ── 2. Required field: op ─────────────────────────────────────────────
  if (!obj.op) {
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'error',
      message: 'Missing required field: "op"',
    })
    return diagnostics // Can't validate further without op
  }

  const opStr = String(obj.op).toUpperCase()
  if (!VALID_OPS.has(opStr)) {
    const span = findValueSpan(lineText, 'op')
    diagnostics.push({
      from: lineFrom + (span?.from ?? 0),
      to: lineFrom + (span?.to ?? lineText.length),
      severity: 'error',
      message: `Invalid op "${obj.op}" — must be one of: DEFINE, CREATE, UPDATE, DELETE`,
    })
    return diagnostics
  }

  // ── 3. Required field: type ───────────────────────────────────────────
  if (!obj.type) {
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'error',
      message: 'Missing required field: "type"',
    })
  }
  else if (!VALID_TYPES.has(String(obj.type))) {
    const span = findValueSpan(lineText, 'type')
    diagnostics.push({
      from: lineFrom + (span?.from ?? 0),
      to: lineFrom + (span?.to ?? lineText.length),
      severity: 'error',
      message: `Invalid type "${obj.type}" — must be "node" or "edge"`,
    })
  }

  const entityType = typeof obj.type === 'string' ? obj.type : undefined

  // ── 4. Op-specific validation ─────────────────────────────────────────
  switch (opStr) {
    case 'DEFINE':
      lintDefine(obj, lineText, lineFrom, lineTo, diagnostics)
      break
    case 'CREATE':
      lintCreate(obj, lineText, lineFrom, lineTo, entityType, diagnostics)
      break
    case 'UPDATE':
      lintUpdate(obj, lineText, lineFrom, lineTo, diagnostics)
      break
    case 'DELETE':
      lintDelete(obj, lineText, lineFrom, lineTo, diagnostics)
      break
  }

  // ── 5. Unknown fields ─────────────────────────────────────────────────
  const validFields = FIELDS_BY_OP[opStr] ?? ALL_FIELDS
  for (const key of Object.keys(obj)) {
    if (!validFields.has(key)) {
      const span = findKeySpan(lineText, key)
      diagnostics.push({
        from: lineFrom + (span?.from ?? 0),
        to: lineFrom + (span?.to ?? lineText.length),
        severity: 'warning',
        message: `Unknown field "${key}" for ${opStr} operation`,
      })
    }
  }

  return diagnostics
}

// ── Op-specific linters ─────────────────────────────────────────────────────

function lintDefine(
  obj: Record<string, unknown>,
  lineText: string,
  lineFrom: number,
  lineTo: number,
  diagnostics: Diagnostic[],
) {
  if (!obj.label) {
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'error',
      message: 'DEFINE: missing required field "label"',
    })
  }
}

function lintCreate(
  obj: Record<string, unknown>,
  lineText: string,
  lineFrom: number,
  lineTo: number,
  entityType: string | undefined,
  diagnostics: Diagnostic[],
) {
  // id
  lintIdField(obj, 'id', 'CREATE', lineText, lineFrom, lineTo, diagnostics)

  // label
  if (!obj.label) {
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'error',
      message: 'CREATE: missing required field "label"',
    })
  }

  // set_properties
  if (!obj.set_properties && obj.set_properties !== 0 && obj.set_properties !== false) {
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'error',
      message: 'CREATE: missing required field "set_properties"',
    })
  }
  else if (typeof obj.set_properties !== 'object' || obj.set_properties === null || Array.isArray(obj.set_properties)) {
    const span = findKeySpan(lineText, 'set_properties')
    diagnostics.push({
      from: lineFrom + (span?.from ?? 0),
      to: lineFrom + (span?.to ?? lineText.length),
      severity: 'error',
      message: 'CREATE: set_properties must be an object',
    })
  }
  else if (typeof obj.set_properties === 'object' && obj.set_properties !== null) {
    const props = obj.set_properties as Record<string, unknown>
    if (!props.data_source_id) {
      const span = findKeySpan(lineText, 'set_properties')
      diagnostics.push({
        from: lineFrom + (span?.from ?? 0),
        to: lineFrom + (span?.to ?? lineText.length),
        severity: 'warning',
        message: 'CREATE: set_properties missing "data_source_id"',
      })
    }
    if (!props.source_path) {
      const span = findKeySpan(lineText, 'set_properties')
      diagnostics.push({
        from: lineFrom + (span?.from ?? 0),
        to: lineFrom + (span?.to ?? lineText.length),
        severity: 'warning',
        message: 'CREATE: set_properties missing "source_path"',
      })
    }
    if (entityType === 'node' && !props.slug) {
      const span = findKeySpan(lineText, 'set_properties')
      diagnostics.push({
        from: lineFrom + (span?.from ?? 0),
        to: lineFrom + (span?.to ?? lineText.length),
        severity: 'warning',
        message: 'CREATE node: set_properties missing "slug"',
      })
    }
  }

  // Edge-specific: start_id, end_id
  if (entityType === 'edge') {
    lintIdField(obj, 'start_id', 'CREATE edge', lineText, lineFrom, lineTo, diagnostics)
    lintIdField(obj, 'end_id', 'CREATE edge', lineText, lineFrom, lineTo, diagnostics)
  }
}

function lintUpdate(
  obj: Record<string, unknown>,
  lineText: string,
  lineFrom: number,
  lineTo: number,
  diagnostics: Diagnostic[],
) {
  lintIdField(obj, 'id', 'UPDATE', lineText, lineFrom, lineTo, diagnostics)

  if (!obj.set_properties && !obj.remove_properties) {
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'warning',
      message: 'UPDATE: requires at least one of "set_properties" or "remove_properties"',
    })
  }
}

function lintDelete(
  obj: Record<string, unknown>,
  lineText: string,
  lineFrom: number,
  lineTo: number,
  diagnostics: Diagnostic[],
) {
  lintIdField(obj, 'id', 'DELETE', lineText, lineFrom, lineTo, diagnostics)
}

/**
 * Validate an ID field (id, start_id, end_id) — checks presence and format.
 */
function lintIdField(
  obj: Record<string, unknown>,
  field: string,
  prefix: string,
  lineText: string,
  lineFrom: number,
  lineTo: number,
  diagnostics: Diagnostic[],
) {
  if (!obj[field] && obj[field] !== 0 && obj[field] !== false) {
    diagnostics.push({
      from: lineFrom,
      to: lineTo,
      severity: 'error',
      message: `${prefix}: missing required field "${field}"`,
    })
  }
  else if (typeof obj[field] !== 'string') {
    const span = findValueSpan(lineText, field)
    diagnostics.push({
      from: lineFrom + (span?.from ?? 0),
      to: lineFrom + (span?.to ?? lineText.length),
      severity: 'error',
      message: `${prefix}: ${field} must be a string`,
    })
  }
  else if (!ID_PATTERN.test(obj[field])) {
    const span = findValueSpan(lineText, field)
    diagnostics.push({
      from: lineFrom + (span?.from ?? 0),
      to: lineFrom + (span?.to ?? lineText.length),
      severity: 'error',
      message: `${prefix}: ${field} "${obj[field]}" does not match required format (label:16hexchars)`,
    })
  }
}

// ── Main lint source ────────────────────────────────────────────────────────

/**
 * CodeMirror 6 lint source for JSONL mutation operations.
 *
 * Processes each line independently. Skips blank lines and comment lines
 * (starting with `//` or `#`). Returns diagnostics with precise positions
 * for inline error/warning underlines.
 */
export function mutationLinter(view: EditorView): Diagnostic[] {
  const doc = view.state.doc
  const diagnostics: Diagnostic[] = []

  for (let i = 1; i <= doc.lines; i++) {
    const line = doc.line(i)
    const trimmed = line.text.trim()

    // Skip blank lines and comments
    if (!trimmed || isCommentLine(trimmed)) continue

    const lineDiags = lintLine(line.text, line.from, line.to)
    diagnostics.push(...lineDiags)
  }

  return diagnostics
}
