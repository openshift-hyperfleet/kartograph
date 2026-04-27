# Intake Review: NFR and Index Specs

**Date:** 2026-04-27
**Reviewer:** PM agent

## Specs Reviewed

| Spec | Disposition | Reason |
|------|-------------|--------|
| `specs/index.spec.md` | No task | Index/catalog file. No behavioral requirements — lists other specs for navigation only. |
| `specs/nfr/api-conventions.spec.md` | No task | Explicitly tagged NFR. Describes REST conventions that implementers follow as a guideline, not a standalone implementation target. |
| `specs/nfr/architecture.spec.md` | Explicitly tagged NFR. Describes DDD layering constraints enforced via `pytest-archon`; architecture tests are generated alongside the domain tasks they guard. |
| `specs/nfr/observability.spec.md` | No task | Explicitly tagged NFR. Describes the Domain-Oriented Observability pattern agents follow when implementing any bounded context. |
| `specs/nfr/testing.spec.md` | No task | Explicitly tagged NFR. Describes the fakes-over-mocks philosophy agents apply when writing tests for any bounded context. |

## Rationale

Per project guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT
> implementation tasks. They are guidelines. Do not create tasks for them.

All four `nfr/` specs are explicitly tagged with `NFR:` in their Purpose section and
match the listed NFR categories (api-conventions, architecture, observability, testing).
The index file is a table of contents with no behavioral requirements.

**Zero tasks created from this intake.**

## How NFRs Are Applied

These specs are referenced by implementer agents at task execution time:

- **api-conventions** — Applied when implementing presentation layers (routes, response models).
- **architecture** — Applied when writing `pytest-archon` import boundary tests alongside each bounded context.
- **observability** — Applied when adding probes to domain, application, and infrastructure layers.
- **testing** — Applied when choosing between fakes, integration tests, and (limited) mocks.
