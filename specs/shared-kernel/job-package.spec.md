# JobPackage

## Purpose
A JobPackage is the shared contract between the Ingestion context (producer) and the Extraction context (consumer). It is a ZIP archive containing a manifest, a changeset of items to process, raw content files, and an adapter checkpoint snapshot. The format is designed to be portable across process boundaries — today in-process, eventually cross-service.

## Requirements

### Requirement: Package Structure
The system SHALL produce JobPackages as ZIP archives with a defined internal structure.

#### Scenario: Package contents
- GIVEN a completed ingestion run
- WHEN a JobPackage is assembled
- THEN the ZIP archive contains exactly four components:
  - `manifest.json` — package metadata
  - `changeset.jsonl` — one entry per changed item
  - `content/` — raw content files, content-addressable using the `sha256:{hex_digest}` filename format
  - `state.json` — adapter checkpoint snapshot

#### Scenario: Package naming
- GIVEN a JobPackage is produced
- THEN the archive is named `job-package-{ulid}.zip`

### Requirement: Manifest
The system SHALL include a manifest with package metadata.

#### Scenario: Manifest fields
- GIVEN a manifest.json
- THEN it contains:
  - `format_version` — semver string (e.g., `"1.0.0"`)
  - `data_source_id` — which data source produced this package
  - `knowledge_graph_id` — which knowledge graph this data feeds
  - `sync_mode` — `"incremental"` or `"full_refresh"`
  - `entry_count` — number of entries in changeset.jsonl
  - `content_checksum` — integrity checksum for the content directory (see Content Checksum Computation below)

#### Scenario: Content checksum computation
- GIVEN the `content/` directory of a JobPackage
- THEN `content_checksum` is the hex-encoded SHA-256 of a canonical byte stream constructed as follows:
  - Walk the `content/` directory recursively; for symlinks, resolve to the target and include it only if the target is within the `content/` root (skip out-of-tree symlinks) and has not already been visited (cycle detection via tracked visited paths)
  - Include all regular files; exclude directories
  - Normalize each file path to POSIX format with no leading `./`, using UTF-8 encoding
  - Sort entries lexicographically by normalized path
  - For each file in sorted order, append to the stream: the normalized path, a newline (`\n`), then the file's raw bytes
- AND file metadata (timestamps, permissions) is excluded from the stream
- AND ephemeral files (e.g., `.git`, temp files) are excluded from the stream
- AND the same `content/` directory always produces the same checksum regardless of filesystem ordering or OS

### Requirement: Changeset Format
The system SHALL express changes as JSONL with one entry per changed item.

#### Scenario: Add operation
- GIVEN a newly discovered item in the data source
- THEN a changeset entry is written with operation `"add"`
- AND it includes: `id`, `type`, `path`, `content_ref`, `content_type`, and `metadata`

#### Scenario: Modify operation
- GIVEN an item that has changed since the last sync
- THEN a changeset entry is written with operation `"modify"`
- AND it includes the same fields as `add`

#### Scenario: Rename represented as modify
- GIVEN an item that has been renamed in the data source
- THEN a `modify` entry is written with `previous_path` in the `metadata` field
- AND no separate rename operation exists

#### Scenario: No delete operation
- GIVEN an item that has been removed from the data source
- THEN no changeset entry is produced
- AND staleness is detected downstream by comparing per-node `last_synced_at` against the data source's `last_sync_at`

#### Scenario: Entry type
- GIVEN a changeset entry
- THEN the `type` field uses reverse-DNS notation (e.g., `io.kartograph.change.file`, `io.kartograph.change.issue`)
- AND the type indicates what kind of source item was changed

#### Scenario: Content reference
- GIVEN a changeset entry with content
- THEN `content_ref` references a file in the `content/` directory
- AND the format is `sha256:{lowercase_hex_digest}`

### Requirement: Content-Addressable Storage
The system SHALL store raw content files using the canonical `sha256:{hex_digest}` format as the filename.

#### Scenario: Content file naming
- GIVEN raw content to include in the package
- WHEN it is written to the `content/` directory
- THEN the filename is `sha256:{lowercase_hex_digest}` (identical to the `content_ref` format)

#### Scenario: Deduplication
- GIVEN two changeset entries referencing identical content
- THEN only one copy is stored in `content/`
- AND both entries reference the same `content_ref`

#### Scenario: Integrity verification
- GIVEN a consumer reading content from the package
- THEN the consumer strips the `sha256:` prefix from the filename and verifies it matches the SHA-256 hash of the file's raw bytes
- AND a mismatch indicates corruption

### Requirement: Adapter Checkpoint
The system SHALL include an adapter checkpoint snapshot for auditability.

#### Scenario: Checkpoint structure
- GIVEN a state.json in the package
- THEN it MUST contain a `schema_version` field (e.g., `"1.0.0"`)
- AND the remaining content is opaque — owned by the adapter that produced it

#### Scenario: Opaque ownership
- GIVEN a state.json
- THEN no component other than the producing adapter inspects or modifies its content
- AND the orchestration layer stores and passes it back on the next invocation

#### Scenario: Snapshot vs authoritative state
- GIVEN a state.json in the ZIP
- THEN it is a debugging/audit snapshot only
- AND the authoritative checkpoint state lives in the database

#### Scenario: Schema version mismatch
- GIVEN a state.json with a `schema_version` the adapter does not recognize
- WHEN the adapter receives it on a subsequent run
- THEN the adapter can detect the version mismatch and handle it (e.g., fall back to full refresh)

### Requirement: Streaming-Friendly Design
The system SHALL support streaming creation and consumption of JobPackages.

#### Scenario: JSONL streaming
- GIVEN a changeset.jsonl
- THEN entries are newline-delimited JSON (one per line)
- AND consumers can process entries without loading the entire file into memory

#### Scenario: ZIP random access
- GIVEN a consumer that only needs the manifest
- THEN it can read manifest.json without extracting the entire archive
