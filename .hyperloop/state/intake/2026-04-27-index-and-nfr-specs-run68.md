# Intake Review: Index & NFR Specs — 2026-04-27 (run 68)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios — navigation document only |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; REST conventions are guidelines for all context implementers, not a standalone deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; DDD layering and bounded-context isolation rules enforced via pytest-archon per-context task |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability probe pattern applied per-context, not a standalone task |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy and test layering applied per-context, not a standalone task |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration on their opening line and describe
cross-cutting conventions rather than discrete deliverables. The index spec is a navigation
document with no behavioral Requirements or Scenarios.

**No task files were created.** These specs serve as reference material for implementing agents
working on bounded-context tasks.
