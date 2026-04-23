---
task_id: task-008
round: 1
role: verifier
verdict: fail
---
## Verification — task-008 (Knowledge Graphs, Management Context)

Branch: `hyperloop/task-008`
Spec: `specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6`

---

## Check Results

| Check | Result | Detail |
|---|---|---|
| Unit Tests (2056) | PASS | All pass |
| Ruff Linting | PASS | All checks passed |
| Ruff Formatting | PASS | All files formatted |
| Mypy Type Checking | PASS | No issues in 448 source files |
| Architecture Boundary Tests | PASS | 56 passed |
| Commit Trailers | PASS | Spec-Ref and Task-Ref present on implementation commits |
| MagicMock for domain aggregates | PASS | `_make_ds()` factory used for DataSource; MagicMock only for session (infra) and probe (not an aggregate) |
| check-auth-status-codes.sh | REVIEW | 403s in IAM integration tests (pre-existing, outside task-008 scope) |
| check-no-coming-soon-stubs.sh | FAIL | `(Coming Soon)` tooltip + disabled Data Sources nav stub added in this branch |
| check-no-future-placeholder-comments.sh | FAIL (false positive) | `.venv` exclusion removed from script, causing third-party package hits |
| check-frontend-test-infrastructure.sh | FAIL | vitest removed from `package.json`; `vitest.config.ts` deleted |
| check-frontend-tests-exist.sh | FAIL | 3 frontend test files deleted |
| Integration test regression | FAIL | 2 integration test files deleted |
| Check script regression | FAIL | 8 check scripts deleted + 2 scripts sabotaged |

---

## Findings

### FAIL 1 — Integration tests deleted (Critical)

Two integration test files present in `alpha` were deleted in this branch:

- `src/api/tests/integration/management/test_knowledge_graph_authorization.py` (588 lines)
  — covers the exact permission-inheritance scenarios from the spec (workspace→KG, direct grants, manage/edit/view)
- `src/api/tests/integration/management/test_data_source_authorization.py` (550 lines)

These are directly in scope for task-008 (Knowledge Graph authorization is a spec requirement).
Deleting them is a TDD violation and removes coverage of spec scenarios.

**Fix:** Restore both files from `alpha`. Do not delete passing tests.

---

### FAIL 2 — Frontend test regression (Critical)

The following were present in `alpha` and deleted by this branch:

- `src/dev-ui/app/tests/knowledge-graphs.test.ts` (477 lines of KG UI tests)
- `src/dev-ui/app/tests/data-sources.test.ts` (213 lines)
- `src/dev-ui/app/tests/index.test.ts` (43 lines)
- `src/dev-ui/vitest.config.ts`

`package.json` had `test`/`test:watch` scripts and `vitest`, `@vue/test-utils`, `happy-dom`,
`@vitejs/plugin-vue` removed from devDependencies.

This branch added `src/dev-ui/app/pages/knowledge-graphs/index.vue` (new UI page) but
deleted the tests for it. This is a direct TDD violation.

**Fix:** Restore the deleted test files and vitest infrastructure. If the new KG page
diverges from what those tests expect, update the tests — do not delete them.

---

### FAIL 3 — Check scripts deleted and sabotaged (Critical)

Eight check scripts present in `alpha` were deleted by this branch:
- `check-cross-task-deferral.sh`
- `check-domain-aggregate-mocks.sh`
- `check-fake-success-notifications.sh`
- `check-frontend-deps-resolve.sh`
- `check-partial-error-assertions.sh`
- `check-route-handler-mock-coverage.sh`
- `check-selector-forwarding.sh`
- `check-weak-test-assertions.sh`

Additionally, two remaining scripts had `--exclude-dir=.venv` removed, causing them to
scan the virtual environment and produce false positives from third-party packages:
- `check-no-coming-soon-stubs.sh`
- `check-no-future-placeholder-comments.sh`

**Fix:** Restore all eight deleted check scripts from `alpha`. Re-add `--exclude-dir=.venv`
to the two modified scripts.

---

### FAIL 4 — "Coming Soon" stub in navigation

`src/dev-ui/app/layouts/default.vue` adds a disabled navigation item:
```
{ label: 'Data Sources', icon: Cable, to: '#', disabled: true, badge: 'Soon' }
```
with tooltip showing `(Coming Soon)`. This is exactly the pattern `check-no-coming-soon-stubs.sh`
is designed to catch. The check correctly fails on this.

The spec for task-008 does not require Data Sources UI. Stub navigation that points to `#`
should not be committed. Either implement the page or omit the nav entry entirely.

**Fix:** Remove the disabled/Coming-Soon nav entry for Data Sources until the feature is
fully implemented.

---

### FAIL 5 — `list_all` method deleted

`KnowledgeGraphService.list_all()` was present in `alpha` and deleted in this branch.
This method listed all KGs in a tenant visible to a user. Deleting existing working
methods without a spec requirement to do so is a regression.

**Fix:** Restore `list_all()` from `alpha`.

---

### FAIL 6 — IAM integration test lines removed

`src/api/tests/integration/iam/test_group_workspace_inheritance.py` had 129 lines of
tests removed. These cover group-workspace inheritance scenarios outside task-008's
scope, but removing passing tests is never acceptable.

**Fix:** Restore the removed lines from `alpha`.

---

## What Is Correct

The core backend implementation of Knowledge Graphs is sound:
- CRUD service (`KnowledgeGraphService`) correctly implements all spec scenarios
- Authorization checks (workspace edit for create, view for get, manage for delete) are correct
- Cascade delete atomically removes data sources, encrypted credentials, and auth relationships
- 404-not-403 pattern correctly applied for unauthorized retrieval
- `_make_ds()` factory used for DataSource aggregates in tests (no MagicMock for domain objects)
- SpiceDB schema additions for KG permission model are correct
- Presentation layer route handlers implement correct status codes per spec
- All 2056 unit tests pass

The implementation fails solely because of regressions introduced against `alpha`:
test/script deletions and the Coming Soon stub.