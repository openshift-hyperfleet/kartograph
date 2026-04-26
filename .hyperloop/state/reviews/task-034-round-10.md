---
task_id: task-034
round: 10
role: verifier
verdict: fail
---
# Verification: task-034 Credentials — FAIL

## Rebase Status

Branch rebased to alpha `1cdf1e7e` (was 13 commits behind).
Post-rebase: `OK: Branch is 0 commit(s) behind 'alpha' — within acceptable range.`

## Backend Suite Output

```
========================================================
 Backend check suite — 2026-04-26T04:42:56-0400
 alpha: 1cdf1e7e710536abe84cb4f5fa90e872364b89a0
========================================================

PASSED (10):
  ✓ check-process-overlays-intact.sh
  ✓ check-branch-has-commits.sh
  ✓ check-branch-rebased-on-alpha.sh
  ✓ check-no-state-file-commits.sh
  ✓ check-no-source-regressions.sh
  ✓ check-no-test-regressions.sh
  ✓ check-no-direct-logger-usage.sh
  ✓ check-no-coming-soon-stubs.sh
  ✓ check-weak-test-assertions.sh
  ✓ check-di-wiring-updated.sh

FAILED (3):
  ✗ check-no-check-script-deletions.sh
  ✗ check-empty-test-stubs.sh
  ✗ check-domain-aggregate-mocks.sh

RESULT: FAIL — resolve all failing checks before submitting.
```

## Spec Coverage

All spec scenarios are COVERED (unchanged from prior verdict):

| Scenario                              | Status  |
|---------------------------------------|---------|
| Store credentials                     | PASS    |
| Retrieve credentials                  | PASS    |
| Credentials not found                 | PASS    |
| Same path, different tenants          | PASS    |
| Key rotation                          | PASS    |
| Data source deletion                  | PASS    |
| Knowledge graph cascade               | PASS ✓  |

Unit tests: **2405 passed, 0 failed** (post-rebase).
Linting: PASS. Formatting: PASS. Type checking: PASS. Architecture tests: PASS.

## Failing Checks — Actionable Fixes Required

### 1. check-no-check-script-deletions.sh — INHERITED VIOLATION

Two check scripts are missing `--exclude-dir=.venv` on their `grep` calls
(present on alpha, not introduced by this task, but attribution is not an
exemption per verifier rules).

**Fix:** Add `--exclude-dir=.venv` to every `grep` call in these two files:
- `.hyperloop/checks/check-fake-success-notifications.sh`
- `.hyperloop/checks/check-pages-have-tests.sh`

Commit message: `fix(process): add --exclude-dir=.venv to missing check scripts`
Include `Fix-Of: <originating-commit-sha>` in the commit message.

### 2. check-empty-test-stubs.sh — INHERITED VIOLATION

One empty integration test stub exists (present on alpha, not introduced by
this task, but must be fixed):

```
src/api/tests/integration/test_api_key_auth.py:691
  test_create_api_key_requires_tenant_membership
```

The body contains only a docstring with no assertions.

**Fix:** Add a `pytest.skip("reason — see unit test: ...")` call as the first
executable statement, or implement the test body with a real assertion.
Commit message: `fix(iam): fill empty test stub for tenant membership API key check`

### 3. check-domain-aggregate-mocks.sh — PARTIALLY INTRODUCED BY THIS TASK

Three new `MagicMock()` violations were introduced in the new tests added by
this task (pre-existing violations at lines 592-593 must also be fixed):

```
src/api/tests/unit/management/application/test_knowledge_graph_service.py
  657:        ds_with_creds = MagicMock()    ← NEW (this task)
  660:        ds_no_creds = MagicMock()      ← NEW (this task)
  712:        ds_with_creds = MagicMock()    ← NEW (this task)
  592:        ds1 = MagicMock()              ← pre-existing (inherited)
  593:        ds2 = MagicMock()              ← pre-existing (inherited)
```

**Fix:** Replace bare `MagicMock()` for DataSource domain aggregates with
`MagicMock(spec=DataSource)` (minimum) or use a real `_make_ds()` factory
that constructs a real DataSource domain object with `credentials_path`
assigned directly. The existing `_make_kg()` factory in this test file is
the reference pattern.

Example fix for the new tests:
```python
ds_with_creds = MagicMock(spec=DataSource)
ds_with_creds.credentials_path = "datasource/ds-001/credentials"

ds_no_creds = MagicMock(spec=DataSource)
ds_no_creds.credentials_path = None
```

Commit message: `fix(management): replace bare MagicMock with spec'd mocks for DataSource aggregates`

## Summary

All spec scenarios are COVERED and implementation is correct. Three inherited
and one partially-introduced check violation prevent a PASS verdict. No
re-implementation of credentials logic is required — only the hygiene fixes
above.

Spec-Ref: specs/management/credentials.spec.md@774c6c8e
Task-Ref: task-034