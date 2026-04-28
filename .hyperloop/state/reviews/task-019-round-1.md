---
task_id: task-019
round: 1
role: verifier
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md (round 8)

The spec implementation itself is correct and complete. All unit tests pass
(2489 passed). The structural branch contamination problem persists: two
process-improvement commits remain on the task-019 branch and cause 3 backend
suite failures.

---

## Check Results

| # | Check | Result |
|---|---|---|
| 1 | Unit tests (`uv run pytest tests/unit -v`) | **PASS** — 2489 passed |
| 2 | Linting (`ruff check .`) | **PASS** — 0 violations |
| 3 | Formatting (`ruff format --check .`) | **PASS** — 498 files formatted |
| 4 | Type checking (`mypy . --ignore-missing-imports`) | **PASS** — 0 errors |
| 5 | Architecture boundary tests | **PASS** (included in unit tests) |
| 6 | check-no-check-script-deletions.sh | **PASS** |
| 7 | check-process-overlays-intact.sh | **PASS** |
| 8 | check-process-overlay-content-intact.sh | **FAIL** (see below) |
| 9 | check-new-checks-pass-on-head.sh | **FAIL** (see below) |
| 10 | check-all-commits-have-task-ref.sh | **PASS** |
| 11 | check-alpha-local-vs-remote.sh | **PASS** |
| 12 | check-no-foreign-task-commits.sh | **FAIL** (see below) |
| 13 | check-branch-rebased-on-alpha.sh | **PASS** |
| 14 | check-no-state-file-commits.sh | **PASS** |
| 15 | check-worker-result-not-committed.sh | **PASS** |
| 16 | check-no-source-regressions.sh | **PASS** |
| 17 | check-no-test-regressions.sh | **PASS** |
| 18 | All other backend checks (23 total) | **PASS** |

---

## Spec Requirement Coverage

All spec requirements are implemented and tested correctly:

| Requirement | Code | Test |
|---|---|---|
| Credential Encryption — store/retrieve with Fernet | `management/infrastructure/repositories/fernet_secret_store.py` | `TestFernetRoundTrip` |
| Credential Encryption — composite key (path, tenant_id) | `EncryptedCredentialModel` PK; `retrieve()` WHERE clause | `TestFernetRoundTrip` |
| Credential Encryption — not-found raises KeyError | `retrieve()` → KeyError | `TestRetrieveNotFound` |
| Tenant Isolation — same path, different tenants | WHERE scoping | `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` + `test_retrieve_with_correct_tenant_succeeds` |
| Key Rotation — MultiFernet fallback | `MultiFernet([Fernet(k) for k in keys])` | `TestMultiFernetRotation` |
| Credential Lifecycle — DS deletion | `DataSourceService.delete()` calls `secret_store.delete()` | `TestDataSourceServiceDelete` |
| Credential Lifecycle — KG cascade | `KnowledgeGraphService.delete()` iterates DS list | `TestKnowledgeGraphServiceDelete` |

---

## Failing Checks — Root Cause

### FAIL 1: check-no-foreign-task-commits.sh

Two commits on the branch carry `Task-Ref: process-improvement` instead of
`Task-Ref: task-019`:

```
a8254502a  chore(process): guard against overlay content regressions...  (Task-Ref: process-improvement)
57a21efa8  chore(process): enforce branch hygiene...                      (Task-Ref: process-improvement)
```

These are orchestrator process-improvement commits that do not belong on the
task-019 delivery branch.

### FAIL 2: check-process-overlay-content-intact.sh

Commit `57a21efa8` modified `.hyperloop/agents/process/verifier-overlay.yaml`
by replacing the line:

```
- Run check-no-test-regressions.sh before any PASS verdict.
```

with three expanded lines. The check detects the original line as "removed"
(even though content was added net-positive) and fails. This regression was
introduced by the foreign process-improvement commit.

### FAIL 3: check-new-checks-pass-on-head.sh

This check fails because the two new checks introduced by the branch
(`check-no-foreign-task-commits.sh` and `check-process-overlay-content-intact.sh`)
themselves fail on HEAD — a logical consequence of failures 1 and 2 above.

---

## Required Fix

The branch currently has exactly 2 task-019 delivery commits:

| SHA | Description |
|---|---|
| `bc9830de3` | chore(checks): restore check-alpha-local-vs-remote.sh |
| `88f6e88fa` | test(management): add positive tenant isolation test for FernetSecretStore |

Cherry-pick ONLY these 2 commits onto a clean branch from current alpha:

```bash
git fetch origin alpha
git checkout -b hyperloop/task-019-v2 origin/alpha
git cherry-pick bc9830de3 88f6e88fa
bash .hyperloop/checks/check-run-backend-suite.sh   # expect all PASS
# write PASS verdict, then:
git push --force-with-lease origin HEAD:hyperloop/task-019
```

Do NOT include the process-improvement commits (`a8254502a`, `57a21efa8`).
Those commits need to land on alpha via a separate process-improvement cycle,
not via the task-019 delivery branch.

Note: `bc9830de3` (restore check-alpha-local-vs-remote.sh) carries
`Task-Ref: task-019` and is a legitimate prerequisite fix for the backend suite
to complete successfully — it should be included.