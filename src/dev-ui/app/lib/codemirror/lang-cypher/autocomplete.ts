import {
  type CompletionContext,
  type CompletionResult,
  type Completion,
  autocompletion,
} from '@codemirror/autocomplete'
import type { Extension } from '@codemirror/state'

// ── Keyword completions ────────────────────────────────────────────────────

const KEYWORD_COMPLETIONS: Completion[] = [
  { label: 'MATCH', type: 'keyword', info: 'Pattern matching clause' },
  { label: 'OPTIONAL MATCH', type: 'keyword', info: 'Optional pattern matching (may not be supported by AGE)' },
  { label: 'WHERE', type: 'keyword', info: 'Filter results by condition' },
  { label: 'RETURN', type: 'keyword', info: 'Specify output columns (AGE: single column only, use map syntax)' },
  { label: 'WITH', type: 'keyword', info: 'Chain query parts, project intermediate results' },
  { label: 'CREATE', type: 'keyword', info: 'Create nodes and relationships' },
  { label: 'MERGE', type: 'keyword', info: 'Match or create a pattern' },
  { label: 'DELETE', type: 'keyword', info: 'Delete nodes and relationships' },
  { label: 'DETACH DELETE', type: 'keyword', info: 'Delete node and all its relationships' },
  { label: 'SET', type: 'keyword', info: 'Update properties on nodes/relationships' },
  { label: 'REMOVE', type: 'keyword', info: 'Remove properties or labels' },
  { label: 'UNWIND', type: 'keyword', info: 'Expand a list into rows' },
  { label: 'ORDER BY', type: 'keyword', info: 'Sort results' },
  { label: 'SKIP', type: 'keyword', info: 'Skip a number of results' },
  { label: 'LIMIT', type: 'keyword', info: 'Limit the number of results' },
  { label: 'AS', type: 'keyword', info: 'Alias an expression' },
  { label: 'DISTINCT', type: 'keyword', info: 'Remove duplicate results' },
  { label: 'ASC', type: 'keyword', info: 'Ascending sort order' },
  { label: 'DESC', type: 'keyword', info: 'Descending sort order' },
  { label: 'CASE', type: 'keyword', info: 'Conditional expression' },
  { label: 'WHEN', type: 'keyword', info: 'Case condition branch' },
  { label: 'THEN', type: 'keyword', info: 'Case result' },
  { label: 'ELSE', type: 'keyword', info: 'Default case result' },
  { label: 'END', type: 'keyword', info: 'End of CASE expression' },
  { label: 'AND', type: 'keyword', info: 'Logical AND' },
  { label: 'OR', type: 'keyword', info: 'Logical OR' },
  { label: 'NOT', type: 'keyword', info: 'Logical NOT' },
  { label: 'XOR', type: 'keyword', info: 'Logical XOR' },
  { label: 'IN', type: 'keyword', info: 'Check list membership' },
  { label: 'IS NULL', type: 'keyword', info: 'Check for null value' },
  { label: 'IS NOT NULL', type: 'keyword', info: 'Check for non-null value' },
  { label: 'STARTS WITH', type: 'keyword', info: 'String prefix match' },
  { label: 'ENDS WITH', type: 'keyword', info: 'String suffix match' },
  { label: 'CONTAINS', type: 'keyword', info: 'String contains match' },
  { label: 'NULL', type: 'keyword', info: 'Null value' },
  { label: 'TRUE', type: 'keyword', info: 'Boolean true' },
  { label: 'FALSE', type: 'keyword', info: 'Boolean false' },
]

// ── Function completions ───────────────────────────────────────────────────

