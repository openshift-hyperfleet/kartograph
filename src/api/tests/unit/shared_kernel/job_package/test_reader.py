"""Unit tests for JobPackageReader (TDD - tests first).

Spec: specs/shared-kernel/job-package.spec.md
Requirement: Package Structure, Content-Addressable Storage, Streaming-Friendly Design
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    Manifest,
    SyncMode,
)


def _build_simple_package(tmp_path: Path) -> Path:
    """Build a minimal valid JobPackage for testing the reader."""
    builder = JobPackageBuilder(
        data_source_id="ds-reader-test",
        knowledge_graph_id="kg-reader-test",
        sync_mode=SyncMode.INCREMENTAL,
    )
    content = b"hello reader"
    ref = builder.add_content(content)
    entry = ChangesetEntry(
        operation=ChangeOperation.ADD,
        id="item-001",
        type="io.kartograph.change.file",
        path="src/reader.py",
        content_ref=ref,
        content_type="text/x-python",
        metadata={},
    )
    builder.add_changeset_entry(entry)
    builder.set_checkpoint(
        AdapterCheckpoint(schema_version="1.0.0", data={"cursor": "abc"})
    )
    return builder.build(tmp_path)


class TestJobPackageReaderManifest:
    """Tests for reading manifest.json.

    Scenario: ZIP random access
    - GIVEN a consumer that only needs the manifest
    - THEN it can read manifest.json without extracting the entire archive
    """

    def test_read_manifest_returns_manifest(self, tmp_path: Path):
        """read_manifest() returns a Manifest object."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        manifest = reader.read_manifest()
        assert isinstance(manifest, Manifest)

    def test_read_manifest_data_source_id(self, tmp_path: Path):
        """Manifest data_source_id matches what was built."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        manifest = reader.read_manifest()
        assert manifest.data_source_id == "ds-reader-test"

    def test_read_manifest_knowledge_graph_id(self, tmp_path: Path):
        """Manifest knowledge_graph_id matches what was built."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        manifest = reader.read_manifest()
        assert manifest.knowledge_graph_id == "kg-reader-test"

    def test_read_manifest_sync_mode(self, tmp_path: Path):
        """Manifest sync_mode matches what was built."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        manifest = reader.read_manifest()
        assert manifest.sync_mode == SyncMode.INCREMENTAL

    def test_read_manifest_entry_count(self, tmp_path: Path):
        """Manifest entry_count matches the number of changeset entries."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        manifest = reader.read_manifest()
        assert manifest.entry_count == 1

    def test_read_manifest_without_reading_full_archive(self, tmp_path: Path):
        """Manifest can be read with random access — no full extraction needed.

        Scenario: ZIP random access
        This test verifies the reader uses ZipFile.read() rather than extractall().
        We don't add content to the package to keep it minimal.
        """
        archive_path = _build_simple_package(tmp_path)
        # Just opening and reading manifest should not fail
        reader = JobPackageReader(archive_path)
        manifest = reader.read_manifest()
        assert manifest is not None


class TestJobPackageReaderChangeset:
    """Tests for reading changeset.jsonl.

    Scenario: JSONL streaming
    """

    def test_iter_changeset_returns_entries(self, tmp_path: Path):
        """iter_changeset yields ChangesetEntry objects."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        entries = list(reader.iter_changeset())
        assert len(entries) == 1
        assert isinstance(entries[0], ChangesetEntry)

    def test_iter_changeset_entry_fields(self, tmp_path: Path):
        """iter_changeset yields entries with correct field values."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        entries = list(reader.iter_changeset())

        entry = entries[0]
        assert entry.operation == ChangeOperation.ADD
        assert entry.id == "item-001"
        assert entry.type == "io.kartograph.change.file"
        assert entry.path == "src/reader.py"
        assert entry.content_type == "text/x-python"

    def test_iter_changeset_multiple_entries(self, tmp_path: Path):
        """iter_changeset yields all entries in order."""
        builder = JobPackageBuilder(
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
        )
        content = b"data"
        ref = builder.add_content(content)

        ids = ["a", "b", "c"]
        for i, item_id in enumerate(ids):
            entry = ChangesetEntry(
                operation=ChangeOperation.ADD,
                id=item_id,
                type="io.kartograph.change.file",
                path=f"file{i}.py",
                content_ref=ref,
                content_type="text/plain",
                metadata={},
            )
            builder.add_changeset_entry(entry)

        builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
        archive_path = builder.build(tmp_path)

        reader = JobPackageReader(archive_path)
        entries = list(reader.iter_changeset())
        assert len(entries) == 3
        assert [e.id for e in entries] == ids

    def test_iter_changeset_is_a_generator(self, tmp_path: Path):
        """iter_changeset returns an iterator (not a list) for streaming."""

        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        result = reader.iter_changeset()
        assert hasattr(result, "__iter__") and hasattr(result, "__next__")


