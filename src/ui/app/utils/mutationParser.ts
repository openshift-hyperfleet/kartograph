/**
 * Robust JSONL / JSON array parser and domain-level validator for
 * Kartograph mutation operations.
 *
 * Parsing strategy (in order):
 * 1. Try to parse the entire content as a JSON array — each element is one operation.
 * 2. Fall back to line-by-line JSONL parsing:
 *    - Skip blank lines and comment lines (starting with // or #).
 *    - For lines that fail JSON.parse, accumulate consecutive non-parseable lines
 *      and try to parse the accumulated block (handles pretty-printed objects).
 * 3. Report clear, per-operation error messages.
 */

// ── Types ──────────────────────────────────────────────────────────────────

export type OpType = 'DEFINE' | 'CREATE' | 'UPDATE' | 'DELETE'
export type EntityType = 'node' | 'edge'

export interface ParsedOperation {
  /** Zero-based index in the parsed list */
  index: number
  /** The raw parsed JSON object */
  raw: Record<string, unknown>
  /** Extracted op type (may be undefined if invalid) */
  op?: OpType
  /** Extracted entity type */
  type?: EntityType
  /** Extracted label */
  label?: string
  /** Extracted id */
  id?: string
  /** Validation warnings for this operation */
  warnings: string[]
}

export interface ParseResult {
  operations: ParsedOperation[]
  /** Fatal parse errors (JSON syntax issues) */
  parseErrors: string[]
}

export interface OperationBreakdown {
  DEFINE: number
  CREATE: number
  UPDATE: number
  DELETE: number
  unknown: number
}

// ── Constants ──────────────────────────────────────────────────────────────

const VALID_OPS: ReadonlySet<string> = new Set(['DEFINE', 'CREATE', 'UPDATE', 'DELETE'])
const ID_PATTERN = /^[0-9a-z_]+:[0-9a-f]{16}$/

// ── Parsing ────────────────────────────────────────────────────────────────

function isCommentLine(line: string): boolean {
  const trimmed = line.trimStart()
  return trimmed.startsWith('//') || trimmed.startsWith('#')
}

/**
 * Try to parse content as a JSON array first, then fall back to JSONL.
 */
export function parseContent(content: string): ParseResult {
  const trimmed = content.trim()
  if (!trimmed) {
    return { operations: [], parseErrors: [] }
  }

  // Strategy 1: Try as a JSON array
  if (trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        const operations = parsed.map((item, i) => buildOperation(item, i))
        return { operations, parseErrors: [] }
      }
    } catch {
      // Not a valid JSON array — fall through to JSONL
    }
  }

  // Strategy 2: Try as a single JSON object (not wrapped in array)
  if (trimmed.startsWith('{')) {
    try {
      const parsed = JSON.parse(trimmed)
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        return { operations: [buildOperation(parsed, 0)], parseErrors: [] }
      }
    } catch {
      // Not a single JSON object — fall through to JSONL
    }
  }

  // Strategy 3: JSONL line-by-line with accumulation for pretty-printed objects
  return parseJsonl(trimmed)
}

function parseJsonl(content: string): ParseResult {
  const lines = content.split('\n')
  const operations: ParsedOperation[] = []
  const parseErrors: string[] = []

  let accumulator = ''
  let accStartLine = -1

  function flushAccumulator(endLine: number) {
    if (!accumulator.trim()) return
    try {
      const parsed = JSON.parse(accumulator)
      if (Array.isArray(parsed)) {
        parsed.forEach((item, i) => {
          operations.push(buildOperation(item, operations.length))
        })
      } else {
        operations.push(buildOperation(parsed, operations.length))
      }
    } catch {
      parseErrors.push(
        `Lines ${accStartLine + 1}-${endLine + 1}: Invalid JSON — could not parse block`,
      )
    }
    accumulator = ''
    accStartLine = -1
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmedLine = line.trim()

    // Skip blank lines and comments (only if we're not accumulating)
    if (!trimmedLine || isCommentLine(trimmedLine)) {
      if (accumulator.trim()) {
        // We were accumulating — flush before skipping
        flushAccumulator(i - 1)
      }
      continue
    }

    // Try parsing this single line as JSON
    try {
      const parsed = JSON.parse(trimmedLine)
      // If we had an accumulator, flush it first
      if (accumulator.trim()) {
        flushAccumulator(i - 1)
      }
      if (Array.isArray(parsed)) {
        parsed.forEach((item) => {
          operations.push(buildOperation(item, operations.length))
        })
      } else {
        operations.push(buildOperation(parsed, operations.length))
      }
    } catch {
      // Accumulate: this line might be part of a multi-line JSON object
      if (!accumulator.trim()) {
        accStartLine = i
      }
      accumulator += line + '\n'
    }
  }

  // Flush any remaining accumulator
  if (accumulator.trim()) {
    flushAccumulator(lines.length - 1)
  }

  return { operations, parseErrors }
}

// ── Operation Building ─────────────────────────────────────────────────────

function buildOperation(raw: unknown, index: number): ParsedOperation {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    return {
      index,
      raw: {},
      warnings: ['Operation must be a JSON object'],
    }
  }

  const obj = raw as Record<string, unknown>
  const op = typeof obj.op === 'string' ? obj.op.toUpperCase() as OpType : undefined
  const type = typeof obj.type === 'string' ? obj.type as EntityType : undefined
  const label = typeof obj.label === 'string' ? obj.label : undefined
  const id = typeof obj.id === 'string' ? obj.id : undefined

  return {
    index,
    raw: obj,
    op: VALID_OPS.has(op ?? '') ? op : undefined,
    type,
    label,
    id,
    warnings: validateOperation(obj),
  }
}

