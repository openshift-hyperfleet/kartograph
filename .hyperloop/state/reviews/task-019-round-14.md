---
task_id: task-019
round: 14
role: verifier
verdict: fail
---
# Verification — specs/management/credentials.spec.md (task-019) — Round 8

## Summary

**FAIL.** Two blocking issues remain on this branch, identical in root cause
to those found in round 7. The spec implementation is substantively correct
and all unit tests pass (2565). The linting gate (ruff F811) and type-checking
gate (mypy no-redef) fail due to a duplicate test function introduced when a
foreign task-032 commit was included on this branch.

---

## Check Results

| Check | Result | Detail |
|---|---|---|
| Unit tests (2565 tests) | PASS | All pass |
| Linting (ruff check) | **FAIL** | F811: duplicate `test_delete_cascades_encrypted_credentials` at line 786 |
| Formatting (ruff format --check) | PASS | 500 files formatted |
| Type checking (mypy) | **FAIL** | no-redef: same duplicate, `test_knowledge_graph_service.py:785` |
| Architecture boundary tests (40 tests) | PASS | All pass |
| check-branch-has-commits | PASS | 7 commits |
| check-branch-rebased-on-alpha | PASS | 1 commit behind, within tolerance |
| check-no-state-file-commits | PASS | |
| check-no-source-regressions | PASS | |
| check-no-test-regressions | PASS | |
| check-no-check-script-deletions | PASS | |
| check-process-overlays-intact | PASS | |
| check-no-foreign-task-commits | **FAIL** | commit `fac1c0eaa8` has Task-Ref: task-032 |
| check-empty-test-stubs | PASS | |
| check-domain-aggregate-mocks | PASS | |
| check-no-direct-logger-usage | PASS | |
| check-no-coming-soon-stubs | PASS | |
| check-di-wiring-updated | PASS | |
| check-pytest-env-skip-if-set | PASS | |
| check-cascade-delete-empty-collection-mocks | PASS | |
| check-cascade-delete-cleanup | PASS | |
| check-no-domain-exception-deletions | PASS | |
| check-no-future-placeholder-comments | PASS | |
| check-no-route-handler-removals | PASS | |
| check-property-merge-semantics | FAIL (pre-existing) | `queries.py:184` on alpha merge-base — not task-019 |
| check-frontend-test-infrastructure | FAIL (pre-existing) | Script bash syntax bug + no dev-ui vitest setup — not task-019 |
| check-frontend-tests-exist | FAIL (pre-existing) | Same pre-existing infra gap |

---

## Finding 1 — Ruff F811 + mypy no-redef: Duplicate Test Function (BLOCKING)

**File:** `src/api/tests/unit/management/application/test_knowledge_graph_service.py`
**Class:** `TestKnowledgeGraphServiceDelete`

Two methods share the name `test_delete_cascades_encrypted_credentials`:

- **Lines 678–738** (task-019 commit `1a52d641b`): uses `service_with_secret_store`
  fixture; tests 3 data sources; uses `assert_any_call()` for 2 paths and verifies
  `call_count == 2`. This is the more complete task-019 test.
- **Lines 785–831** (foreign task-032 commit `fac1c0eaa8`): uses `service` fixture;
  tests 2 data sources; uses `assert_awaited_once_with()`.

Python silently ignores the first definition (line 678); ruff reports F811;
mypy raises `no-redef`.

**Exact fix:** Remove the definition at **lines 785–831** (including the
`@pytest.mark.asyncio` decorator at line 785). The task-019 version at
lines 678–738 covers the spec scenario more completely.

```
# Delete lines 785–831 from test_knowledge_graph_service.py
# (from @pytest.mark.asyncio before the second definition through
#  the last assertion before "# ---- list_all ----")
```

---

## Finding 2 — Foreign Task Commit Present (BLOCKING)

Commit `fac1c0eaa8` (`feat(iam): enforce last-admin protection in group member
management (#476)`, Task-Ref: task-032) is in the branch history ahead of alpha.
`check-no-foreign-task-commits.sh` reports FAIL.

This commit is the root cause of Finding 1: it introduced an initial
`test_delete_cascades_encrypted_credentials` method (at line 701 at that point),
and it also introduced fixtures/factories (`mock_secret_store`,
`service_with_secret_store`, `_make_ds`) that the task-019 commits then reused.

