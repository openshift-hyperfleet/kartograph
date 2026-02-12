import { EditorView } from '@codemirror/view'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { tags } from '@lezer/highlight'

/**
 * CodeMirror 6 theme matching the Kartograph shadcn-vue design system.
 * Uses CSS variables so it adapts to light/dark mode automatically.
 */
export const kartographTheme = EditorView.theme({
  '&': {
    backgroundColor: 'hsl(var(--muted))',
    color: 'hsl(var(--foreground))',
    fontSize: '0.875rem',
    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
  },
  '&.cm-focused': {
    outline: 'none',
  },
  '.cm-content': {
    padding: '0.75rem 1rem',
    caretColor: 'hsl(var(--foreground))',
    lineHeight: '1.6',
  },
  '.cm-cursor, .cm-dropCursor': {
    borderLeftColor: 'hsl(var(--foreground))',
    borderLeftWidth: '2px',
  },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
    backgroundColor: 'hsl(var(--accent) / 0.4)',
  },
  '.cm-panels': {
    backgroundColor: 'hsl(var(--card))',
    color: 'hsl(var(--card-foreground))',
  },
  '.cm-panels.cm-panels-top': {
    borderBottom: '1px solid hsl(var(--border))',
  },
  '.cm-panels.cm-panels-bottom': {
    borderTop: '1px solid hsl(var(--border))',
  },
  '.cm-searchMatch': {
    backgroundColor: 'hsl(var(--chart-4) / 0.3)',
  },
  '.cm-searchMatch.cm-searchMatch-selected': {
    backgroundColor: 'hsl(var(--chart-4) / 0.5)',
  },
  '.cm-activeLine': {
    backgroundColor: 'hsl(var(--accent) / 0.15)',
  },
  '.cm-selectionMatch': {
    backgroundColor: 'hsl(var(--accent) / 0.3)',
  },
  '.cm-matchingBracket, .cm-nonmatchingBracket': {
    outline: '1px solid hsl(var(--ring) / 0.5)',
  },
  '.cm-gutters': {
    backgroundColor: 'transparent',
    color: 'hsl(var(--muted-foreground))',
    border: 'none',
    paddingRight: '4px',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'hsl(var(--accent) / 0.15)',
  },
  '.cm-foldPlaceholder': {
    backgroundColor: 'hsl(var(--muted))',
    color: 'hsl(var(--muted-foreground))',
    border: '1px solid hsl(var(--border))',
  },
  '.cm-tooltip': {
    backgroundColor: 'hsl(var(--popover))',
    color: 'hsl(var(--popover-foreground))',
    border: '1px solid hsl(var(--border))',
    borderRadius: 'calc(var(--radius) - 2px)',
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
  },
  '.cm-tooltip .cm-tooltip-arrow:before': {
    borderTopColor: 'hsl(var(--border))',
    borderBottomColor: 'hsl(var(--border))',
  },
  '.cm-tooltip .cm-tooltip-arrow:after': {
    borderTopColor: 'hsl(var(--popover))',
    borderBottomColor: 'hsl(var(--popover))',
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
      backgroundColor: 'hsl(var(--accent))',
      color: 'hsl(var(--accent-foreground))',
    },
  },
  '.cm-completionLabel': {
    fontSize: '0.8125rem',
  },
  '.cm-completionDetail': {
    fontStyle: 'normal',
    color: 'hsl(var(--muted-foreground))',
    marginLeft: '8px',
  },
  // Lint markers
  '.cm-lintRange-error': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline hsl(var(--destructive))',
    textDecorationSkipInk: 'none',
    textUnderlineOffset: '3px',
  },
  '.cm-lintRange-warning': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline hsl(var(--chart-5))',
    textDecorationSkipInk: 'none',
    textUnderlineOffset: '3px',
  },
  '.cm-lintRange-info': {
    backgroundImage: 'none',
    textDecoration: 'wavy underline hsl(var(--chart-2))',
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
    backgroundColor: 'hsl(var(--popover))',
    color: 'hsl(var(--popover-foreground))',
  },
  '.cm-diagnosticText': {
    fontSize: '0.8125rem',
  },
  '.cm-diagnosticAction': {
    backgroundColor: 'hsl(var(--primary))',
    color: 'hsl(var(--primary-foreground))',
    borderRadius: 'calc(var(--radius) - 4px)',
    padding: '2px 8px',
    fontSize: '0.75rem',
    marginLeft: '8px',
    cursor: 'pointer',
    border: 'none',
  },
})

/**
 * Syntax highlighting colors using the shadcn chart color palette.
 */
export const kartographHighlightStyle = syntaxHighlighting(
  HighlightStyle.define([
    // Keywords: MATCH, WHERE, RETURN, CREATE, DELETE, SET, etc.
    { tag: tags.keyword, color: 'hsl(var(--chart-1))', fontWeight: 'bold' },
    // Control: AND, OR, NOT, IN, IS, NULL
    { tag: tags.controlKeyword, color: 'hsl(var(--chart-1))', fontWeight: 'bold' },
    // Operators: =, <>, <, >, +, -, etc.
    { tag: tags.operator, color: 'hsl(var(--muted-foreground))' },
    // Labels/types: Person, KNOWS
    { tag: tags.typeName, color: 'hsl(var(--chart-2))' },
    { tag: tags.labelName, color: 'hsl(var(--chart-2))' },
    // Functions: count(), collect(), labels(), type()
    { tag: tags.function(tags.variableName), color: 'hsl(var(--chart-3))' },
    // Strings
    { tag: tags.string, color: 'hsl(var(--chart-4))' },
    // Numbers
    { tag: tags.number, color: 'hsl(var(--chart-5))' },
    // Booleans
    { tag: tags.bool, color: 'hsl(var(--chart-5))' },
    // Variables: n, m, r
    { tag: tags.variableName, color: 'hsl(var(--foreground))' },
    // Properties: .name, .age
    { tag: tags.propertyName, color: 'hsl(var(--chart-2))' },
    // Punctuation / Brackets
    { tag: tags.bracket, color: 'hsl(var(--muted-foreground))' },
    { tag: tags.paren, color: 'hsl(var(--muted-foreground))' },
    { tag: tags.squareBracket, color: 'hsl(var(--muted-foreground))' },
    { tag: tags.brace, color: 'hsl(var(--muted-foreground))' },
    // Comments
    { tag: tags.comment, color: 'hsl(var(--muted-foreground))', fontStyle: 'italic' },
    { tag: tags.lineComment, color: 'hsl(var(--muted-foreground))', fontStyle: 'italic' },
    // Null
    { tag: tags.null, color: 'hsl(var(--chart-5))', fontStyle: 'italic' },
    // Special
    { tag: tags.special(tags.variableName), color: 'hsl(var(--chart-3))' },
  ])
)
