---
id: task-023
title: Secure Enclave — per-entity SpiceDB authorization in query service
spec_ref: specs/iam/authorization.spec.md@774c6c8eb35f1f3d4226385ff483f4e5dc344a08
status: not-started
phase: null
deps: [task-022]
round: 0
branch: null
pr: null
---

## What

Wire the Secure Enclave per-entity authorization into the application
and presentation layers so that every Cypher query result is filtered
before returning to the MCP caller.

This picks up the domain redaction logic from task-022 and adds:
- Application service: for each entity in query results, resolve its
  `knowledge_graph_id`, check SpiceDB `view` permission for that
  KnowledgeGraph, and apply redaction if denied or if knowledge_graph_id
  is absent/unresolvable.
- Presentation integration: inject the authorization context (user_id,
  tenant_id) into `MCPQueryService.execute_cypher_query` so the service
  can perform per-entity checks.

## Scenarios to cover (from spec)

- Authorized entity — full properties returned (no redaction)
- Unauthorized node — only entity ID in result (properties stripped)
- Unauthorized edge — only ID, start_id, end_id in result
- Permission derivation from knowledge_graph_id via SpiceDB `view` check
- Missing or unresolvable knowledge_graph_id → entity is redacted
- KnowledgeGraph access inheritable from workspace membership (SpiceDB
  handles this — no extra code needed, just use the existing check)

## Work

1. Extend `MCPQueryService` to accept caller identity (user_id, tenant_id)
   and an `AuthorizationProvider` dependency.

2. After executing the Cypher query, iterate each entity in the result:
   - Extract `knowledge_graph_id` from entity properties
   - If missing or malformed → redact (use domain functions from task-022)
   - Otherwise, check `view` on `knowledge_graph:{id}` for the caller
   - If denied → redact using domain functions
   - If permitted → return entity unchanged

3. Update `query/dependencies.py` and `query/presentation/mcp.py` to
   inject the authorization provider and caller identity from the MCP
   auth context (`MCPAuthContext`) into the service.

4. Write application-layer unit tests in
   `tests/unit/query/application/test_mcp_query_service_secure_enclave.py`
   using an in-memory fake `AuthorizationProvider`:
   - All entities authorized → results unchanged
   - Mixed: some authorized, some not → partial redaction
   - All unauthorized → all entities redacted, topology preserved
   - Missing knowledge_graph_id → redacted

5. Write at least one integration test in
   `tests/integration/query/test_secure_enclave.py` against a real
   SpiceDB instance confirming end-to-end redaction.

## Dependencies

- task-022: Provides `redact_node`, `redact_edge`,
  `extract_knowledge_graph_id` domain functions
- The SpiceDB schema already supports `knowledge_graph:view` checks —
  no schema changes needed
- The `MCPAuthContext` ContextVar already carries user_id and tenant_id
  from `MCPApiKeyAuthMiddleware`

## Boundaries

- Do not change SpiceDB schema
- Secure Enclave enforcement must NOT break queries where the caller
  is authorized for all entities (no latency regression on happy path
  without large result sets — bulk permission checks are acceptable)
- Follow the Domain-Oriented Observability pattern: add a
  `SecureEnclaveProbe` method for each redaction decision
