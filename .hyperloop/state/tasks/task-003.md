---
id: task-003
title: Implement per-tenant graph routing for mutations and queries
spec_ref: specs/graph/mutations.spec.md
status: not-started
phase: null
deps: [task-002]
round: 0
branch: null
pr: null
---

## What

Change the graph context so that mutations and queries execute against the tenant-specific AGE graph (`tenant_{tenant_id}`) derived from the authenticated request's tenant context, instead of the static `settings.graph_name`.

## Spec gaps

**mutations.spec.md — Per-Tenant Graph Isolation:**
> - GIVEN an authenticated user in tenant "t1"
> - WHEN mutations are submitted
> - THEN they execute against the AGE graph named `tenant_{tenant_id}`
> - AND no data is written to any other tenant's graph

**queries.spec.md — Per-Tenant Graph Routing:**
> - GIVEN an authenticated user in tenant "t1"
> - WHEN any graph query is executed
> - THEN it runs against the AGE graph named `tenant_{tenant_id}`
> - AND no data from other tenants' graphs is accessible

## Current state

`graph/dependencies.py` — `get_age_graph_client()` instantiates `AgeGraphClient` with `settings.graph_name` (static from environment). All mutations and queries use this single graph regardless of tenant.

## Required changes

1. Thread the `TenantContext` (already resolved by `shared_kernel/middleware/tenant_context.py`) into the graph dependencies.
2. Compute graph name as `f"tenant_{tenant_id}"` per request.
3. Pass dynamic graph name to `AgeGraphClient`, `AgeBulkLoadingStrategy`, and `MutationApplier`.
4. Update integration tests to verify tenant isolation (data written in tenant A does not appear in tenant B queries).

## Notes

- Depends on task-002 so the AGE graph exists before routing to it.
- This change is required before tasks 004, 005, and 006 can be implemented correctly.
