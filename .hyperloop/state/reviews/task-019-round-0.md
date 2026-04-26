---
task_id: task-019
round: 0
role: verifier
verdict: fail
---
## Verification Summary

Independent review of task-019 (credentials spec). The previous worker-result
claimed PASS, but this review finds one blocking gap.

---

## Check Results

### 1. Unit Tests — PASS
2407 passed, 0 failed, 0 errors.

### 2. Linting (ruff check) — PASS
Zero violations.

### 3. Formatting (ruff format --check) — PASS
All 479 files already formatted.

### 4. Type Checking (mypy) — PASS
Zero errors across 479 source files.

### 5. Architecture Boundary Tests — PASS
All 40 pytest-archon tests passed.

### 6. Commit Trailers — PASS
Both task commits carry Spec-Ref and Task-Ref trailers:
- `bd0bc80d` — Spec-Ref: credentials.spec.md, Task-Ref: task-019
- `4dc2d710` — Spec-Ref: credentials.spec.md, Task-Ref: task-019

### 7. Check Scripts — PARTIAL (pre-existing failures only, except one gap)
Pre-existing failures (present in alpha, not introduced by this task):
- `check-no-direct-logger-usage.sh`: `print()` in `query/presentation/mcp.py:197` (file not touched by task)
- `check-empty-test-stubs.sh`: empty stub in `tests/integration/test_api_key_auth.py:691` (file not touched)
- `check-domain-aggregate-mocks.sh`: `ds1 = MagicMock()` / `ds2 = MagicMock()` in
  `test_delete_cascades_data_sources` (pre-existed in alpha at lines 592–593; task correctly
  used `_make_ds()` in all new tests — missed opportunity to fix the pre-existing line in
  the same file but not a new violation)
- `check-no-check-script-deletions.sh`: 5 scripts lack `--exclude-dir=.venv` (pre-existing)

### 8. Code Review — FAIL (blocking)

**Critical: DI wiring not updated — spec scenario not fulfilled in production**

The task added `secret_store: ISecretStoreRepository | None = None` to
`KnowledgeGraphService.__init__()` and guarded the cleanup with
`if self._secret_store is not None`. The unit tests directly inject a mock
`secret_store` and pass. However, the FastAPI dependency factory that creates
`KnowledgeGraphService` for live requests was **not updated**:

```python
# src/api/management/dependencies/knowledge_graph.py  (unchanged by this task)
return KnowledgeGraphService(
    session=session,
    knowledge_graph_repository=kg_repo,
    data_source_repository=ds_repo,
    authz=authz,
    scope_to_tenant=current_user.tenant_id.value,
    probe=DefaultKnowledgeGraphServiceProbe(),
    # secret_store is NOT passed → defaults to None
)
```

Compare with `data_source.py`, which correctly wires `FernetSecretStore`:

```python
secret_store = FernetSecretStore(session=session, encryption_keys=encryption_keys)
return DataSourceService(..., secret_store=secret_store, ...)
```

**Impact:** The spec requirement "Scenario: Knowledge graph cascade" is satisfied
only in unit tests. In production, deleting a KnowledgeGraph via the API will
cascade-delete DataSource rows but will silently skip credential deletion because
`self._secret_store is None`. Orphaned encrypted credentials remain in the database.

**Fix required** in `src/api/management/dependencies/knowledge_graph.py`:
1. Import `FernetSecretStore` and `get_management_settings` (same pattern as
   `data_source.py`).
2. Instantiate `FernetSecretStore(session=session, encryption_keys=encryption_keys)`.
3. Pass it as `secret_store=secret_store` when constructing `KnowledgeGraphService`.

No other changes are needed; the service logic and tests are correct.