// ── Validation ─────────────────────────────────────────────────────────────

function validateOperation(obj: Record<string, unknown>): string[] {
  const warnings: string[] = []

  // op is required
  if (!obj.op) {
    warnings.push('Missing required field: op')
    return warnings // Can't validate further without op
  }
  const op = String(obj.op).toUpperCase()
  if (!VALID_OPS.has(op)) {
    warnings.push(`Invalid op "${obj.op}" — must be one of: DEFINE, CREATE, UPDATE, DELETE`)
    return warnings
  }

  // type is required
  if (!obj.type) {
    warnings.push('Missing required field: type')
  } else if (obj.type !== 'node' && obj.type !== 'edge') {
    warnings.push(`Invalid type "${obj.type}" — must be "node" or "edge"`)
  }

  // Op-specific validation
  switch (op) {
    case 'DEFINE':
      validateDefine(obj, warnings)
      break
    case 'CREATE':
      validateCreate(obj, warnings)
      break
    case 'UPDATE':
      validateUpdate(obj, warnings)
      break
    case 'DELETE':
      validateDelete(obj, warnings)
      break
  }

  return warnings
}

function validateDefine(obj: Record<string, unknown>, warnings: string[]) {
  if (!obj.label) {
    warnings.push('DEFINE: missing required field "label"')
  }
}

function validateCreate(obj: Record<string, unknown>, warnings: string[]) {
  if (!obj.id) {
    warnings.push('CREATE: missing required field "id"')
  } else if (typeof obj.id === 'string' && !ID_PATTERN.test(obj.id)) {
    warnings.push(`CREATE: id "${obj.id}" does not match required format label:16hexchars`)
  }

  if (!obj.label) {
    warnings.push('CREATE: missing required field "label"')
  }

  if (!obj.set_properties) {
    warnings.push('CREATE: missing required field "set_properties"')
  } else if (typeof obj.set_properties === 'object' && obj.set_properties !== null) {
    const props = obj.set_properties as Record<string, unknown>

    if (!props.data_source_id) {
      warnings.push('CREATE: missing required property "data_source_id" in set_properties')
    }
    if (!props.source_path) {
      warnings.push('CREATE: missing required property "source_path" in set_properties')
    }

    if (obj.type === 'node' && !props.slug) {
      warnings.push('CREATE node: missing required property "slug" in set_properties')
    }
  }

  if (obj.type === 'edge') {
    if (!obj.start_id) {
      warnings.push('CREATE edge: missing required field "start_id"')
    } else if (typeof obj.start_id === 'string' && !ID_PATTERN.test(obj.start_id)) {
      warnings.push(`CREATE edge: start_id "${obj.start_id}" does not match required format`)
    }

    if (!obj.end_id) {
      warnings.push('CREATE edge: missing required field "end_id"')
    } else if (typeof obj.end_id === 'string' && !ID_PATTERN.test(obj.end_id)) {
      warnings.push(`CREATE edge: end_id "${obj.end_id}" does not match required format`)
    }
  }
}

function validateUpdate(obj: Record<string, unknown>, warnings: string[]) {
  if (!obj.id) {
    warnings.push('UPDATE: missing required field "id"')
  } else if (typeof obj.id === 'string' && !ID_PATTERN.test(obj.id)) {
    warnings.push(`UPDATE: id "${obj.id}" does not match required format label:16hexchars`)
  }

  if (!obj.set_properties && !obj.remove_properties) {
    warnings.push('UPDATE: requires at least one of "set_properties" or "remove_properties"')
  }
}

function validateDelete(obj: Record<string, unknown>, warnings: string[]) {
  if (!obj.id) {
    warnings.push('DELETE: missing required field "id"')
  } else if (typeof obj.id === 'string' && !ID_PATTERN.test(obj.id)) {
    warnings.push(`DELETE: id "${obj.id}" does not match required format label:16hexchars`)
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────

export function getBreakdown(operations: ParsedOperation[]): OperationBreakdown {
  const breakdown: OperationBreakdown = {
    DEFINE: 0,
    CREATE: 0,
    UPDATE: 0,
    DELETE: 0,
    unknown: 0,
  }

  for (const op of operations) {
    if (op.op && op.op in breakdown) {
      breakdown[op.op]++
    } else {
      breakdown.unknown++
    }
  }

  return breakdown
}

export function generateHexId(): string {
  const bytes = new Uint8Array(8)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Convert parsed operations back to JSONL for submission.
 * Each operation is serialized as a single-line JSON string.
 */
export function toJsonl(operations: ParsedOperation[]): string {
  return operations.map(op => JSON.stringify(op.raw)).join('\n')
}

/**
 * Get a compact summary for an operation (for the preview panel).
 */
export function operationSummary(op: ParsedOperation): string {
  const parts: string[] = []
  if (op.type) parts.push(op.type)
  if (op.label) parts.push(`"${op.label}"`)
  if (op.id) parts.push(op.id)
  return parts.join(' ') || 'unknown'
}
