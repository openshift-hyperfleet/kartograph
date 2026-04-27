# Intake Review: Index & NFR Specs — 2026-04-26

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No task | Pure table-of-contents; contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR — URL structure, status codes, error format, auth patterns are conventions implementers must follow, not a deliverable |
| `specs/nfr/architecture.spec.md` | No task | Explicitly tagged NFR — DDD layering rules enforced via pytest-archon within each bounded-context task |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR — Domain-Oriented Observability probe pattern applied per-context during each context's own tasks |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR — fakes-over-mocks philosophy and test layering strategy applied per-context |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

`specs/index.spec.md` contains no Requirements or Scenarios. It is a navigation document that
cross-references the behavioral specs in each bounded context. No implementation work derives
from it.

The four NFR specs describe cross-cutting constraints that every implementing agent MUST consult
when working on domain-specific tasks:

- **api-conventions** — Uniform URL structure (`/{context}/{resources}/{id}`), HTTP status codes
  (201/200/204, 400/403/404/409/422), `{"detail": "..."}` error format, ULID IDs, snake_case
  fields, ISO 8601 timestamps. Every presentation-layer task must conform; no standalone task.
- **architecture** — DDD layering rules (domain → ports → application → infrastructure →
  presentation) enforced by pytest-archon import-boundary tests embedded in each bounded context.
  Bounded context isolation and shared-kernel independence are verified by existing arch tests.
- **observability** — Domain probe Protocols with structlog `DefaultXxxProbe` implementations,
  `ObservationContext` immutable dataclass for request-scoped correlation. Applied inline within
  each bounded context's own tasks; no standalone task.
- **testing** — Fakes over mocks, in-memory repository fakes implementing port interfaces,
  contract tests, integration tests against real infrastructure (Postgres/AGE, SpiceDB).
  Governs how all other tasks write their test suites, not a deliverable in itself.

## Conclusion

**No task files were created in this intake run.** All five specs are non-actionable per
the project's task decomposition guidelines.

Prior intake records confirming the same conclusion:

| Date | Location |
|------|----------|
| 2026-04-23 | `.hyperloop/state/intake/2026-04-23-index-and-nfr-specs.md` |
| 2026-04-24 | `.hyperloop/intake/nfr-and-index-intake.md` |
| 2026-04-25 | `.hyperloop/state/intake/2026-04-25-tenants-and-tenant-context.md` (combined run) |
