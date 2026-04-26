---
task_id: task-019
round: 7
role: spec-reviewer
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md (round 5)

Branch contamination from orchestrator intake commits persists unchanged from
round 4. All three backend suite failures identified in round 4 remain. The
spec implementation itself is correct and complete.

---

## Spec Requirement Coverage

| Requirement | Status | Code | Test |
|---|---|---|---|
| Credential Encryption — store/retrieve with Fernet | COVERED | `management/infrastructure/repositories/fernet_secret_store.py` | `tests/unit/management/infrastructure/test_fernet_secret_store.py::TestFernetRoundTrip` |
| Credential Encryption — composite key (path, tenant_id) | COVERED | `EncryptedCredentialModel` PK; `retrieve()` WHERE clause | `TestFernetRoundTrip` |
| Credential Encryption — not-found raises KeyError | COVERED | `retrieve()` scalar_one_or_none → KeyError | `TestRetrieveNotFound::test_raises_key_error` |
| Tenant Isolation — same path, different tenants | COVERED | `WHERE path=… AND tenant_id=…` scoping | `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` (07dd3715) |
| Key Rotation — MultiFernet fallback decryption | COVERED | `MultiFernet([Fernet(k) for k in keys])` | `TestMultiFernetRotation::test_decrypt_with_rotated_keys` |
| Key Rotation — new key encrypts, old key decrypts | COVERED | MultiFernet: first key encrypts, all keys tried on decrypt | `TestMultiFernetRotation::test_decrypt_with_rotated_keys` |
| Credential Lifecycle — DS deletion removes credentials | COVERED | `DataSourceService.delete()` calls `secret_store.delete()` | `TestDataSourceServiceDelete::test_delete_removes_credentials_if_path_exists` |
| Credential Lifecycle — KG cascade deletes all DS credentials | COVERED | `KnowledgeGraphService.delete()` iterates DS list, deletes creds | `TestKnowledgeGraphServiceDelete::test_delete_cascades_encrypted_credentials` (3ed67df2) |

All 2405 unit tests pass: `uv run pytest tests/unit` → **2405 passed**.

---

## Backend Suite Results (round 5 — unchanged from round 4)

| Check | Result |
|---|---|
| check-no-check-script-deletions.sh | PASS |
| check-process-overlays-intact.sh | PASS |
| check-branch-has-commits.sh | PASS |
| check-branch-rebased-on-alpha.sh | **FAIL** (now 8 commits behind alpha) |
| check-no-state-file-commits.sh | **FAIL** |
| check-no-source-regressions.sh | **FAIL** |
| check-no-test-regressions.sh | **FAIL** |
| check-empty-test-stubs.sh | PASS |
| check-domain-aggregate-mocks.sh | PASS |
| check-no-direct-logger-usage.sh | PASS |
| check-no-coming-soon-stubs.sh | PASS |
| check-weak-test-assertions.sh | PASS |
| check-di-wiring-updated.sh | PASS |
| check-pytest-env-skip-if-set.sh | PASS |
| check-cascade-delete-empty-collection-mocks.sh | PASS |
| Unit tests (uv run pytest tests/unit) | PASS (2405 passed) |

Note: `check-branch-rebased-on-alpha.sh` has degraded from "2 commits behind"
(round 4) to "8 commits behind" as alpha continues to receive intake commits.

---

## Root Cause: Orchestrator Contamination (Unchanged)

The offending commit is `13ba0b7a` ("chore(intake): record Run 6 review..."),
which ran on this task branch and accidentally:

- **Deleted source files** (exist on alpha, absent on branch):
  - `src/api/management/dependencies/encryption_keys.py`
  - `src/api/management/presentation/auth_bridge.py`
- **Deleted test files** (exist on alpha, absent on branch):
  - `src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py`
  - `src/api/tests/unit/iam/presentation/test_tenant_routes.py`
  - `src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py`
- **Added `.hyperloop/state/` files** to branch git history.

The 4 task-019 delivery commits remain on the branch and are correct:

| SHA | Description |
|---|---|
| `07dd3715` | test: add tenant isolation unit tests for FernetSecretStore |
| `3ed67df2` | feat(management): cascade credential deletion on KG delete |
| `5e5e4b35` | fix(test): replace bare MagicMock() with real DataSource instances |
| `bd7456b5` | test(iam): add non-empty group cascade test in TestDeleteTenant |

---

## Required Fix (same as round 4)

The branch history cannot be cleaned in-place. Cherry-pick the 4 delivery
commits onto a fresh branch from current alpha:

```bash
git fetch origin alpha
git checkout -b hyperloop/task-019-v2 origin/alpha
git cherry-pick 07dd3715 3ed67df2 5e5e4b35 bd7456b5
bash .hyperloop/checks/check-run-backend-suite.sh   # expect all PASS
# write PASS verdict, then:
git push --force-with-lease origin HEAD:hyperloop/task-019
```

Only cherry-pick the 4 SHAs above. Do NOT include any intake, process, or
chore commits.