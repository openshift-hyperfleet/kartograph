---
id: task-039
title: Fix tenant graph provisioning — transaction safety and atomic existence check
spec_ref: specs/iam/tenants.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gap

`specs/iam/tenants.spec.md` — **Tenant Creation / Tenant graph provisioning** scenario, two new requirements added in the latest diff.

Both requirements **FAIL** audit against the current implementation in
`src/api/graph/infrastructure/tenant_graph_handler.py`.

## Requirements

### Requirement 1 — Transaction safety on all code paths
> the database connection MUST be properly committed or rolled back on all code paths
> (including the no-op/exists path) to avoid leaking open transactions back to the
> connection pool

**Current bug:** `ensure_graph_exists` returns early when the graph already exists
(line ~80) without calling `conn.commit()` or `conn.rollback()`. The SELECT that ran
the existence check opened a transaction (psycopg2 default `autocommit=False`). That
open transaction is returned to the pool uncommitted, which can cause connection pool
exhaustion or stale transaction state.

**Fix:** Ensure `conn.commit()` (or `conn.rollback()`) is called on every code path
— including the early-return no-op branch — before returning the connection.

### Requirement 2 — Atomic existence check + graph creation
> the existence check and graph creation MUST be performed atomically (e.g. via
> `CREATE GRAPH IF NOT EXISTS` or an advisory lock) to prevent race conditions under
> concurrent duplicate event deliveries

**Current bug:** The implementation uses a two-step SELECT-then-create pattern
(TOCTOU). Two concurrent event deliveries for the same tenant can both observe
"no graph" and both attempt `create_graph(...)`, causing one to fail with a
duplicate-graph error.

**Fix:** Replace the SELECT + create pattern with an atomic alternative:
- Use `CREATE GRAPH IF NOT EXISTS` (if the Apache AGE version supports it), or
- Wrap the check-and-create in a PostgreSQL advisory lock, or
- Rely on a unique constraint / exception handler that treats the "already exists"
  error from `create_graph` as a no-op.

## Scenarios to implement (from spec)

### Scenario: Tenant graph provisioning
- GIVEN a tenant is successfully created
- WHEN the creation event is processed (via outbox)
- THEN a dedicated AGE graph named `tenant_{tenant_id}` is provisioned only if it
  does not already exist (create-if-not-exists)
- AND all knowledge graph data for this tenant will be stored in this graph
- AND if the graph already exists, the event is treated as a no-op (idempotent
  replay is safe)
- AND the database connection MUST be properly committed or rolled back on all code
  paths (including the no-op/exists path) to avoid leaking open transactions back to
  the connection pool
- AND the existence check and graph creation MUST be performed atomically (e.g. via
  `CREATE GRAPH IF NOT EXISTS` or an advisory lock) to prevent race conditions under
  concurrent duplicate event deliveries

## TDD approach

Write (or extend) tests first in
`src/api/tests/unit/graph/infrastructure/test_tenant_graph_handler.py`:

1. **Transaction safety — no-op path:** Assert that when the graph already exists,
   the connection receives exactly one `commit()` or `rollback()` call before being
   returned to the pool. The existing `test_skips_create_when_graph_already_exists`
   does NOT assert this.

2. **Atomicity — race condition simulation:** Write a test that simulates two
   concurrent calls to `ensure_graph_exists` for the same graph name and asserts
   that exactly one graph is created and neither call raises an unhandled exception.
   Use an integration test against a real PostgreSQL+AGE instance if the atomicity
   mechanism relies on database-level semantics.

Then fix `src/api/graph/infrastructure/tenant_graph_handler.py`:
- Ensure commit/rollback is always called (move `return` after `commit`, or call
  `commit` inside the no-op branch).
- Replace the TOCTOU SELECT + create with an atomic create-if-not-exists pattern.
