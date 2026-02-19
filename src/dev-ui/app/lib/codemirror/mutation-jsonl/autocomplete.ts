import type {
  CompletionContext,
  CompletionResult,
  Completion,
} from '@codemirror/autocomplete'

// ── Schema constants ────────────────────────────────────────────────────────

const VALID_OPS = ['DEFINE', 'CREATE', 'UPDATE', 'DELETE'] as const
const VALID_TYPES = ['node', 'edge'] as const

/** Fields valid for each operation type. */
const FIELDS_BY_OP: Record<string, readonly string[]> = {
  DEFINE: ['op', 'type', 'label', 'description', 'required_properties', 'optional_properties'],
  CREATE: ['op', 'type', 'id', 'label', 'set_properties', 'start_id', 'end_id'],
  UPDATE: ['op', 'type', 'id', 'set_properties', 'remove_properties'],
  DELETE: ['op', 'type', 'id'],
}

/** All possible top-level field names across every operation. */
const ALL_FIELDS = [
  'op', 'type', 'id', 'label', 'description',
  'required_properties', 'optional_properties',
  'set_properties', 'remove_properties',
  'start_id', 'end_id',
] as const

/** Common system properties expected inside set_properties. */
const SYSTEM_PROPERTIES = ['data_source_id', 'source_path', 'slug'] as const

// ── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Attempt a lightweight partial parse of the current JSONL line to extract
 * existing keys, the current `op` value, and the current `type` value.
 *
 * This does NOT rely on a full JSON parse — the line may be incomplete while
 * the user is typing.  We scan for `"key"` patterns instead.
 */
interface LineContext {
  /** Keys already present in the object. */
  existingKeys: Set<string>
  /** Value of the "op" field if present. */
  op: string | undefined
  /** Value of the "type" field if present. */
  type: string | undefined
  /** Whether the cursor is inside a `set_properties` sub-object. */
  inSetProperties: boolean
}

function analyseLineContext(lineText: string, cursorCol: number): LineContext {
  const existingKeys = new Set<string>()
  let op: string | undefined
  let type: string | undefined

  // Extract all "key": "value" pairs via regex.
  // Handles both "key": "value" and "key": value patterns.
  const kvRegex = /"([^"]+)"\s*:\s*(?:"([^"]*)")?/g
  let match: RegExpExecArray | null
  while ((match = kvRegex.exec(lineText)) !== null) {
    const key = match[1]
    existingKeys.add(key)
    if (key === 'op' && match[2]) op = match[2].toUpperCase()
    if (key === 'type' && match[2]) type = match[2]
  }

  // Determine whether the cursor sits inside a `set_properties` sub-object.
  // Strategy: find "set_properties" position, then count braces between it
  // and the cursor position.
  let inSetProperties = false
  const spMatch = /"set_properties"\s*:\s*\{/.exec(lineText)
  if (spMatch) {
    const spStart = spMatch.index + spMatch[0].length
    if (cursorCol > spStart) {
      // Count braces between spStart and cursor to check we're still inside.
      let depth = 1
      for (let i = spStart; i < cursorCol && i < lineText.length; i++) {
        if (lineText[i] === '{') depth++
        else if (lineText[i] === '}') depth--
      }
      if (depth > 0) inSetProperties = true
    }
  }

  return { existingKeys, op, type, inSetProperties }
}

/**
 * Determine whether the cursor is at a position where a JSON **key** is
 * expected (as opposed to a **value**).
 *
 * Heuristic: look at the non-whitespace characters just before the cursor.
 * A key position is after `{`, `,`, or at the very start of an object.
 */
function isCursorAtKeyPosition(textBeforeCursor: string): boolean {
  const trimmed = textBeforeCursor.trimEnd()
  if (trimmed.length === 0) return false
  const last = trimmed[trimmed.length - 1]
  // After opening brace or comma → key position
  if (last === '{' || last === ',') return true
  // Partially typed key — e.g. `"op` or `"s`
  // Check if the last quote is an opening quote for a key
  const afterLastStructural = trimmed.match(/[{,]\s*"[^"]*$/)
  if (afterLastStructural) return true
  // Just a quote at the start of input (edge case)
  if (trimmed.match(/^\s*"[^"]*$/)) return true
  return false
}

/**
 * Determine if the cursor is at a position where a JSON **value** is
 * expected, and if so return the key name.
 *
 * Heuristic: look for `"key" :` or `"key":` just before the cursor.
 */
function getValueKey(textBeforeCursor: string): string | null {
  const trimmed = textBeforeCursor.trimEnd()
  // Match "key" : (with optional whitespace and optional partial value)
  const match = trimmed.match(/"([^"]+)"\s*:\s*"?[^",{}[\]]*$/)
  if (match) return match[1]
  return null
}

/**
 * Get the text of the word (partial key or value) being typed, starting
 * from the last quote if inside a string.
 */
function getPartialWord(textBeforeCursor: string): { from: number; word: string } {
  // Check if we're inside a quoted string
  const quoteMatch = textBeforeCursor.match(/"([^"]*)$/)
  if (quoteMatch) {
    return {
      from: textBeforeCursor.length - quoteMatch[0].length,
      word: quoteMatch[1],
    }
  }
  // Otherwise get trailing word characters
  const wordMatch = textBeforeCursor.match(/(\w*)$/)
  if (wordMatch) {
    return {
      from: textBeforeCursor.length - wordMatch[1].length,
      word: wordMatch[1],
    }
  }
  return { from: textBeforeCursor.length, word: '' }
}

