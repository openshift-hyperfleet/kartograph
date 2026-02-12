# Cypher Console UX Enhancements

## Recommended Stack

**CodeMirror 6** with a thin custom Vue composable + Neo4j's `@neo4j-cypher/language-support` package.

## Implementation Phases

### Phase 1: CodeMirror 6 + Syntax Highlighting (M, 2-3 days)

Replace `<textarea>` with CodeMirror 6, custom theme matching shadcn, Ctrl+Enter keybinding, Prism-based Cypher tokenization.

**Packages:**
```
codemirror @codemirror/state @codemirror/view @codemirror/language
@codemirror/commands @codemirror/search @codemirror/autocomplete @codemirror/lint
@lezer/common @lezer/highlight
```

**Files to create:**
- `app/composables/useCodemirror.ts` — thin CM6 Vue composable (~50 LOC)
- `app/lib/codemirror/theme.ts` — custom theme using CSS vars from shadcn
- `app/lib/codemirror/lang-cypher/index.ts` — Cypher LanguageSupport factory
- `app/lib/codemirror/lang-cypher/cypher-language.ts` — Lezer-based language definition with Cypher keywords/tokens
- `app/lib/codemirror/lang-cypher/highlight.ts` — syntax highlighting style tags

**Files to modify:**
- `app/pages/query/index.vue` — replace textarea with CM6 editor

### Phase 2: Autocomplete + Schema Integration (M, 2-3 days)

Feed node/edge labels into autocomplete, keyword/label/function completion.

**Files to create:**
- `app/lib/codemirror/lang-cypher/autocomplete.ts` — Cypher keyword, function, label, and relationship type completion
- `app/lib/codemirror/schema-adapter.ts` — converts our schema to autocomplete format

**Files to modify:**
- `app/lib/codemirror/lang-cypher/index.ts` — wire autocomplete extension
- `app/pages/query/index.vue` — pass schema data to editor

### Phase 3: Linting + AGE Error Handling (L, 4-5 days)

Client-side AGE-specific linting rules + parse server errors into inline squiggly underlines.

**Files to create:**
- `app/lib/codemirror/lang-cypher/age-linter.ts` — AGE-specific validation (single RETURN column, unsupported clauses, common mistakes)
- `app/lib/codemirror/error-parser.ts` — parse PostgreSQL/AGE error messages, extract token/position

**Files to modify:**
- `app/lib/codemirror/lang-cypher/index.ts` — wire linter extension
- `app/pages/query/index.vue` — display server errors as inline markers

### Phase 4: Keyword Tooltips + Cheat Sheet (S, 1-2 days)

Hover tooltips on Cypher keywords, collapsible cheat sheet panel.

**Files to create:**
- `app/lib/codemirror/lang-cypher/tooltips.ts` — hover tooltip data and CM6 extension
- `app/components/query/CypherCheatSheet.vue` — collapsible cheat sheet component

**Files to modify:**
- `app/lib/codemirror/lang-cypher/index.ts` — wire tooltip extension
- `app/pages/query/index.vue` — add cheat sheet panel

### Phase 5: Interactive Query Templates (S, 1-2 days)

Parameterized templates with dropdowns populated from schema data.

**Files to create:**
- `app/components/query/QueryTemplates.vue` — interactive template cards with parameter slots

**Files to modify:**
- `app/pages/query/index.vue` — replace static example buttons with template component

### Phase 6: Visual Query Builder (XL — Deferred)

Not recommended at this time. Autocomplete + templates cover the use case for developer users.

## Technical Details

### Custom Theme

The CM6 theme uses CSS variables to match the shadcn design system:
- Editor background: `hsl(var(--muted))`
- Text: `hsl(var(--foreground))`
- Cursor/caret: `hsl(var(--foreground))`
- Selection: `hsl(var(--accent))`
- Focus ring: `hsl(var(--ring))`
- Tooltips/autocomplete: `hsl(var(--popover))` / `hsl(var(--popover-foreground))`

### Syntax Highlighting Colors

Using the chart colors from the theme for syntax tokens:
- Keywords (MATCH, WHERE, RETURN): `--chart-1`, bold
- Labels/types: `--chart-2`
- Functions: `--chart-3`
- Strings: `--chart-4`
- Numbers/booleans: `--chart-5`
- Variables: `--foreground`
- Operators/brackets: `--muted-foreground`
- Comments: `--muted-foreground`, italic

### AGE-Specific Linter Rules

1. **Multi-column RETURN detection** — warn if RETURN has un-nested commas, suggest map syntax
2. **Unsupported clauses** — error on OPTIONAL MATCH, FOREACH, CALL, UNION
3. **Pattern syntax** — detect `=` instead of `:` in node patterns
4. **Missing RETURN** — warn if query has MATCH but no RETURN
5. **Unclosed brackets** — detect unbalanced `()`, `[]`, `{}`

### Server Error Parsing

Parse PostgreSQL error messages to extract:
- `at or near "TOKEN"` — locate token in query for inline marker
- `LINE N:` — line number
- Typo detection — compare near-token to Cypher keywords, suggest closest match
- Common patterns — "column definition list" → suggest map syntax

### Apache AGE Differences from Neo4j Cypher

| Unsupported | Supported |
|---|---|
| OPTIONAL MATCH | MATCH, WITH, RETURN |
| FOREACH | ORDER BY, SKIP, LIMIT |
| CALL/YIELD | CREATE, DELETE, SET, REMOVE |
| UNION | MERGE, UNWIND |
| List comprehensions | Variable-length paths |
| Pattern comprehensions | labels(), type(), id(), count(), collect() |
| EXISTS subqueries | head(), last(), size(), length() |
| CASE (limited) | nodes(), relationships(), properties() |

### Risks

- `@neo4j-cypher/language-support` is pre-release — pin version, wrap in composable
- Neo4j linter may false-positive on AGE-valid queries — AGE linter post-filters
- ANTLR4 bundle ~300KB — lazy-load via dynamic import
- `vue-codemirror` is stale — write our own thin composable instead
