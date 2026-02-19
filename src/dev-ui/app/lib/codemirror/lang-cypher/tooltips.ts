import { hoverTooltip, type Tooltip } from '@codemirror/view'
import type { Extension } from '@codemirror/state'

interface KeywordDoc {
  title: string
  description: string
  syntax?: string
  example?: string
  ageNote?: string
}

const KEYWORD_DOCS: Record<string, KeywordDoc> = {
  'MATCH': {
    title: 'MATCH',
    description: 'Searches the graph for patterns. The most common starting clause.',
    syntax: 'MATCH (pattern)',
    example: 'MATCH (n:Person) RETURN n',
  },
  'WHERE': {
    title: 'WHERE',
    description: 'Filters results based on conditions. Used after MATCH or WITH.',
    syntax: 'WHERE condition',
    example: "MATCH (n) WHERE n.age > 30 RETURN n",
  },
  'RETURN': {
    title: 'RETURN',
    description: 'Specifies what to include in the query result.',
    syntax: 'RETURN expression [AS alias]',
    example: 'MATCH (n) RETURN n.name',
    ageNote: 'AGE requires a single RETURN column. Use map syntax for multiple values: RETURN {name: n.name, age: n.age}',
  },
  'WITH': {
    title: 'WITH',
    description: 'Chains query parts. Projects and limits intermediate results. Acts like RETURN but continues the query.',
    syntax: 'WITH expression [AS alias]',
    example: 'MATCH (n) WITH n.name AS name WHERE name STARTS WITH "A" RETURN name',
  },
  'CREATE': {
    title: 'CREATE',
    description: 'Creates new nodes and relationships in the graph.',
    syntax: 'CREATE (pattern)',
    example: 'CREATE (n:Person {name: "Alice"})',
  },
  'MERGE': {
    title: 'MERGE',
    description: 'Matches existing patterns or creates them if they don\'t exist.',
    syntax: 'MERGE (pattern)',
    example: 'MERGE (n:Person {name: "Alice"})',
  },
  'DELETE': {
    title: 'DELETE',
    description: 'Removes nodes and relationships. Use DETACH DELETE to remove a node and all its relationships.',
    syntax: 'DELETE variable',
    example: 'MATCH (n:Temp) DELETE n',
  },
  'DETACH': {
    title: 'DETACH DELETE',
    description: 'Deletes a node and automatically removes all its relationships.',
    syntax: 'DETACH DELETE variable',
    example: 'MATCH (n:Temp) DETACH DELETE n',
  },
  'SET': {
    title: 'SET',
    description: 'Updates properties on nodes and relationships.',
    syntax: 'SET variable.property = value',
    example: 'MATCH (n {name: "Alice"}) SET n.age = 30',
  },
  'REMOVE': {
    title: 'REMOVE',
    description: 'Removes properties or labels from nodes.',
    syntax: 'REMOVE variable.property',
    example: 'MATCH (n) REMOVE n.tempProp',
  },
  'UNWIND': {
    title: 'UNWIND',
    description: 'Expands a list into individual rows. Useful for processing collections.',
    syntax: 'UNWIND list AS variable',
    example: 'UNWIND [1, 2, 3] AS x RETURN x',
  },
  'ORDER': {
    title: 'ORDER BY',
    description: 'Sorts results by one or more expressions.',
    syntax: 'ORDER BY expression [ASC|DESC]',
    example: 'MATCH (n) RETURN n ORDER BY n.name',
  },
  'SKIP': {
    title: 'SKIP',
    description: 'Skips a number of results. Used with LIMIT for pagination.',
    syntax: 'SKIP number',
    example: 'MATCH (n) RETURN n SKIP 10 LIMIT 10',
  },
  'LIMIT': {
    title: 'LIMIT',
    description: 'Limits the number of results returned.',
    syntax: 'LIMIT number',
    example: 'MATCH (n) RETURN n LIMIT 25',
  },
  'DISTINCT': {
    title: 'DISTINCT',
    description: 'Removes duplicate results.',
    syntax: 'RETURN DISTINCT expression',
    example: 'MATCH (n) RETURN DISTINCT labels(n)',
  },
  'AS': {
    title: 'AS',
    description: 'Creates an alias for an expression in RETURN or WITH.',
    syntax: 'expression AS alias',
    example: 'RETURN n.name AS personName',
  },
  'AND': {
    title: 'AND',
    description: 'Logical AND — both conditions must be true.',
    syntax: 'condition1 AND condition2',
    example: 'WHERE n.age > 20 AND n.age < 40',
  },
  'OR': {
    title: 'OR',
    description: 'Logical OR — at least one condition must be true.',
    syntax: 'condition1 OR condition2',
    example: 'WHERE n.role = "admin" OR n.role = "owner"',
  },
  'NOT': {
    title: 'NOT',
    description: 'Logical NOT — negates a condition.',
    syntax: 'NOT condition',
    example: 'WHERE NOT n.deleted',
  },
  'IN': {
    title: 'IN',
    description: 'Checks if a value is in a list.',
    syntax: 'expression IN list',
    example: 'WHERE n.status IN ["active", "pending"]',
  },
  'IS': {
    title: 'IS NULL / IS NOT NULL',
    description: 'Checks if a value is null or not null.',
    syntax: 'expression IS [NOT] NULL',
    example: 'WHERE n.email IS NOT NULL',
  },
  'CONTAINS': {
    title: 'CONTAINS',
    description: 'String contains check.',
    syntax: 'string CONTAINS substring',
    example: 'WHERE n.name CONTAINS "alice"',
  },
  'STARTS': {
    title: 'STARTS WITH',
    description: 'String prefix match.',
    syntax: 'string STARTS WITH prefix',
    example: 'WHERE n.name STARTS WITH "A"',
  },
  'ENDS': {
    title: 'ENDS WITH',
    description: 'String suffix match.',
    syntax: 'string ENDS WITH suffix',
    example: 'WHERE n.email ENDS WITH "@example.com"',
  },
  'CASE': {
    title: 'CASE',
    description: 'Conditional expression. Returns different values based on conditions.',
    syntax: 'CASE WHEN condition THEN result [ELSE default] END',
    example: 'RETURN CASE WHEN n.age < 18 THEN "minor" ELSE "adult" END',
    ageNote: 'CASE expressions have limited support in Apache AGE.',
  },
  'NULL': {
    title: 'NULL',
    description: 'Represents a missing or undefined value.',
    syntax: 'NULL',
    example: 'WHERE n.deletedAt IS NULL',
  },
  'TRUE': {
    title: 'TRUE',
    description: 'Boolean true value.',
    syntax: 'TRUE',
    example: 'WHERE n.active = TRUE',
  },
  'FALSE': {
    title: 'FALSE',
    description: 'Boolean false value.',
    syntax: 'FALSE',
    example: 'WHERE n.deleted = FALSE',
  },
}

