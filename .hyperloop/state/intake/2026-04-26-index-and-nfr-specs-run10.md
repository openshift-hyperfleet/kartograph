# Intake Review: Index & NFR Specs — 2026-04-26 (run 10)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; cross-cutting convention guideline for all bounded contexts |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; DDD layering rules enforced via pytest-archon in per-context tasks |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability pattern applied per-context |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context |

## Rationale

Per intake guidelines:
> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration in their opening line and describe
cross-cutting conventions rather than discrete deliverables. The index spec is a navigation
document with no behavioral requirements.

These specs remain available as reference material for implementing agents when working on
bounded-context tasks.

## Note

This is run 10 of this identical intake batch. No new tasks have been created on any run.
The highest existing task ID is task-038. This batch does not increment that counter.
