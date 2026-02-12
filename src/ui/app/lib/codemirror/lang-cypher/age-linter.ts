import { linter, type Diagnostic } from '@codemirror/lint'
import type { Extension } from '@codemirror/state'
import type { EditorView } from '@codemirror/view'

/**
 * Check if a RETURN clause has multiple un-nested commas,
 * indicating a multi-column return that AGE doesn't support.
 */
function hasUnnestedCommas(clause: string): boolean {
  let depth = 0
  for (const ch of clause) {
    if (ch === '(' || ch === '[' || ch === '{') depth++
    else if (ch === ')' || ch === ']' || ch === '}') depth--
    else if (ch === ',' && depth === 0) return true
  }
  return false
}

/**
 * Find all non-overlapping matches with their positions in the doc.
 */
function findAllMatches(doc: string, regex: RegExp): { index: number; match: RegExpExecArray }[] {
  const results: { index: number; match: RegExpExecArray }[] = []
  let m: RegExpExecArray | null
  while ((m = regex.exec(doc)) !== null) {
    results.push({ index: m.index, match: m })
  }
  return results
}

function ageLintSource(view: EditorView): Diagnostic[] {
  const doc = view.state.doc.toString()
  const trimmed = doc.trim()
  if (!trimmed) return []

  const diagnostics: Diagnostic[] = []

  // ── Rule 1: Multi-column RETURN ──────────────────────────────────────
  // Find RETURN clauses and check for un-nested commas
  const returnRegex = /\bRETURN\b\s+([\s\S]+?)(?=\bORDER\b|\bSKIP\b|\bLIMIT\b|\bUNION\b|;|\s*$)/gi
  const returnMatches = findAllMatches(doc, returnRegex)
  for (const { index, match } of returnMatches) {
    const returnClause = match[1]
    if (hasUnnestedCommas(returnClause)) {
      const from = index
      const to = Math.min(index + match[0].length, doc.length)
      diagnostics.push({
        from,
        to,
        severity: 'warning',
        message: 'Apache AGE requires a single RETURN column.\n\nWrap multiple values in a map:\n  RETURN {a: val1, b: val2}',
        actions: [{
          name: 'Wrap in map',
          apply: (view, from, to) => {
            const currentText = view.state.sliceDoc(from, to)
            // Extract just the return expressions (after RETURN keyword)
            const returnKeywordMatch = currentText.match(/^(\s*RETURN\s+)/i)
            if (returnKeywordMatch) {
              const prefix = returnKeywordMatch[1]
              const expressions = currentText.slice(prefix.length)
              view.dispatch({
                changes: { from, to, insert: `${prefix}{${expressions.trim()}}` },
              })
            }
          },
        }],
      })
    }
  }

  // ── Rule 2: Unsupported clauses ──────────────────────────────────────
  const unsupportedClauses = [
    { pattern: /\bOPTIONAL\s+MATCH\b/gi, name: 'OPTIONAL MATCH' },
    { pattern: /\bFOREACH\b/gi, name: 'FOREACH' },
    { pattern: /\bCALL\b/gi, name: 'CALL' },
    { pattern: /\bYIELD\b/gi, name: 'YIELD' },
    { pattern: /\bUNION\b/gi, name: 'UNION' },
  ]

  for (const { pattern, name } of unsupportedClauses) {
    const matches = findAllMatches(doc, pattern)
    for (const { index, match } of matches) {
      diagnostics.push({
        from: index,
        to: index + match[0].length,
        severity: 'error',
        message: `'${name}' is not supported by Apache AGE.`,
      })
    }
  }

  // ── Rule 3: Missing RETURN ───────────────────────────────────────────
  const hasMatch = /\bMATCH\b/i.test(trimmed)
  const hasReturn = /\bRETURN\b/i.test(trimmed)
  const hasMutation = /\b(CREATE|DELETE|SET|MERGE|REMOVE)\b/i.test(trimmed)

  if (hasMatch && !hasReturn && !hasMutation) {
    // Find the end of the document for the warning
    diagnostics.push({
      from: doc.length - trimmed.length + trimmed.lastIndexOf(trimmed.split(/\s+/).pop()!),
      to: doc.length,
      severity: 'warning',
      message: 'Query has MATCH but no RETURN clause. Results will not be returned.\n\nAdd a RETURN clause, e.g.:\n  RETURN n',
    })
  }

  // ── Rule 4: Unbalanced brackets ──────────────────────────────────────
  const bracketPairs: [string, string][] = [['(', ')'], ['[', ']'], ['{', '}']]
  for (const [open, close] of bracketPairs) {
    let depth = 0
    let lastOpenPos = -1
    for (let i = 0; i < doc.length; i++) {
      // Skip characters inside strings
      if (doc[i] === '"' || doc[i] === "'") {
        const quote = doc[i]
        i++
        while (i < doc.length && doc[i] !== quote) {
          if (doc[i] === '\\') i++
          i++
        }
        continue
      }
      if (doc[i] === open) {
        depth++
        lastOpenPos = i
      } else if (doc[i] === close) {
        depth--
        if (depth < 0) {
          diagnostics.push({
            from: i,
            to: i + 1,
            severity: 'error',
            message: `Unexpected closing '${close}' — no matching '${open}'.`,
          })
          depth = 0
        }
      }
    }
    if (depth > 0 && lastOpenPos >= 0) {
      diagnostics.push({
        from: lastOpenPos,
        to: lastOpenPos + 1,
        severity: 'error',
        message: `Unclosed '${open}' — missing matching '${close}'.`,
      })
    }
  }

  return diagnostics
}

/**
 * Create an Apache AGE-specific linter extension for CodeMirror 6.
 * Detects common AGE compatibility issues and syntax problems.
 */
export function ageCypherLinter(): Extension {
  return linter(ageLintSource, {
    delay: 500, // Debounce linting by 500ms
  })
}
