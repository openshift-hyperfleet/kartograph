# Intake Record: Index & NFR Specs — 2026-04-27

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Pure table-of-contents — no Requirements or Scenarios; contains only links to other specs |
| `specs/nfr/api-conventions.spec.md` | No tasks | Explicitly tagged `NFR:` — REST conventions are a guideline for implementers, applied per bounded context |
| `specs/nfr/architecture.spec.md` | No tasks | Explicitly tagged `NFR:` — DDD layering rules enforced via pytest-archon, not a standalone deliverable |
| `specs/nfr/observability.spec.md` | No tasks | Explicitly tagged `NFR:` — Domain-Oriented Observability pattern applied within each context's tasks |
| `specs/nfr/testing.spec.md` | No tasks | Explicitly tagged `NFR:` — fakes-over-mocks philosophy applied within each context's tasks |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs open with an explicit `NFR:` declaration and describe cross-cutting conventions
rather than discrete deliverables. The index spec is a navigation document with no behavioral
requirements of its own.

These specs serve as standing reference material for agents implementing bounded-context tasks.
No new task IDs are issued from this intake run.
