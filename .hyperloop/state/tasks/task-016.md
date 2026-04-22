---
id: task-016
title: Implement UI — Explore section (query console, schema browser, graph explorer)
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps: [task-014]
round: 0
branch: null
pr: null
---

## What

Implement the Explore section of the Kartograph UI: the Cypher query console with schema-aware assistance, the schema browser, and the interactive graph explorer.

## Spec requirements covered

**Query Console:**
- Cypher editor with syntax highlighting, autocomplete (schema-aware), and linting
- Execute with button or Ctrl/Cmd+Enter; display results as table with execution time and row count
- Query history panel: browse, re-execute, or insert past queries
- Optional KnowledgeGraph scope selector; unscoped queries span all accessible KGs

**Schema Browser:**
- List node types and edge types with search and filtering
- Expand a type to see description, required properties, and optional properties
- Cross-navigation: from a type → query console (pre-filled), graph explorer (filtered by type), or ontology editor

**Graph Explorer:**
- Node search by type, name, or slug → results shown as cards with properties
- Expand neighbors: connected nodes and edges with labels and direction
- Drill-down trail: build an exploration history as neighbors are expanded

**Interaction Principles:**
- Keyboard shortcut `/` to focus search in graph explorer
- Ctrl/Cmd+Enter to execute query in console
- Copy-to-clipboard for node IDs, query text

## Location

`src/ui/src/pages/explore/` — query, schema, graph pages.
`src/ui/src/components/explore/` — query editor, result table, schema tree, graph canvas.

## Notes

- Depends on task-014 for the design system and application shell.
- Does NOT depend on task-008 / task-009 (Explore reads from existing graph data, not management API).
- The Cypher autocomplete should leverage the schema API (`GET /graph/schema/labels`, `GET /graph/schema/ontology`) which is already implemented in `graph/presentation/routes.py`.
- Graph visualization may use a lightweight library (e.g., Vue Flow, D3, or Cytoscape.js); choose based on the interactive trail requirement.
