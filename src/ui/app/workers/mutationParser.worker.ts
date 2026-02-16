/**
 * Web Worker for parsing large JSONL mutation content off the main thread.
 *
 * Communicates via postMessage. Types are duplicated here because workers
 * cannot import from Vue modules.
 */

// ── Types (duplicated from main thread) ────────────────────────────────────

type OpType = 'DEFINE' | 'CREATE' | 'UPDATE' | 'DELETE'
type EntityType = 'node' | 'edge'

export interface LightParsedOperation {
  index: number
  op?: OpType
  type?: EntityType
  label?: string
  id?: string
  warnings: string[]
  /** Line offset in the original content for this operation */
  lineStart: number
}

export interface WorkerParseResult {
  totalOps: number
  breakdown: { DEFINE: number; CREATE: number; UPDATE: number; DELETE: number; unknown: number }
  parseErrors: string[]
  /** Only first 200 operations for preview */
  previewOps: LightParsedOperation[]
  warningCount: number
  hasWarnings: boolean
}

export interface WorkerMessage {
  type: 'parse'
  content: string
  id: number
}

export interface WorkerResponse {
  type: 'result'
  result: WorkerParseResult
  id: number
  parseTimeMs: number
}

// ── Constants ──────────────────────────────────────────────────────────────

const VALID_OPS = new Set(['DEFINE', 'CREATE', 'UPDATE', 'DELETE'])
const ID_PATTERN = /^[0-9a-z_]+:[0-9a-f]{16}$/

// ── Helpers ────────────────────────────────────────────────────────────────

function isCommentLine(line: string): boolean {
  const trimmed = line.trimStart()
  return trimmed.startsWith('//') || trimmed.startsWith('#')
}

/**
 * Lightweight validation — same logic as mutationParser.ts but doesn't
 * store raw objects.
 */
function validateOperation(obj: Record<string, unknown>): string[] {
  const warnings: string[] = []

  if (!obj.op) {
    warnings.push('Missing required field: op')
    return warnings
  }

  const op = String(obj.op).toUpperCase()
  if (!VALID_OPS.has(op)) {
    warnings.push(`Invalid op "${obj.op}"`)
    return warnings
  }

  if (!obj.type) {
    warnings.push('Missing required field: type')
  }
  else if (obj.type !== 'node' && obj.type !== 'edge') {
    warnings.push(`Invalid type "${obj.type}"`)
  }

  switch (op) {
    case 'DEFINE':
      if (!obj.label) warnings.push('DEFINE: missing "label"')
      if (!obj.description) warnings.push('DEFINE: missing "description"')
      if (!obj.required_properties) warnings.push('DEFINE: missing "required_properties"')
      else if (!Array.isArray(obj.required_properties)) warnings.push('DEFINE: "required_properties" must be an array')
      if (obj.id) warnings.push('DEFINE: cannot include "id"')
      if (obj.set_properties) warnings.push('DEFINE: cannot include "set_properties"')
      break
    case 'CREATE':
      if (!obj.id) warnings.push('CREATE: missing "id"')
      else if (typeof obj.id === 'string' && !ID_PATTERN.test(obj.id)) warnings.push('CREATE: invalid id format')
      if (!obj.label) warnings.push('CREATE: missing "label"')
      if (!obj.set_properties) warnings.push('CREATE: missing "set_properties"')
      else if (typeof obj.set_properties === 'object' && obj.set_properties !== null) {
        const p = obj.set_properties as Record<string, unknown>
        if (!p.data_source_id) warnings.push('CREATE: missing "data_source_id"')
        if (!p.source_path) warnings.push('CREATE: missing "source_path"')
        if (obj.type === 'node' && !p.slug) warnings.push('CREATE: missing "slug"')
      }
      if (obj.type === 'edge') {
        if (!obj.start_id) warnings.push('CREATE edge: missing "start_id"')
        if (!obj.end_id) warnings.push('CREATE edge: missing "end_id"')
      }
      break
    case 'UPDATE':
      if (!obj.id) warnings.push('UPDATE: missing "id"')
      else if (typeof obj.id === 'string' && !ID_PATTERN.test(obj.id)) warnings.push('UPDATE: invalid id format')
      if (!obj.set_properties && !obj.remove_properties) warnings.push('UPDATE: needs set_properties or remove_properties')
      break
    case 'DELETE':
      if (!obj.id) warnings.push('DELETE: missing "id"')
      else if (typeof obj.id === 'string' && !ID_PATTERN.test(obj.id)) warnings.push('DELETE: invalid id format')
      break
  }

  return warnings
}