**Why the dependency matters:** Simply dropping commit `fac1c0eaa8` would
break the task-019 tests because they rely on:
- `mock_secret_store()` fixture (line 64 of the file in that commit's state)
- `service_with_secret_store` fixture (lines 101–111)
- `_make_ds()` factory function (line 141)

**Recommended fix:**

Option A — Minimal (fixes linting/mypy immediately, foreign-commit check still fails):
1. Remove lines 785–831 (the duplicate test definition).
2. Run `ruff check` and `mypy` to confirm they pass.
3. Commit as `fix(test): remove duplicate test_delete_cascades_encrypted_credentials`.

This still leaves `fac1c0eaa8` on the branch, so `check-no-foreign-task-commits.sh`
continues to FAIL. Option B fully resolves both findings.

Option B — Full clean (fixes both findings):
1. Extract the three fixtures/factories that task-019 needs from `fac1c0eaa8`
   into the task-019 test infrastructure commit (`3294c8e52` or a new fixup commit).
2. Rebase interactively to drop `fac1c0eaa8`:
   ```bash
   git rebase -i be25b37a3eadebea9aeec6277ef2b49f40217a6b
   # Mark fac1c0eaa80ec4e978efd9953b83b725d644cc20 as 'drop'
   # Resolve conflicts by adding the extracted fixtures/factories
   ```
3. After the rebase, the duplicate test disappears naturally (only the
   task-019 version remains), and the foreign-task check passes.
4. Run unit tests, ruff, and mypy to confirm all pass.

---

## Missing Task-Ref Trailer (Non-blocking, but should be fixed)

Commit `fa157f980a` ("test: add tenant isolation unit tests for FernetSecretStore")
lacks a `Task-Ref: task-019` trailer. `check-no-foreign-task-commits.sh` reports
this as INFO only (not FAIL), but the trailer should be present for traceability.

**Fix:** Amend the commit to add `Task-Ref: task-019` as a git trailer.

---

## Pre-Existing Issues (Not introduced by task-019)

These checks fail on the alpha merge-base and are therefore not regressions:

1. **check-property-merge-semantics.sh**: `src/api/graph/infrastructure/age_bulk_loading/queries.py:184`
   — `SET properties =` without `||` merge operator. Confirmed pre-existing at
   commit `be25b37a3` (alpha merge-base).

2. **check-frontend-test-infrastructure.sh** / **check-frontend-tests-exist.sh**:
   These fail due to a bash syntax bug in the check script (line 32: `[[: 0`) combined
   with the absence of vitest setup in `src/dev-ui`. Both conditions exist on alpha.

---

## Spec Requirement Coverage (All Covered — Implementation is Correct)

| Requirement | Status | Location |
|---|---|---|
| Credential Encryption — Fernet store/retrieve | COVERED | `fernet_secret_store.py` + `test_fernet_secret_store.py` |
| Composite key (path, tenant_id) | COVERED | `EncryptedCredentialModel` PK; `WHERE path=… AND tenant_id=…` |
| Not-found raises KeyError | COVERED | `scalar_one_or_none → KeyError`; `TestRetrieveNotFound` |
| Tenant Isolation — same path, different tenant | COVERED | `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` |
| Key Rotation — MultiFernet fallback | COVERED | `MultiFernet([Fernet(k) for k in keys])`; `TestMultiFernetRotation` |
| Credential Lifecycle — DS deletion removes credentials | COVERED | `DataSourceService.delete()` → `secret_store.delete()` |
| Credential Lifecycle — KG cascade deletes all DS credentials | COVERED | `KnowledgeGraphService.delete()` iterates DS list; `test_delete_cascades_encrypted_credentials` (line 678) |

The implementation is correct and complete. Once the duplicate test at lines
785–831 is removed (and optionally the foreign commit dropped), this branch
should pass all checks.

---

## Required Action

1. Remove lines 785–831 from `test_knowledge_graph_service.py` (duplicate test).
2. Commit the removal as a fixup.
3. Re-run: `uv run ruff check .` and `uv run mypy . --config-file pyproject.toml`.
4. Optionally resolve the foreign-commit issue via Option B above.
5. Re-trigger verification.

Task-Ref: task-019