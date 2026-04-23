"""Unit tests for JobPackage value objects (TDD - tests first).

Spec: specs/shared-kernel/job-package.spec.md
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import FrozenInstanceError

import pytest

from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    JobPackageId,
    Manifest,
    SyncMode,
)


class TestJobPackageId:
    """Tests for JobPackageId value object.

    Scenario: Package naming
    - GIVEN a JobPackage is produced
    - THEN the archive is named `job-package-{ulid}.zip`
    """

    def test_generates_unique_id(self):
        """Two generated IDs should differ."""
        id1 = JobPackageId.generate()
        id2 = JobPackageId.generate()
        assert id1.value != id2.value

    def test_archive_name_format(self):
        """Archive name must follow job-package-{ulid}.zip pattern."""
        pkg_id = JobPackageId.generate()
        name = pkg_id.archive_name()
        assert name.startswith("job-package-")
        assert name.endswith(".zip")

    def test_archive_name_contains_ulid(self):
        """Archive name embeds the ULID value."""
        pkg_id = JobPackageId.generate()
        name = pkg_id.archive_name()
        assert pkg_id.value in name

    def test_archive_name_pattern(self):
        """Archive name matches exact pattern job-package-{ULID}.zip."""
        pkg_id = JobPackageId.generate()
        name = pkg_id.archive_name()
        # ULID is 26 chars of [0-9A-Z]
        assert re.match(r"^job-package-[0-9A-Z]{26}\.zip$", name), (
            f"Archive name {name!r} does not match expected pattern"
        )

    def test_is_immutable(self):
        """JobPackageId is a frozen dataclass."""
        pkg_id = JobPackageId.generate()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            pkg_id.value = "changed"  # type: ignore[misc]

    def test_from_string(self):
        """Can construct from existing ULID string."""
        ulid_str = "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
        pkg_id = JobPackageId(value=ulid_str)
        assert pkg_id.value == ulid_str
        assert pkg_id.archive_name() == f"job-package-{ulid_str}.zip"


class TestSyncMode:
    """Tests for SyncMode enum.

    Scenario: Manifest fields - sync_mode is 'incremental' or 'full_refresh'
    """

    def test_incremental_value(self):
        assert SyncMode.INCREMENTAL == "incremental"

    def test_full_refresh_value(self):
        assert SyncMode.FULL_REFRESH == "full_refresh"

    def test_only_two_modes(self):
        """There are exactly two sync modes."""
        assert len(SyncMode) == 2


class TestChangeOperation:
    """Tests for ChangeOperation enum.

    Scenario: Add operation - operation 'add'
    Scenario: Modify operation - operation 'modify'
    Scenario: No delete operation
    """

    def test_add_value(self):
        assert ChangeOperation.ADD == "add"

    def test_modify_value(self):
        assert ChangeOperation.MODIFY == "modify"

    def test_no_delete_operation(self):
        """Per spec: no delete operation exists in the changeset format."""
        operation_values = {op.value for op in ChangeOperation}
        assert "delete" not in operation_values
        assert "remove" not in operation_values

    def test_only_add_and_modify(self):
        """There are exactly two operations: add and modify."""
        assert len(ChangeOperation) == 2


class TestContentRef:
    """Tests for ContentRef value object.

    Scenario: Content reference - content_ref references content/ directory
    Scenario: Content file naming - filename is lowercase hex digest only
    """

    def test_from_bytes_produces_sha256(self):
        """ContentRef.from_bytes computes SHA-256 of raw bytes."""
        data = b"hello world"
        expected_hex = hashlib.sha256(data).hexdigest()
        ref = ContentRef.from_bytes(data)
        assert ref.hex_digest == expected_hex

    def test_ref_string_format(self):
        """ref_string has sha256:{hex_digest} format."""
        ref = ContentRef(hex_digest="a" * 64)
        assert ref.ref_string == "sha256:" + "a" * 64

    def test_filename_is_hex_only(self):
        """filename is just the hex digest, no prefix."""
        hex_digest = "a3f2c1" + "0" * 58
        ref = ContentRef(hex_digest=hex_digest)
        assert ref.filename == hex_digest
        assert "sha256:" not in ref.filename

    def test_hex_digest_is_lowercase(self):
        """from_bytes always produces lowercase hex."""
        data = b"Test data"
        ref = ContentRef.from_bytes(data)
        assert ref.hex_digest == ref.hex_digest.lower()

    def test_from_ref_string(self):
        """Can reconstruct ContentRef from 'sha256:{hex}' string."""
        hex_digest = hashlib.sha256(b"data").hexdigest()
        ref_str = f"sha256:{hex_digest}"
        ref = ContentRef.from_ref_string(ref_str)
        assert ref.hex_digest == hex_digest
        assert ref.ref_string == ref_str

    def test_from_ref_string_invalid_raises(self):
        """from_ref_string rejects strings not starting with 'sha256:'."""
        with pytest.raises(ValueError):
            ContentRef.from_ref_string("md5:abc123")

    def test_is_immutable(self):
        """ContentRef is a frozen dataclass."""
        ref = ContentRef(hex_digest="a" * 64)
        with pytest.raises((FrozenInstanceError, AttributeError)):
            ref.hex_digest = "b" * 64  # type: ignore[misc]

    def test_equality_by_value(self):
        """Two ContentRefs with same digest are equal."""
        hex_digest = "a" * 64
        assert ContentRef(hex_digest=hex_digest) == ContentRef(hex_digest=hex_digest)

    def test_different_digests_not_equal(self):
        """ContentRefs with different digests are not equal."""
        assert ContentRef(hex_digest="a" * 64) != ContentRef(hex_digest="b" * 64)


class TestChangesetEntry:
    """Tests for ChangesetEntry value object.

    Scenario: Add operation
    Scenario: Modify operation
    Scenario: Entry type (reverse-DNS notation)
    Scenario: Content reference
    """

    def _make_ref(self) -> ContentRef:
        return ContentRef.from_bytes(b"some content")

    def test_add_entry_fields(self):
        """Add entry contains all required fields."""
        ref = self._make_ref()
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="repo-123",
            type="io.kartograph.change.file",
            path="src/main.py",
            content_ref=ref,
            content_type="text/x-python",
            metadata={},
        )
        assert entry.operation == ChangeOperation.ADD
        assert entry.id == "repo-123"
        assert entry.type == "io.kartograph.change.file"
        assert entry.path == "src/main.py"
        assert entry.content_ref == ref
        assert entry.content_type == "text/x-python"
        assert entry.metadata == {}

    def test_modify_entry_fields(self):
        """Modify entry has same fields as add."""
        ref = self._make_ref()
        entry = ChangesetEntry(
            operation=ChangeOperation.MODIFY,
            id="issue-456",
            type="io.kartograph.change.issue",
            path="issues/456",
            content_ref=ref,
            content_type="application/json",
            metadata={},
        )
        assert entry.operation == ChangeOperation.MODIFY

    def test_rename_as_modify_with_previous_path(self):
        """Rename is represented as modify with previous_path in metadata.

        Scenario: Rename represented as modify
        """
        ref = self._make_ref()
        entry = ChangesetEntry(
            operation=ChangeOperation.MODIFY,
            id="file-789",
            type="io.kartograph.change.file",
            path="src/renamed.py",
            content_ref=ref,
            content_type="text/x-python",
            metadata={"previous_path": "src/old_name.py"},
        )
        assert entry.operation == ChangeOperation.MODIFY
        assert entry.metadata["previous_path"] == "src/old_name.py"

    def test_type_uses_reverse_dns_notation(self):
        """Type field must use reverse-DNS notation (io.kartograph.change.*)."""
        ref = self._make_ref()
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="item-1",
            type="io.kartograph.change.file",
            path="file.py",
            content_ref=ref,
            content_type="text/plain",
            metadata={},
        )
        # Verify the type looks like reverse-DNS (contains dots, not a simple word)
        assert "." in entry.type
        assert entry.type.startswith("io.")

    def test_content_ref_format_in_entry(self):
        """content_ref contains sha256:{hex} when serialized."""
        data = b"file content"
        ref = ContentRef.from_bytes(data)
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="f-1",
            type="io.kartograph.change.file",
            path="a.py",
            content_ref=ref,
            content_type="text/plain",
            metadata={},
        )
        assert entry.content_ref.ref_string.startswith("sha256:")

    def test_is_immutable(self):
        """ChangesetEntry is frozen."""
        ref = self._make_ref()
        entry = ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="x",
            type="io.kartograph.change.file",
            path="x.py",
            content_ref=ref,
            content_type="text/plain",
            metadata={},
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            entry.id = "y"  # type: ignore[misc]


class TestManifest:
    """Tests for Manifest value object.

    Scenario: Manifest fields
    """

    def test_manifest_required_fields(self):
        """Manifest contains all required fields."""
        manifest = Manifest(
            format_version="1.0.0",
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
            entry_count=5,
            content_checksum="a" * 64,
        )
        assert manifest.format_version == "1.0.0"
        assert manifest.data_source_id == "ds-01"
        assert manifest.knowledge_graph_id == "kg-01"
        assert manifest.sync_mode == SyncMode.INCREMENTAL
        assert manifest.entry_count == 5
        assert manifest.content_checksum == "a" * 64

    def test_format_version_is_semver(self):
        """format_version looks like a semver string."""
        manifest = Manifest(
            format_version="1.0.0",
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.FULL_REFRESH,
            entry_count=0,
            content_checksum="b" * 64,
        )
        # Semver: major.minor.patch
        assert re.match(r"^\d+\.\d+\.\d+$", manifest.format_version)

    def test_entry_count_zero_for_empty_changeset(self):
        """entry_count can be zero for empty changeset."""
        manifest = Manifest(
            format_version="1.0.0",
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
            entry_count=0,
            content_checksum="c" * 64,
        )
        assert manifest.entry_count == 0

    def test_is_immutable(self):
        """Manifest is a frozen dataclass."""
        manifest = Manifest(
            format_version="1.0.0",
            data_source_id="ds-01",
            knowledge_graph_id="kg-01",
            sync_mode=SyncMode.INCREMENTAL,
            entry_count=1,
            content_checksum="d" * 64,
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            manifest.entry_count = 99  # type: ignore[misc]


class TestAdapterCheckpoint:
    """Tests for AdapterCheckpoint value object.

    Scenario: Checkpoint structure
    Scenario: Opaque ownership
    Scenario: Schema version mismatch
    """

    def test_requires_schema_version(self):
        """AdapterCheckpoint must contain schema_version."""
        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0",
            data={},
        )
        assert checkpoint.schema_version == "1.0.0"

    def test_opaque_data_is_dict(self):
        """The data field is opaque — any dict is accepted."""
        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0",
            data={"cursor": "abc123", "page": 5, "nested": {"key": "val"}},
        )
        assert checkpoint.data["cursor"] == "abc123"
        assert checkpoint.data["page"] == 5

    def test_schema_version_mismatch_detectable(self):
        """Consumers can inspect schema_version to detect mismatches."""
        checkpoint = AdapterCheckpoint(
            schema_version="2.0.0",
            data={"some_new_field": True},
        )
        known_version = "1.0.0"
        # Adapter detects version mismatch and can fall back to full refresh
        assert checkpoint.schema_version != known_version

    def test_empty_data_is_valid(self):
        """state.json with no extra fields beyond schema_version is valid."""
        checkpoint = AdapterCheckpoint(schema_version="1.0.0", data={})
        assert checkpoint.data == {}
