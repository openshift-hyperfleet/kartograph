# Intake Review: Index & NFR Specs — 2026-04-27 (run 60)

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; REST conventions are a guideline for all bounded-context presenters, not a standalone deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; DDD layering rules enforced via pytest-archon within each bounded-context task |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability probe pattern applied per bounded-context task |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per bounded-context task |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs open with an explicit `NFR:` declaration and describe cross-cutting
constraints that every implementing agent applies while working on domain-specific tasks.
They are not discrete deliverables.

`specs/index.spec.md` is a navigation document with no Requirements, Scenarios, or
behavioral obligations. It serves as a registry of all bounded-context specs.

## Note on repeated intake

This batch (`specs/index.spec.md` + all four `nfr/` specs) has been submitted for intake
many times. All prior runs reach the same conclusion. The current task-id ceiling is
**task-039**. No new tasks were created by this run.
