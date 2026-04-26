# Intake Review: Index & NFR Specs — Run 32 (2026-04-26)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; cross-cutting guideline, not a deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; enforced via pytest-archon in per-context tasks |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; probe patterns applied per-context, not standalone |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` tag in their opening line and describe
cross-cutting conventions rather than discrete deliverables. The index spec is a navigation
document with no behavioral requirements.

These specs remain available as reference material for implementing agents when working on
bounded-context tasks.

## Note

This is a repeat intake run (run 32). The same five specs have been reviewed and rejected
for task creation in all prior runs. The decision is stable and unchanged.
