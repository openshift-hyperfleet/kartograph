# Intake Review: Index & NFR Specs — Run 19 (2026-04-26)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; is a guideline for implementers, not a deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; enforced via pytest-archon in individual bounded-context tasks |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; probe patterns are applied per-context, not as a standalone task |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; testing philosophy is applied per-context, not as a standalone task |

## Rationale

Per intake guidelines:
> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration in their opening line and describe
cross-cutting conventions rather than discrete deliverables. The index spec is a navigation
document with no behavioral requirements.

These specs remain available as reference material for implementing agents when working on
bounded-context tasks.

## Note

This batch has now been reviewed 19 times. The outcome is stable. If these specs continue
to be submitted for intake, consider suppressing them at the orchestrator level to avoid
generating redundant commits.