const FUNCTION_COMPLETIONS: Completion[] = [
  // Aggregation
  { label: 'count', type: 'function', apply: 'count(', info: 'Count results' },
  { label: 'collect', type: 'function', apply: 'collect(', info: 'Collect values into a list' },
  { label: 'sum', type: 'function', apply: 'sum(', info: 'Sum numeric values' },
  { label: 'avg', type: 'function', apply: 'avg(', info: 'Average of numeric values' },
  { label: 'min', type: 'function', apply: 'min(', info: 'Minimum value' },
  { label: 'max', type: 'function', apply: 'max(', info: 'Maximum value' },
  // Graph
  { label: 'labels', type: 'function', apply: 'labels(', info: 'Get labels of a node' },
  { label: 'type', type: 'function', apply: 'type(', info: 'Get type of a relationship' },
  { label: 'id', type: 'function', apply: 'id(', info: 'Get internal ID of node/relationship' },
  { label: 'keys', type: 'function', apply: 'keys(', info: 'Get property keys' },
  { label: 'properties', type: 'function', apply: 'properties(', info: 'Get all properties as a map' },
  { label: 'nodes', type: 'function', apply: 'nodes(', info: 'Get nodes from a path' },
  { label: 'relationships', type: 'function', apply: 'relationships(', info: 'Get relationships from a path' },
  { label: 'startNode', type: 'function', apply: 'startNode(', info: 'Get start node of a relationship' },
  { label: 'endNode', type: 'function', apply: 'endNode(', info: 'Get end node of a relationship' },
  // List
  { label: 'head', type: 'function', apply: 'head(', info: 'First element of a list' },
  { label: 'last', type: 'function', apply: 'last(', info: 'Last element of a list' },
  { label: 'size', type: 'function', apply: 'size(', info: 'Size of a list or string' },
  { label: 'length', type: 'function', apply: 'length(', info: 'Length of a path' },
  { label: 'tail', type: 'function', apply: 'tail(', info: 'All but first element of a list' },
  { label: 'range', type: 'function', apply: 'range(', info: 'Create a list of integers' },
  { label: 'reduce', type: 'function', apply: 'reduce(', info: 'Reduce a list to a single value' },
  // Scalar
  { label: 'coalesce', type: 'function', apply: 'coalesce(', info: 'Return first non-null value' },
  { label: 'exists', type: 'function', apply: 'exists(', info: 'Check if property exists' },
  // Type conversion
  { label: 'toString', type: 'function', apply: 'toString(', info: 'Convert to string' },
  { label: 'toInteger', type: 'function', apply: 'toInteger(', info: 'Convert to integer' },
  { label: 'toFloat', type: 'function', apply: 'toFloat(', info: 'Convert to float' },
  { label: 'toBoolean', type: 'function', apply: 'toBoolean(', info: 'Convert to boolean' },
  // String
  { label: 'trim', type: 'function', apply: 'trim(', info: 'Remove leading/trailing whitespace' },
  { label: 'ltrim', type: 'function', apply: 'ltrim(', info: 'Remove leading whitespace' },
  { label: 'rtrim', type: 'function', apply: 'rtrim(', info: 'Remove trailing whitespace' },
  { label: 'replace', type: 'function', apply: 'replace(', info: 'Replace substring' },
  { label: 'substring', type: 'function', apply: 'substring(', info: 'Get substring' },
  { label: 'left', type: 'function', apply: 'left(', info: 'Get left n characters' },
  { label: 'right', type: 'function', apply: 'right(', info: 'Get right n characters' },
  { label: 'split', type: 'function', apply: 'split(', info: 'Split string by delimiter' },
  { label: 'reverse', type: 'function', apply: 'reverse(', info: 'Reverse a string or list' },
  { label: 'toUpper', type: 'function', apply: 'toUpper(', info: 'Convert to uppercase' },
  { label: 'toLower', type: 'function', apply: 'toLower(', info: 'Convert to lowercase' },
  // Math
  { label: 'abs', type: 'function', apply: 'abs(', info: 'Absolute value' },
  { label: 'ceil', type: 'function', apply: 'ceil(', info: 'Round up to nearest integer' },
  { label: 'floor', type: 'function', apply: 'floor(', info: 'Round down to nearest integer' },
  { label: 'round', type: 'function', apply: 'round(', info: 'Round to nearest integer' },
  { label: 'sign', type: 'function', apply: 'sign(', info: 'Sign of a number (-1, 0, 1)' },
  { label: 'rand', type: 'function', apply: 'rand()', info: 'Random float between 0 and 1' },
  { label: 'sqrt', type: 'function', apply: 'sqrt(', info: 'Square root' },
  { label: 'log', type: 'function', apply: 'log(', info: 'Natural logarithm' },
  { label: 'log10', type: 'function', apply: 'log10(', info: 'Base-10 logarithm' },
  { label: 'exp', type: 'function', apply: 'exp(', info: 'e raised to a power' },
  // Temporal
  { label: 'timestamp', type: 'function', apply: 'timestamp()', info: 'Current timestamp in ms' },
]

