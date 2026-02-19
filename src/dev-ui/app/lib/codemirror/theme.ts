import { EditorView } from '@codemirror/view'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { tags } from '@lezer/highlight'

/**
 * CodeMirror 6 theme matching the Kartograph shadcn-vue design system.
 * Uses CSS variables so it adapts to light/dark mode automatically.
 *
 * IMPORTANT: The shadcn CSS variables (--foreground, --chart-1, etc.) contain
 * complete oklch() color values, NOT raw channel numbers. Therefore we must use
 * var(--name) directly — never hsl(var(--name)).
 *
 * For opacity variants we use color-mix() instead of the hsl slash syntax.
 */
export const kartographTheme = EditorView.theme({
  '&': {
    backgroundColor: 'var(--muted)',
    color: 'var(--foreground)',
    fontSize: '0.875rem',
    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
  },
  '&.cm-focused': {
    outline: 'none',
  },
  '.cm-content': {
    padding: '0.75rem 1rem',
    caretColor: 'var(--foreground)',
    lineHeight: '1.6',
  },
  '.cm-cursor, .cm-dropCursor': {
    borderLeftColor: 'var(--foreground)',
    borderLeftWidth: '2px',
  },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
    backgroundColor: 'color-mix(in oklch, var(--ring), transparent 60%)',
  },
  '.cm-panels': {
    backgroundColor: 'var(--card)',
    color: 'var(--card-foreground)',
  },
  '.cm-panels.cm-panels-top': {
    borderBottom: '1px solid var(--border)',
  },
  '.cm-panels.cm-panels-bottom': {
    borderTop: '1px solid var(--border)',
  },
  '.cm-searchMatch': {
    backgroundColor: 'color-mix(in oklch, var(--chart-4), transparent 70%)',
  },
  '.cm-searchMatch.cm-searchMatch-selected': {
    backgroundColor: 'color-mix(in oklch, var(--chart-4), transparent 50%)',
  },
  '.cm-activeLine': {
    backgroundColor: 'color-mix(in oklch, var(--ring), transparent 85%)',
  },
  '.cm-selectionMatch': {
    backgroundColor: 'color-mix(in oklch, var(--ring), transparent 70%)',
  },
  '.cm-matchingBracket, .cm-nonmatchingBracket': {
    outline: '1px solid color-mix(in oklch, var(--ring), transparent 50%)',
  },
  '.cm-gutters': {
    backgroundColor: 'transparent',
    color: 'var(--muted-foreground)',
    border: 'none',
    paddingRight: '4px',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'color-mix(in oklch, var(--ring), transparent 85%)',
  },
  '.cm-foldPlaceholder': {
    backgroundColor: 'var(--muted)',
    color: 'var(--muted-foreground)',
    border: '1px solid var(--border)',
  },
  '.cm-tooltip': {
    backgroundColor: 'var(--popover)',
    color: 'var(--popover-foreground)',
    border: '1px solid var(--border)',
    borderRadius: 'calc(var(--radius) - 2px)',
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
  },
  '.cm-tooltip.cm-tooltip-hover': {
    backgroundColor: 'var(--popover)',
    color: 'var(--popover-foreground)',
    border: '1px solid var(--border)',
    borderRadius: 'calc(var(--radius) - 2px)',
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
  },
  '.cm-tooltip .cm-tooltip-arrow:before': {
    borderTopColor: 'var(--border)',
    borderBottomColor: 'var(--border)',
  },
  '.cm-tooltip .cm-tooltip-arrow:after': {
    borderTopColor: 'var(--popover)',
    borderBottomColor: 'var(--popover)',
  },
  '.cm-tooltip-autocomplete': {
    '& > ul': {
      fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
      fontSize: '0.8125rem',
    },
    '& > ul > li': {
      padding: '2px 8px',
    },
    '& > ul > li[aria-selected]': {
      backgroundColor: 'var(--accent)',
      color: 'var(--accent-foreground)',
    },
  },
  '.cm-completionLabel': {
    fontSize: '0.8125rem',
  },
  '.cm-completionDetail': {
    fontStyle: 'normal',
    color: 'var(--muted-foreground)',
    marginLeft: '8px',
  },
  // Lint markers
  '.cm-lintRange-error': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline var(--destructive)',
    textDecorationSkipInk: 'none',
    textUnderlineOffset: '3px',
  },
  '.cm-lintRange-warning': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline var(--chart-5)',
    textDecorationSkipInk: 'none',
    textUnderlineOffset: '3px',
  },
  '.cm-lintRange-info': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline var(--chart-2)',
    textDecorationSkipInk: 'none',
    textUnderlineOffset: '3px',
  },
  '.cm-lint-marker-error': {
    content: '"!"',
  },
  '.cm-lint-marker-warning': {
    content: '"?"',
  },
  // Lint tooltip
  '.cm-tooltip.cm-tooltip-lint': {
    backgroundColor: 'var(--popover)',
    color: 'var(--popover-foreground)',
  },
  '.cm-diagnosticText': {
    fontSize: '0.8125rem',
  },
  '.cm-diagnosticAction': {
    backgroundColor: 'var(--primary)',
    color: 'var(--primary-foreground)',
    borderRadius: 'calc(var(--radius) - 4px)',
    padding: '2px 8px',
    fontSize: '0.75rem',
    marginLeft: '8px',
    cursor: 'pointer',
    border: 'none',
  },
})

