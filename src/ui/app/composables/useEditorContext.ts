import { ref, watch, onUnmounted, type Ref } from 'vue'
import type { EditorView } from '@codemirror/view'
import type { CypherResult } from '~/types'

/**
 * Composable that tracks contextual editor state for sidebar reactions.
 *
 * Provides reactive data derived from:
 * - Query results (labels present in the result set)
 * - Cursor position (label context for auto-filtering)
 * - Query errors (suggested labels via fuzzy matching)
 */
export function useEditorContext(
  editorView: Ref<EditorView | null>,
  result: Ref<CypherResult | null>,
  error: Ref<string | null>,
  nodeLabels: Ref<string[]>,
  edgeLabels: Ref<string[]>,
) {
  // ── Phase 1: Result Labels ────────────────────────────────────────────

  /** Labels that appeared in the most recent successful query result. */
  const resultLabels = ref<Set<string>>(new Set())

  watch(result, (newResult) => {
    const labels = new Set<string>()
    if (!newResult?.rows) {
      resultLabels.value = labels
      return
    }

    for (const row of newResult.rows) {
      extractLabelsFromRow(row, labels)
    }

    resultLabels.value = labels
  })

  // ── Phase 2: Cursor Label Filter ──────────────────────────────────────

  /**
   * Text typed after `:` in a label position (e.g., `(n:Foo` → "Foo").
   * Empty string when the cursor is not in a label context.
   */
  const cursorLabelFilter = ref<string>('')

  let cursorPollTimer: ReturnType<typeof setInterval> | null = null

  function startCursorTracking() {
    // Poll every 150ms — lightweight since we only read a small slice of
    // the document around the cursor.
    cursorPollTimer = setInterval(() => {
      const view = editorView.value
      if (!view) {
        cursorLabelFilter.value = ''
        return
      }

      cursorLabelFilter.value = parseLabelAtCursor(view)
    }, 150)
  }

  function stopCursorTracking() {
    if (cursorPollTimer !== null) {
      clearInterval(cursorPollTimer)
      cursorPollTimer = null
    }
  }

  // Start tracking once the editor view becomes available.
  watch(
    editorView,
    (view) => {
      if (view) {
        startCursorTracking()
      } else {
        stopCursorTracking()
        cursorLabelFilter.value = ''
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    stopCursorTracking()
  })

  // ── Phase 3: Suggested Labels on Error ────────────────────────────────

  /**
   * Labels suggested via fuzzy matching when a query error mentions an
   * unknown label. Empty array when there is no relevant error.
   */
  const suggestedLabels = ref<string[]>([])

  watch(error, (newError) => {
    if (!newError) {
      suggestedLabels.value = []
      return
    }

    const unknownLabel = extractUnknownLabelFromError(newError)
    if (!unknownLabel) {
      suggestedLabels.value = []
      return
    }

    const allLabels = [...nodeLabels.value, ...edgeLabels.value]
    suggestedLabels.value = fuzzyMatch(unknownLabel, allLabels)
  })

  return {
    resultLabels,
    cursorLabelFilter,
    suggestedLabels,
  }
}

// ── Internal Helpers ──────────────────────────────────────────────────────

/**
 * Recursively extract label strings from a query result row.
 *
 * Apache AGE returns graph entities as objects with a `label` property
 * (for both nodes and edges). They may also be nested inside maps or
 * path results.
 */
function extractLabelsFromRow(
  value: unknown,
  labels: Set<string>,
): void {
  if (value === null || value === undefined) return

  if (Array.isArray(value)) {
    for (const item of value) {
      extractLabelsFromRow(item, labels)
    }
    return
  }

  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>

    // A graph entity with a label property
    if (typeof obj.label === 'string' && obj.label.length > 0) {
      labels.add(obj.label)
    }

    // Recurse into all values (handles nested maps, path objects, etc.)
    for (const key of Object.keys(obj)) {
      extractLabelsFromRow(obj[key], labels)
    }
  }
}

/**
 * Determine the label filter text at the current cursor position.
 *
 * Looks backward from the cursor for a `:` preceded by `(`, `[`, or a
 * variable binding pattern (e.g., `(n:`, `-[r:`) which indicates the
 * user is typing a label name.
 *
 * Returns the partial label text typed after the colon, or empty string
 * if the cursor is not in a label context.
 */
