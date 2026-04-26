---
task_id: task-019
round: 3
role: spec-reviewer
verdict: fail
---
## Spec Alignment Review — specs/management/credentials.spec.md

### Requirement: Credential Encryption — COVERED

**Scenario: Store credentials**
- Code: `management/infrastructure/repositories/fernet_secret_store.py` — `FernetSecretStore.store()` encrypts via `MultiFernet.encrypt()` and stores via SQLAlchemy merge with composite PK `(path, tenant_id)` in `EncryptedCredentialModel`.
- Test: `tests/unit/management/infrastructure/test_fernet_secret_store.py::TestFernetRoundTrip::test_round_trip_single_key` — ✓

**Scenario: Retrieve credentials**
- Code: `FernetSecretStore.retrieve()` queries by `(path, tenant_id)`, decrypts via `MultiFernet.decrypt()`, returns `dict[str, str]`.
- Test: `TestFernetRoundTrip::test_round_trip_single_key` — ✓

**Scenario: Credentials not found**
- Code: `FernetSecretStore.retrieve()` raises `KeyError("Credentials not found")` when `scalar_one_or_none()` returns `None`.
- Test: `TestRetrieveNotFound::test_raises_key_error` — ✓

---

### Requirement: Tenant Isolation — COVERED

**Scenario: Same path, different tenants**
- Code: `EncryptedCredentialModel` uses composite primary key `(path, tenant_id)`; `FernetSecretStore.retrieve()` filters the query on both columns, ensuring tenant-B cannot access tenant-A's row.
- Test: `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` — exercises the exact spec scenario (path "datasource/abc/credentials", tenant-B gets `KeyError`). ✓

---

### Requirement: Key Rotation — COVERED

**Scenario: Key rotation**
- Code: `FernetSecretStore.__init__` constructs `MultiFernet([Fernet(key) for key in encryption_keys])`. The first key encrypts; all keys are tried for decryption, so credentials encrypted with an old key remain readable after rotation.
- Test: `TestMultiFernetRotation::test_decrypt_with_rotated_keys` — encrypts with `key1`, creates a second store with `[key2, key1]`, asserts the old ciphertext decrypts correctly. ✓

---

### Requirement: Credential Lifecycle — PARTIAL

**Scenario: Data source deletion** — COVERED
- Code: `management/application/services/data_source_service.py` — `DataSourceService.delete()` (lines 384–389) explicitly calls `self._secret_store.delete(path=ds.credentials_path, tenant_id=...)` when `ds.credentials_path` is set, inside the same transaction.
- Test: `tests/unit/management/application/test_data_source_service.py::TestDataSourceServiceDelete::test_delete_removes_credentials_if_path_exists` — asserts `mock_secret_store.delete` is called with the correct path and tenant. ✓

**Scenario: Knowledge graph cascade** — MISSING (FAIL)
- The spec requires: WHEN a knowledge graph is deleted, THEN all data sources AND their credentials are deleted.
- Code: `management/application/services/knowledge_graph_service.py` — `KnowledgeGraphService.delete()` (lines 399–408) calls `ds_repo.delete(ds)` for each data source but does **NOT** call `secret_store.delete()` for any data source's `credentials_path`. The class has no `_secret_store` attribute and no `ISecretStoreRepository` injection.
- Database schema: `encrypted_credentials` has no foreign key referencing `data_sources`, so there is no DB-level cascade.
- Test: `test_delete_cascades_data_sources` asserts only that `ds_repo.delete` is called twice; there is **no assertion** on any secret store mock and no secret store fixture is present. The test uses bare `MagicMock()` for `ds1`/`ds2` (pre-existing issue noted by prior reviewers), which hides any `credentials_path` check.
- **Result:** The encrypted credential records are orphaned when a knowledge graph is deleted. This is a SHALL requirement with neither implementation nor test coverage.

---

## What Is Needed to Pass

To satisfy the **Knowledge graph cascade** scenario:

1. **Implementation:** Inject `ISecretStoreRepository` into `KnowledgeGraphService.__init__` (optional parameter, mirroring the `data_source_repository` pattern). In `KnowledgeGraphService.delete()`, after finding data sources but before calling `ds_repo.delete(ds)`, check `ds.credentials_path` and call `secret_store.delete(path=ds.credentials_path, tenant_id=self._scope_to_tenant)` for each data source that has credentials.

2. **Test:** Add a unit test in `TestKnowledgeGraphServiceDelete` (e.g., `test_delete_cascades_encrypted_credentials`) that:
   - Creates a mock/fake `ISecretStoreRepository`
   - Sets up data sources with `credentials_path` populated
   - Calls `service.delete()`
   - Asserts `secret_store.delete()` is called once per data source with the correct path and tenant

---

## NFR Note (non-blocking for this spec, but noted)

`tests/unit/management/application/test_data_source_service.py` and `test_knowledge_graph_service.py` use `AsyncMock()` for repository and secret store ports rather than in-memory fake implementations. Per `specs/nfr/testing.spec.md` (SHALL: No Mocking Libraries for Domain or Application Logic), proper fake classes should be used. No fake for `ISecretStoreRepository` exists in `tests/fakes/`. This is a pre-existing pattern across the codebase; flagged for awareness but evaluated against `credentials.spec.md` only for this review's verdict.