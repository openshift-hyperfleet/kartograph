import { StreamLanguage, type StreamParser } from '@codemirror/language'
import { LanguageSupport } from '@codemirror/language'
import { tags, type Tag } from '@lezer/highlight'

const CYPHER_KEYWORDS = new Set([
  'match', 'optional', 'where', 'return', 'with', 'create', 'delete',
  'detach', 'set', 'remove', 'merge', 'on', 'unwind', 'as', 'order',
  'by', 'skip', 'limit', 'asc', 'desc', 'ascending', 'descending',
  'distinct', 'case', 'when', 'then', 'else', 'end', 'union',
  'call', 'yield', 'foreach',
])

const CYPHER_OPERATORS = new Set([
  'and', 'or', 'xor', 'not', 'in', 'starts', 'ends', 'contains', 'is',
])

const CYPHER_CONSTANTS = new Set([
  'null', 'true', 'false',
])

const CYPHER_FUNCTIONS = new Set([
  'count', 'collect', 'sum', 'avg', 'min', 'max',
  'labels', 'type', 'id', 'keys', 'properties',
  'nodes', 'relationships', 'startnode', 'endnode',
  'head', 'last', 'size', 'length', 'tail', 'range', 'reduce',
  'coalesce', 'tostring', 'tointeger', 'tofloat', 'toboolean',
  'trim', 'ltrim', 'rtrim', 'replace', 'substring', 'left', 'right',
  'split', 'reverse', 'upper', 'lower', 'toupper', 'tolower',
  'abs', 'ceil', 'floor', 'round', 'sign', 'rand', 'sqrt',
  'log', 'log10', 'exp', 'e', 'pi',
  'timestamp', 'date', 'datetime', 'time', 'duration',
  'point', 'distance',
  'exists',
])

interface CypherState {
  /** Are we inside a node/relationship pattern? Track for label highlighting */
  inPattern: boolean
  /** Did we just see a colon (for label detection)? */
  afterColon: boolean
}

const cypherStreamParser: StreamParser<CypherState> = {
  name: 'cypher',

  startState(): CypherState {
    return { inPattern: false, afterColon: false }
  },

  token(stream, state): string | null {
    // Skip whitespace
    if (stream.eatSpace()) {
      state.afterColon = false
      return null
    }

    // Line comments: //
    if (stream.match('//')) {
      stream.skipToEnd()
      return 'comment'
    }

    // Block comments: /* ... */
    if (stream.match('/*')) {
      while (!stream.eol()) {
        if (stream.match('*/')) break
        stream.next()
      }
      return 'comment'
    }

    // Strings: "..." or '...'
    const quote = stream.peek()
    if (quote === '"' || quote === "'") {
      stream.next()
      let escaped = false
      while (!stream.eol()) {
        const ch = stream.next()
        if (escaped) {
          escaped = false
        } else if (ch === '\\') {
          escaped = true
        } else if (ch === quote) {
          break
        }
      }
      state.afterColon = false
      return 'string'
    }

    // Numbers
    if (stream.match(/^-?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?/)) {
      state.afterColon = false
      return 'number'
    }

    // Pattern start/end
    if (stream.peek() === '(' || stream.peek() === '[') {
      state.inPattern = true
      state.afterColon = false
      stream.next()
      return 'bracket'
    }
    if (stream.peek() === ')' || stream.peek() === ']') {
      state.inPattern = false
      state.afterColon = false
      stream.next()
      return 'bracket'
    }

    // Braces
    if (stream.peek() === '{' || stream.peek() === '}') {
      state.afterColon = false
      stream.next()
      return 'bracket'
    }

    // Colon (label prefix in patterns)
    if (stream.peek() === ':') {
      stream.next()
      if (state.inPattern) {
        state.afterColon = true
      }
      return 'operator'
    }

    // Dot (property access)
    if (stream.peek() === '.') {
      stream.next()
      // Read the property name after the dot
      if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
        state.afterColon = false
        return 'propertyName'
      }
      return 'operator'
    }

    // Arrows and comparison operators
    if (stream.match(/^(<>|<=|>=|<-|->|--|=~|<|>|=|\+|-|\*|\/|%|\^)/)) {
      state.afterColon = false
      return 'operator'
    }

    // Comma, semicolon
    if (stream.peek() === ',' || stream.peek() === ';') {
      stream.next()
      state.afterColon = false
      return 'operator'
    }

    // Backtick-quoted identifiers
    if (stream.peek() === '`') {
      stream.next()
      while (!stream.eol() && stream.peek() !== '`') stream.next()
      if (stream.peek() === '`') stream.next()
      // Backtick identifiers after colon are labels
      if (state.afterColon) {
        state.afterColon = false
        return 'typeName'
      }
      state.afterColon = false
      return 'variableName'
    }

    // Parameter: $paramName
    if (stream.peek() === '$') {
      stream.next()
      stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)
      state.afterColon = false
      return 'special.variableName'
    }

    // Words (keywords, functions, variables, labels)
    if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
      const word = stream.current()
      const lower = word.toLowerCase()

      // After colon in pattern = label
      if (state.afterColon) {
        state.afterColon = false
        return 'typeName'
      }

      // Check if followed by ( => function
      if (stream.peek() === '(') {
        if (CYPHER_FUNCTIONS.has(lower)) {
          return 'definition.variableName'
        }
        // Unknown function name
        return 'definition.variableName'
      }

      // Keywords
      if (CYPHER_KEYWORDS.has(lower)) {
        return 'keyword'
      }

      // Operator keywords (AND, OR, NOT, IN, etc.)
      if (CYPHER_OPERATORS.has(lower)) {
        return 'keyword'
      }

      // Constants (null, true, false)
      if (CYPHER_CONSTANTS.has(lower)) {
        return 'atom'
      }

      state.afterColon = false
      return 'variableName'
    }

    // Anything else
    stream.next()
    state.afterColon = false
    return null
  },

  languageData: {
    commentTokens: { line: '//' },
    closeBrackets: { brackets: ['(', '[', '{', '"', "'"] },
  },
}

// Map stream token names to Lezer highlight tags.
// Note: StreamLanguage.define() has a built-in mapping from these token strings
// to tags. This map is kept for reference and potential external use.
const tokenTagMap: Record<string, Tag> = {
  'keyword': tags.keyword,
  'operator': tags.operator,
  'string': tags.string,
  'number': tags.number,
  'atom': tags.atom,
  'comment': tags.comment,
  'typeName': tags.typeName,
  'variableName': tags.variableName,
  'propertyName': tags.propertyName,
  'bracket': tags.bracket,
  'definition.variableName': tags.definition(tags.variableName),
  'special.variableName': tags.special(tags.variableName),
}

/**
 * Create a Cypher language support extension for CodeMirror 6.
 */
export function cypher(): LanguageSupport {
  const language = StreamLanguage.define(cypherStreamParser)
  return new LanguageSupport(language)
}

export { CYPHER_KEYWORDS, CYPHER_FUNCTIONS, CYPHER_OPERATORS, CYPHER_CONSTANTS }
