---
task_id: task-014
round: 1
role: verifier
verdict: fail
---
## Verification Summary

### Checks Executed

| Check | Result | Detail |
|---|---|---|
| Unit tests (1997) | PASS | All pass, 0 failures |
| Ruff linting | PASS | Zero violations |
| Ruff formatting | PASS | 439 files formatted |
| Mypy type checking | PASS | Zero errors in 439 source files |
| Architecture boundary tests (40) | PASS | All pass |
| check-failure-path-tests.sh | PASS | No failure-path conditions in spec |
| check-idempotency-tests.sh | PASS | No idempotency requirements in spec |
| check-frontend-tests-exist.sh | **FAIL** | 185 UI source files, ZERO test files |
| check-no-coming-soon-stubs.sh | **FAIL** | 2 stub markers in production source |

---

## Findings

### FAIL 1 — No Frontend Tests (check-frontend-tests-exist.sh)

The TDD mandate in `AGENTS.md` requires tests to be written before writing component
code. The `check-frontend-tests-exist.sh` script enforces this. There are 185 Vue/TS
source files in `src/dev-ui` but zero test files (`*.test.ts`, `*.spec.ts`, etc.).

**Required action:** Add vitest + @vue/test-utils to `src/dev-ui/package.json` and
write at least one component test per implemented spec scenario. Priority tests:

- `data-sources/index.vue` — wizard step navigation, adapter selection, field
  validation, credential-token show/hide, ontology type inline editing,
  approval confirmation, re-extraction warning
- `pages/index.vue` — returning-user redirect logic, workspace-guidance toast
- `graph/schema.vue` — edge-type explorer cross-navigation button

---

### FAIL 2 — Coming Soon Stub Markers (check-no-coming-soon-stubs.sh)

**Instance A** — `src/dev-ui/app/pages/data-sources/index.vue:396`:

```ts
function approveOntology() {
  // The full data source + ontology pipeline is not yet wired to the backend.
  toast.info('Data source connection coming soon', { ... })
  wizardOpen.value = false
}
```

The wizard guides users through four steps (adapter selection, configuration, intent,
ontology review) but the final "Approve & Start Extraction" action is a stub toast.
The spec scenario "Ontology review and approval" (Requirement: Ontology Design) says:
> "extraction begins only after the user explicitly approves"

A stub toast is not an implementation. The UI should call the Management API to
persist the data source configuration and ontology (even if the ingestion pipeline is
not yet available). If the Ingestion backend is blocked on a future task, that should
be raised as a scope blocker before submission, not silently stubbed.

**Instance B** — `src/dev-ui/app/layouts/default.vue:532`:

```html
{{ item.label }}{{ item.disabled ? ' (Coming Soon)' : '' }}
```

The GitLab and Jira adapters in the data-sources wizard use `available: false` and
display "(Coming Soon)" in the tooltip. The check script matches any `"Coming Soon"`
string in production source files regardless of context. Either:
- Remove the `(Coming Soon)` tooltip text and replace with "not yet available", or
- Move the disabled adapter entries out of the production source entirely until they
  are implemented.

---

### FAIL 3 — Sync Monitoring Scenarios Not Implemented

All four Sync Monitoring scenarios in the spec remain unimplemented:

- **Active sync progress** (ingesting → extracting → applying with progress indicator)
- **Sync history** (list of runs with status, timestamps, duration)
- **Sync logs** (per-run detailed log viewer)
- **Manual sync trigger** (for users with manage permission)

The current `data-sources/index.vue` only shows an empty-state card and a wizard for
adding new sources. The data source list section (line 462–464) contains only a comment:
```html
<!-- Future: data source cards with sync status, history, trigger -->
```

This is effectively a stub for an entire spec requirement. Even if the Ingestion backend
doesn't exist yet, the UI structure (cards with status badges, history table, log drawer,
trigger button) should be scaffolded and driven from mock/empty state so the spec
scenarios are visually satisfied. Alternatively, raise a formal scope blocker.

---

### Additional Observations (Non-blocking for this verdict)

- **Commit trailers**: The two implementation commits (`51d205bd`, `b7503747`) and the
  worker-result commit (`1ff61ebf`) all carry `Spec-Ref` and `Task-Ref` trailers.
  ✓ Compliant.
- **No hardcoded secrets**: No credentials or environment-specific values found.
- **No logger/print in Vue**: Domain-probe pattern not applicable to frontend Vue
  components; no inappropriate logging found.
- **Python backend unchanged**: All 1997 unit tests pass; DDD boundary tests pass.
  This task is UI-only and correctly scoped.

---

## Required Fixes Before Re-submission

1. Add `vitest` + `@vue/test-utils` to `src/dev-ui` dev dependencies and write
   component tests for the new data-sources wizard and the index-page redirect logic.
2. Remove the `'Data source connection coming soon'` stub toast from `approveOntology()`
   and either (a) call the Management API to save the data source + ontology, or
   (b) formally document this as out-of-scope for task-014 and raise a blocker.
3. Remove or replace the `(Coming Soon)` tooltip text in `layouts/default.vue`.
4. Implement (or explicitly scope-block) the four Sync Monitoring UI scenarios.