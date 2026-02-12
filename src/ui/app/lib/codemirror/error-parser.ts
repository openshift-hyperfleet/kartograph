import { type Diagnostic } from '@codemirror/lint'
import { type EditorView } from '@codemirror/view'
import { setDiagnostics } from '@codemirror/lint'

/**
 * Parsed error information extracted from AGE/PostgreSQL error messages.
 */
export interface ParsedError {
  message: string
  /** The token near where the error occurred */
  near?: string
  /** Line number (1-based) from PostgreSQL error */
  line?: number
  /** Suggested fix for the error */
  suggestion?: string
}

// Common Cypher keywords for typo detection
const CYPHER_KEYWORDS = [
  'MATCH', 'WHERE', 'RETURN', 'WITH', 'CREATE', 'DELETE', 'SET',
  'REMOVE', 'MERGE', 'UNWIND', 'ORDER', 'LIMIT', 'SKIP', 'DISTINCT',
  'OPTIONAL', 'DETACH', 'AS', 'BY', 'ASC', 'DESC', 'AND', 'OR',
  'NOT', 'IN', 'IS', 'NULL', 'TRUE', 'FALSE', 'CASE', 'WHEN',
  'THEN', 'ELSE', 'END', 'EXISTS', 'CONTAINS', 'STARTS', 'ENDS',
]

/**
 * Calculate Levenshtein distance between two strings.
 */
function levenshtein(a: string, b: string): number {
  const matrix: number[][] = []
  for (let i = 0; i <= a.length; i++) matrix[i] = [i]
  for (let j = 0; j <= b.length; j++) matrix[0][j] = j
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost,
      )
    }
  }
  return matrix[a.length][b.length]
}

/**
 * Find the closest matching keyword to a given token.
 */
function findClosestKeyword(token: string): string | null {
  const upper = token.toUpperCase()
  let bestMatch: string | null = null
  let bestDistance = Infinity

  for (const kw of CYPHER_KEYWORDS) {
    const dist = levenshtein(upper, kw)
    // Only suggest if the distance is reasonable (less than half the word length)
    if (dist < Math.ceil(kw.length / 2) && dist < bestDistance) {
      bestDistance = dist
      bestMatch = kw
    }
  }

  return bestMatch !== upper ? bestMatch : null
}

/**
 * Parse an error message from PostgreSQL/AGE/MCP into structured data.
 */
export function parseAgeError(errorMsg: string): ParsedError {
  const result: ParsedError = { message: errorMsg }

  // Extract "at or near" token
  const nearMatch = errorMsg.match(/at or near "([^"]+)"/)
  if (nearMatch) {
    result.near = nearMatch[1]
  }

  // Extract line number (PostgreSQL format)
  const lineMatch = errorMsg.match(/LINE (\d+):/)
  if (lineMatch) {
    result.line = parseInt(lineMatch[1])
  }

  // ── Pattern-based suggestions ──────────────────────────────────────────

  // Multi-column RETURN error
  if (errorMsg.includes('column definition list') || errorMsg.includes('return row and column')) {
    result.suggestion = 'Wrap multiple RETURN values in a map: RETURN {a: val1, b: val2}'
  }

  // Function not found
  const funcMatch = errorMsg.match(/function\s+[\w.]*"?(\w+)"?\s.*does not exist/i)
  if (funcMatch) {
    result.suggestion = `Function '${funcMatch[1]}' is not available in Apache AGE. Check the supported function list.`
  }

  // Label not found / vertex not found
  if (errorMsg.includes('label') && errorMsg.includes('does not exist')) {
    result.suggestion = 'The specified label does not exist. Check the Schema Reference for available labels.'
  }

  // Graph does not exist
  if (errorMsg.includes('graph') && (errorMsg.includes('does not exist') || errorMsg.includes('not found'))) {
    result.suggestion = 'The knowledge graph may not be initialized. Ensure data has been ingested.'
  }

  // Aggregation grouping error
  if (errorMsg.includes('must be either part of an explicitly listed key') || errorMsg.includes('used inside an aggregate function')) {
    result.suggestion = 'Non-aggregated expressions must be grouped. Use WITH to group first:\n  MATCH (n) WITH labels(n) AS label, count(*) AS cnt RETURN {label: label, count: cnt}'
  }

  // Permission denied
  if (errorMsg.includes('permission denied') || errorMsg.includes('access denied')) {
    result.suggestion = 'Check your API key and tenant permissions.'
  }

  // Typo detection via the "near" token
  if (result.near && !result.suggestion) {
    const closest = findClosestKeyword(result.near)
    if (closest) {
      result.suggestion = `Did you mean '${closest}'?`
    }
  }

  return result
}

/**
 * Apply server error diagnostics to a CodeMirror editor view.
 * Attempts to locate the error position in the document and display
 * an inline error marker with squiggly underline.
 *
 * @param view - The CodeMirror EditorView
 * @param errorMsg - The raw error message from the server
 * @returns The parsed error for display purposes
 */
export function applyServerError(view: EditorView, errorMsg: string): ParsedError {
  const parsed = parseAgeError(errorMsg)
  const doc = view.state.doc.toString()
  const diagnostics: Diagnostic[] = []

  let errorFrom = -1
  let errorTo = -1

  // Try to locate the error position using the "near" token
  if (parsed.near) {
    // Search for the token in the document (case-insensitive)
    const searchTerm = parsed.near
    const docLower = doc.toLowerCase()
    const termLower = searchTerm.toLowerCase()
    const idx = docLower.indexOf(termLower)

    if (idx >= 0) {
      errorFrom = idx
      errorTo = idx + searchTerm.length
    }
  }

  // Build the diagnostic message
  let message = parsed.message
  if (parsed.suggestion) {
    message += `\n\nSuggestion: ${parsed.suggestion}`
  }

  if (errorFrom >= 0 && errorTo >= 0) {
    // We found the error location — show inline marker
    diagnostics.push({
      from: errorFrom,
      to: errorTo,
      severity: 'error',
      message,
    })
  } else {
    // Can't locate error — mark the entire document
    diagnostics.push({
      from: 0,
      to: Math.min(doc.length, 1),
      severity: 'error',
      message,
    })
  }

  // Apply diagnostics to the editor
  view.dispatch(setDiagnostics(view.state, diagnostics))

  return parsed
}

/**
 * Clear all server error diagnostics from the editor.
 */
export function clearServerErrors(view: EditorView): void {
  view.dispatch(setDiagnostics(view.state, []))
}
