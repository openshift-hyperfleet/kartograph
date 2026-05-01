---
id: task-042
title: Implement UI — ontology design flow (intent, proposal review, type editing)
spec_ref: specs/ui/experience.spec.md
status: not-started
phase: null
deps:
  - task-014
  - task-015
round: 0
branch: null
pr: null
---

## Spec Coverage

**Requirement: Ontology Design** — all 5 scenarios from `specs/ui/experience.spec.md`:

1. **Intent description** — After a data source is connected, prompt the user to
   describe (in free text) what problems or questions they want to solve with this data.

2. **Agent-proposed ontology** — Submit intent to the backend; display the proposed
   ontology (node types, edge types, properties) returned by the AI agent for review.
   Note: the extraction backend endpoint is gated on AIHCM-174. Build the UI with a
   loading/pending state and a clear stub contract so the backend can be wired in later
   without UI changes.

3. **Ontology review and approval** — Present proposed types in a reviewable list.
   The user can approve as-is or iterate. Extraction begins only after explicit approval.

4. **Individual type editing** — Inline editor for each type: modify label, description,
   required properties, optional properties, and relationship types. Validate that
   `documentation_page` (or any type with a required property) enforces the constraint
   (e.g., `source_url` must be required).

5. **Ontology change after initial extraction** — When the ontology is modified on a KG
   that has completed extraction, show a warning that full re-extraction will be triggered.
   The user must confirm before the change is applied.

## Acceptance Criteria

- Intent description step renders after data source save and accepts free text (1–2000 chars).
- Proposal review step renders a list of node types and edge types with their properties.
- Each type in the list has an "Edit" action that opens the type editor inline or in a
  side panel (no separate page navigation per the Interaction Principles requirement).
- Approve button is disabled until the user has reviewed the proposal (opened or scrolled).
- Re-extraction warning modal is shown when editing the ontology post-extraction; cancel
  aborts the edit without saving.
- All mutations show toast feedback (success or error).
- Copy-to-clipboard is available for type slugs and any generated identifiers.
- Tests are written first (TDD) in `src/dev-ui/app/tests/ontology.test.ts` before
  implementing any component logic.

## UI Location

- Flow is accessible from the data source detail page (step after "Connection configuration").
- A separate "Ontology" tab or section on the data source detail page allows returning
  users to view and edit the current ontology.

## Dependencies

- **task-014** must be complete (design system, navigation scaffold, shadcn/vue components).
- **task-015** must be complete (data source connection UI must exist; this flow continues
  from the data source save step).
- **AIHCM-174 extraction spike** (external blocker for AI proposal backend): the UI
  stub/loading state allows task-042 to merge before the backend is ready.

## TDD Cycle

1. Write tests in `src/dev-ui/app/tests/ontology.test.ts` (will fail initially).
2. Implement components in `src/dev-ui/app/pages/data-sources/` or a dedicated
   `ontology/` subdirectory.
3. Run `cd src/dev-ui && pnpm test` — all tests must pass before committing.
4. Commit atomically per conventional commit conventions.
