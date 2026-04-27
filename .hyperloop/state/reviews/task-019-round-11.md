---
task_id: task-019
round: 11
role: verifier
verdict: fail
---
## Worker Result — task-019 (specs/management/credentials.spec.md)

Worker: verifier
Date: 2026-04-27
Round: 7

---

### Check Results

| Check | Result | Notes |
|---|---|---|
| Unit tests (2467) | **PASS** | `uv run pytest tests/unit` — 2467 passed, 45 warnings |
| Ruff lint | **PASS** | Zero violations |
| Ruff format | **PASS** | 495 files already formatted |
| mypy type check | **PASS** | Zero errors, 495 source files |
| Architecture tests | **PASS** | 40/40 passed |
| check-no-check-script-deletions.sh | **PASS** |  |
| check-process-overlays-intact.sh | **PASS** |  |
| check-branch-has-commits.sh | **PASS** | 6 commits ahead of alpha |
| check-branch-rebased-on-alpha.sh | **PASS** | 3 commits behind — within acceptable range |
| check-no-state-file-commits.sh | **PASS** | No state files in branch commits |
| check-no-source-regressions.sh | **PASS** |  |
| check-no-route-handler-removals.sh | **PASS** |  |
| check-no-test-regressions.sh | **PASS** |  |
| check-empty-test-stubs.sh | **PASS** |  |
| check-domain-aggregate-mocks.sh | **PASS** |  |
| check-no-direct-logger-usage.sh | **PASS** |  |
| check-no-coming-soon-stubs.sh | **PASS** |  |
| check-weak-test-assertions.sh | **PASS** |  |
| check-di-wiring-updated.sh | **PASS** |  |
| check-event-handlers-registered.sh | **PASS** |  |
| check-domain-events-have-consumers.sh | **PASS** |  |
| check-pytest-env-skip-if-set.sh | **PASS** |  |
| check-cascade-delete-cleanup.sh | **PASS** | `knowledge_graph_service.py` contains `_secret_store.delete` |
| check-new-checks-pass-on-head.sh | MISSING | Does NOT exist on alpha — infrastructure gap, not a regression |
| check-no-foreign-task-commits.sh | MISSING | Does NOT exist on alpha — infrastructure gap, not a regression |
| check-cascade-delete-empty-collection-mocks.sh | MISSING | Does NOT exist on alpha — infrastructure gap, not a regression |

---

### Commit Trailers (delivery commits)

| SHA | Spec-Ref | Task-Ref |
|---|---|---|
| `1d284c27` test: add tenant isolation unit tests for FernetSecretStore | ✓ | ✓ |
| `c63b9661` feat(management): cascade credential deletion when knowledge graph is deleted | ✓ | ✓ |
| `1ea5de54` test(iam): add non-empty group cascade test in TestDeleteTenant | ✓ | ✓ |
| `1edbf819` feat(management): implement cascade credential deletion in KnowledgeGraphService | ✓ | ✓ |

---

### Spec Requirement Coverage

| Requirement | Implementation | Test | Status |
|---|---|---|---|
| Credential Encryption — Fernet encrypt/decrypt | `fernet_secret_store.py` | `TestFernetRoundTrip` | ✓ |
| Credential Encryption — composite key (path, tenant_id) | `EncryptedCredentialModel` PK | `TestFernetRoundTrip` | ✓ |
| Credential Encryption — not-found raises KeyError | `retrieve()` scalar_one_or_none | `TestRetrieveNotFound` | ✓ |
| Tenant Isolation — same path, different tenants | `WHERE path=... AND tenant_id=...` | `TestTenantIsolation::test_same_path_different_tenant_raises_key_error` | ✓ |
| Key Rotation — MultiFernet fallback decryption | `MultiFernet([Fernet(k) for k in keys])` | `TestMultiFernetRotation` | ✓ |
| Credential Lifecycle — DS deletion removes credentials | `DataSourceService.delete()` calls `secret_store.delete()` | `TestDataSourceServiceDelete::test_delete_removes_credentials_if_path_exists` | ✓ |
| **Credential Lifecycle — KG cascade deletes all DS credentials** | `KnowledgeGraphService.delete()` calls `_secret_store.delete()` when `credentials_path` set | **NO DEDICATED TEST** | **✗ FAIL** |

---

### Finding: Missing Test — KG Cascade Credential Deletion

**Severity: FAIL**

The spec scenario "Knowledge graph cascade" requires:
> GIVEN a knowledge graph with data sources that have credentials
> WHEN the knowledge graph is deleted
> THEN all data sources and their credentials are deleted

The production code in `management/application/services/knowledge_graph_service.py` (commit `1edbf819`) does contain the correct implementation:

```python
if self._secret_store is not None and ds.credentials_path:
    await self._secret_store.delete(
        path=ds.credentials_path,
        tenant_id=self._scope_to_tenant,
    )
```

However, the `service_with_secret_store` fixture (added in `c63b9661`) is **defined but never used** in any test. The spec coverage table from prior rounds cited `TestKnowledgeGraphServiceDelete::test_delete_cascades_encrypted_credentials` as covering this scenario, but **that test does not exist** in the current branch.

The `test_delete_cascades_data_sources` test (updated in `1edbf819`) exercises the general cascade but:
1. Uses `service` (without secret_store injected)
2. Creates DataSources with `credentials_path=None` (the default)

So the credential deletion code path (`if self._secret_store is not None and ds.credentials_path`) is never exercised by any unit test.

**Fix required:**
Add the following test to `TestKnowledgeGraphServiceDelete` in
`src/api/tests/unit/management/application/test_knowledge_graph_service.py`:

```python
@pytest.mark.asyncio
async def test_delete_cascades_encrypted_credentials(
    self,
    service_with_secret_store,
    mock_authz,
    mock_kg_repo,
    mock_ds_repo,
    mock_secret_store,
    user_id,
    tenant_id,
):
    """delete() calls secret_store.delete() for each DS that has a credentials_path.

    Scenario (spec: credentials.spec.md — Knowledge graph cascade):
        GIVEN a knowledge graph with data sources that have credentials
        WHEN the knowledge graph is deleted
        THEN all data sources and their credentials are deleted
    """
    kg = _make_kg(tenant_id=tenant_id)
    # ds1 has credentials; ds2 does not
    ds1 = _make_ds(
        ds_id="ds-001",
        kg_id=kg.id.value,
        tenant_id=tenant_id,
        credentials_path="datasource/ds-001/credentials",
    )
    ds2 = _make_ds(ds_id="ds-002", kg_id=kg.id.value, tenant_id=tenant_id)

    mock_authz.check_permission.return_value = True
    mock_kg_repo.get_by_id.return_value = kg
    mock_ds_repo.find_by_knowledge_graph.return_value = [ds1, ds2]
    mock_ds_repo.delete.return_value = True
    mock_kg_repo.delete.return_value = True

    await service_with_secret_store.delete(user_id=user_id, kg_id=kg.id.value)

    # Only ds1 has credentials_path — secret_store.delete called once
    mock_secret_store.delete.assert_called_once_with(
        path="datasource/ds-001/credentials",
        tenant_id=tenant_id,
    )
```

---

### Summary

7 of 8 spec requirements are fully implemented and covered by non-fragile tests.
The 8th requirement (KG cascade credential deletion) is correctly implemented in
production code but the unit test verifying the behavior was never written.
The `service_with_secret_store` fixture was scaffolded in anticipation of the test
but left unused. Add the test above and the task will be ready for PASS.

**VERDICT: FAIL — add `test_delete_cascades_encrypted_credentials` to close the coverage gap.**