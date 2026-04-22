---
id: task-006
title: Implement graph queries KnowledgeGraph filtering and secure enclave
spec_ref: specs/graph/queries.spec.md
status: not-started
phase: null
deps: [task-003]
round: 0
branch: null
pr: null
---

## What

Add two related capabilities to graph query results:
1. **KnowledgeGraph filtering** — optionally scope query results to a single KG.
2. **Secure enclave** — check authorization on every node/edge in query results and redact properties for unauthorized entities.

## Spec gaps

**KnowledgeGraph Filtering:**
> - GIVEN a query with a `knowledge_graph_id` parameter
> - WHEN the query is executed
> - THEN only nodes and edges with a matching `knowledge_graph_id` property are returned

**Secure Enclave — Per-Entity Authorization:**
> - GIVEN a node the user does NOT have `view` permission on
> - WHEN the node appears in query results
> - THEN only the entity ID is returned — all other properties are stripped
>
> - GIVEN an edge the user does NOT have `view` permission on
> - WHEN the edge appears in query results
> - THEN only the edge ID, `start_id`, and `end_id` are returned — all other properties are stripped
>
> - GIVEN a query that traverses authorized and unauthorized entities
> - THEN graph topology is preserved (unauthorized entities appear as stubs, not removed)

**Permission derivation:**
> - GIVEN a node or edge with a `knowledge_graph_id` property
> - THEN `view` permission is derived from the user's access to that KnowledgeGraph
>
> - GIVEN a node or edge whose `knowledge_graph_id` is missing, null, malformed, or unresolvable
> - THEN `view` permission MUST be denied

## Current state

`GraphQueryService` and `IGraphReadOnlyRepository` have no authorization parameter. `find_nodes_by_slug`, `get_neighbors`, and `execute_raw_query` return all properties unconditionally.

## Required changes

1. Add optional `knowledge_graph_id` filter to `IGraphReadOnlyRepository` query methods; enforce via Cypher `WHERE` clause on the `knowledge_graph_id` property.
2. Add an `enclave_check(entity_ids, user_id)` capability that bulk-checks `view` permissions via `AuthorizationProvider.check_bulk_permission()`.
3. Implement `SecureEnclaveFilter` in the application layer: after fetching results, redact properties from unauthorized entities (strip all props except ID for nodes; strip all props except ID/start_id/end_id for edges).
4. Update `GraphQueryService` to accept `AuthorizationProvider` and apply the enclave filter before returning results.
5. Update the graph presentation routes to pass the authorization provider and `knowledge_graph_id` filter.
6. Write unit tests for redaction logic (authorized entity → full props, unauthorized node → ID only, unauthorized edge → ID+endpoints only, missing KG ID → denied).
