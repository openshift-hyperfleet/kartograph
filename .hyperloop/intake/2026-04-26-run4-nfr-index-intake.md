# Intake Record: NFR + Index Specs (2026-04-26, Run 4)

**Date:** 2026-04-26

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Navigation/TOC document only — no behavioral Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | NFR guideline — URL conventions, status codes, error format are applied per-context during domain tasks, not a standalone deliverable |
| `specs/nfr/architecture.spec.md` | No tasks | NFR guideline — DDD layering rules enforced via pytest-archon; agents consult this as a guardrail, not a feature to ship |
| `specs/nfr/observability.spec.md` | No tasks | NFR guideline — Domain-Oriented Observability probe pattern applied inline within each bounded context's tasks |
| `specs/nfr/testing.spec.md` | No tasks | NFR guideline — fakes-over-mocks philosophy governs how all other tasks write test suites, not a deliverable on its own |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

`specs/index.spec.md` contains no Requirements or Scenarios — it is a table of contents that
links to the actual behavioral specs in each bounded context subdirectory. No implementation
work is derived from it directly.

The four NFR specs describe cross-cutting constraints that every implementing agent MUST follow:

- **api-conventions** — URL structure, HTTP status codes, error body format, Pydantic model
  conventions (snake_case, ULID IDs, ISO 8601 timestamps). Applied during every
  presentation-layer task; there is no standalone API conventions task.
- **architecture** — DDD layering rules (domain → ports → application → infrastructure →
  presentation) with pytest-archon import checks. Enforced by the test suite across all
  bounded context tasks.
- **observability** — Domain probe Protocols + structlog `DefaultXxxProbe` pattern.
  Implemented inline within each bounded context's own domain/application/infrastructure tasks.
- **testing** — Fakes over mocks philosophy, in-memory fake implementations, contract tests,
  and test layering. Governs how all tasks write their test suites.

## Prior Records

| Date | File |
|------|------|
| 2026-04-24 | `.hyperloop/intake/nfr-and-index-intake.md` |
| 2026-04-26 (run 1) | `.hyperloop/intake/2026-04-26-nfr-index-intake.md` |
| 2026-04-26 (run 2) | `.hyperloop/intake/2026-04-26-run2-nfr-index-intake.md` |

This is the fourth consecutive pass confirming the same conclusion: **no tasks warranted for
this spec set**. These specs are stable guidelines — they do not change with each processing run.
