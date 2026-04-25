---
id: task-037
title: Fix AGEGraphProvisioner — commit/rollback on no-op path and atomic existence-check
spec_ref: specs/iam/tenants.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Spec Gap

`specs/iam/tenants.spec.md` — **Tenant Graph Provisioning** was updated at commit
`1b98beac` to add two requirements not covered by the completed `task-002`:

> - AND the database connection MUST be properly committed or rolled back on all
>   code paths (including the no-op/exists path) to avoid leaking open transactions
>   back to the connection pool
> - AND the existence check and graph creation MUST be performed atomically (e.g.
>   via `CREATE GRAPH IF NOT EXISTS` or an advisory lock) to prevent race conditions
>   under concurrent duplicate event deliveries

## Bugs in current code

**Bug 1 — Transaction leak on the no-op path**

In `src/api/graph/infrastructure/tenant_graph_handler.py`, `AGEGraphProvisioner.ensure_graph_exists()`:

```python
if cursor.fetchone() is not None:
    # Graph already exists — idempotent no-op
    return   # ← early return WITHOUT commit or rollback
```

The `conn.commit()` and `conn.rollback()` are after the `with conn.cursor()` block.
When the graph already exists, execution returns before reaching either cleanup call,
leaving the connection with an open (uncommitted) transaction that is returned to the
pool. This can corrupt subsequent users of the connection.

**Bug 2 — Race condition between existence check and creation**

The SELECT then CREATE pattern has a TOCTOU gap. Two concurrent handlers that both
receive the same `TenantCreated` event can both SELECT (see "not found") and then
both attempt CREATE, causing one to fail with a database error.

## Fix

Rewrite `AGEGraphProvisioner.ensure_graph_exists()` to:

1. **Always commit or rollback** — restructure so that `conn.rollback()` is called
   in the no-op path (or use a context manager that always cleans up).
2. **Use an advisory lock or `CREATE GRAPH IF NOT EXISTS`** — if Apache AGE supports
   `CREATE GRAPH IF NOT EXISTS`, use it. Otherwise, acquire a PostgreSQL advisory
   lock keyed on the graph name before the SELECT+CREATE to ensure atomicity.

## Tests to write (TDD first)

- Unit test: `ensure_graph_exists()` calls `conn.rollback()` (or `conn.commit()`)
  even when the graph already exists (no-op path does not leak the transaction).
- Unit test: concurrent calls to `ensure_graph_exists()` for the same graph name
  result in exactly one graph created (simulate the race by controlling the mock).
- The existing unit test `test_tenant_graph_handler.py` should be extended with
  these scenarios before changing implementation code.