/**
 * JSON-specific highlight style — softer, muted colors suited for reading
 * data rather than editing code. Uses the shadcn palette but avoids the
 * bright yellow (chart-4) that's hard to read on light backgrounds.
 */
export const jsonHighlightStyle = syntaxHighlighting(
  HighlightStyle.define([
    { tag: tags.string, color: 'var(--chart-2)' },
    { tag: tags.number, color: 'var(--chart-3)' },
    { tag: tags.bool, color: 'var(--chart-5)', fontStyle: 'italic' },
    { tag: tags.null, color: 'var(--muted-foreground)', fontStyle: 'italic' },
    { tag: tags.atom, color: 'var(--chart-5)', fontStyle: 'italic' },
    { tag: tags.propertyName, color: 'var(--foreground)', fontWeight: '600' },
    { tag: tags.punctuation, color: 'var(--muted-foreground)' },
    { tag: tags.bracket, color: 'var(--muted-foreground)' },
  ])
)

/**
 * Syntax highlighting colors using the shadcn chart color palette.
 * CSS variables contain complete oklch() values so we use var() directly.
 */
export const kartographHighlightStyle = syntaxHighlighting(
  HighlightStyle.define([
    // Keywords: MATCH, WHERE, RETURN, CREATE, DELETE, SET, AND, OR, NOT, IN, etc.
    { tag: tags.keyword, color: 'var(--chart-1)', fontWeight: 'bold' },
    // Operators: =, <>, <, >, +, -, etc.
    { tag: tags.operator, color: 'var(--muted-foreground)' },
    // Labels/types: Person, KNOWS (CM6 maps 'type' → tags.typeName)
    { tag: tags.typeName, color: 'var(--chart-2)' },
    // Functions: count(), collect(), labels(), type() (CM6 maps 'def' → tags.definition(tags.variableName))
    { tag: tags.definition(tags.variableName), color: 'var(--chart-3)' },
    { tag: tags.function(tags.variableName), color: 'var(--chart-3)' },
    // Strings
    { tag: tags.string, color: 'var(--chart-4)' },
    // Numbers
    { tag: tags.number, color: 'var(--chart-5)' },
    // Atoms: true, false, null (CM6 maps 'atom' → tags.atom)
    { tag: tags.atom, color: 'var(--chart-5)', fontStyle: 'italic' },
    // Variables: n, m, r (CM6 maps 'variable' → tags.variableName)
    { tag: tags.variableName, color: 'var(--foreground)' },
    // Properties: .name, .age (CM6 maps 'property' → tags.propertyName)
    { tag: tags.propertyName, color: 'var(--chart-2)' },
    // Brackets: (), [], {} (CM6 maps 'bracket' → tags.bracket)
    { tag: tags.bracket, color: 'var(--muted-foreground)' },
    // Comments: // and /* */ (CM6 maps 'comment' → tags.comment)
    { tag: tags.comment, color: 'var(--muted-foreground)', fontStyle: 'italic' },
    // Parameters: $param (CM6 maps 'variable-2' → tags.variableName)
    { tag: tags.special(tags.variableName), color: 'var(--chart-3)' },
  ])
)
