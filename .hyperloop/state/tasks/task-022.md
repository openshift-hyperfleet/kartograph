---
id: task-022
title: Secure Enclave — domain redaction value objects and unit tests
spec_ref: specs/iam/authorization.spec.md@774c6c8eb35f1f3d4226385ff483f4e5dc344a08
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

Implement the domain layer of the Secure Enclave per-entity graph
authorization model described in the authorization spec.

The Secure Enclave requires that every entity appearing in a graph
query result is individually authorized. Entities the caller cannot
view must be redacted — nodes are stripped to ID only; edges are
stripped to ID, start_id, and end_id only. Graph topology is always
preserved (entities are never removed from the result set).

## Scenarios to cover (from spec)

- Authorized entity — full properties returned unchanged
- Unauthorized node — only entity ID returned; all other properties stripped
- Unauthorized edge — only edge ID, `start_id`, and `end_id` returned
- Permission derivation: `view` permission is derived from the user's
  access to the `knowledge_graph_id` property on each entity
- Missing or unresolvable `knowledge_graph_id` → treat as redacted
  (deny-by-default)

## Work

1. Define value objects in `query/domain/`:
   - `RedactedNode` — carries only entity ID
   - `RedactedEdge` — carries only edge ID, start_id, end_id
   - `GraphEntityAuthorizationResult` — wraps an entity with an
     authorized/redacted flag and the redacted form

2. Define a pure function / domain service for redaction:
   - `redact_node(node: dict) -> dict` — strip all props except entity ID
   - `redact_edge(edge: dict) -> dict` — strip all props except ID/endpoints
   - `extract_knowledge_graph_id(entity: dict) -> str | None`

3. Write unit tests (no infrastructure, no SpiceDB) in
   `tests/unit/query/domain/test_secure_enclave_redaction.py`:
   - Redacting a node strips all properties except the entity ID
   - Redacting an edge keeps only ID, start_id, end_id
   - Full entity is returned unchanged when authorized
   - extract_knowledge_graph_id returns None for missing/malformed value
   - Redaction is triggered when knowledge_graph_id is missing

## Boundaries

- Domain layer only — no FastAPI, no SpiceDB, no database
- All redaction logic must be pure functions / value objects
- No infrastructure dependencies (follow architecture spec)
