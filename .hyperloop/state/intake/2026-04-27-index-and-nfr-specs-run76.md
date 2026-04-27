# Intake Review: Index & NFR Specs — 2026-04-27 (run 76)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; no Requirements or Scenarios — links only to other specs |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged `NFR:` — REST conventions are guidelines for implementers, not a discrete deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged `NFR:` — DDD layering rules enforced via pytest-archon per bounded context |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged `NFR:` — Domain-Oriented Observability pattern applied within each context's tasks |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged `NFR:` — fakes-over-mocks philosophy applied within each context's tasks |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs open with an explicit `NFR:` declaration and describe cross-cutting
conventions rather than discrete deliverables. `specs/index.spec.md` is a navigation
document with no behavioral requirements of its own.

These specs serve as standing reference material for agents implementing bounded-context tasks.
No new task IDs are issued from this intake run.

## Classification: Permanent

This batch of 5 specs has been reviewed and permanently classified as non-actionable for
task generation. Future intake runs should confirm this classification without re-examining
the specs in detail.
