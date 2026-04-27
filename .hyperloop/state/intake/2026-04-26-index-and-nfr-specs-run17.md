# Intake Review: Index & NFR Specs — 2026-04-26 (Run 17)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no requirements or scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; is a guideline for implementers, not a deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; enforced via pytest-archon in individual bounded-context tasks |
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
bounded-context tasks. Decision is stable across 17 reviews.
