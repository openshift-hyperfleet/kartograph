---
task_id: task-019
round: 12
role: spec-reviewer
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md (round 8)

All spec requirements remain fully implemented and tested (2468 unit tests pass).
Backend suite fails on one check: `check-worker-result-not-committed.sh`.
Root cause: the round 7 verifier committed `.hyperloop/worker-result.yaml` in
commit `0dc8cec4`, which now lives in branch history. The check detects this
and returns exit 1.

---

## Backend Suite Results

| Check | Result |
|---|---|
| check-no-check-script-deletions.sh | PASS |
| check-process-overlays-intact.sh | PASS |
| check-new-checks-pass-on-head.sh | PASS |
| check-branch-has-commits.sh | PASS |
| check-branch-rebased-on-alpha.sh | PASS (3 behind — within tolerance) |
| check-no-state-file-commits.sh | PASS |
| check-worker-result-not-committed.sh | **FAIL** |
| check-no-foreign-task-commits.sh | PASS |
| check-no-source-regressions.sh | PASS |
| check-no-route-handler-removals.sh | PASS |
| check-no-test-regressions.sh | PASS |
| check-empty-test-stubs.sh | PASS |
| check-domain-aggregate-mocks.sh | PASS |
| check-no-direct-logger-usage.sh | PASS |
| check-no-coming-soon-stubs.sh | PASS |
| check-weak-test-assertions.sh | PASS |
| check-di-wiring-updated.sh | PASS |
| check-event-handlers-registered.sh | PASS |
| check-domain-events-have-consumers.sh | PASS |
| check-pytest-env-skip-if-set.sh | PASS |
| check-cascade-delete-cleanup.sh | PASS |
| check-cascade-delete-empty-collection-mocks.sh | PASS |
| check-unused-fixtures.sh | PASS |
| check-no-future-placeholder-comments.sh | PASS |
| Unit tests (2468 passed, 0 failed) | PASS |

BACKEND SUITE: **FAIL — 23/24 checks passed, 1 failed**.

---

## Spec Requirement Coverage

| Requirement | Status | Code | Test |
|---|---|---|---|
| Credential Encryption — store with Fernet symmetric encryption | COVERED | `FernetSecretStore.store()` using `MultiFernet.encrypt()` | `TestFernetRoundTrip::test_round_trip_single_key` |
| Credential Encryption — composite key (path, tenant_id) | COVERED | `EncryptedCredentialModel` WHERE `path=… AND tenant_id=…` | `TestFernetRoundTrip` (path+tenant_id passed throughout) |
| Credential Encryption — retrieve decrypts to original dict | COVERED | `FernetSecretStore.retrieve()` → `MultiFernet.decrypt()` → `json.loads()` | `TestFernetRoundTrip::test_round_trip_single_key` |
| Credential Encryption — not-found raises KeyError | COVERED | `scalar_one_or_none() is None` → `raise KeyError` | `TestRetrieveNotFound::test_raises_key_error` |
| Tenant Isolation — same path, different tenant raises | COVERED | WHERE clause scopes by `tenant_id`; no cross-tenant leakage | `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` |
| Key Rotation — MultiFernet fallback decryption | COVERED | `MultiFernet([Fernet(k) for k in keys])` — first key encrypts, all tried on decrypt | `TestMultiFernetRotation::test_decrypt_with_rotated_keys` |
| Credential Lifecycle — DS deletion removes credentials | COVERED | `DataSourceService.delete()` calls `secret_store.delete(path, tenant_id)` | `TestDataSourceServiceDelete::test_delete_removes_credentials_if_path_exists` |
| Credential Lifecycle — KG cascade deletes all DS credentials | COVERED | `KnowledgeGraphService.delete()` iterates DS list, calls `secret_store.delete()` per DS | `TestKnowledgeGraphServiceDelete::test_delete_cascades_encrypted_credentials` |

All 8 spec scenarios: **COVERED**.

---

## Root Cause of Backend Suite Failure

The `check-worker-result-not-committed.sh` check detects that
`.hyperloop/worker-result.yaml` was committed on this branch. The offending
commit is:

```
0dc8cec4  chore: record verifier pass verdict for task-019 (round 7)
```

This commit is a round 7 verifier verdict that committed the worker-result file
directly to the task branch. The check was introduced to prevent exactly this
pattern (it was added in response to a similar contamination on task-035).

Note: this spec reviewer is also required by its protocol to commit
worker-result.yaml. The contradiction between "workers must commit this file"
and "this file must not appear in commits" is a protocol-level conflict that
requires orchestrator resolution.

---

## Required Fix

Drop commit `0dc8cec4` from the branch history. The 8 delivery commits that
constitute the actual task work are:

| SHA | Description |
|---|---|
| `8d770a37` | test: add tenant isolation unit tests for FernetSecretStore |
| `2aa843ff` | feat(management): cascade credential deletion when knowledge graph is deleted |
| `34d8e79f` | test(iam): add non-empty group cascade test in TestDeleteTenant |
| `61022a0c` | feat(management): implement cascade credential deletion in KnowledgeGraphService |
| `e9e57007` | test(management): add KG cascade credential deletion test |
| `2eeec531` | chore(process): add missing check scripts referenced by backend suite |
| `a0bca3c3` | fix(test): add missing mock_secret_store fixture and _make_ds factory |

The verifier commit `0dc8cec4` must be dropped (or the worker-result.yaml file
stripped from it via amend). After that, the backend suite should be 24/24 PASS.

Procedure:
```bash
git rebase -i alpha   # drop 0dc8cec4 in the editor
bash .hyperloop/checks/check-run-backend-suite.sh   # expect all 24 PASS
git push --force-with-lease origin HEAD:hyperloop/task-019
```