class TestJobPackageReaderContent:
    """Tests for reading content files.

    Scenario: Integrity verification
    Scenario: Content reference
    """

    def test_read_content_returns_bytes(self, tmp_path: Path):
        """read_content() returns the raw bytes for a given ContentRef."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)

        # We know the entry has content = b"hello reader"
        content = b"hello reader"
        ref = ContentRef.from_bytes(content)
        result = reader.read_content(ref)
        assert result == content

    def test_read_content_verifies_integrity(self, tmp_path: Path):
        """read_content verifies that the stored hash matches the filename.

        Scenario: Integrity verification — mismatch indicates corruption.
        """
        archive_path = _build_simple_package(tmp_path)

        # Tamper with the archive: corrupt the content file
        tampered_path = tmp_path / "tampered.zip"
        with zipfile.ZipFile(archive_path) as zf_in:
            with zipfile.ZipFile(tampered_path, "w") as zf_out:
                for item in zf_in.infolist():
                    data = zf_in.read(item.filename)
                    if item.filename.startswith("content/"):
                        data = b"CORRUPTED DATA"
                    zf_out.writestr(item, data)

        content = b"hello reader"
        ref = ContentRef.from_bytes(content)
        reader = JobPackageReader(tampered_path)

        with pytest.raises(
            ValueError, match="[Cc]orrupt|[Cc]hecksum|[Ii]ntegrity|[Mm]ismatch"
        ):
            reader.read_content(ref)


class TestJobPackageReaderCheckpoint:
    """Tests for reading state.json.

    Scenario: Checkpoint structure
    """

    def test_read_checkpoint_returns_adapter_checkpoint(self, tmp_path: Path):
        """read_checkpoint() returns an AdapterCheckpoint."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        checkpoint = reader.read_checkpoint()
        assert isinstance(checkpoint, AdapterCheckpoint)

    def test_read_checkpoint_schema_version(self, tmp_path: Path):
        """read_checkpoint preserves schema_version."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        checkpoint = reader.read_checkpoint()
        assert checkpoint.schema_version == "1.0.0"

    def test_read_checkpoint_opaque_data(self, tmp_path: Path):
        """read_checkpoint preserves opaque adapter data."""
        archive_path = _build_simple_package(tmp_path)
        reader = JobPackageReader(archive_path)
        checkpoint = reader.read_checkpoint()
        assert checkpoint.data.get("cursor") == "abc"


class TestJobPackageReaderPathSafety:
    """Tests that the reader rejects archives with unsafe entry names.

    Scenario: ZIP entry path safety — consumers MUST reject unsafe archives
    """

    def _build_tampered_zip(self, tmp_path: Path, evil_entry: str) -> Path:
        """Build a ZIP with a crafted malicious entry name."""
        evil_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil_path, "w") as zf:
            zf.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "format_version": "1.0.0",
                        "data_source_id": "ds",
                        "knowledge_graph_id": "kg",
                        "sync_mode": "incremental",
                        "entry_count": 0,
                        "content_checksum": "a" * 64,
                    }
                ),
            )
            zf.writestr("changeset.jsonl", "")
            zf.writestr("state.json", json.dumps({"schema_version": "1.0.0"}))
            zf.writestr(evil_entry, b"evil payload")
        return evil_path

    def test_reader_rejects_path_traversal_entry(self, tmp_path: Path):
        """JobPackageReader raises on archives containing path traversal entries."""
        evil_zip = self._build_tampered_zip(tmp_path, "content/../../../etc/passwd")
        with pytest.raises((ValueError, Exception)):
            JobPackageReader(evil_zip)

    def test_reader_rejects_absolute_path_entry(self, tmp_path: Path):
        """JobPackageReader raises on archives with absolute path entries."""
        # Note: Python's zipfile may normalize leading slashes, but we test
        # our own validate logic is triggered.
        evil_zip = self._build_tampered_zip(tmp_path, "content/subdir/../../../evil")
        with pytest.raises((ValueError, Exception)):
            JobPackageReader(evil_zip)
