# Intake Review: Index & NFR Specs — 2026-04-27 (run 45)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no requirements or scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; guideline for implementers, not a deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; enforced via pytest-archon in individual bounded-context tasks |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; probe patterns applied per-context, not a standalone task |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context, not a standalone task |

## Rationale

Per intake guidelines:
> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration in their opening line and describe
cross-cutting conventions rather than discrete deliverables. The index spec is a navigation
document with no behavioral requirements or scenarios. No new task files are created.
