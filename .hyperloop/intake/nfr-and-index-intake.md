# Intake Record: NFR + Index Specs

**Date:** 2026-04-24

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Navigation/TOC document only — no behavioral requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | NFR guideline — all bounded contexts must follow conventions, no standalone implementation task |
| `specs/nfr/architecture.spec.md` | No tasks | NFR guideline — structural constraints enforced via pytest-archon, not a feature |
| `specs/nfr/observability.spec.md` | No tasks | NFR guideline — Domain-Oriented Observability pattern, applied per-context during context tasks |
| `specs/nfr/testing.spec.md` | No tasks | NFR guideline — fakes-over-mocks philosophy, applied per-context during context tasks |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

The `index.spec.md` contains no Requirements or Scenarios — it is a table of contents linking to
other specs. No implementation work derives from it directly.

The four NFR specs (api-conventions, architecture, observability, testing) describe cross-cutting
constraints and patterns that every implementing agent is expected to follow when working on
domain-specific tasks. They are not standalone deliverables.
