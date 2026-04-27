# Intake Review: Index & NFR Specs — 2026-04-26 (run 28)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Pure table-of-contents; no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | Explicitly tagged NFR; convention guideline for all bounded-context implementers |
| `specs/nfr/architecture.spec.md` | No tasks | Explicitly tagged NFR; DDD layering constraints enforced via pytest-archon per-context |
| `specs/nfr/observability.spec.md` | No tasks | Explicitly tagged NFR; Domain-Oriented Observability probe pattern applied per-context |
| `specs/nfr/testing.spec.md` | No tasks | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration on their opening line and describe
cross-cutting conventions rather than discrete deliverables. The `index.spec.md` is a
navigation document with no behavioral requirements or implementation obligations.

## No Tasks Created

Tasks exist up to `task-039`. This intake batch produces no new task files.
This decision has been confirmed consistently across all prior runs of this intake batch.
