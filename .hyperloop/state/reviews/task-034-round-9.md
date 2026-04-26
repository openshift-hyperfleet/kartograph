---
task_id: task-034
round: 9
role: spec-reviewer
verdict: fail
---
# Spec Alignment Review: Credentials

## Summary

The implementation is comprehensive and well-structured for most scenarios. One
scenario — **Knowledge graph cascade credential deletion** — has both an
implementation gap and a missing test. `KnowledgeGraphService.delete` cascades
to delete data source DB rows but does NOT invoke the secret store to delete the
associated encrypted credentials. All other scenarios are fully covered with
both implementation and tests.

---

## Requirement: Credential Encryption

### Scenario: Store credentials — COVERED

Implementation:
- `src/api/management/infrastructure/repositories/fernet_secret_store.py:53-70`
  `FernetSecretStore.store()` serializes credentials to JSON, encrypts with
  `MultiFernet`, and upserts via `session.merge()`.
- `src/api/management/infrastructure/models/encrypted_credential.py:15-35`
  `EncryptedCredentialModel` uses a composite primary key of `(path, tenant_id)`.
- `src/api/infrastructure/migrations/versions/d5e6f7a8b9c0_create_encrypted_credentials_table.py`
  Migration creates the table with `(path, tenant_id)` composite PK.

Tests:
- Unit: `src/api/tests/unit/management/infrastructure/test_fernet_secret_store.py:65-121`
  `TestFernetRoundTrip` covers single key, multiple credentials, and empty values.
- Integration: `src/api/tests/integration/management/test_fernet_secret_store.py:54-73`
  `TestRoundTrip::test_store_and_retrieve` exercises against real PostgreSQL.

### Scenario: Retrieve credentials — COVERED

Implementation:
- `src/api/management/infrastructure/repositories/fernet_secret_store.py:72-93`
  `FernetSecretStore.retrieve()` queries by `(path, tenant_id)`, decrypts, returns dict.

Tests:
- Unit: Same `TestFernetRoundTrip` round-trip tests verify retrieval returns original dict.
- Integration: `src/api/tests/integration/management/test_fernet_secret_store.py:54-73`

### Scenario: Credentials not found — COVERED

Implementation:
- `src/api/management/infrastructure/repositories/fernet_secret_store.py:85-89`
  Raises `KeyError("Credentials not found")` when query returns None.

Tests:
- Unit: `src/api/tests/unit/management/infrastructure/test_fernet_secret_store.py:148-160`
  `TestRetrieveNotFound::test_raises_key_error`
- Integration: `src/api/tests/integration/management/test_fernet_secret_store.py:143-154`
  `TestNotFound::test_nonexistent_path_raises_key_error`

---

## Requirement: Tenant Isolation

### Scenario: Same path, different tenants — COVERED

Implementation:
- `src/api/management/infrastructure/repositories/fernet_secret_store.py:80-83`
  `retrieve()` WHERE clause filters on both `path` AND `tenant_id`.
- `src/api/management/infrastructure/models/encrypted_credential.py:25-26`
  Composite PK `(path, tenant_id)` enforces DB-level isolation.

Tests:
- Unit: `src/api/tests/unit/management/infrastructure/test_fernet_secret_store.py:293-356`
  `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` covers the
  exact Given/When/Then (tenant A stores at a path, tenant B retrieval raises
  `KeyError`). Also covers `test_delete_with_wrong_tenant_does_not_delete`.
- Integration: `src/api/tests/integration/management/test_fernet_secret_store.py:123-140`
  `TestTenantIsolation::test_tenant_a_cannot_read_tenant_b` exercises against live DB.

---

## Requirement: Key Rotation

### Scenario: Key rotation — COVERED (unit only; no integration test)

Implementation:
- `src/api/management/infrastructure/repositories/fernet_secret_store.py:50`
  `MultiFernet([Fernet(key) for key in encryption_keys])` — first key encrypts,
  all keys tried for decryption.
- `src/api/management/infrastructure/repositories/fernet_secret_store.py:60`
  `self._multi_fernet.encrypt(plaintext)` uses the first (primary) key.
