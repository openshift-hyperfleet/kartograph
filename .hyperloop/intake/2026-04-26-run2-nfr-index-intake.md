# Intake Record: NFR + Index Specs (2026-04-26, Run 2)

**Date:** 2026-04-26

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Navigation/TOC document only — no behavioral Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | NFR guideline — URL conventions, status codes, error format applied per-context during domain tasks |
| `specs/nfr/architecture.spec.md` | No tasks | NFR guideline — DDD layering rules enforced via pytest-archon; no standalone deliverable |
| `specs/nfr/observability.spec.md` | No tasks | NFR guideline — Domain-Oriented Observability probe pattern applied per-context |
| `specs/nfr/testing.spec.md` | No tasks | NFR guideline — fakes-over-mocks philosophy applied per-context during context tasks |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

`specs/index.spec.md` contains no Requirements or Scenarios — it is a table of contents that
links to the actual behavioral specs. No implementation work derives from it directly.

The four NFR specs describe cross-cutting constraints and patterns that every implementing agent
MUST consult when working on domain-specific tasks:

- **api-conventions** — URL structure, HTTP status codes, error format, Pydantic model rules.
  Every presentation-layer task must conform; there is no standalone API conventions task.
- **architecture** — DDD layering rules (domain → ports → application → infrastructure →
  presentation) enforced by pytest-archon import checks. Violated by code, caught by existing
  arch tests.
- **observability** — Domain probe Protocols + structlog DefaultXxxProbe pattern. Implemented
  inline within each bounded context's own tasks.
- **testing** — Fakes over mocks philosophy, contract tests, test layering. Governs how
  all other tasks write their test suites, not a deliverable on its own.

## Prior Records

| Date | File |
|------|------|
| 2026-04-24 | `.hyperloop/intake/nfr-and-index-intake.md` |
| 2026-04-26 | `.hyperloop/intake/2026-04-26-nfr-index-intake.md` |

This is the third consecutive pass confirming the same conclusion: no tasks warranted for
this spec set.
