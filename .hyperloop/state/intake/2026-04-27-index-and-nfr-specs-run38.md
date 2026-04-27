# Intake Review: Index & NFR Specs — Run 38

**Date:** 2026-04-27

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR; cross-cutting guideline for all bounded-context implementers |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR; structural constraints enforced via pytest-archon per context |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR; Domain-Oriented Observability pattern applied per bounded context |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per bounded context |

## Rationale

Per intake guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation
> tasks. They are guidelines. Do not create tasks for them.

Each NFR spec opens with an explicit `NFR:` declaration and describes a cross-cutting
convention or pattern to be applied by agents when working on bounded-context tasks — not a
discrete deliverable. In detail:

- **`specs/index.spec.md`** — Navigation document only. Lists bounded contexts and links to
  their spec files. Contains zero Requirements or Scenarios.
- **`specs/nfr/api-conventions.spec.md`** — URL structure, status codes, error format, and
  request/response model conventions. Guideline enforced during each presentation-layer task.
- **`specs/nfr/architecture.spec.md`** — DDD layering rules and bounded-context isolation
  enforced via pytest-archon. Each context task is responsible for maintaining the rules.
- **`specs/nfr/observability.spec.md`** — Domain-Oriented Observability probe pattern.
  Applied per context when implementing probes and structlog configuration.
- **`specs/nfr/testing.spec.md`** — Fakes-over-mocks philosophy, contract tests, and test
  layering. Applied as a constraint across all context implementation tasks.

## Decision

**Zero task files created.** Existing task inventory (task-001 through task-039) is
unchanged. These specs serve as standing guidelines consumed by implementing agents.
