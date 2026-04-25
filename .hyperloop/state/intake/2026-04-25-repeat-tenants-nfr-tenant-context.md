# Intake Review: Tenants (modified), NFR specs (new), Index (new), Tenant Context (modified)
## Date: 2026-04-25 (repeat verification pass)

## Specs Reviewed

| Spec | Status | Decision | Reason |
|------|--------|----------|--------|
| `specs/iam/tenants.spec.md` | modified | No new task | task-037 already captures both new AND-clauses (transaction leak + atomic check). See commit `2ab8b665`. |
| `specs/index.spec.md` | new | No task | Pure table-of-contents with no requirements or scenarios. |
| `specs/nfr/api-conventions.spec.md` | new | No task | Explicitly tagged NFR (line 3: "NFR: This spec describes…"). Guidelines: do not create tasks for NFR specs. |
| `specs/nfr/architecture.spec.md` | new | No task | Explicitly tagged NFR (line 3: "NFR: This spec describes…"). Same policy. |
| `specs/nfr/observability.spec.md` | new | No task | Explicitly tagged NFR (line 3: "NFR: This spec describes…"). Same policy. |
| `specs/nfr/testing.spec.md` | new | No task | Explicitly tagged NFR (line 3: "NFR: This spec describes…"). Same policy. |
| `specs/shared-kernel/tenant-context.spec.md` | modified | No task | File is 87 lines — identical to blob `ded09d09b3de73d6ed9527214fcd081069a55630` referenced by task-031. Zero content change. All 13 scenarios verified implemented (see `2026-04-25-tenants-and-tenant-context.md`). |

---

## Verification Detail

### `specs/iam/tenants.spec.md`

The supplied diff adds exactly two AND-clauses to **Scenario: Tenant graph provisioning**:

```
- AND the database connection MUST be properly committed or rolled back on all code paths
  (including the no-op/exists path) to avoid leaking open transactions back to the connection pool
- AND the existence check and graph creation MUST be performed atomically (e.g. via
  `CREATE GRAPH IF NOT EXISTS` or an advisory lock) to prevent race conditions under concurrent
  duplicate event deliveries
```

**task-037** (status: not-started, created commit `2ab8b665`) covers both requirements with
detailed bug descriptions, fix strategy, and TDD test plan targeting
`src/api/graph/infrastructure/tenant_graph_handler.py`. No new task required.

### NFR Specs

All four NFR specs (`api-conventions`, `architecture`, `observability`, `testing`) are:
- Explicitly self-identified as NFRs in their opening paragraph.
- Guidelines for agent implementers, not deliverables with acceptance criteria.
- Per project guidelines: "NFR specs … are NOT implementation tasks. They are guidelines.
  Do not create tasks for them."

### `specs/index.spec.md`

A navigational index table with no Requirements, Scenarios, or behavioral contracts.
No implementation task can be derived from an index.

### `specs/shared-kernel/tenant-context.spec.md`

Content hash confirmed identical to task-031's `spec_ref` blob. The full scenario
coverage table from `2026-04-25-tenants-and-tenant-context.md` applies unchanged:
- 5/5 Multi-Tenant Header Resolution scenarios: implemented and tested.
- 4/4 Single-Tenant Auto-Selection scenarios: implemented and tested.
- 4/4 MCP Authentication scenarios: implemented and tested.

---

## Conclusion

No new task files created. All specs either:
1. Already have covering tasks (task-037 for tenants modification), or
2. Carry no implementation requirements (NFR, index), or
3. Are fully implemented with zero spec content change (tenant-context).
