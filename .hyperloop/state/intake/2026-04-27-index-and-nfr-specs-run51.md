# Intake Review: Index & NFR Specs — 2026-04-27 (Run 51)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; guideline for all bounded-context implementers, not a standalone deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; structural constraints enforced via pytest-archon within each bounded-context task |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability pattern applied per-context, not a standalone task |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context, not a standalone task |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

All four `nfr/` specs carry an explicit `NFR:` declaration in their opening line and describe
cross-cutting conventions that every agent must follow when working on domain-specific tasks.
They are not standalone deliverables.

`specs/index.spec.md` is a navigation document (table of contents) that links to other specs.
It contains no Requirements or Scenarios of its own. No implementation work derives directly
from it.

**No task files were created for this intake run.**
