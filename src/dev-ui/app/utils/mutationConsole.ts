/**
 * Pure utility functions for the Mutations Console page.
 *
 * Extracted from mutations.vue to enable direct unit testing without
 * mounting the component. Each function is a pure transformation with
 * no side-effects and no framework imports.
 */

// ── File upload ────────────────────────────────────────────────────────────

/** File extensions accepted for JSONL mutation uploads. */
export const ACCEPTED_MUTATION_FILE_EXTENSIONS = ['.jsonl', '.json', '.ndjson'] as const

/** Returns true if the filename has an accepted mutation file extension. */
export function isAcceptedMutationFile(filename: string): boolean {
  return ACCEPTED_MUTATION_FILE_EXTENSIONS.some(ext => filename.endsWith(ext))
}

// ── Editor visibility ──────────────────────────────────────────────────────

/**
 * Computes whether the empty state should be shown.
 * The empty state is visible when the editor is inactive and large-file
 * mode is off.
 */
export function getShowEmptyState(showEditor: boolean, largeFileMode: boolean): boolean {
  return !showEditor && !largeFileMode
}

/**
 * Determines whether the editor should be shown based on a route query
 * change (browser back/forward navigation).
 *
 * - Returns `true`  → activate the editor (route query is "editor").
 * - Returns `false` → deactivate the editor (route query changed away and
 *                     there is no content to preserve).
 * - Returns `null`  → preserve the current editor state (content exists).
 */
export function getEditorVisibilityForViewChange(
  newView: string | undefined,
  hasContent: boolean,
): boolean | null {
  if (newView === 'editor') return true
  if (!hasContent) return false
  return null // content exists — keep editor open regardless of URL
}

// ── Content merging ────────────────────────────────────────────────────────

/**
 * Merges template content into the current editor content.
 *
 * - If current content is non-empty, appends with a newline separator.
 * - If current content is empty, replaces it with the template.
 */
export function getMergedEditorContent(current: string, template: string): string {
  if (current.trim()) {
    return current + '\n' + template
  }
  return template
}

// ── Keyboard handling ──────────────────────────────────────────────────────

/**
 * Returns true if the keyboard event is the Ctrl+Enter (or Cmd+Enter on
 * Mac) shortcut used to submit mutations.
 */
export function isCtrlOrCmdEnterEvent(e: {
  ctrlKey: boolean
  metaKey: boolean
  key: string
}): boolean {
  return (e.ctrlKey || e.metaKey) && e.key === 'Enter'
}

// ── Submission gate ────────────────────────────────────────────────────────

/**
 * Returns true when all conditions required to submit mutations are met.
 *
 * Submission is blocked when:
 * - A submission is already in progress (`submitting`) or the large-file
 *   payload is being prepared (`preparing`).
 * - No knowledge graph has been selected (`selectedKnowledgeGraphId` is
 *   null or empty).
 * - For small files: the editor content is empty.
 *   (Large-file mode bypasses this check because the content is already
 *   known to be non-empty from the upload step.)
 */
export function canSubmitMutations(opts: {
  selectedKnowledgeGraphId: string | null
  content: string
  isLargeFile: boolean
  submitting: boolean
  preparing: boolean
}): boolean {
  if (opts.submitting || opts.preparing) return false
  if (!opts.selectedKnowledgeGraphId) return false
  if (!opts.isLargeFile && !opts.content.trim()) return false
  return true
}