// ── Core Parse Logic ───────────────────────────────────────────────────────

function parseAndSummarize(content: string, maxPreview: number = 200): WorkerParseResult {
  const breakdown = { DEFINE: 0, CREATE: 0, UPDATE: 0, DELETE: 0, unknown: 0 }
  const parseErrors: string[] = []
  const previewOps: LightParsedOperation[] = []
  let totalOps = 0
  let warningCount = 0

  const lines = content.split('\n')
  let accumulator = ''
  let accStartLine = -1

  function processObj(obj: Record<string, unknown>, lineStart: number) {
    const op = typeof obj.op === 'string' ? obj.op.toUpperCase() : undefined
    if (op && op in breakdown) {
      (breakdown as Record<string, number>)[op]++
    }
    else {
      breakdown.unknown++
    }

    const warnings = validateOperation(obj)
    warningCount += warnings.length
    totalOps++

    if (previewOps.length < maxPreview) {
      previewOps.push({
        index: totalOps - 1,
        op: VALID_OPS.has(op ?? '') ? (op as OpType) : undefined,
        type: typeof obj.type === 'string' ? (obj.type as EntityType) : undefined,
        label: typeof obj.label === 'string' ? obj.label : undefined,
        id: typeof obj.id === 'string' ? obj.id : undefined,
        warnings,
        lineStart,
      })
    }
  }

  function flushAccumulator(endLine: number) {
    if (!accumulator.trim()) return
    try {
      const parsed = JSON.parse(accumulator)
      if (Array.isArray(parsed)) {
        parsed.forEach((item: unknown) => {
          if (typeof item === 'object' && item !== null) {
            processObj(item as Record<string, unknown>, accStartLine)
          }
        })
      }
      else if (typeof parsed === 'object' && parsed !== null) {
        processObj(parsed as Record<string, unknown>, accStartLine)
      }
    }
    catch {
      if (parseErrors.length < 50) {
        parseErrors.push(`Lines ${accStartLine + 1}-${endLine + 1}: Invalid JSON`)
      }
    }
    accumulator = ''
    accStartLine = -1
  }

  // Try as JSON array first
  const trimmed = content.trim()
  if (trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        parsed.forEach((item: unknown) => {
          if (typeof item === 'object' && item !== null) {
            processObj(item as Record<string, unknown>, 0)
          }
        })
        return { totalOps, breakdown, parseErrors, previewOps, warningCount, hasWarnings: warningCount > 0 }
      }
    }
    catch {
      /* fall through to JSONL */
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmedLine = line.trim()

    if (!trimmedLine || isCommentLine(trimmedLine)) {
      if (accumulator.trim()) flushAccumulator(i - 1)
      continue
    }

    try {
      const parsed = JSON.parse(trimmedLine)
      if (accumulator.trim()) flushAccumulator(i - 1)
      if (Array.isArray(parsed)) {
        parsed.forEach((item: unknown) => {
          if (typeof item === 'object' && item !== null) {
            processObj(item as Record<string, unknown>, i)
          }
        })
      }
      else if (typeof parsed === 'object' && parsed !== null) {
        processObj(parsed as Record<string, unknown>, i)
      }
    }
    catch {
      if (!accumulator.trim()) accStartLine = i
      accumulator += line + '\n'
    }
  }

  if (accumulator.trim()) flushAccumulator(lines.length - 1)

  return { totalOps, breakdown, parseErrors, previewOps, warningCount, hasWarnings: warningCount > 0 }
}

// ── Worker Message Handler ─────────────────────────────────────────────────

self.onmessage = (e: MessageEvent<WorkerMessage>) => {
  if (e.data.type === 'parse') {
    const start = performance.now()
    const result = parseAndSummarize(e.data.content)
    const elapsed = performance.now() - start
    self.postMessage({
      type: 'result',
      result,
      id: e.data.id,
      parseTimeMs: elapsed,
    } satisfies WorkerResponse)
  }
}
