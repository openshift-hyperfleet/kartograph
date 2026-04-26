---
task_id: task-034
round: 5
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — task-034 (Credentials Spec)

Date: 2026-04-26

---

## Spec Coverage

All requirements and scenarios in `specs/management/credentials.spec.md` are covered.

### Requirement: Credential Encryption

**Scenario: Store credentials** — COVERED
- Implementation: `src/api/management/infrastructure/repositories/fernet_secret_store.py:53-70` (`FernetSecretStore.store`)
  - Encrypts credentials via `MultiFernet.encrypt` before persisting via `session.merge`
  - Stores with composite primary key `(path, tenant_id)` (`EncryptedCredentialModel.__tablename__` = `encrypted_credentials`, PK = `path` + `tenant_id`)
- Unit test: `src/api/tests/unit/management/infrastructure/test_fernet_secret_store.py::TestFernetRoundTrip::test_round_trip_single_key` (PASS)
- Integration test: `src/api/tests/integration/management/test_fernet_secret_store.py::TestRoundTrip::test_store_and_retrieve` (integration)

**Scenario: Retrieve credentials** — COVERED
- Implementation: `fernet_secret_store.py:72-93` (`FernetSecretStore.retrieve`) — decrypts and returns `dict[str, str]`
- Unit test: `TestFernetRoundTrip::test_round_trip_single_key`, `test_round_trip_multiple_credentials`, `test_round_trip_empty_values` (PASS)
- Integration test: `TestRoundTrip::test_store_and_retrieve`

**Scenario: Credentials not found** — COVERED
- Implementation: `fernet_secret_store.py:87-89` — raises `KeyError("Credentials not found")` when no row returned
- Unit test: `TestRetrieveNotFound::test_raises_key_error` (PASS)
- Integration test: `TestNotFound::test_nonexistent_path_raises_key_error`

### Requirement: Tenant Isolation

**Scenario: Same path, different tenants** — COVERED
- Implementation: `EncryptedCredentialModel` uses composite PK `(path, tenant_id)` (`encrypted_credential.py:25-26`) — DB-level isolation
- Implementation: `FernetSecretStore.retrieve` WHERE clause at `fernet_secret_store.py:80-83` includes both `path` and `tenant_id`
- Unit test: `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` (PASS)
- Integration test: `TestTenantIsolation::test_tenant_a_cannot_read_tenant_b`

### Requirement: Key Rotation

**Scenario: Key rotation** — COVERED
- Implementation: `fernet_secret_store.py:50` — `MultiFernet([Fernet(key) for key in encryption_keys])` — first key encrypts new credentials, all keys tried for decryption
- Unit test: `TestMultiFernetRotation::test_decrypt_with_rotated_keys` — encrypts with key1, decrypts with [key2, key1] (PASS)

### Requirement: Credential Lifecycle

**Scenario: Data source deletion** — COVERED
- Implementation: `data_source_service.py:384-392` — `delete()` calls `secret_store.delete(path=ds.credentials_path, tenant_id=...)` before deleting the DS record
- Unit test: `TestDataSourceServiceDelete::test_delete_removes_credentials_if_path_exists` (PASS)

**Scenario: Knowledge graph cascade** — COVERED
- Implementation: `knowledge_graph_service.py:404-415` — `delete()` iterates all data sources for the KG, deletes credentials (if `credentials_path` set) then deletes each DS before deleting the KG
- Unit test: `TestKnowledgeGraphServiceDeleteCredentialCascade::test_delete_cascades_credentials_for_ds_with_credentials_path` (PASS)
- Unit test: `TestKnowledgeGraphServiceDeleteCredentialCascade::test_delete_cascades_credentials_for_multiple_data_sources` (PASS)
- Unit test: `TestKnowledgeGraphServiceDeleteCredentialCascade::test_delete_does_not_call_secret_store_when_no_credentials` (PASS)

### Supporting Infrastructure

- `ICredentialReader` port: `src/api/shared_kernel/credential_reader.py` — `@runtime_checkable Protocol` with `retrieve(path, tenant_id) -> dict[str, str]`; raises `KeyError` on not found
- `ISecretStoreRepository` port: `src/api/management/ports/secret_store.py` — `store`, `retrieve`, `delete`
- `FernetSecretStore` implements both protocols (confirmed by `TestProtocolConformance` tests)
- Unit test: `src/api/tests/unit/shared_kernel/test_credential_reader.py` — 8 tests covering protocol shape, runtime checkability, and behavior contract (all PASS)

---

## Test Run

89 unit tests across all credential-related files: **89 passed, 0 failed**

```
cd src/api && uv run pytest tests/unit/management/infrastructure/test_fernet_secret_store.py \
  tests/unit/shared_kernel/test_credential_reader.py \
  tests/unit/management/application/test_data_source_service.py \
  tests/unit/management/application/test_knowledge_graph_service.py -v
# Result: 89 passed in 1.47s
```

---

## Process Gate Failures

The spec implementation is complete and correct. However, two process gates block a PASS verdict:

### 1. check-branch-rebased-on-alpha — FAIL (PRIMARY BLOCKER)

Branch is **24 commits behind alpha** (merge-base: `ce482a01`). Alpha has moved forward with process overlays and new check scripts.

Fix:
```
git fetch origin && git rebase origin/alpha
```

### 2. check-no-check-script-deletions — FAIL

Three check scripts are missing `--exclude-dir=.venv` (present on alpha but not on this branch due to the stale branch):
- `.hyperloop/checks/check-auth-status-codes.sh`
- `.hyperloop/checks/check-fake-success-notifications.sh`
- `.hyperloop/checks/check-pages-have-tests.sh`

This will be resolved by the rebase in item 1.

---

## Verdict Rationale

The credentials spec is **fully implemented and all unit tests pass**. Every scenario from `specs/management/credentials.spec.md` is covered by both implementation and tests. No spec misalignments found.

Verdict is **FAIL** solely due to the stale branch condition (24 commits behind alpha). After rebasing onto alpha:
1. Re-run `bash .hyperloop/checks/check-branch-rebased-on-alpha.sh` — must pass
2. Re-run `bash .hyperloop/checks/check-no-check-script-deletions.sh` — must pass
3. Re-run unit tests to confirm no rebase conflicts: `make test-unit`