# Intake Review: Index & NFR Specs — 2026-04-26 (run 30)

## Specs Reviewed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Pure table-of-contents; no Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | Explicitly tagged NFR; REST convention guideline for all bounded-context implementers |
| `specs/nfr/architecture.spec.md` | No tasks | Explicitly tagged NFR; DDD layering constraints enforced via pytest-archon per-context |
| `specs/nfr/observability.spec.md` | No tasks | Explicitly tagged NFR; Domain-Oriented Observability probe pattern applied per-context |
| `specs/nfr/testing.spec.md` | No tasks | Explicitly tagged NFR; fakes-over-mocks philosophy applied per-context |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

`specs/index.spec.md` is a navigation document listing bounded contexts and their spec files.
It contains no behavioral Requirements or Scenarios; no implementation work derives from it.

The four `nfr/` specs each carry an explicit `NFR:` declaration on their opening line and
describe cross-cutting conventions governing *how* code is written — not *what* is built:

- **api-conventions**: URL structure, HTTP status codes, error format, Pydantic model rules.
  Applied by agents when implementing bounded-context presentation layers.
- **architecture**: DDD layering rules (domain → ports → application → infrastructure →
  presentation) enforced via `pytest-archon`. Architecture tests are written as part of
  each context's task, not as a separate deliverable.
- **observability**: Domain-Oriented Observability probe pattern (Protocol + DefaultImpl +
  ObservationContext). Probe implementations are authored alongside domain services within
  each context's task.
- **testing**: Fakes-over-mocks philosophy, contract tests, test layering. Applied as a
  discipline within every implementation task, not a standalone deliverable.

## Conclusion

**Zero tasks created.** All five specs are guidelines or navigation documents.
Tasks remain at `task-039` (highest existing). This conclusion is consistent with all
prior runs of this intake batch.
