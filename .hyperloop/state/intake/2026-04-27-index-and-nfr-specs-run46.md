# Intake Review: Index & NFR Specs — Run 46 (2026-04-27)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; cross-cutting guideline for all bounded-context implementers |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; structural constraints enforced via pytest-archon within context tasks |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability probe pattern applied per-context |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context, not a standalone deliverable |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration in their opening line and describe
cross-cutting conventions rather than discrete deliverables. The index spec is a navigation
document with no behavioral requirements.

These specs remain available as reference material for implementing agents when working on
bounded-context tasks. No new tasks were created in `.hyperloop/state/tasks/`.