function parseLabelAtCursor(view: EditorView): string {
  const state = view.state
  const cursor = state.selection.main.head
  const doc = state.doc

  // Extract text from the start of the current line to the cursor
  const line = doc.lineAt(cursor)
  const textBeforeCursor = doc.sliceString(line.from, cursor)

  // Find the last `:` that could be a label separator.
  // We search backward for patterns like `(n:`, `(:`, `[r:`, `[:`
  // The colon must be preceded by `(`, `[`, or an identifier after `(` or `[`.
  const labelMatch = textBeforeCursor.match(
    /[\(\[]\s*[a-zA-Z_]*\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*)?$/,
  )

  if (!labelMatch) return ''

  // The captured group is the partial label text (may be undefined if
  // the user just typed the colon).
  return labelMatch[1] ?? ''
}

/**
 * Extract the unknown label name from an Apache AGE error message.
 *
 * Common patterns:
 * - "label \"Foo\" does not exist"
 * - "label 'Foo' does not exist"
 * - "label Foo does not exist"
 * - "Unknown label: Foo"
 */
function extractUnknownLabelFromError(errorMessage: string): string | null {
  // Pattern: label "X" does not exist / label 'X' does not exist
  const quotedMatch = errorMessage.match(
    /label\s+["']([^"']+)["']\s+does\s+not\s+exist/i,
  )
  if (quotedMatch) return quotedMatch[1]

  // Pattern: label X does not exist (unquoted)
  const unquotedMatch = errorMessage.match(
    /label\s+([A-Za-z_][A-Za-z0-9_]*)\s+does\s+not\s+exist/i,
  )
  if (unquotedMatch) return unquotedMatch[1]

  // Pattern: Unknown label: X
  const unknownMatch = errorMessage.match(
    /unknown\s+label[:\s]+["']?([A-Za-z_][A-Za-z0-9_]*)["']?/i,
  )
  if (unknownMatch) return unknownMatch[1]

  return null
}

/**
 * Find labels that fuzzy-match the given input string.
 *
 * Uses a simple approach: a candidate matches if all characters of the
 * input appear in the candidate in order (case-insensitive). Results are
 * sorted by match quality (shorter candidates and earlier matches rank
 * higher).
 */
function fuzzyMatch(input: string, candidates: string[]): string[] {
  if (!input || candidates.length === 0) return []

  const inputLower = input.toLowerCase()

  const scored: { label: string; score: number }[] = []

  for (const candidate of candidates) {
    const candidateLower = candidate.toLowerCase()

    // Exact match (case-insensitive) gets the best score but is excluded
    // since the user already typed the correct label — the error is about
    // something else.
    if (candidateLower === inputLower) continue

    const score = fuzzyScore(inputLower, candidateLower)
    if (score >= 0) {
      scored.push({ label: candidate, score })
    }
  }

  // Sort by score ascending (lower = better match)
  scored.sort((a, b) => a.score - b.score)

  // Return top 5 suggestions
  return scored.slice(0, 5).map((s) => s.label)
}

/**
 * Compute a fuzzy match score. Returns -1 if there is no match.
 *
 * Score is based on:
 * - Total gap between matched character positions (lower = better)
 * - Bonus for prefix matches (consecutive chars from the start)
 * - Length difference penalty
 */
function fuzzyScore(input: string, candidate: string): number {
  let inputIdx = 0
  let totalGap = 0
  let lastMatchPos = -1

  for (let i = 0; i < candidate.length && inputIdx < input.length; i++) {
    if (candidate[i] === input[inputIdx]) {
      if (lastMatchPos >= 0) {
        totalGap += i - lastMatchPos - 1
      }
      lastMatchPos = i
      inputIdx++
    }
  }

  // Not all input characters were matched
  if (inputIdx < input.length) return -1

  // Prefix bonus: reduce score if the match starts at position 0
  const prefixBonus = candidate.startsWith(input) ? -100 : 0

  // Length penalty: prefer candidates closer in length to the input
  const lengthPenalty = Math.abs(candidate.length - input.length)

  return totalGap + lengthPenalty + prefixBonus
}
