"""Unit tests for JobPackageBuilder (TDD - tests first).

Spec: specs/shared-kernel/job-package.spec.md
Requirement: Package Structure, Changeset Format, Content-Addressable Storage
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    SyncMode,
)


def _make_entry(
    operation: ChangeOperation = ChangeOperation.ADD,
    content: bytes = b"file content",
    item_id: str = "item-1",
    path: str = "src/file.py",
) -> tuple[ChangesetEntry, ContentRef]:
    ref = ContentRef.from_bytes(content)
    entry = ChangesetEntry(
        operation=operation,
        id=item_id,
        type="io.kartograph.change.file",
        path=path,
        content_ref=ref,
        content_type="text/x-python",
        metadata={},
    )
    return entry, ref


class TestJobPackageBuilderPackageStructure:
    """Tests that the built ZIP has the correct structure.

    Scenario: Package contents
    - GIVEN a completed ingestion run
    - WHEN a JobPackage is assembled
    - THEN the ZIP archive contains exactly four top-level entries:
      manifest.json, changeset.jsonl, content/, state.json
    """

    def test_built_zip_contains_manifest(self, tmp_path: Path):
        """Built archive must contain manifest.json."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            assert "manifest.json" in zf.namelist()

    def test_built_zip_contains_changeset(self, tmp_path: Path):
        """Built archive must contain changeset.jsonl."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            assert "changeset.jsonl" in zf.namelist()

    def test_built_zip_contains_state(self, tmp_path: Path):
        """Built archive must contain state.json."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            assert "state.json" in zf.namelist()

    def test_built_zip_contains_content_files(self, tmp_path: Path):
        """Content files appear under content/ in the archive."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"hello world"
        ref = builder.add_content(content)
        entry, _ = _make_entry(content=content)
        # Replace entry's content_ref with the one from builder
        entry = ChangesetEntry(
            operation=entry.operation,
            id=entry.id,
            type=entry.type,
            path=entry.path,
            content_ref=ref,
            content_type=entry.content_type,
            metadata=entry.metadata,
        )
        builder.add_changeset_entry(entry)
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
            content_entries = [n for n in names if n.startswith("content/")]
            assert len(content_entries) >= 1
            expected_file = f"content/{ref.filename}"
            assert expected_file in names


class TestJobPackageBuilderNaming:
    """Tests for archive naming convention.

    Scenario: Package naming
    - THEN the archive is named `job-package-{ulid}.zip`
    """

    def test_archive_name_follows_convention(self, tmp_path: Path):
        """Archive filename matches job-package-{ULID}.zip."""
        import re

        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        assert re.match(r"^job-package-[0-9A-Z]{26}\.zip$", archive_path.name), (
            f"Archive name {archive_path.name!r} does not match expected pattern"
        )

    def test_archive_is_a_zip_file(self, tmp_path: Path):
        """The built archive is a valid ZIP file."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        assert zipfile.is_zipfile(archive_path)


class TestJobPackageBuilderManifest:
    """Tests that the manifest is correctly written.

    Scenario: Manifest fields
    """

    def test_manifest_contains_required_fields(self, tmp_path: Path):
        """manifest.json contains all required fields."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.FULL_REFRESH,
        )
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            manifest_bytes = zf.read("manifest.json")
            manifest = json.loads(manifest_bytes)

        assert "format_version" in manifest
        assert "data_source_id" in manifest
        assert "knowledge_graph_id" in manifest
        assert "sync_mode" in manifest
        assert "entry_count" in manifest
        assert "content_checksum" in manifest

    def test_manifest_data_source_id(self, tmp_path: Path):
        """manifest.json reflects the correct data_source_id."""
        builder = JobPackageBuilder(
            data_source_id="my-source-42",
            knowledge_graph_id="kg-07",
            sync_mode=SyncMode.INCREMENTAL,
        )
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            manifest = json.loads(zf.read("manifest.json"))

        assert manifest["data_source_id"] == "my-source-42"
        assert manifest["knowledge_graph_id"] == "kg-07"
        assert manifest["sync_mode"] == "incremental"

    def test_manifest_entry_count_matches_changeset(self, tmp_path: Path):
        """entry_count equals the number of changeset entries."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )

        content = b"file A"
        ref = builder.add_content(content)
        for i in range(3):
            entry = ChangesetEntry(
                operation=ChangeOperation.ADD,
                id=f"item-{i}",
                type="io.kartograph.change.file",
                path=f"src/file{i}.py",
                content_ref=ref,
                content_type="text/x-python",
                metadata={},
            )
            builder.add_changeset_entry(entry)

        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            manifest = json.loads(zf.read("manifest.json"))

        assert manifest["entry_count"] == 3


