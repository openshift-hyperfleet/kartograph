# Intake Review: Index + NFR Specs
## Date: 2026-04-28

## Specs Reviewed

| Spec | Status | Decision | Reason |
|------|--------|----------|--------|
| `specs/index.spec.md` | new | No task | Navigation/TOC document only — no behavioral requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | new | No task | Explicitly tagged NFR; REST conventions are guidelines for implementers, not deliverables |
| `specs/nfr/architecture.spec.md` | new | No task | Explicitly tagged NFR; DDD layering rules enforced via pytest-archon per bounded-context tasks |
| `specs/nfr/observability.spec.md` | new | No task | Explicitly tagged NFR; probe protocol pattern applied per bounded context |
| `specs/nfr/testing.spec.md` | new | No task | Explicitly tagged NFR; fakes-over-mocks philosophy applied per bounded context |

---

## Detailed Findings

### `specs/index.spec.md`

A table-of-contents document listing all bounded contexts and their associated spec files.
Contains no Requirements or Scenarios of its own — it is purely navigational, linking to
authoritative specs in the IAM, Graph, Management, Query, Ingestion, Shared Kernel, and UI
directories. No implementation work is derived directly from this file.

**Decision**: No task. Index document with no behavioral contracts.

---

### `specs/nfr/api-conventions.spec.md`

Self-identifies as an NFR at line 3: _"NFR: This spec describes REST API conventions that all
bounded context presentation layers MUST follow for consistency."_

Defines URL structure patterns (`/{context}/{resources}`), HTTP status codes (201/200/204/400/403/404/409/422/500),
error response format (`{"detail": "..."}`), Pydantic model conventions (snake_case fields,
ULID IDs, ISO 8601 timestamps), and FastAPI dependency injection rules. These are conventions
that presentation-layer implementers reference during bounded-context tasks — not a standalone
deliverable.

**Decision**: No task. NFR per project policy.

---

### `specs/nfr/architecture.spec.md`

Self-identifies as an NFR at line 3: _"NFR: This spec describes structural constraints enforced
via automated tests, not domain behavior."_

Defines DDD layering rules (domain → ports → application → infrastructure → presentation),
bounded context isolation, shared kernel independence, composition layer exception
(`infrastructure.mcp_dependencies`), and outbox infrastructure isolation. These constraints are
enforced via pytest-archon and referenced by implementers during each bounded-context task.

**Decision**: No task. NFR per project policy.

---

### `specs/nfr/observability.spec.md`

Self-identifies as an NFR at line 3: _"NFR: This spec describes a non-functional architectural
pattern, not domain behavior."_

Defines the Domain-Oriented Observability pattern: probe Protocols with domain-meaningful method
names, `DefaultXxxProbe` implementations using structlog, `ObservationContext` propagation
(frozen dataclass, `with_context()`, `with_extra()`, `as_dict()` excluding None fields), probe
layering (domain / application / infrastructure), and environment-aware log formatting (colored
console vs. JSON). Implementers apply these patterns within each bounded context's own tasks.

**Decision**: No task. NFR per project policy.

---

### `specs/nfr/testing.spec.md`

Self-identifies as an NFR at line 3: _"NFR: This spec describes the testing philosophy and
constraints for Kartograph."_

Defines the fakes-over-mocks philosophy: no `MagicMock`/`AsyncMock`/`patch` for domain or
application collaborators; in-memory fakes implementing port interfaces with domain-meaningful
setup methods; contract tests verifying fakes against real implementations; integration tests
against real PostgreSQL+AGE and SpiceDB; mocking acceptable only for HTTP clients, gRPC channels,
filesystem I/O, and clock/time. Implementers apply these conventions when writing tests for each
bounded-context task.

**Decision**: No task. NFR per project policy.

---

## Prior Art

These same specs have been reviewed in multiple prior intake runs (2026-04-23 through 2026-04-27)
with identical decisions each time. This run re-confirms those decisions with no change.

---

## Conclusion

No task files were created in this intake run. All five specs fall into categories explicitly
excluded from task creation per project guidelines:

- `specs/index.spec.md`: navigation document with no behavioral contracts
- Four NFR specs: project-wide guidelines that agents apply during domain task implementation

> _"NFR specs (testing, architecture, observability, API conventions) are NOT implementation
> tasks. They are guidelines. Do not create tasks for them."_
