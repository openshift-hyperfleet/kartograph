# Intake Review: Index & NFR Specs — 2026-04-26 (run 29)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; convention guideline for all bounded-context tasks |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; structural constraints enforced via pytest-archon within bounded-context tasks |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability probe pattern applied per-context |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration in their opening line and describe
cross-cutting conventions rather than discrete deliverables. The `index.spec.md` is a pure
navigation document with no behavioral requirements.

**No new tasks created.** These specs are guidelines to be followed by agents working on
bounded-context tasks.
