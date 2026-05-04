"""Value objects for the JobPackage shared kernel.

All objects are immutable (frozen dataclasses) or enums. No I/O,
no framework imports — pure Python domain types.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ulid import ULID


# ---------------------------------------------------------------------------
# JobPackageId
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JobPackageId:
    """Identifier for a JobPackage, encoded as a ULID.

    The ULID provides lexicographic sortability and guaranteed uniqueness
    across producers, which is critical when packages are stored in object
    storage or compared across services.
    """

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> "JobPackageId":
        """Generate a new, unique JobPackageId."""
        return cls(value=str(ULID()))

    def archive_name(self) -> str:
        """Return the canonical ZIP archive filename for this package.

        Format: ``job-package-{ULID}.zip``
        """
        return f"job-package-{self.value}.zip"


# ---------------------------------------------------------------------------
# SyncMode
# ---------------------------------------------------------------------------


class SyncMode(StrEnum):
    """Synchronisation mode for an ingestion run."""

    INCREMENTAL = "incremental"
    """Only items that changed since the last sync are included."""

    FULL_REFRESH = "full_refresh"
    """All items from the data source are included regardless of prior state."""


# ---------------------------------------------------------------------------
# ChangeOperation
# ---------------------------------------------------------------------------


class ChangeOperation(StrEnum):
    """The type of change represented by a changeset entry.

    Note: There is deliberately no DELETE operation. Staleness is detected
    downstream by comparing per-node ``last_synced_at`` against the data
    source's ``last_sync_at`` timestamp.
    """

    ADD = "add"
    """A newly discovered item that did not exist in the previous sync."""

    MODIFY = "modify"
    """An item that was updated or renamed since the last sync.

    Renames are represented as a MODIFY with ``previous_path`` in metadata.
    """


# ---------------------------------------------------------------------------
# ContentRef
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContentRef:
    """A content-addressable reference to a raw content file.

    The file is stored in the ``content/`` directory of the JobPackage
    using only the lowercase hex digest as the filename (no algorithm prefix).
    The ``ref_string`` property returns the full ``sha256:{hex_digest}`` form
    used in ``changeset.jsonl``.
    """

    hex_digest: str
    """Lowercase hex-encoded SHA-256 digest of the raw content bytes."""

    @classmethod
    def from_bytes(cls, data: bytes) -> "ContentRef":
        """Compute a ContentRef from raw bytes by hashing with SHA-256.

        Args:
            data: Raw bytes to hash.

        Returns:
            ContentRef whose hex_digest is the SHA-256 of ``data``.
        """
        digest = hashlib.sha256(data).hexdigest()
        return cls(hex_digest=digest)

    @classmethod
    def from_ref_string(cls, ref_string: str) -> "ContentRef":
        """Parse a ``sha256:{hex_digest}`` string into a ContentRef.

        Args:
            ref_string: Reference string of the form ``sha256:<hex>``.

        Returns:
            ContentRef instance.

        Raises:
            ValueError: If the string does not start with ``sha256:``.
        """
        prefix = "sha256:"
        if not ref_string.startswith(prefix):
            raise ValueError(
                f"ContentRef string must start with 'sha256:', got: {ref_string!r}"
            )
        return cls(hex_digest=ref_string[len(prefix) :])

    @property
    def ref_string(self) -> str:
        """Full reference string used in changeset.jsonl: ``sha256:{hex_digest}``."""
        return f"sha256:{self.hex_digest}"

    @property
    def filename(self) -> str:
        """Filename under ``content/``: the lowercase hex digest only (no prefix)."""
        return self.hex_digest


# ---------------------------------------------------------------------------
# ChangesetEntry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangesetEntry:
    """A single entry in the changeset JSONL file.

    Represents one changed item from the data source. The ``type`` field
    uses reverse-DNS notation (e.g. ``io.kartograph.change.file``) to identify
    the kind of source item that changed.

    The ``metadata`` dict is opaque and adapter-specific. Adapters use it
    for adapter-specific data such as ``previous_path`` for renames.
    """

    operation: ChangeOperation
    """The kind of change: add or modify."""

    id: str
    """Stable identifier for the item within the data source."""

    type: str
    """Reverse-DNS type identifier (e.g. ``io.kartograph.change.file``)."""

    path: str
    """Current path or location of the item in the data source."""

    content_ref: ContentRef
    """Reference to the raw content file in the ``content/`` directory."""

    content_type: str
    """MIME type of the raw content (e.g. ``text/x-python``)."""

    metadata: dict[str, Any]
    """Adapter-specific metadata; opaque to the extraction context."""

    def to_dict(self) -> dict[str, Any]:
        """Serialise this entry to a JSON-compatible dictionary.

        The dict is suitable for writing as a single line in ``changeset.jsonl``.
        """
        return {
            "operation": str(self.operation),
            "id": self.id,
            "type": self.type,
            "path": self.path,
            "content_ref": self.content_ref.ref_string,
            "content_type": self.content_type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChangesetEntry":
        """Deserialise a changeset entry from a JSON-parsed dictionary.

        Args:
            data: Dictionary parsed from a single line of ``changeset.jsonl``.

        Returns:
            ChangesetEntry instance.
        """
        return cls(
            operation=ChangeOperation(data["operation"]),
            id=data["id"],
            type=data["type"],
            path=data["path"],
            content_ref=ContentRef.from_ref_string(data["content_ref"]),
            content_type=data["content_type"],
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Manifest:
    """Package metadata included in ``manifest.json``.

    The manifest is the first file consumers typically read; it can be
    loaded via ZIP random access without extracting the full archive.
    """

    format_version: str
    """Semantic version string describing the package format (e.g. ``"1.0.0"``)."""

    data_source_id: str
    """Identifier of the DataSource that produced this package."""

    knowledge_graph_id: str
    """Identifier of the KnowledgeGraph this package feeds."""

    sync_mode: SyncMode
    """Whether this run was incremental or a full refresh."""

    entry_count: int
    """Number of entries in ``changeset.jsonl``."""

    content_checksum: str
    """Hex-encoded SHA-256 of the canonical content-directory byte stream."""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "format_version": self.format_version,
            "data_source_id": self.data_source_id,
            "knowledge_graph_id": self.knowledge_graph_id,
            "sync_mode": str(self.sync_mode),
            "entry_count": self.entry_count,
            "content_checksum": self.content_checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        """Deserialise from a JSON-parsed dictionary.

        Args:
            data: Dictionary parsed from ``manifest.json``.

        Returns:
            Manifest instance.
        """
        return cls(
            format_version=data["format_version"],
            data_source_id=data["data_source_id"],
            knowledge_graph_id=data["knowledge_graph_id"],
            sync_mode=SyncMode(data["sync_mode"]),
            entry_count=data["entry_count"],
            content_checksum=data["content_checksum"],
        )


# ---------------------------------------------------------------------------
# AdapterCheckpoint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterCheckpoint:
    """Snapshot of the adapter's state at the time of the ingestion run.

    Included in ``state.json`` for debugging and audit purposes.
    The ``data`` field is completely opaque — only the producing adapter
    understands its structure.

    The ``schema_version`` field allows the adapter to detect version
    mismatches and fall back to a full refresh when needed.
    """

    schema_version: str
    """Version of the checkpoint schema understood by the producing adapter."""

    data: dict[str, Any]
    """Opaque adapter-specific checkpoint state."""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary for ``state.json``."""
        result: dict[str, Any] = {"schema_version": self.schema_version}
        result.update(self.data)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdapterCheckpoint":
        """Deserialise from a JSON-parsed dictionary read from ``state.json``.

        Args:
            data: Dictionary parsed from ``state.json``.

        Returns:
            AdapterCheckpoint instance.

        Raises:
            ValueError: If ``schema_version`` is missing.
        """
        if "schema_version" not in data:
            raise ValueError("state.json must contain a 'schema_version' field")
        schema_version = data["schema_version"]
        opaque_data = {k: v for k, v in data.items() if k != "schema_version"}
        return cls(schema_version=schema_version, data=opaque_data)
