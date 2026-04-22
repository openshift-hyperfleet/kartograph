---
id: task-005
title: Implement persistent per-tenant type definition storage
spec_ref: specs/graph/schema.spec.md
status: not-started
phase: null
deps: [task-003]
round: 0
branch: null
pr: null
---

## What

Replace the global `InMemoryTypeDefinitionRepository` (lru_cache, process-scoped, not tenant-aware) with a persistent, per-tenant PostgreSQL-backed type definition repository.

## Spec gaps

**Ontology Retrieval:**
> - GIVEN type definitions exist for multiple node and edge types
> - WHEN the ontology is requested
> - THEN all type definitions are returned

**Schema Evolution:**
> - GIVEN a type "person" with required property "name"
> - WHEN a CREATE mutation includes a "title" property not in the definition
> - THEN "title" is added to the type's optional properties

The in-memory store fails these scenarios across server restarts or in multi-process deployments. Critically, type definitions are global (not tenant-scoped), violating per-tenant isolation.

## Current state

- `graph/infrastructure/type_definition_repository.py` — `InMemoryTypeDefinitionRepository` with `@lru_cache` in `get_type_definition_repository()`.
- All type definitions are stored in a process-global dict — lost on restart, not scoped to tenant.

## Required changes

1. Add a `type_definitions` table to PostgreSQL (migration) with columns: `tenant_id`, `label`, `entity_type`, `description`, `required_properties` (jsonb), `optional_properties` (jsonb).
2. Implement `PostgresTypeDefinitionRepository` satisfying `ITypeDefinitionRepository`.
3. Scope all reads/writes by `tenant_id` (extracted from the request's tenant context).
4. Update `get_type_definition_repository()` dependency to provide the Postgres-backed implementation.
5. Write unit tests (with fake postgres or in-memory) and integration tests.

## Notes

- Contract tests must ensure `PostgresTypeDefinitionRepository` satisfies the same `ITypeDefinitionRepository` protocol as `InMemoryTypeDefinitionRepository`.
- The in-memory implementation can be retained for unit tests (as a fake).
