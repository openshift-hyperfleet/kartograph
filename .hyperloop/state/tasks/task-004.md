---
id: task-004
title: "Ingestion — Adapter port and GitHub adapter"
spec_ref: specs/ingestion/adapters.spec.md
status: not-started
phase: null
deps: [task-003]
round: 0
branch: null
pr: null
---

## Summary

The Ingestion bounded context does not yet exist in the codebase. This task creates the context skeleton with its domain adapter port and the first concrete adapter: GitHub. The context uses `dlt` (data load tool) for its Extract phase only.

This task depends on `task-003` (JobPackage) because the adapter's output is packaged into a `JobPackage` by the `JobPackager` service in this same task.

## Scope

Create `src/api/ingestion/` with full DDD layering:

```
ingestion/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── ports.py          # IDatasourceAdapter Protocol
│   └── value_objects.py  # SyncMode, AdapterType, ExtractResult
├── ports/
│   ├── __init__.py
│   └── protocols.py      # IJobPackager, IIngestionService
├── application/
│   ├── __init__.py
│   ├── services.py       # IngestionService: orchestrates extract → package → publish
│   └── observability/
│       ├── __init__.py
│       ├── ingestion_probe.py        # Protocol
│       └── default_ingestion_probe.py # structlog impl
├── infrastructure/
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── github/
│   │       ├── __init__.py
│   │       └── adapter.py   # GithubAdapter implementing IDatasourceAdapter
│   └── job_packager.py      # Assembles JobPackage from dlt output
└── dependencies/
    ├── __init__.py
    └── ingestion.py         # FastAPI dependency injection
```

### `IDatasourceAdapter` port (domain layer)

```python
class IDatasourceAdapter(Protocol):
    def extract(
        self,
        credentials: dict[str, str],
        checkpoint: dict | None,
        sync_mode: SyncMode,
    ) -> ExtractResult: ...
```

`ExtractResult` contains: raw files on disk path, updated checkpoint dict.

The domain layer MUST NOT import `dlt` or any adapter framework.

### GitHub Adapter

- Uses dlt for extraction (in-process, no Docker/subprocess)
- State persistence: dlt `dlt_internal` database schema (Postgres)
- Fetches repository tree via GitHub Trees API
- Incremental: changes since last checkpoint (commit SHA); full refresh if no checkpoint
- Content: only changed files fetched, not entire repo
- Credentials: received as plaintext dict via `ICredentialReader` port (already in shared_kernel)
- Adapter does NOT import the Management context directly

### JobPackager

Reads dlt output files and assembles a `JobPackage` (from task-003):
- Writes changeset entries (one per changed file, operation `"add"` or `"modify"`)
- Writes content files (content-addressable by SHA-256)
- Writes manifest and state.json
- Returns archive path

### IngestionService (application layer)

Orchestrates:
1. Resolve credentials via `ICredentialReader`
2. Run adapter → `ExtractResult`
3. Run `JobPackager` → `JobPackage` archive
4. Publish `JobPackageProduced` outbox event

On failure: publish `IngestionFailed` event.

## TDD Notes

Write unit tests first under `tests/unit/ingestion/`:
- `test_github_adapter.py`: mock GitHub API responses; test incremental vs full_refresh; test checkpoint update
- `test_job_packager.py`: given mock dlt output directory, assert package structure, deduplication, checksum

Write integration tests under `tests/integration/ingestion/test_ingestion_service.py` using fake adapter and real outbox.
