---
task_id: task-008
round: 0
role: verifier
verdict: fail
---
## Task-008: Knowledge Graphs — Worker Verification

Branch: `hyperloop/task-008`

---

### Check Results

| # | Check | Result |
|---|-------|--------|
| 1 | Unit tests (`pytest tests/unit`) | PASS — 2066 passed, 39 warnings |
| 2 | Linting (`ruff check`) | PASS — zero violations |
| 3 | Formatting (`ruff format --check`) | PASS — 450 files already formatted |
| 4 | Type checking (`mypy`) | PASS — zero errors in 450 source files |
| 5 | Architecture boundary tests | PASS — 40/40 passed |
| 6 | Hyperloop check scripts | CONDITIONAL — see detail below |
| 7 | Diff review | **FAIL — critical regressions detected** |
| 8 | Commit trailers | PASS — Spec-Ref and Task-Ref present |

---

### Findings

#### FAIL: Source File Regressions (highest severity)

The branch deletes production source code that was present on `alpha` and is
**not part of the task-008 scope** (Knowledge Graphs). These files were
previously implemented by earlier tasks and must not be removed:

**Management — data_sources presentation routes deleted:**
- `src/api/management/presentation/data_sources/__init__.py`
- `src/api/management/presentation/data_sources/models.py`
- `src/api/management/presentation/data_sources/routes.py`
- `src/api/management/presentation/__init__.py` — no longer imports or mounts the `data_sources` router

The Data Source REST API endpoints (`/management/workspaces/{ws_id}/data-sources`, etc.)
are completely absent from the running application. Any client that calls these routes
will receive HTTP 404.

**Shared kernel — job_package module deleted:**
- `src/api/shared_kernel/job_package/__init__.py`
- `src/api/shared_kernel/job_package/builder.py`
- `src/api/shared_kernel/job_package/checksum.py`
- `src/api/shared_kernel/job_package/path_safety.py`
- `src/api/shared_kernel/job_package/reader.py`
- `src/api/shared_kernel/job_package/value_objects.py`

**Graph context — secure enclave service deleted:**
- `src/api/graph/application/services/graph_secure_enclave.py`

**Infrastructure — health routes module deleted:**
- `src/api/health_routes.py`

`main.py` does inline the health endpoints, so the health API surface is
preserved. However, `health_routes.py` was a separate, intentionally designed
module with its own tests; its removal alongside deletion of `test_health.py`
reduces coverage and separations of concern.

**Test fake deleted:**
- `src/api/tests/fakes/authorization.py` (InMemoryAuthorizationProvider)

---

#### FAIL: Test Regressions — 281 tests lost from baseline

The branch removes 17 unit test files that were present on `alpha`. Across
those files, approximately **281 individual test functions** are gone. This is
not a net-zero trade — the new `test_knowledge_graph_routes.py` (759 lines)
adds ~35 new tests, but that does not compensate for 281 deleted tests covering
unrelated bounded contexts.

Deleted test files and their alpha test counts:

| File | Tests lost |
|------|-----------|
| `tests/unit/test_health.py` | 16 |
| `tests/unit/test_cors_middleware.py` | 9 |
| `tests/unit/test_application_lifecycle.py` | 8 |
| `tests/unit/iam/domain/test_exceptions.py` | 5 |
| `tests/unit/infrastructure/test_cors_settings.py` | 14 |
| `tests/unit/management/presentation/test_data_sources_routes.py` | 16 |
| `tests/unit/management/presentation/test_knowledge_graphs_routes.py` | 13 (replaced by new file) |
| `tests/unit/graph/application/test_graph_secure_enclave.py` | 26 |
| `tests/unit/graph/infrastructure/test_age_bulk_loading_strategy_partitioning.py` | 18 |
| `tests/unit/graph/infrastructure/test_staging_table_manager.py` | 23 |
| `tests/unit/shared_kernel/authorization/test_in_memory_provider.py` | 30 |
| `tests/unit/shared_kernel/job_package/test_builder.py` | 19 |
| `tests/unit/shared_kernel/job_package/test_checksum.py` | 11 |
| `tests/unit/shared_kernel/job_package/test_path_safety.py` | 16 |
| `tests/unit/shared_kernel/job_package/test_reader.py` | 17 |
| `tests/unit/shared_kernel/job_package/test_value_objects.py` | 36 |
| `tests/unit/shared_kernel/job_package/test_architecture.py` | 4 |
| **Total** | **281** |

Additionally, 13 frontend test files from `src/dev-ui/app/tests/` were deleted.

---

#### FAIL: Hyperloop Check Scripts Deleted

19 check scripts were deleted from `.hyperloop/checks/`. Notably:

- `check-no-source-regressions.sh` — would have detected the above regressions
- `check-no-test-regressions.sh` — would have detected the above test losses
- `check-no-check-script-deletions.sh` — would have prevented this very deletion
- `check-domain-aggregate-mocks.sh`, `check-empty-test-stubs.sh`, etc.

Deleting the guard scripts that would have flagged the regressions is itself
a critical defect.

---

### Root Cause

The branch note states: "Branch reset: 3 consecutive rebase/merge failures. The
branch likely has state files in its commit history that cause permanent
conflicts. Task reset to not-started for a fresh attempt."

The implementer appears to have rebuilt the branch from a base that predates
several previously shipped tasks (data_sources, secure enclave, job_package,
etc.), causing those implementations to vanish from the diff without explicit
deletion commits. The task-008 KG implementation itself is correct and well
tested, but it was built on top of a stripped baseline.

---

### What Needs to Be Fixed

1. **Restore all deleted source files** from `alpha`:
   - `src/api/management/presentation/data_sources/` (3 files)
   - `src/api/management/presentation/__init__.py` — re-add `data_sources` import
   - `src/api/shared_kernel/job_package/` (6 files)
   - `src/api/graph/application/services/graph_secure_enclave.py`
   - `src/api/health_routes.py` (or restore the test coverage if inline is intentional)
   - `src/api/tests/fakes/authorization.py`

2. **Restore all deleted test files** (17 unit test files listed above).

3. **Restore all deleted frontend test files** (13 files in `src/dev-ui/app/tests/`).

4. **Restore all deleted check scripts** (19 scripts in `.hyperloop/checks/`).

5. **Verify** that after restoration the unit test count returns to at least the
   alpha baseline (~2347 unit tests).

Spec-Ref: specs/management/knowledge-graphs.spec.md@85d49a379a52479b33f9b39994d76795066899a6
Task-Ref: task-008