// ── Common property names ──────────────────────────────────────────────────

const COMMON_PROPERTIES: Completion[] = [
  { label: 'name', type: 'property', info: 'Name property' },
  { label: 'slug', type: 'property', info: 'URL-friendly identifier' },
  { label: 'title', type: 'property', info: 'Title property' },
  { label: 'id', type: 'property', info: 'Identifier property' },
  { label: 'description', type: 'property', info: 'Description text' },
  { label: 'data_source_id', type: 'property', info: 'Data source identifier' },
  { label: 'source_path', type: 'property', info: 'Source file path' },
  { label: 'created_at', type: 'property', info: 'Creation timestamp' },
  { label: 'updated_at', type: 'property', info: 'Last update timestamp' },
]

// ── Schema interface ───────────────────────────────────────────────────────

export interface CypherSchema {
  labels?: string[]
  relationshipTypes?: string[]
  propertyKeys?: string[]
}

// ── Completion source ──────────────────────────────────────────────────────

function buildLabelCompletions(labels: string[]): Completion[] {
  return labels.map(label => ({
    label,
    type: 'type',
    info: 'Node label',
    boost: 1,
  }))
}

function buildRelTypeCompletions(types: string[]): Completion[] {
  return types.map(type => ({
    label: type,
    type: 'type',
    info: 'Relationship type',
    boost: 1,
  }))
}

function buildPropertyCompletions(keys: string[]): Completion[] {
  return keys.map(key => ({
    label: key,
    type: 'property',
    info: 'Property key',
  }))
}

function cypherCompletionSource(schema: CypherSchema) {
  return (context: CompletionContext): CompletionResult | null => {
    const { state, pos } = context
    const doc = state.doc.toString()

    // Get context around cursor
    const lineBefore = doc.slice(Math.max(0, doc.lastIndexOf('\n', pos - 1) + 1), pos)

    // After a dot: suggest property names
    const dotMatch = lineBefore.match(/\.\w*$/)
    if (dotMatch) {
      const from = pos - (dotMatch[0].length - 1) // exclude the dot itself
      const propertyCompletions = schema.propertyKeys
        ? buildPropertyCompletions(schema.propertyKeys)
        : COMMON_PROPERTIES
      return {
        from,
        options: propertyCompletions,
        validFor: /^\w*$/,
      }
    }

    // After colon in a node pattern: suggest labels
    // Look for patterns like (n: or (:
    const colonNodeMatch = lineBefore.match(/\(\s*\w*\s*:\s*\w*$/)
    if (colonNodeMatch) {
      const wordMatch = lineBefore.match(/:\s*(\w*)$/)
      const from = pos - (wordMatch?.[1]?.length ?? 0)
      return {
        from,
        options: buildLabelCompletions(schema.labels ?? []),
        validFor: /^\w*$/,
      }
    }

    // After colon in a relationship pattern: suggest relationship types
    // Look for patterns like [r: or [:
    const colonRelMatch = lineBefore.match(/\[\s*\w*\s*:\s*\w*$/)
    if (colonRelMatch) {
      const wordMatch = lineBefore.match(/:\s*(\w*)$/)
      const from = pos - (wordMatch?.[1]?.length ?? 0)
      return {
        from,
        options: buildRelTypeCompletions(schema.relationshipTypes ?? []),
        validFor: /^\w*$/,
      }
    }

    // General word completion: keywords + functions
    const wordMatch = context.matchBefore(/\w{2,}/)
    if (!wordMatch && !context.explicit) return null

    const from = wordMatch?.from ?? pos

    return {
      from,
      options: [...KEYWORD_COMPLETIONS, ...FUNCTION_COMPLETIONS],
      validFor: /^\w*$/,
    }
  }
}

/**
 * Create a Cypher autocompletion extension for CodeMirror 6.
 *
 * @param schema - Node labels, relationship types, and property keys for context-aware completion
 */
export function cypherAutocomplete(schema: CypherSchema = {}): Extension {
  return autocompletion({
    override: [cypherCompletionSource(schema)],
    icons: true,
    addToOptions: [],
  })
}
