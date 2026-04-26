# Intake Review: Tenants (modified), NFR specs (new), Index (new)
## Date: 2026-04-26

## Specs Reviewed

| Spec | Status | Decision | Reason |
|------|--------|----------|--------|
| `specs/iam/tenants.spec.md` | modified | No new task | task-037 (not-started) already covers both new AND-clauses. See prior intake `2026-04-25-repeat-tenants-nfr-tenant-context.md` and commit `3ef003d5`. |
| `specs/index.spec.md` | new | No task | Pure table-of-contents with no requirements or scenarios. |
| `specs/nfr/api-conventions.spec.md` | new | No task | Explicitly tagged NFR (line 3). Guidelines: do not create tasks for NFR specs. |
| `specs/nfr/architecture.spec.md` | new | No task | Explicitly tagged NFR (line 3). Same policy. |
| `specs/nfr/observability.spec.md` | new | No task | Explicitly tagged NFR (line 3). Same policy. |
| `specs/nfr/testing.spec.md` | new | No task | Explicitly tagged NFR (line 3). Same policy. |

---

## Verification Detail

### `specs/iam/tenants.spec.md`

The diff adds exactly two AND-clauses to **Scenario: Tenant graph provisioning**:

```
- AND the database connection MUST be properly committed or rolled back on all code paths
  (including the no-op/exists path) to avoid leaking open transactions back to the connection pool
- AND the existence check and graph creation MUST be performed atomically (e.g. via
  `CREATE GRAPH IF NOT EXISTS` or an advisory lock) to prevent race conditions under concurrent
  duplicate event deliveries
```

**Current code (`src/api/graph/infrastructure/tenant_graph_handler.py`)** confirms the bugs:

- **Bug 1 (transaction leak):** `AGEGraphProvisioner.ensure_graph_exists()` returns early on the
  no-op/exists path (`if cursor.fetchone() is not None: return`) *before* calling `conn.commit()`
  or `conn.rollback()`. The existing unit test `test_skips_create_when_graph_already_exists` does
  NOT assert that rollback/commit is called on the no-op path — confirming this scenario is unimplemented.

- **Bug 2 (TOCTOU race):** The SELECT then CREATE pattern has no advisory lock or `IF NOT EXISTS`
  guard. Two concurrent handlers seeing the same `TenantCreated` event can both SELECT (empty),
  then both attempt CREATE.

**task-037** (status: not-started) captures both bugs with a full fix strategy and TDD test plan.
No new task required — task-037 is the correct vehicle.

### NFR Specs

All four NFR specs (`api-conventions`, `architecture`, `observability`, `testing`) are:
- Explicitly self-identified as NFRs in their opening paragraph ("NFR: This spec describes…").
- Cross-cutting conventions for agent implementers, not discrete deliverables.
- Excluded by project intake guidelines: "NFR specs … are NOT implementation tasks."

### `specs/index.spec.md`

A navigational index table listing all other specs. Contains no Requirements, Scenarios,
or behavioral contracts. No implementation task can be derived from an index.

---

## Conclusion

**No new task files created.** This is the third intake pass over this exact set of specs.
Decisions are stable: task-037 covers the tenants gap; NFR specs and the index are excluded.
