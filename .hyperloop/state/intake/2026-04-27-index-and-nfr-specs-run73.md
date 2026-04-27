# Intake Review: Index & NFR Specs — 2026-04-27 (run 73)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; guideline applied per bounded-context task |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; structural rules enforced via pytest-archon per context |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability pattern applied per context |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per context |

## Rationale

Per intake guidelines:
> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration and describe cross-cutting conventions,
not discrete deliverables. `specs/index.spec.md` is a navigation document with no behavioral
requirements. No task files are created from this intake run.
