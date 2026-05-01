---
id: task-048
title: Update schema browser cross-navigation — add ontology editor link per type
spec_ref: specs/ui/experience.spec.md@97bf3eeef007dbfe56dbe4d198ea9283e446a31d
status: not-started
phase: null
deps:
  - task-043
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Schema Browser — Scenario: Cross-navigation** from `specs/ui/experience.spec.md`:

> GIVEN a type in the schema browser
> THEN the user can navigate directly to the query console (pre-filled query), graph explorer
> (filtered by type), OR **ontology editor for that type**

## Current State (FAIL)

The schema browser (`src/dev-ui/app/pages/graph/schema.vue`) already implements two of the
three cross-navigation targets correctly:

1. **Terminal icon** — "Query instances" → `/query` with pre-filled Cypher ✅
2. **Share2 icon** — "Explore instances" → `/graph/explorer?type=<label>` ✅
3. **FileCode icon** — "Edit type definition" → `/graph/mutations` with a pre-filled DEFINE
   template ❌ (should navigate to the **ontology editor**, not the Mutations Console)

The third button navigates to the raw Mutations Console rather than to the dedicated ontology
editor that task-043 introduces. This was an intentional workaround — the ontology editor
did not exist when task-016 was completed.

After task-043 lands, the ontology editor is accessible from the data source detail page
as an "Ontology" tab. To make the schema browser's cross-navigation spec-compliant, the
third button must be updated to link into the ontology editor context for the relevant type.

## Design Approach

The ontology editor lives on the data source detail page (within the data sources list at
`/data-sources`). A type may appear in multiple knowledge graphs and data sources, so the
cross-navigation should:

1. Navigate to `/data-sources` and open the appropriate context for the type.
2. OR, if a dedicated ontology editor route is introduced by task-043 (e.g.
   `/ontology?type=<label>`), navigate there directly.

**Preferred approach (to decide in implementation):**
- If task-043 exposes a standalone `/ontology` or `/data-sources/ontology` route with a
  `?type=` query parameter, update the schema browser to link directly to that route.
- If no standalone route is added, update the button to navigate to `/data-sources` with
  a `?openOntologyType=<label>` query parameter and have the data sources page detect it
  and open the relevant panel.
- In both cases the tooltip text should change from "Edit type definition" to
  "Edit in ontology editor."

## Changes Required

### 1. `src/dev-ui/app/tests/schema-browser.test.ts`

Write tests **before** updating the implementation (TDD):

1. **Third button label is "Edit in ontology editor":**
   Assert that each type row's third contextual button has tooltip text "Edit in ontology
   editor" (not "Edit type definition").

2. **Third button navigates to ontology editor URL:**
   Assert that clicking the third button on a node type with label `FileNode` calls
   `navigateTo` with a URL that references the ontology editor (e.g.
   `/ontology?type=FileNode` or `/data-sources?openOntologyType=FileNode`), NOT
   `/graph/mutations`.

3. **First and second buttons are unchanged:**
   Assert that the Query instances button still navigates to `/query` and the
   Explore instances button still navigates to `/graph/explorer?type=FileNode`.

### 2. `src/dev-ui/app/pages/graph/schema.vue`

- Update `navigateToMutations()` (lines 199–213) — rename the function to
  `navigateToOntologyEditor()` and change the target URL to the ontology editor route
  (determined by task-043's implementation).
- Update the button's icon from `FileCode` to a more appropriate icon (e.g. `PenLine` or
  `Settings`) if the design warrants it.
- Update the button `title` attribute from `"Edit type definition"` to
  `"Edit in ontology editor"`.

### 3. (Conditional) Ontology editor route wiring

If task-043 does not expose a standalone route:
- Add a `onMounted` watch in `src/dev-ui/app/pages/data-sources/index.vue` that reads
  `route.query.openOntologyType` and, if present, automatically opens the ontology panel
  for the matching type.

## Acceptance Criteria

- The schema browser's third contextual button per type is labelled "Edit in ontology
  editor" and navigates to the ontology editor (not the Mutations Console).
- The first two buttons (query console, graph explorer) remain unchanged.
- All tests written first pass before committing: `cd src/dev-ui && pnpm test`.
- The change applies consistently to both node-type rows and edge-type rows.

## UI Location

- `src/dev-ui/app/pages/graph/schema.vue` — schema browser (third button update)
- `src/dev-ui/app/pages/data-sources/index.vue` — if query-param wiring is needed

## Dependencies

- **task-043** must be complete: the ontology editor must exist and be navigable before
  the schema browser link can point to it. The exact target URL is determined by
  task-043's implementation.

## TDD Cycle

1. Write tests in `src/dev-ui/app/tests/schema-browser.test.ts` — they will fail
   because the third button currently navigates to `/graph/mutations`.
2. Coordinate with task-043's output to determine the ontology editor URL.
3. Update `schema.vue` to use the new URL and label.
4. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
5. Commit atomically per conventional commit conventions.
