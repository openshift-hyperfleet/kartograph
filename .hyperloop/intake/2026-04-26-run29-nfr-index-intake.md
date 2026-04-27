# Intake Record: NFR + Index Specs (Run 29)

**Date:** 2026-04-26

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Navigation/TOC document only — contains no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | NFR guideline — REST conventions agents must follow per-context; not a standalone deliverable |
| `specs/nfr/architecture.spec.md` | No tasks | NFR guideline — DDD layering rules enforced via pytest-archon; not a feature task |
| `specs/nfr/observability.spec.md` | No tasks | NFR guideline — Domain-Oriented Observability pattern applied during context tasks |
| `specs/nfr/testing.spec.md` | No tasks | NFR guideline — fakes-over-mocks philosophy applied during context tasks |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

`specs/index.spec.md` is a table-of-contents document. It lists bounded contexts and their
spec files but contains no behavioral Requirements or Scenarios of its own. No implementation
work derives from it directly.

The four `nfr/` specs each open with an explicit `NFR:` declaration and describe cross-cutting
constraints governing *how* code is written — not *what* is built:

- **api-conventions**: URL structure, status codes, error format, Pydantic models. Agents
  must follow these conventions when building bounded-context presentation layers.
- **architecture**: DDD layering rules (domain → ports → application → infrastructure →
  presentation) enforced via `pytest-archon`. Tests are written as part of each context
  task, not as a separate deliverable.
- **observability**: Domain-Oriented Observability probe pattern (Protocol + DefaultImpl +
  ObservationContext). Probe implementations are created alongside domain services in each
  context task.
- **testing**: Fakes-over-mocks philosophy, contract tests, test layering. Applied as a
  discipline within every implementation task.

## Conclusion

**Zero tasks created.** All five specs are guidelines or navigation documents, not deliverables.
