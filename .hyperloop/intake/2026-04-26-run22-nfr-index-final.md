# Intake Record: NFR + Index Specs (Run 22 — Definitive)

**Date:** 2026-04-26

## Specs Processed

| Spec | Decision | Reason |
|------|----------|--------|
| `specs/index.spec.md` | No tasks | Navigation/TOC document only — no behavioral Requirements or Scenarios |
| `specs/nfr/api-conventions.spec.md` | No tasks | NFR guideline — REST conventions agents must follow per-context; not a deliverable |
| `specs/nfr/architecture.spec.md` | No tasks | NFR guideline — DDD layering rules enforced via pytest-archon; not a feature task |
| `specs/nfr/observability.spec.md` | No tasks | NFR guideline — Domain-Oriented Observability pattern applied during context tasks |
| `specs/nfr/testing.spec.md` | No tasks | NFR guideline — fakes-over-mocks philosophy applied during context tasks |

## Rationale

Per the task decomposition guidelines:

> NFR specs (testing, architecture, observability, API conventions) are NOT implementation tasks.
> They are guidelines. Do not create tasks for them.

`specs/index.spec.md` contains no Requirements or Scenarios — it is a table of contents
linking to other specs. No implementation work derives from it directly.

The four NFR specs describe cross-cutting constraints and patterns every implementing agent
MUST follow when working on domain-specific tasks. They govern *how* code is written
(layering rules, observability probes, test fakes, URL conventions), not *what* is built.
Agents are expected to consult these specs as guardrails during each context's
implementation tasks.

## Prior Records

Multiple prior intake runs (runs 1–21) reached the same conclusion and are documented in:
- `.hyperloop/intake/nfr-and-index-intake.md` (original, 2026-04-24)
- `.hyperloop/intake/2026-04-26-nfr-index-intake.md` through `run6`
- `.hyperloop/state/intake/` (runs 4–21, untracked — see git status)

The committed baseline is: `edca2158 chore(intake): record run-21 intake decision for index and NFR specs`

## Conclusion

**Zero tasks created.** These specs are guidelines, not deliverables.
