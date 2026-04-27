# Intake Record: Index & NFR Specs — 2026-04-27 (run 66)

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Pure table-of-contents — no Requirements or Scenarios; links only to other specs |
| `specs/nfr/api-conventions.spec.md` | No tasks | Explicitly tagged `NFR:` — REST conventions are a guideline for all bounded context implementers, not a standalone deliverable |
| `specs/nfr/architecture.spec.md` | No tasks | Explicitly tagged `NFR:` — DDD layering rules enforced via pytest-archon, applied during context implementation tasks |
| `specs/nfr/observability.spec.md` | No tasks | Explicitly tagged `NFR:` — Domain-Oriented Observability pattern applied within each context's tasks |
| `specs/nfr/testing.spec.md` | No tasks | Explicitly tagged `NFR:` — fakes-over-mocks philosophy applied within each context's tasks |

## Rationale

Per task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs open with an explicit `NFR:` declaration and describe cross-cutting constraints
rather than discrete deliverables. The `index.spec.md` is a navigation document with no behavioral
requirements of its own — it contains only a table of links to other specs.

These specs serve as standing reference material for agents implementing bounded-context tasks.
No new task IDs are issued from this intake run.
