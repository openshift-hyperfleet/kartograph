# Intake Record: Index & NFR Specs — 2026-04-27 (run 40)

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Pure table-of-contents — no Requirements or Scenarios; links only to other specs |
| `specs/nfr/api-conventions.spec.md` | No tasks | Explicitly tagged `NFR:` — REST conventions are a guideline for all bounded context implementers |
| `specs/nfr/architecture.spec.md` | No tasks | Explicitly tagged `NFR:` — DDD layering rules enforced via pytest-archon, not a discrete deliverable |
| `specs/nfr/observability.spec.md` | No tasks | Explicitly tagged `NFR:` — Domain-Oriented Observability pattern applied within each context's tasks |
| `specs/nfr/testing.spec.md` | No tasks | Explicitly tagged `NFR:` — fakes-over-mocks philosophy applied within each bounded context's tasks |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs open with an explicit `NFR:` declaration and describe cross-cutting conventions
rather than discrete deliverables. The `index.spec.md` is a navigation document containing only
links to other specs — it has no Requirements, Scenarios, or behavioral contracts.

**No new task IDs are issued from this intake run.**

## Note

This same set of specs has been processed many times with the same outcome. These specs do not
generate tasks by design. The intake loop should be redirected to other spec files (see
`specs/index.spec.md` for the full list of bounded-context specs that do generate tasks).