class TestJobPackageBuilderContentAddressable:
    """Tests for content-addressable storage.

    Scenario: Content file naming
    Scenario: Deduplication
    """

    def test_content_file_named_by_hex_digest_only(self, tmp_path: Path):
        """Content filename is the lowercase hex digest with no prefix."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"important content"
        ref = builder.add_content(content)
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="item-1",
            type="io.kartograph.change.file",
            path="src/important.py",
            content_ref=ref,
            content_type="text/x-python",
            metadata={},
        )
        builder.add_changeset_entry(entry)
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()

        # filename must be ONLY the hex digest, no "sha256:" prefix
        assert f"content/{ref.hex_digest}" in names
        assert f"content/sha256:{ref.hex_digest}" not in names

    def test_identical_content_stored_once(self, tmp_path: Path):
        """Two entries with identical content share one content file.

        Scenario: Deduplication
        """
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"duplicated content"
        ref1 = builder.add_content(content)
        ref2 = builder.add_content(content)

        # Both refs must be identical
        assert ref1 == ref2

        for i in range(2):
            entry = ChangesetEntry(
                operation=ChangeOperation.ADD,
                id=f"item-{i}",
                type="io.kartograph.change.file",
                path=f"src/dup{i}.py",
                content_ref=ref1,
                content_type="text/x-python",
                metadata={},
            )
            builder.add_changeset_entry(entry)

        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            content_files = [n for n in zf.namelist() if n.startswith("content/")]

        # Only one content file even though two entries reference it
        assert len(content_files) == 1

    def test_content_ref_in_changeset_uses_sha256_prefix(self, tmp_path: Path):
        """changeset.jsonl entries reference content with sha256:{hex} format."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"my source file"
        ref = builder.add_content(content)
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="item-1",
            type="io.kartograph.change.file",
            path="src/main.py",
            content_ref=ref,
            content_type="text/x-python",
            metadata={},
        )
        builder.add_changeset_entry(entry)
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            lines = zf.read("changeset.jsonl").decode("utf-8").strip().split("\n")

        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["content_ref"].startswith("sha256:")


class TestJobPackageBuilderChangeset:
    """Tests for changeset JSONL format.

    Scenario: Add operation
    Scenario: Modify operation
    Scenario: JSONL streaming
    """

    def test_changeset_is_jsonl(self, tmp_path: Path):
        """changeset.jsonl is newline-delimited JSON."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"data"
        ref = builder.add_content(content)

        for i in range(3):
            entry = ChangesetEntry(
                operation=ChangeOperation.ADD,
                id=f"item-{i}",
                type="io.kartograph.change.file",
                path=f"src/{i}.py",
                content_ref=ref,
                content_type="text/plain",
                metadata={},
            )
            builder.add_changeset_entry(entry)

        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            raw = zf.read("changeset.jsonl").decode("utf-8")

        lines = [line for line in raw.strip().split("\n") if line]
        assert len(lines) == 3
        for line in lines:
            record = json.loads(line)  # must be valid JSON
            assert "operation" in record

    def test_add_entry_serialized_correctly(self, tmp_path: Path):
        """Add entries include all required fields in changeset.jsonl."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"the file content"
        ref = builder.add_content(content)
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="repo:file:abc",
            type="io.kartograph.change.file",
            path="src/module.py",
            content_ref=ref,
            content_type="text/x-python",
            metadata={"lang": "python"},
        )
        builder.add_changeset_entry(entry)
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            lines = zf.read("changeset.jsonl").decode("utf-8").strip().split("\n")

        record = json.loads(lines[0])
        assert record["operation"] == "add"
        assert record["id"] == "repo:file:abc"
        assert record["type"] == "io.kartograph.change.file"
        assert record["path"] == "src/module.py"
        assert record["content_ref"] == ref.ref_string
        assert record["content_type"] == "text/x-python"
        assert record["metadata"] == {"lang": "python"}


class TestJobPackageBuilderCheckpoint:
    """Tests for adapter checkpoint serialization.

    Scenario: Checkpoint structure
    """

    def test_state_json_contains_schema_version(self, tmp_path: Path):
        """state.json always contains schema_version."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0",
            data={"cursor": "xyz", "page": 3},
        )
        builder.set_checkpoint(checkpoint)
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            state = json.loads(zf.read("state.json"))

        assert state["schema_version"] == "1.0.0"

    def test_state_json_opaque_data_preserved(self, tmp_path: Path):
        """Opaque adapter data in state.json is round-tripped unchanged."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        opaque = {"cursor": "abc123", "page": 5, "nested": {"key": "val"}}
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data=opaque))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            state = json.loads(zf.read("state.json"))

        assert state["cursor"] == "abc123"
        assert state["page"] == 5
        assert state["nested"] == {"key": "val"}

    def test_build_raises_without_checkpoint(self, tmp_path: Path):
        """build() raises if no checkpoint has been set."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        with pytest.raises(ValueError, match="[Cc]heckpoint"):
            builder.build(tmp_path)


class TestJobPackageBuilderZipPathSafety:
    """Tests that the builder produces safe ZIP entry names."""

    def test_all_entry_names_are_safe(self, tmp_path: Path):
        """Every entry in the built archive has a safe path name."""
        from shared_kernel.job_package.path_safety import validate_zip_entry_name

        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"safe data"
        ref = builder.add_content(content)
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="x",
            type="io.kartograph.change.file",
            path="x.py",
            content_ref=ref,
            content_type="text/plain",
            metadata={},
        )
        builder.add_changeset_entry(entry)
        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                validate_zip_entry_name(name)  # must not raise
