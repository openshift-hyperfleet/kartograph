---
id: task-003
title: "Shared Kernel — JobPackage ZIP contract"
spec_ref: specs/shared-kernel/job-package.spec.md
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
---

## Summary

The `JobPackage` is the shared contract between the Ingestion context (producer) and the Extraction context (consumer). It does not yet exist in the codebase. This task implements the `shared_kernel/job_package/` module that both contexts will import.

## Scope

Create `src/api/shared_kernel/job_package/`:

- `__init__.py` — re-exports public API
- `models.py` — dataclasses / Pydantic models for `Manifest`, `ChangesetEntry`, `JobPackageState`
- `builder.py` — `JobPackageBuilder`: streams entries and content into a ZIP archive
- `reader.py` — `JobPackageReader`: reads manifest, iterates changeset, reads content by ref
- `checksum.py` — content checksum computation (canonical walk, SHA-256)
- `path_safety.py` — ZIP entry path validation (no `..`, no leading `/`, forward-slash only)

### Manifest (`manifest.json`)

Fields:
- `format_version` (semver, e.g. `"1.0.0"`)
- `data_source_id` (ULID string)
- `knowledge_graph_id` (ULID string)
- `sync_mode` (`"incremental"` | `"full_refresh"`)
- `entry_count` (int)
- `content_checksum` (hex SHA-256)

### Changeset (`changeset.jsonl`)

One JSON object per line. Operations: `"add"` | `"modify"`. Fields:
- `id`, `type` (reverse-DNS, e.g. `io.kartograph.change.file`), `path`
- `content_ref` (`sha256:{lowercase_hex}`)
- `content_type` (MIME string)
- `metadata` (arbitrary dict; renames use `previous_path` here)

No `delete` operation — staleness detected downstream via `last_synced_at`.

### Content directory (`content/`)

- Files named by lowercase hex digest only (no `sha256:` prefix)
- Deduplication: one file per unique content, referenced by multiple changeset entries
- Consumer verifies integrity: strip `sha256:` prefix → read file → SHA-256 → compare

### Adapter checkpoint (`state.json`)

- Must contain `schema_version` field
- Remaining content is opaque (owned by producing adapter)
- Authoritative state lives in the DB; this is an audit snapshot only

### Package naming

Archive is named `job-package-{ulid}.zip`.

### Key invariants

- Path safety: reject (raise) any entry with `..` segments, leading `/`, drive letters, or backslashes — both on write and read
- Content checksum: deterministic canonical walk (sorted POSIX paths, regular files matching `[0-9a-f]+` only, symlink resolution with cycle detection)
- Streaming-friendly: changeset entries can be iterated without loading entire file into memory
- ZIP random access: manifest readable without full extraction

## TDD Notes

Write unit tests first under `tests/unit/shared_kernel/test_job_package.py`:

- Round-trip test: build a package, read it back, verify manifest fields, changeset entries, content integrity
- Path safety: assert `..` entries are rejected
- Content deduplication: two entries with identical bytes → one content file
- Checksum determinism: same content in different filesystem order → same checksum
- Reader rejects malformed archives (missing manifest, unsafe paths)
