---
id: task-001
title: Implement JobPackage ZIP contract
spec_ref: specs/shared-kernel/job-package.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## What

Implement the `JobPackage` class in `shared_kernel/` as the ZIP-based contract between the Ingestion context (producer) and the Extraction context (consumer).

## Spec gaps (all scenarios unimplemented — no code exists)

- `manifest.json` with format_version, data_source_id, knowledge_graph_id, sync_mode, entry_count, content_checksum
- `changeset.jsonl` with add/modify operations (no delete operation — staleness detected downstream)
- `content/` directory with content-addressable files (lowercase hex digest filenames)
- `state.json` adapter checkpoint snapshot (opaque, schema_version required)
- ZIP entry path safety validation (no leading `/`, no `..`, forward-slash separators only)
- Content checksum computation: SHA-256 of sorted canonical byte stream over `content/` regular files
- Deduplication: two changeset entries referencing identical content share one file
- Integrity verification: consumer strips `sha256:` prefix from `content_ref`, reads file, verifies hash
- Package naming: `job-package-{ulid}.zip`
- Streaming-friendly: JSONL one-per-line, ZIP random access (manifest readable without full extraction)

## Location

`src/api/shared_kernel/job_package/` — new module under the shared kernel. Domain layer only (no FastAPI, no DB dependencies).
