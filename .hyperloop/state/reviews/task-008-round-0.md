---
task_id: task-008
round: 0
role: verifier
verdict: fail
---
## Implementation Verification — task-008 (Knowledge Graphs, Management Context)

Branch: `hyperloop/task-008`
Spec: `specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6`

### Check Results

| Check | Result | Detail |
|---|---|---|
| Unit Tests | PASS | 2056 passed, 0 failed |
| Ruff Linting | PASS | `All checks passed!` |
| Ruff Formatting | PASS | `448 files already formatted` |
| Mypy Type Checking | PASS | `Success: no issues found in 448 source files` |
| Architecture Boundary Tests | PASS | 16 passed |
| Hyperloop Checks | PASS | All stub/placeholder failures are in `.venv` (third-party libs) or unrelated `dev-ui` code — not in task-008 implementation |
| Commit Trailers | PASS | Spec-Ref and Task-Ref present on all substantive commits |
| No logger/print usage | PASS | No direct logger/print calls found |
| MagicMock for domain collaborators | **FAIL** | See below |

---

### Finding: MagicMock Used for DataSource Domain Aggregates

**File:** `tests/unit/management/application/test_knowledge_graph_service.py`

**Guideline violated:** "No MagicMock/AsyncMock for domain/application collaborators (use fakes)"

Three test methods construct `DataSource` domain aggregates using `MagicMock()` instead of real domain objects:

- `test_delete_cascades_data_sources` — lines 605–606: `ds1 = MagicMock()`, `ds2 = MagicMock()`
- `test_delete_rolls_back_on_ds_deletion_failure` — lines 653, 655: same
- `test_delete_cascades_encrypted_credentials` — lines 687, 689: `ds_with_creds = MagicMock()`, `ds_no_creds = MagicMock()`

**Established pattern:** `tests/unit/management/application/test_data_source_service.py` defines a `_make_ds()` factory (lines 128–150) that returns real `DataSource` domain objects. The same tests that exercise cascading data source operations use `_make_ds()` — not mocks.

**Required fix:** Add a `_make_ds()` helper to `test_knowledge_graph_service.py` mirroring the one in `test_data_source_service.py`, then replace all six `MagicMock()` instances above with real `DataSource` objects. Use attribute assignment (e.g. `ds.credentials_path = "..."`) on real objects where the test needs to control field values.

The `MagicMock` for `session` (line 34) and `mock_probe` (line 71) are acceptable because those are infrastructure/observability collaborators, not domain objects.