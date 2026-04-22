---
id: task-002
title: Provision tenant AGE graph on TenantCreated event
spec_ref: specs/iam/tenants.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

Wire an outbox event handler that, when a `TenantCreated` event is processed, creates the tenant-specific AGE graph (`tenant_{tenant_id}`) if it does not already exist.

## Spec gap

All other tenant scenarios are implemented. The one missing scenario is:

> **Tenant graph provisioning**
> - GIVEN a tenant is successfully created
> - WHEN the creation event is processed (via outbox)
> - THEN a dedicated AGE graph named `tenant_{tenant_id}` is provisioned only if it does not already exist (create-if-not-exists)
> - AND if the graph already exists, the event is treated as a no-op (idempotent replay is safe)

## Context

- `TenantCreated` domain event exists (`iam/domain/events/tenant.py`).
- The `IAMEventTranslator` translates it to SpiceDB operations but does NOT create the AGE graph.
- `AgeGraphClient` can create graphs (uses `CREATE GRAPH IF NOT EXISTS`-style DDL via AGE).
- The new handler should be registered with the `CompositeEventHandler` in `main.py`.

## Suggested approach

1. Write a new `TenantGraphProvisioningHandler` (in `graph/infrastructure/` or `infrastructure/outbox/`) that handles `TenantCreated`.
2. The handler calls the AGE client to create `tenant_{tenant_id}` if it does not exist.
3. Register the handler alongside `SpiceDBEventHandler` in the lifespan startup.
4. Write unit + integration tests verifying idempotent create-if-not-exists behaviour.
