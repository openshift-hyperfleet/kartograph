---
id: task-012
title: Implement Ingestion context — GitHub adapter and dlt framework integration
spec_ref: specs/ingestion/adapters.spec.md
status: not-started
phase: null
deps: [task-001, task-009]
round: 0
branch: null
pr: null
---

## What

Implement the Ingestion bounded context with:
1. The `IDatasourceAdapter` port (domain layer, no framework imports).
2. The GitHub adapter using dlt (Extract phase only) for incremental and full-refresh sync.
3. The `JobPackager` that assembles a `JobPackage` ZIP from extracted dlt output.

## Spec requirements (context does not exist — build from scratch)

**Adapter Port:**
- `IDatasourceAdapter` in `ingestion/domain/` — implements `extract(credentials, checkpoint_state)` returning `(raw_data, updated_checkpoint)`.
- Domain layer must NOT import dlt or any adapter framework.

**GitHub Adapter:**
- Fetch repository tree via GitHub Trees API.
- Identify files added/modified since last sync.
- Fetch raw file content via GitHub API (changed files only).
- Incremental sync via checkpoint (e.g., last commit SHA).
- Full refresh when no checkpoint or `sync_mode=full_refresh`.
- Retrieve credentials via `ICredentialReader` shared kernel port (not by importing Management directly).

**dlt Framework Integration:**
- Execute dlt in-process as a Python library (no Docker, no subprocess).
- Persist dlt checkpoint state in `dlt_internal` database schema.
- Extracted data available as files in pipeline working directory.

**JobPackager:**
- Assembles `JobPackage` (task-001) from dlt output files.
- Produces `changeset.jsonl` entries for add/modify operations.
- Stores content-addressable files in `content/`.
- Writes `state.json` checkpoint snapshot.
- Writes `manifest.json` with all required fields.
- Names output `job-package-{ulid}.zip`.

## Location

New `src/api/ingestion/` bounded context:
- `ingestion/domain/` — `IDatasourceAdapter` port, value objects
- `ingestion/ports/` — `IJobPackager` port
- `ingestion/application/services/` — `IngestionService`
- `ingestion/infrastructure/adapters/github_adapter.py` — GitHub + dlt implementation
- `ingestion/infrastructure/packager.py` — `JobPackager` implementation

## Notes

- Depends on task-001 (JobPackage contract) and task-009 (DataSource REST API provides the data source configs the adapter reads).
- Use `ICredentialReader` from `shared_kernel/credential_reader.py` — do not import `management/`.
