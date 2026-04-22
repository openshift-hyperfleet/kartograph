---
id: task-004
title: Enforce KnowledgeGraph authorization and KG ID stamping on mutations
spec_ref: specs/graph/mutations.spec.md
status: not-started
phase: null
deps: [task-003]
round: 0
branch: null
pr: null
---

## What

Add KnowledgeGraph-scoped authorization to the `/graph/mutations` route and stamp `knowledge_graph_id` onto all created/updated nodes and edges.

## Spec gaps

**KnowledgeGraph Scoping — Mutation authorization:**
> - GIVEN a mutation request targeting a specific KnowledgeGraph
> - WHEN the request is processed
> - THEN the user MUST have `edit` permission on the KnowledgeGraph (via SpiceDB)
> - AND the request is rejected with a forbidden error if permission is denied

**KnowledgeGraph ID stamping:**
> - GIVEN a mutation targeting KnowledgeGraph "kg-123"
> - WHEN CREATE or UPDATE operations are applied
> - THEN `knowledge_graph_id` is stamped on all created/updated nodes and edges from the authorized target KnowledgeGraph
> - AND any `knowledge_graph_id` value provided by the caller is rejected or ignored
> - AND this applies to mutation validation logic so callers cannot spoof the graph ID

## Current state

- `POST /graph/mutations` only requires `get_current_user` (authentication), no authorization against a specific KG.
- No `knowledge_graph_id` parameter in the route.
- No KG ID stamping in `GraphMutationService` or `MutationApplier`.

## Required changes

1. Add `knowledge_graph_id` as a required query parameter to `POST /graph/mutations`.
2. Check `edit` permission on the KG via `AuthorizationProvider` before applying mutations.
3. In `GraphMutationService.apply_mutations_from_jsonl()`, strip caller-provided `knowledge_graph_id` from `set_properties` and stamp the authorized KG ID instead.
4. Add system property validation: reject mutations where `knowledge_graph_id` is present in the caller's payload.
5. Write unit tests for KG ID stamping and forbidden scenario; integration test for permission enforcement.