// ── Completion builders ─────────────────────────────────────────────────────

function buildFieldCompletions(
  fields: readonly string[],
  existingKeys: Set<string>,
): Completion[] {
  return fields
    .filter(f => !existingKeys.has(f))
    .map((field, i) => ({
      label: `"${field}"`,
      type: 'property' as const,
      apply: `"${field}": `,
      boost: field === 'op' ? 10 : field === 'type' ? 9 : 8 - i * 0.1,
      info: fieldInfo(field),
    }))
}

function fieldInfo(field: string): string {
  switch (field) {
    case 'op': return 'Operation type (DEFINE, CREATE, UPDATE, DELETE)'
    case 'type': return 'Entity type (node or edge)'
    case 'id': return 'Entity ID (format: label:16hexchars)'
    case 'label': return 'Type label for the entity'
    case 'description': return 'Description of the type definition'
    case 'required_properties': return 'Array of required property names'
    case 'optional_properties': return 'Array of optional property names'
    case 'set_properties': return 'Properties to set on the entity'
    case 'remove_properties': return 'Array of property names to remove'
    case 'start_id': return 'Start node ID for edge (format: label:16hexchars)'
    case 'end_id': return 'End node ID for edge (format: label:16hexchars)'
    default: return field
  }
}

function buildOpValueCompletions(): Completion[] {
  return VALID_OPS.map(op => ({
    label: `"${op}"`,
    type: 'enum' as const,
    apply: `"${op}"`,
    info: `${op} operation`,
  }))
}

function buildTypeValueCompletions(): Completion[] {
  return VALID_TYPES.map(t => ({
    label: `"${t}"`,
    type: 'enum' as const,
    apply: `"${t}"`,
    info: `${t} entity`,
  }))
}

function buildSetPropertyCompletions(existingKeys: Set<string>, entityType: string | undefined): Completion[] {
  const props = entityType === 'edge'
    ? (['data_source_id', 'source_path'] as const)
    : SYSTEM_PROPERTIES
  return props
    .filter(p => !existingKeys.has(p))
    .map(prop => ({
      label: `"${prop}"`,
      type: 'property' as const,
      apply: `"${prop}": `,
      info: `System property`,
    }))
}

// ── Main completion source ──────────────────────────────────────────────────

/**
 * CodeMirror 6 CompletionSource for JSONL mutation operations.
 *
 * Provides context-aware suggestions for field names, enum values, and
 * system property keys based on the current `op` and `type` values.
 */
export function mutationAutocomplete(
  context: CompletionContext,
): CompletionResult | null {
  const { state, pos } = context
  const line = state.doc.lineAt(pos)
  const lineText = line.text
  const cursorCol = pos - line.from
  const textBeforeCursor = lineText.slice(0, cursorCol)

  // Skip blank/comment lines
  const trimmedLine = lineText.trim()
  if (!trimmedLine || trimmedLine.startsWith('//') || trimmedLine.startsWith('#')) {
    return null
  }

  // Analyse the current line for context
  const ctx = analyseLineContext(lineText, cursorCol)

  // ── Inside set_properties sub-object → suggest system properties ────
  if (ctx.inSetProperties && isCursorAtKeyPosition(textBeforeCursor)) {
    // Collect keys already present in the set_properties sub-object
    const spMatch = /"set_properties"\s*:\s*\{/.exec(lineText)
    const spExistingKeys = new Set<string>()
    if (spMatch) {
      const spStart = spMatch.index + spMatch[0].length
      const spText = lineText.slice(spStart, cursorCol)
      const spKvRegex = /"([^"]+)"\s*:/g
      let m: RegExpExecArray | null
      while ((m = spKvRegex.exec(spText)) !== null) {
        spExistingKeys.add(m[1])
      }
    }

    const partial = getPartialWord(textBeforeCursor)
    const from = line.from + partial.from
    return {
      from,
      options: buildSetPropertyCompletions(spExistingKeys, ctx.type),
      validFor: /^"?\w*"?$/,
    }
  }

  // ── Key position → suggest field names ──────────────────────────────
  if (isCursorAtKeyPosition(textBeforeCursor)) {
    const fields = ctx.op && FIELDS_BY_OP[ctx.op]
      ? FIELDS_BY_OP[ctx.op]
      : ALL_FIELDS

    // For CREATE operations, only include start_id/end_id if type is edge
    let filteredFields = [...fields]
    if (ctx.op === 'CREATE' && ctx.type !== 'edge') {
      filteredFields = filteredFields.filter(f => f !== 'start_id' && f !== 'end_id')
    }

    const partial = getPartialWord(textBeforeCursor)
    const from = line.from + partial.from
    return {
      from,
      options: buildFieldCompletions(filteredFields, ctx.existingKeys),
      validFor: /^"?\w*"?$/,
    }
  }

  // ── Value position → suggest enum values ────────────────────────────
  const valueKey = getValueKey(textBeforeCursor)
  if (valueKey) {
    const partial = getPartialWord(textBeforeCursor)
    const from = line.from + partial.from

    if (valueKey === 'op') {
      return {
        from,
        options: buildOpValueCompletions(),
        validFor: /^"?\w*"?$/,
      }
    }

    if (valueKey === 'type') {
      return {
        from,
        options: buildTypeValueCompletions(),
        validFor: /^"?\w*"?$/,
      }
    }
  }

  // No completions in other contexts
  return null
}
