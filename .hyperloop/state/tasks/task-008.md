---
id: task-008
title: "UI — Query console, schema browser and graph explorer"
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: [task-006]
round: 0
branch: null
pr: null
---

## Summary

Implements the Explore section of the UI: the Cypher query console, schema browser, and graph explorer with neighbor traversal. These consume already-implemented backend APIs (`/graph/` and query endpoints). Depends on `task-006` (navigation shell).

## Scope

### Query Console (`/explore/query`)

**Editor**:
- Cypher syntax highlighting (use CodeMirror or Monaco with a Cypher language extension)
- Autocomplete based on current schema (node/edge types, property names)
- Basic linting (flag write keywords: CREATE, DELETE, SET, MERGE, REMOVE)
- Execute shortcut: Ctrl/Cmd+Enter

**Execution**:
- Optional knowledge graph scope selector (dropdown: "All KGs" or specific KG)
- Calls `query_graph` MCP tool or the graph query REST endpoint
- Displays results as a sortable table with columns auto-derived from response rows
- Shows: execution time, row count, truncation warning if `truncated: true`

**Query History**:
- Persist last N queries in localStorage
- History panel: click to insert query into editor; re-run directly

### Schema Browser (`/explore/schema`)

**Type listing**:
- Split view: node types tab | edge types tab
- Search field (filters by label name, case-insensitive)
- Filter by property name (`has_property` filter)

**Type detail** (expand/accordion or slide-out panel):
- Description
- Required properties (name + type)
- Optional properties
- Cross-navigation links:
  - "Query" → opens Query Console pre-filled with `MATCH (n:Label) RETURN n LIMIT 25`
  - "Explore" → opens Graph Explorer filtered by this type

Calls `GET /graph/schema/types` (or equivalent schema endpoint).

### Graph Explorer (`/explore/graph`)

**Node search**:
- Search by slug or node type (calls slug-based lookup endpoint)
- Results displayed as property cards (node type badge, key properties)

**Neighbor traversal**:
- Click a node card → expand to show connected nodes and edges
- Directional display: inbound / outbound arrows with edge type label
- Drill into neighbors (each neighbor is itself expandable)
- Breadcrumb trail showing exploration path

**Redaction handling**:
- Unauthorized nodes rendered as "Redacted node [id]" with ID only
- Unauthorized edges shown as stub arrows with endpoints visible

### API Client Layer

Add typed clients for:
- `GET /graph/schema/types` (or schema endpoint)
- `GET /graph/schema/types/{label}`
- `GET /graph/nodes?slug={slug}&node_type={type}` (or equivalent)
- `GET /graph/nodes/{id}/neighbors`
- Query execution (via MCP SSE or REST query endpoint)

## TDD Notes

Component tests using Vitest + Vue Test Utils with MSW:
- Query console: write keyword triggers lint warning; Ctrl+Enter fires execution
- Query history: executed queries persist and reload on page refresh
- Schema browser: search filters node types by name; property filter works
- Graph explorer: node search returns cards; expand neighbor shows connected nodes
- Redacted node renders ID-only placeholder
