---
task_id: audit-specs/ingestion/adapters.spec.md@85d49a379a52479b33f9b39994d76795066899a6
round: 0
role: auditor
verdict: fail
---
## Auditor Verdict — specs/ingestion/adapters.spec.md

Worker: auditor
Date: 2026-04-28

---

## Summary

Most of the spec is faithfully implemented. The adapter port, GitHub adapter,
ICredentialReader shared kernel port, and dlt runner are all present and
well-tested. Two gaps prevent a full pass verdict:

1. **Missing runtime wiring of ICredentialReader in the Ingestion context.**
   The spec requires that "plaintext credentials are retrieved via the
   ICredentialReader shared kernel port" when the adapter runs. No Ingestion
   service, application layer, or orchestration code exists that calls
   `ICredentialReader.retrieve()` before passing credentials to `adapter.extract()`.
   The port is defined and tested in isolation, but the wire-up between the
   credential reader and the adapter invocation is absent.

2. **Missing integration tests for dlt state persistence via the PostgreSQL
   dlt_internal schema.** The spec states "dlt restores state from a dedicated
   dlt_internal database schema." The unit tests (`test_dlt_runner.py`) exercise
   state round-trips using `dlt.destinations.filesystem` and explicitly reference
   a missing test directory (`tests/integration/ingestion/`) for the PostgreSQL
   scenario. That directory does not exist. No integration test verifies that
   dlt writes to and reads from the `dlt_internal` schema in PostgreSQL.

---

## Detailed Findings

### Requirement: Adapter Port — PASS

- `IDatasourceAdapter` Protocol defined at
  `src/api/ingestion/ports/adapters.py` (lines 50–97).
- `extract()` accepts `connection_config`, `credentials`, `checkpoint`, and
  `sync_mode`; returns `ExtractionResult` with changeset entries, content blobs,
  and updated checkpoint.
- Port lives in `ingestion/ports/` and imports zero dlt or adapter framework
  symbols (enforced by architecture tests in
  `src/api/tests/unit/ingestion/test_architecture.py`).
- Unit tests at `src/api/tests/unit/ingestion/ports/test_adapter_port.py` cover
  all protocol scenarios.

### Requirement: GitHub Adapter — PASS

- `GitHubAdapter` at `src/api/ingestion/infrastructure/adapters/github.py`
  satisfies `IDatasourceAdapter` structurally.
- Repository tree extraction: `_get_all_tree_blobs()` calls
  `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` (line 223).
- Content fetching: `_fetch_blob()` calls `GET /repos/{owner}/{repo}/git/blobs/{sha}`
  (line 394); only changed files are fetched.
- Incremental sync: `_get_changed_files()` uses Compare API
  (`/compare/{base}...{head}`, line 271); checkpoint updated with HEAD SHA
  (lines 156–159).
- Full refresh: triggered when `checkpoint=None` or `sync_mode=FULL_REFRESH`
  (lines 115–119).
- Credential handling: token extracted from `credentials["token"]` (line 113)
  and sent as `Authorization: Bearer {token}` (lines 122–126).
- Full unit test coverage in
  `src/api/tests/unit/ingestion/infrastructure/adapters/test_github_adapter.py`.

### Requirement: Pluggable Credential Backend — PARTIAL PASS (interface present; runtime wiring absent)

**What is implemented:**
- `ICredentialReader` Protocol at `src/api/shared_kernel/credential_reader.py`
  with `retrieve(path, tenant_id) -> dict[str, str]` (lines 14–44).
- `FernetSecretStore` at
  `src/api/management/infrastructure/repositories/fernet_secret_store.py`
  structurally satisfies both `ISecretStoreRepository` and `ICredentialReader`
  (confirmed in docstring at line 36 and unit test at
  `src/api/tests/unit/management/infrastructure/test_fernet_secret_store.py:62`).
- Architecture tests prevent Ingestion from importing Management directly
  (`test_ingestion_does_not_import_management` in `test_architecture.py`
  line 177).

**Gap:**
- No Ingestion application layer, service, or sync-trigger code exists that
  calls `credential_reader.retrieve()` and passes the result to `adapter.extract()`.
  The spec scenario "Credential handling" states the Ingestion context SHALL
  retrieve plaintext credentials via the port. Currently callers of
  `adapter.extract()` must supply credentials directly; no Ingestion-owned code
  performs that retrieval. This is a wiring gap, not an interface gap.

### Requirement: dlt Framework Integration — PARTIAL PASS (unit-tested; integration test missing)

**What is implemented:**
- `DltAdapterRunner` at `src/api/ingestion/infrastructure/dlt_runner.py` runs
  dlt in-process as a Python library (no Docker, no subprocess) via
  `loop.run_in_executor` (lines 134–143).
- Checkpoint state is stored and restored through `dlt.current.resource_state()`
  (lines 190–216); references `dlt_internal` schema for PostgreSQL destination
  in docstrings and comments.
- Extracted data written to disk: `_write_output_files()` writes
  `changeset.jsonl` and `blobs/{hex_digest}` files (lines 268–290).
- Unit tests at `src/api/tests/unit/ingestion/infrastructure/test_dlt_runner.py`
  cover in-process execution, state round-trips (filesystem destination), and
  data-on-disk scenarios.

**Gap:**
- The spec scenario "State persistence via database" requires dlt state to land
  in the `dlt_internal` database schema when deployed on Kubernetes (PostgreSQL
  destination). No integration test verifies this. The unit test file explicitly
  defers this to `tests/integration/ingestion/` (line 13), which does not exist.
  The PostgreSQL `dlt_internal` schema persistence path is tested only through
  documentation/comments, not executable tests.

---

## Scenario Coverage

| Requirement | Scenario | Status |
|---|---|---|
| Adapter Port | Extract contract | PASS |
| Adapter Port | Domain isolation | PASS |
| GitHub Adapter | Repository tree extraction | PASS |
| GitHub Adapter | Content fetching | PASS |
| GitHub Adapter | Incremental sync via checkpoint | PASS |
| GitHub Adapter | Full refresh | PASS |
| GitHub Adapter | Credential handling | PASS |
| Pluggable Credential Backend | Port-based credential retrieval (interface) | PASS |
| Pluggable Credential Backend | Port-based credential retrieval (runtime wiring) | FAIL |
| Pluggable Credential Backend | Backend independence | PASS |
| dlt Framework Integration | In-process execution | PASS |
| dlt Framework Integration | State persistence via database (unit/filesystem) | PASS |
| dlt Framework Integration | State persistence via database (integration/PostgreSQL) | FAIL |
| dlt Framework Integration | Extracted data on disk | PASS |

---

## Files Examined

- `src/api/ingestion/ports/adapters.py`
- `src/api/ingestion/infrastructure/adapters/github.py`
- `src/api/ingestion/infrastructure/dlt_runner.py`
- `src/api/ingestion/domain/__init__.py`
- `src/api/ingestion/__init__.py`
- `src/api/shared_kernel/credential_reader.py`
- `src/api/management/ports/secret_store.py`
- `src/api/management/infrastructure/repositories/fernet_secret_store.py`
- `src/api/shared_kernel/job_package/value_objects.py`
- `src/api/tests/unit/ingestion/ports/test_adapter_port.py`
- `src/api/tests/unit/ingestion/infrastructure/adapters/test_github_adapter.py`
- `src/api/tests/unit/ingestion/infrastructure/test_dlt_runner.py`
- `src/api/tests/unit/ingestion/test_architecture.py`
- `src/api/tests/integration/` (no ingestion subdirectory present)