- `src/api/management/infrastructure/repositories/fernet_secret_store.py:91`
  `self._multi_fernet.decrypt(...)` tries all keys in order.

Tests:
- Unit: `src/api/tests/unit/management/infrastructure/test_fernet_secret_store.py:123-145`
  `TestMultiFernetRotation::test_decrypt_with_rotated_keys` encrypts with `key1`,
  then creates a new store with `[key2, key1]` and verifies the old ciphertext
  decrypts. Covers the full Given/When/Then.
- Integration: NONE — no integration test for key rotation exists.

Note: The unit test fully satisfies the spec scenario. The missing integration
test is a minor gap but does not drive the fail verdict.

---

## Requirement: Credential Lifecycle

### Scenario: Data source deletion — COVERED

Implementation:
- `src/api/management/application/services/data_source_service.py:384-392`
  `DataSourceService.delete()` checks `ds.credentials_path` and calls
  `self._secret_store.delete(path=ds.credentials_path, tenant_id=...)` before
  deleting the data source record.

Tests:
- Unit: `src/api/tests/unit/management/application/test_data_source_service.py:627-641`
  `test_delete_removes_credentials_if_path_exists` — asserts `mock_secret_store.delete`
  is called with the correct path and tenant when a DS with credentials is deleted.

### Scenario: Knowledge graph cascade — FAIL

Implementation gap:
- `src/api/management/application/services/knowledge_graph_service.py:399-408`
  `KnowledgeGraphService.delete()` cascades by calling `self._ds_repo.delete(ds)`
  for each child data source. It does NOT call `self._secret_store.delete(...)`.
  `KnowledgeGraphService` has no `secret_store` constructor parameter at all.
- Result: when a KG is deleted, data source DB rows are removed but the encrypted
  credential blobs in `encrypted_credentials` remain as orphaned rows.

Test gap:
- Unit: `src/api/tests/unit/management/application/test_knowledge_graph_service.py:587-607`
  `test_delete_cascades_data_sources` verifies `ds.mark_for_deletion()` and
  `mock_ds_repo.delete` are called per data source, but the test has no
  `mock_secret_store` fixture and makes no assertion about credential deletion.
- Integration: No integration test verifies that encrypted credentials are removed
  when a KG (and its data sources) is cascade-deleted.

What is needed:
1. Add `secret_store: ISecretStoreRepository | None = None` to
   `KnowledgeGraphService.__init__`.
2. In `KnowledgeGraphService.delete`, for each data source where
   `ds.credentials_path` is set, call
   `await self._secret_store.delete(path=ds.credentials_path, tenant_id=...)`
   before `await self._ds_repo.delete(ds)`.
3. Add a unit test asserting `mock_secret_store.delete` is called for each DS
   with credentials when a KG is cascade-deleted.
4. Optionally add an integration test that stores credentials for a DS under a
   KG, deletes the KG, and asserts the `encrypted_credentials` table is empty.

---

## Files Reviewed

- `src/api/shared_kernel/credential_reader.py` — ICredentialReader protocol
- `src/api/management/ports/secret_store.py` — ISecretStoreRepository protocol
- `src/api/management/infrastructure/repositories/fernet_secret_store.py` — implementation
- `src/api/management/infrastructure/models/encrypted_credential.py` — ORM model
- `src/api/management/infrastructure/observability/secret_store_probe.py` — domain probe
- `src/api/infrastructure/migrations/versions/d5e6f7a8b9c0_create_encrypted_credentials_table.py`
- `src/api/management/application/services/data_source_service.py`
- `src/api/management/application/services/knowledge_graph_service.py` — MISSING credential cleanup
- `src/api/management/infrastructure/repositories/data_source_repository.py`
- `src/api/tests/unit/shared_kernel/test_credential_reader.py`
- `src/api/tests/unit/management/infrastructure/test_fernet_secret_store.py`
- `src/api/tests/integration/management/test_fernet_secret_store.py`
- `src/api/tests/unit/management/application/test_data_source_service.py`
- `src/api/tests/unit/management/application/test_knowledge_graph_service.py`
- `src/api/tests/integration/management/test_data_source_repository.py`
- `src/api/tests/integration/management/conftest.py`