const FUNCTION_DOCS: Record<string, KeywordDoc> = {
  'count': { title: 'count()', description: 'Count the number of results.', syntax: 'count(expression)', example: 'RETURN {count: count(*)}' },
  'collect': { title: 'collect()', description: 'Collect values into a list.', syntax: 'collect(expression)', example: 'RETURN {names: collect(n.name)}' },
  'sum': { title: 'sum()', description: 'Sum numeric values.', syntax: 'sum(expression)', example: 'RETURN {total: sum(n.amount)}' },
  'avg': { title: 'avg()', description: 'Calculate the average of numeric values.', syntax: 'avg(expression)', example: 'RETURN {average: avg(n.score)}' },
  'min': { title: 'min()', description: 'Find the minimum value.', syntax: 'min(expression)', example: 'RETURN {min: min(n.age)}' },
  'max': { title: 'max()', description: 'Find the maximum value.', syntax: 'max(expression)', example: 'RETURN {max: max(n.age)}' },
  'labels': { title: 'labels()', description: 'Get labels of a node as a list.', syntax: 'labels(node)', example: 'RETURN {labels: labels(n)}' },
  'type': { title: 'type()', description: 'Get the type of a relationship.', syntax: 'type(relationship)', example: 'MATCH ()-[r]->() RETURN {type: type(r)}' },
  'id': { title: 'id()', description: 'Get the internal ID of a node or relationship.', syntax: 'id(node_or_rel)', example: 'RETURN {id: id(n)}' },
  'keys': { title: 'keys()', description: 'Get all property keys of a node or relationship.', syntax: 'keys(node_or_rel)', example: 'RETURN {keys: keys(n)}' },
  'properties': { title: 'properties()', description: 'Get all properties as a map.', syntax: 'properties(node_or_rel)', example: 'RETURN {props: properties(n)}' },
  'size': { title: 'size()', description: 'Get the size of a list or length of a string.', syntax: 'size(list_or_string)', example: 'WHERE size(n.name) > 5' },
  'length': { title: 'length()', description: 'Get the length of a path.', syntax: 'length(path)', example: 'MATCH p=(a)-[*]->(b) RETURN {len: length(p)}' },
  'head': { title: 'head()', description: 'Get the first element of a list.', syntax: 'head(list)', example: 'RETURN {first: head(labels(n))}' },
  'last': { title: 'last()', description: 'Get the last element of a list.', syntax: 'last(list)', example: 'RETURN {last: last(collect(n.name))}' },
  'coalesce': { title: 'coalesce()', description: 'Return the first non-null value.', syntax: 'coalesce(val1, val2, ...)', example: 'RETURN {name: coalesce(n.name, n.slug, "unknown")}' },
  'tostring': { title: 'toString()', description: 'Convert a value to a string.', syntax: 'toString(expression)', example: 'RETURN {str: toString(n.age)}' },
  'tointeger': { title: 'toInteger()', description: 'Convert a value to an integer.', syntax: 'toInteger(expression)', example: 'WHERE toInteger(n.count) > 5' },
  'exists': { title: 'exists()', description: 'Check if a property exists on a node/relationship.', syntax: 'exists(property)', example: 'WHERE exists(n.email)' },
  'range': { title: 'range()', description: 'Create a list of integers.', syntax: 'range(start, end [, step])', example: 'UNWIND range(1, 10) AS i RETURN i' },
  'reverse': { title: 'reverse()', description: 'Reverse a string or list.', syntax: 'reverse(string_or_list)', example: 'RETURN {reversed: reverse(n.name)}' },
  'trim': { title: 'trim()', description: 'Remove leading and trailing whitespace.', syntax: 'trim(string)', example: 'RETURN {clean: trim(n.name)}' },
  'replace': { title: 'replace()', description: 'Replace occurrences of a substring.', syntax: 'replace(original, search, replacement)', example: 'RETURN {clean: replace(n.name, " ", "_")}' },
  'abs': { title: 'abs()', description: 'Get the absolute value.', syntax: 'abs(number)', example: 'RETURN {diff: abs(a.value - b.value)}' },
  'round': { title: 'round()', description: 'Round to the nearest integer.', syntax: 'round(number)', example: 'RETURN {rounded: round(n.score)}' },
  'rand': { title: 'rand()', description: 'Generate a random float between 0 and 1.', syntax: 'rand()', example: 'RETURN {random: rand()}' },
  'timestamp': { title: 'timestamp()', description: 'Get current timestamp in milliseconds.', syntax: 'timestamp()', example: 'RETURN {ts: timestamp()}' },
}

