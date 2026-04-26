---
task_id: task-019
round: 8
role: spec-reviewer
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md (round 6)

Branch contamination from orchestrator intake commits persists unchanged from
rounds 4 and 5. All four backend suite failures identified in round 4 remain.
The spec implementation itself is correct and complete. This is a structural
branch history problem requiring orchestrator intervention to cherry-pick
delivery commits onto a clean branch from current alpha.

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

## Backend Suite Results (round 6 — unchanged from rounds 4 and 5)

The backend suite halts at `check-branch-rebased-on-alpha.sh`. Individual
checks were run separately to capture full status:

| Check | Result |
|---|---|
| check-no-check-script-deletions.sh | PASS |
| check-process-overlays-intact.sh | PASS |
| check-branch-has-commits.sh | PASS |
| check-branch-rebased-on-alpha.sh | **FAIL** (now 10 commits behind alpha) |
| check-no-state-file-commits.sh | **FAIL** (38 state files in branch history) |
| check-no-source-regressions.sh | **FAIL** (2 source files deleted) |
| check-no-test-regressions.sh | **FAIL** (3 test files deleted + net line removals) |
| check-empty-test-stubs.sh | PASS |
| check-domain-aggregate-mocks.sh | PASS |
| check-no-direct-logger-usage.sh | PASS |
| check-no-coming-soon-stubs.sh | PASS |
| check-di-wiring-updated.sh | PASS |
| check-pytest-env-skip-if-set.sh | PASS |
| check-cascade-delete-empty-collection-mocks.sh | PASS |
| Unit tests (uv run pytest tests/unit) | PASS (2405 passed) |

Staleness progression: 2 behind (round 4) → 8 behind (round 5) → 10 behind (round 6).
The gap widens each round as alpha receives intake commits while this branch stagnates.

---

## Root Cause: Orchestrator Contamination (Unchanged since round 4)

The offending commit is `13ba0b7a` ("chore(intake): record Run 6 review..."),
which ran on this task branch and accidentally:

- **Added `.hyperloop/state/` files** to branch git history (38 files total).
- **Deleted source files** (exist on alpha, absent on branch):
  - `src/api/management/dependencies/encryption_keys.py`
  - `src/api/management/presentation/auth_bridge.py`
- **Deleted test files** (exist on alpha, absent on branch):
  - `src/api/tests/unit/iam/domain/test_workspace_role_hierarchy.py`
  - `src/api/tests/unit/iam/presentation/test_tenant_routes.py`
  - `src/api/tests/unit/management/presentation/test_knowledge_graph_routes.py`

Subsequent intake/process commits added more state files to the branch, making
an in-place interactive rebase impractical (38 contaminated files across 42 commits).

The 4 task-019 delivery commits remain on the branch and are correct:

| SHA | Description |
|---|---|
| `07dd3715` | test: add tenant isolation unit tests for FernetSecretStore |
| `3ed67df2` | feat(management): cascade credential deletion on KG delete |
| `5e5e4b35` | fix(test): replace bare MagicMock() with real DataSource instances |
| `bd7456b5` | test(iam): add non-empty group cascade test in TestDeleteTenant |

---

## Required Fix (same as rounds 4 and 5)

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
chore commits. The `bef9a6c3` ("chore: record worker pass verdict") and
`1ce502d5` ("fix(management): replace bare MagicMock...") commits were
pre-task-019 fixes and should NOT be cherry-picked unless their content is
already on alpha.

This fix must be performed by the orchestrator or a human operator — it requires
force-pushing to `hyperloop/task-019`, which is beyond the spec reviewer's scope.