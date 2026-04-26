# Intake Record: NFR + Index Specs (2026-04-26)

**Date:** 2026-04-26

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Navigation/TOC document only — no behavioral requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | NFR guideline — conventions applied per-context during domain tasks, not a standalone deliverable |
| `specs/nfr/architecture.spec.md` | No tasks | NFR guideline — DDD layering rules enforced via pytest-archon, not a feature task |
| `specs/nfr/observability.spec.md` | No tasks | NFR guideline — Domain-Oriented Observability pattern, applied per-context during context tasks |
| `specs/nfr/testing.spec.md` | No tasks | NFR guideline — fakes-over-mocks philosophy, applied per-context during context tasks |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

The `index.spec.md` contains no Requirements or Scenarios — it is a table of contents linking to
other specs. No implementation work derives from it directly.

The four NFR specs describe cross-cutting constraints and patterns that every implementing agent
MUST follow when working on domain-specific tasks. They govern how code is written (layering,
observability probes, test fakes, URL conventions), not what is built. Agents are expected to
consult these specs as guardrails during each context's implementation tasks.

## Prior Record

An earlier intake record covering the same spec set exists at
`.hyperloop/intake/nfr-and-index-intake.md` (2026-04-24). This record is a subsequent pass
confirming the same conclusion: no tasks warranted.