/**
 * Create a DOM element for the tooltip content.
 */
function createTooltipDom(doc: KeywordDoc): HTMLElement {
  const container = document.createElement('div')
  container.setAttribute('role', 'tooltip')
  container.setAttribute('aria-label', doc.title + ': ' + doc.description)
  container.style.maxWidth = '360px'
  container.style.padding = '8px 12px'
  container.style.fontSize = '0.8125rem'
  container.style.lineHeight = '1.5'
  container.style.backgroundColor = 'var(--popover)'
  container.style.color = 'var(--popover-foreground)'
  container.style.border = '1px solid var(--border)'
  container.style.borderRadius = 'calc(var(--radius) - 2px)'
  container.style.boxShadow = '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)'

  // Title
  const title = document.createElement('div')
  title.style.fontWeight = '600'
  title.style.marginBottom = '4px'
  title.style.fontFamily = 'ui-monospace, monospace'
  title.textContent = doc.title
  container.appendChild(title)

  // Description
  const desc = document.createElement('div')
  desc.style.marginBottom = '6px'
  desc.textContent = doc.description
  container.appendChild(desc)

  // Syntax
  if (doc.syntax) {
    const syntax = document.createElement('div')
    syntax.style.fontFamily = 'ui-monospace, monospace'
    syntax.style.fontSize = '0.75rem'
    syntax.style.padding = '4px 6px'
    syntax.style.borderRadius = '4px'
    syntax.style.backgroundColor = 'var(--muted)'
    syntax.style.marginBottom = '4px'
    syntax.textContent = doc.syntax
    container.appendChild(syntax)
  }

  // Example
  if (doc.example) {
    const exLabel = document.createElement('div')
    exLabel.style.fontSize = '0.6875rem'
    exLabel.style.color = 'var(--muted-foreground)'
    exLabel.style.marginBottom = '2px'
    exLabel.textContent = 'Example:'
    container.appendChild(exLabel)

    const example = document.createElement('div')
    example.style.fontFamily = 'ui-monospace, monospace'
    example.style.fontSize = '0.75rem'
    example.style.padding = '4px 6px'
    example.style.borderRadius = '4px'
    example.style.backgroundColor = 'var(--muted)'
    example.style.marginBottom = '4px'
    example.textContent = doc.example
    container.appendChild(example)
  }

  // AGE note
  if (doc.ageNote) {
    const note = document.createElement('div')
    note.style.fontSize = '0.6875rem'
    note.style.padding = '4px 6px'
    note.style.borderRadius = '4px'
    note.style.border = '1px solid color-mix(in oklch, var(--chart-5), transparent 70%)'
    note.style.backgroundColor = 'color-mix(in oklch, var(--chart-5), transparent 90%)'
    note.textContent = 'AGE: ' + doc.ageNote
    container.appendChild(note)
  }

  return container
}

/**
 * Create a hover tooltip extension for Cypher keywords and functions.
 */
export function cypherTooltips(): Extension {
  return hoverTooltip((view, pos, side): Tooltip | null => {
    const { from, to, text } = view.state.doc.lineAt(pos)
    const colStart = pos - from

    // Find the word boundaries at the cursor position
    let wordStart = colStart
    let wordEnd = colStart

    while (wordStart > 0 && /\w/.test(text[wordStart - 1])) wordStart--
    while (wordEnd < text.length && /\w/.test(text[wordEnd])) wordEnd++

    if (wordStart === wordEnd) return null

    const word = text.slice(wordStart, wordEnd)
    const upper = word.toUpperCase()
    const lower = word.toLowerCase()

    // Check keywords first
    let doc = KEYWORD_DOCS[upper]
    if (!doc) {
      // Check functions
      doc = FUNCTION_DOCS[lower]
    }

    if (!doc) return null

    return {
      pos: from + wordStart,
      end: from + wordEnd,
      above: true,
      create: () => ({
        dom: createTooltipDom(doc!),
      }),
    }
  })
}
