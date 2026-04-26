---
task_id: task-019
round: 4
role: verifier
verdict: fail
---
## Verification Summary — specs/management/credentials.spec.md

### Check Results

| Check | Result | Detail |
|-------|--------|--------|
| 1. Unit Tests | PASS | 2404 passed, 0 failures |
| 2. Linting (ruff check) | PASS | All checks passed |
| 3. Formatting (ruff format --check) | PASS | 479 files already formatted |
| 4. Type Checking (mypy) | PASS | No issues found in 479 source files |
| 5. Architecture Boundary Tests | PASS | 40 passed |
| 6. check-domain-aggregate-mocks.sh | FAIL | See below |
| 7. Code Review | FAIL | Same as #6 |

---

## Failing Check: Domain Aggregate Mocks

`check-domain-aggregate-mocks.sh` fails. The newly added test
`TestKnowledgeGraphServiceDelete::test_delete_cascades_encrypted_credentials`
(lines 654–694 of `tests/unit/management/application/test_knowledge_graph_service.py`)
introduces bare `MagicMock()` for domain aggregate `DataSource`:

```
667:        ds1 = MagicMock()
669:        ds2 = MagicMock()
671:        ds3 = MagicMock()
```

Per project guidelines (specs/nfr/testing.spec.md) and `AGENTS.md`, domain aggregates
must **not** be mocked with bare `MagicMock()`/`AsyncMock()` because it hides interface
regressions and bypasses domain validation logic.

Note: Lines 620–621 in `test_delete_cascades_data_sources` are a **pre-existing**
violation (present on `alpha` before this task). The check was already failing on those
lines. This task added **three additional violations** in the new test.

---

## Required Fix (Narrow)

In `test_delete_cascades_encrypted_credentials`, replace bare `MagicMock()` with
spec'd mocks or a `_make_ds()` factory. The simplest acceptable fix:

```python
from management.domain.models.data_source import DataSource  # adjust import

# Option A — spec'd mock (acceptable when test only needs the interface)
ds1 = MagicMock(spec=DataSource)
ds1.credentials_path = "datasource/ds-001/credentials"
ds2 = MagicMock(spec=DataSource)
ds2.credentials_path = "datasource/ds-002/credentials"
ds3 = MagicMock(spec=DataSource)
ds3.credentials_path = None
```

Or, preferred per the process-overlay rules added in commit `d0aa5cdc`:

```python
# Option B — create a _make_ds() factory parallel to the existing _make_kg()
def _make_ds(ds_id="ds-001", credentials_path=None, tenant_id="tenant-123"):
    # Use the real DataSource constructor
    ...

ds1 = _make_ds(ds_id="ds-001", credentials_path="datasource/ds-001/credentials")
ds2 = _make_ds(ds_id="ds-002", credentials_path="datasource/ds-002/credentials")
ds3 = _make_ds(ds_id="ds-003", credentials_path=None)
```

The same fix should be applied to the pre-existing violations at lines 620–621 in
`test_delete_cascades_data_sources`, but that is a pre-existing issue and **not** the
cause of this task's FAIL verdict. Address lines 667–671 at minimum.

---

## Spec Coverage (Unaffected by the Fix)

The implementation logic is correct and complete. All spec scenarios are covered:

- **Credential Encryption**: `FernetSecretStore.store/retrieve` — PASS
- **Tenant Isolation**: Composite PK `(path, tenant_id)` — PASS
- **Key Rotation**: `MultiFernet` with fallback keys — PASS
- **Credential Lifecycle / data source deletion**: `DataSourceService.delete()` — PASS
- **Credential Lifecycle / knowledge graph cascade**: `KnowledgeGraphService.delete()`
  now calls `secret_store.delete()` for each DS with a `credentials_path` — PASS
  (implementation correct; only the test mock style is the issue)

Commit trailers are present on both key implementation commits:
- `54647a2c` (feat) — Spec-Ref + Task-Ref ✓
- `dd7fa79b` (test) — Spec-Ref + Task-Ref ✓